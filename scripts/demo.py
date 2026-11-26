"""Create a sample board over HTTP and export its analytics."""

import argparse
import json
from pathlib import Path
from secrets import token_hex, token_urlsafe
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SAMPLES = [
    ("Спроектировать таблицы", "База данных", True, "done"),
    ("Добавить индексы", "База данных", True, "done"),
    ("Проверить миграции", "База данных", False, "in_progress"),
    ("Реализовать CRUD", "API", True, "done"),
    ("Проверить фильтрацию", "API", True, "in_progress"),
    ("Настроить тестовый стенд", "API", False, "blocked"),
    ("Подготовить инструкцию", "Документация", False, "new"),
    ("Описать связи в ERD", "Документация", False, "new"),
]


def request(base_url, method, path, *, token=None, body=None):
    headers = {}
    data = None
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode()
    req = Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            return response.read()
    except HTTPError as error:
        raise SystemExit(f"{method} {path}: HTTP {error.code} {error.reason}") from None
    except URLError as error:
        raise SystemExit(f"{base_url}: {error.reason}") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=Path("demo-output"))
    args = parser.parse_args()

    request(args.url, "GET", "/health")
    suffix = token_hex(4)
    owner = {"username": f"demo_owner_{suffix}", "password": token_urlsafe(18)}
    assignee = {"username": f"demo_assignee_{suffix}", "password": token_urlsafe(18)}
    request(args.url, "POST", "/auth/register", body=owner)
    member = json.loads(request(args.url, "POST", "/auth/register", body=assignee))
    login = json.loads(request(args.url, "POST", "/auth/token", body=owner))
    token = login["access_token"]

    topics = {}
    for name in dict.fromkeys(sample[1] for sample in SAMPLES):
        topic = json.loads(request(args.url, "POST", "/topics", token=token, body={"name": name}))
        topics[name] = topic["id"]

    for title, topic, assigned, status in SAMPLES:
        body = {"title": title, "topic_id": topics[topic], "assignee_id": member["id"] if assigned else None}
        task = json.loads(request(args.url, "POST", "/tasks", token=token, body=body))
        if status != "new":
            request(args.url, "PATCH", f"/tasks/{task['id']}/status", token=token, body={"status": status})

    args.out.mkdir(parents=True, exist_ok=True)
    summary = request(args.url, "GET", "/analytics/tasks", token=token)
    (args.out / "summary.json").write_text(
        json.dumps(json.loads(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    for group in ("status", "topic", "assignee"):
        png = request(args.url, "GET", f"/analytics/tasks/chart?group_by={group}", token=token)
        (args.out / f"by-{group}.png").write_bytes(png)
    print(f"{len(SAMPLES)} tasks exported to {args.out.resolve()}")


if __name__ == "__main__":
    main()
