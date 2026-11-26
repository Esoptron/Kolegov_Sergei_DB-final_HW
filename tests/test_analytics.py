from io import BytesIO

import pytest
from PIL import Image


@pytest.fixture
def sample_tasks(client, new_user, new_topic, new_task):
    _, owner = new_user("owner")
    member, member_headers = new_user("member")
    api = new_topic(owner, "API")
    docs = new_topic(owner, "Документация")
    private_topic = new_topic(member_headers, "Личное")
    completed = new_task(owner, api, "Роутер", assignee_id=member["id"])
    new_task(owner, api, "Схема", assignee_id=member["id"])
    new_task(owner, docs, "Инструкция")
    new_task(member_headers, private_topic, "Личная задача")
    response = client.patch(f"/tasks/{completed['id']}/status", headers=owner, json={"status": "done"})
    assert response.status_code == 200
    return owner, member, api, docs


def test_analytics_counts_visible_tasks_and_filters(client, sample_tasks):
    owner, member, api, docs = sample_tasks
    response = client.get("/analytics/tasks", headers=owner)
    assert response.status_code == 200
    summary = response.json()
    assert (summary["total"], summary["completed"], summary["completion_percent"]) == (3, 1, 33.33)
    assert {row["status"]: row["count"] for row in summary["by_status"]} == {
        "new": 2, "in_progress": 0, "blocked": 0, "done": 1,
    }
    assert summary["by_topic"] == [
        {"topic_id": api, "topic": "API", "count": 2},
        {"topic_id": docs, "topic": "Документация", "count": 1},
    ]
    assert summary["by_assignee"] == [
        {"assignee_id": member["id"], "assignee": member["username"], "count": 2},
        {"assignee_id": None, "assignee": None, "count": 1},
    ]

    filtered = client.get("/analytics/tasks", headers=owner, params={"q": "роутер", "topic_id": api})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["completion_percent"] == 100.0


@pytest.mark.parametrize("group", ["status", "topic", "assignee"])
def test_each_chart_is_a_png(client, sample_tasks, group):
    owner, *_ = sample_tasks
    response = client.get("/analytics/tasks/chart", headers=owner, params={"group_by": group})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    with Image.open(BytesIO(response.content)) as image:
        assert image.format == "PNG"
        assert image.width > 500
        image.verify()


def test_empty_summary_and_chart(client, new_user):
    _, headers = new_user("empty")
    summary = client.get("/analytics/tasks", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["total"] == 0
    assert summary.json()["completion_percent"] == 0.0
    assert summary.json()["by_topic"] == summary.json()["by_assignee"] == []
    assert all(row["count"] == 0 for row in summary.json()["by_status"])
    chart = client.get("/analytics/tasks/chart", headers=headers, params={"group_by": "topic"})
    with Image.open(BytesIO(chart.content)) as image:
        image.verify()
