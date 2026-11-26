from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Task


def test_task_crud_persists_changes(client, sessions, new_user, new_topic, new_task):
    account, headers = new_user("owner")
    topic = new_topic(headers, "API")
    other_topic = new_topic(headers, "Документация")
    task = new_task(
        headers, topic, "Подготовить схему", description="Первый вариант", assignee_id=account["id"],
    )
    path = f"/tasks/{task['id']}"
    assert task["status"] == "new"
    assert task["owner_id"] == account["id"]
    assert client.get(path, headers=headers).json() == task

    changes = {"title": "Проверить схему", "description": None, "assignee_id": None, "topic_id": other_topic}
    updated = client.patch(path, headers=headers, json=changes)
    assert updated.status_code == 200
    assert {key: updated.json()[key] for key in changes} == changes
    assert datetime.fromisoformat(updated.json()["updated_at"]) >= datetime.fromisoformat(task["created_at"])

    done = client.patch(f"{path}/status", headers=headers, json={"status": "done"})
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    with sessions() as db:
        stored = db.get(Task, UUID(task["id"]))
        assert (stored.title, stored.status, stored.topic_id) == ("Проверить схему", "done", UUID(other_topic))

    deleted = client.delete(path, headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(path, headers=headers).status_code == 404
    with sessions() as db:
        assert db.get(Task, UUID(task["id"])) is None


def test_task_visibility_and_assignee_permissions(client, new_user, new_topic, new_task):
    _, owner = new_user("creator")
    member, assignee = new_user("member")
    _, stranger = new_user("stranger")
    topic = new_topic(owner, "API")
    task = new_task(owner, topic, "Собрать отчёт", assignee_id=member["id"])
    path = f"/tasks/{task['id']}"

    assert client.get("/topics", headers=assignee).json() == []
    assert client.get("/tasks", headers=assignee).json() == [task]
    assert client.get("/tasks", headers=stranger).json() == []
    assert client.get(path, headers=assignee).status_code == 200
    assert client.get(path, headers=stranger).status_code == 404
    assert client.patch(path, headers=assignee, json={"title": "Новый заголовок"}).status_code == 403
    assert client.delete(path, headers=assignee).status_code == 403

    status = client.patch(f"{path}/status", headers=assignee, json={"status": "in_progress"})
    assert status.status_code == 200
    assert status.json()["status"] == "in_progress"
    assert client.patch(f"{path}/status", headers=stranger, json={"status": "done"}).status_code == 404

    assert client.patch(path, headers=owner, json={"assignee_id": None}).status_code == 200
    assert client.get(path, headers=assignee).status_code == 404


def test_combined_filters_pagination_and_literal_search(client, new_user, new_topic, new_task):
    _, owner = new_user("owner")
    member, _ = new_user("member")
    first_topic = new_topic(owner, "API")
    second_topic = new_topic(owner, "Данные")
    matched = new_task(
        owner, first_topic, "Отчёт O'Reilly 50%_", assignee_id=member["id"], description="Проверить данные",
    )
    distraction = new_task(owner, first_topic, "Отчёт 50ab", assignee_id=member["id"])
    newest = new_task(owner, second_topic, "Импорт данных")
    changed = client.patch(f"/tasks/{matched['id']}/status", headers=owner, json={"status": "blocked"})
    assert changed.status_code == 200

    result = client.get(
        "/tasks", headers=owner,
        params={"status": "blocked", "topic_id": first_topic, "assignee_id": member["id"], "q": "ОТЧЁТ"},
    )
    assert result.status_code == 200
    assert [task["id"] for task in result.json()] == [matched["id"]]

    for search in ("50%_", "o'reilly", "ПРОВЕРИТЬ"):
        response = client.get("/tasks", headers=owner, params={"q": search})
        assert response.status_code == 200
        assert [task["id"] for task in response.json()] == [matched["id"]]

    page = client.get("/tasks", headers=owner, params={"limit": 2, "offset": 0})
    assert [task["id"] for task in page.json()] == [newest["id"], distraction["id"]]
    page = client.get("/tasks", headers=owner, params={"limit": 2, "offset": 2})
    assert [task["id"] for task in page.json()] == [matched["id"]]


def test_invalid_task_fields_and_relations_are_rejected(client, new_user, new_topic, new_task):
    _, owner = new_user("owner")
    _, other = new_user("other")
    topic = new_topic(owner, "API")
    foreign_topic = new_topic(other, "API")
    assert client.post("/topics", headers=owner, json={"name": "API"}).status_code == 409

    for data in (
        {"topic_id": foreign_topic, "title": "Чужая тема"},
        {"topic_id": topic, "title": "Неизвестный исполнитель", "assignee_id": str(uuid4())},
    ):
        assert client.post("/tasks", headers=owner, json=data).status_code == 404

    assert client.post("/tasks", headers=owner, json={"topic_id": topic, "title": "   "}).status_code == 422
    task = new_task(owner, topic, "Задача")
    path = f"/tasks/{task['id']}"
    assert client.patch(path, headers=owner, json={"topic_id": None}).status_code == 422
    assert client.patch(path, headers=owner, json={"topic_id": foreign_topic}).status_code == 404
    assert client.patch(f"{path}/status", headers=owner, json={"status": "unknown"}).status_code == 422
    assert client.get("/tasks", headers=owner, params={"limit": 0}).status_code == 422
    assert client.get(path, headers=owner).json() == task


def test_database_rejects_invalid_status_and_cross_owner_topic(sessions, new_user, new_topic):
    owner, owner_headers = new_user("owner")
    _, another = new_user("other")
    own_topic = new_topic(owner_headers, "API")
    foreign_topic = new_topic(another, "Данные")
    with sessions() as db:
        db.add(Task(
            owner_id=UUID(owner["id"]), topic_id=UUID(own_topic), title="Статус", status="invalid",
        ))
        with pytest.raises(IntegrityError) as error:
            db.flush()
        assert error.value.orig.diag.constraint_name == "ck_tasks_status"
        db.rollback()

        db.add(Task(
            owner_id=UUID(owner["id"]), topic_id=UUID(foreign_topic), title="Чужая тема",
        ))
        with pytest.raises(IntegrityError) as error:
            db.flush()
        assert error.value.orig.diag.constraint_name == "fk_tasks_owner_topic"
