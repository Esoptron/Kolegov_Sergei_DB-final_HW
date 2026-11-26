# Колегов Сергей · Итоговое задание по базам данных

**Трекер задач** на FastAPI и PostgreSQL. Пользователь создаёт задачи в своих темах и может назначать их другим зарегистрированным пользователям. Видимые задачи можно отфильтровать, а их статистику получить в JSON или в виде диаграммы PNG.

[Мини-презентация проекта (PDF)](docs/presentation.pdf)

## Запуск через Docker Compose

Требуется Docker с командой `docker compose`.

```sh
git clone https://github.com/Esoptron/Kolegov_Sergei_DB-final_HW.git
cd Kolegov_Sergei_DB-final_HW
cp .env.example .env
```

Сгенерируйте два секретных значения и впишите их в `.env` как `POSTGRES_PASSWORD` и `JWT_SECRET` соответственно.

```sh
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32)); print(secrets.token_hex(32))"
```

```sh
docker compose up --build -d
```

При старте API ждёт готовности PostgreSQL и выполняет `alembic upgrade head`. Откройте [Swagger UI](http://127.0.0.1:8000/docs) и проверьте [готовность сервиса](http://127.0.0.1:8000/health). Порт API можно задать в `.env` через `API_PORT`. Данные хранятся в именованном томе Compose.

Для просмотра журнала выполните `docker compose logs api`. Команда `docker compose stop` останавливает сервис с сохранением данных.

<details>
<summary>Запуск с локальным PostgreSQL</summary>

Нужны Python 3.12 и PostgreSQL 18 с кодировкой UTF-8. Создайте базу `tracker`, принадлежащую отдельной роли приложения.

```sh
python -m venv .venv
```

Активируйте окружение командой `source .venv/bin/activate` в Bash или `.\.venv\Scripts\Activate.ps1` в PowerShell. Выполните `python -m pip install -r requirements.txt`.

В `.env` укажите фактические данные подключения и сгенерированный секрет JWT. Специальные символы пароля в URL должны быть закодированы.

```dotenv
DATABASE_URL=postgresql+psycopg://tracker:your-password@127.0.0.1:5432/tracker
JWT_SECRET=your-random-secret-of-at-least-32-characters
JWT_TTL_MINUTES=60
```

```sh
alembic upgrade head
uvicorn app.main:app
```

</details>

## Работа с API

1. В Swagger зарегистрируйте пользователя через `POST /auth/register`. Передайте JSON с полями `username` и `password`. Имя пользователя содержит 3-32 символа, начинается с латинской буквы и может включать цифры и подчёркивание. Пароль содержит 10-128 символов.
2. Отправьте те же данные в `POST /auth/token`. Скопируйте `access_token` и вставьте его в окно **Authorize** в Swagger. При использовании HTTP-клиента передавайте `Authorization: Bearer <token>`.
3. Создайте тему через `POST /topics`, например `{"name":"База данных"}`. Используйте возвращённый `id` как `topic_id` при создании задачи через `POST /tasks`. Обязательные поля задачи - `title` и `topic_id`. Поля `description` и `assignee_id` можно опустить.
4. Чтобы назначить задачу, получите ID исполнителя через `GET /users/{username}`. После создания задачи смените её статус через `PATCH /tasks/{task_id}/status`, например `{"status":"in_progress"}`.

| Запрос | Результат |
| --- | --- |
| `GET /auth/me` | Профиль текущего пользователя |
| `GET /topics` | Темы текущего пользователя |
| `POST /tasks` | Новая задача со статусом `new` |
| `GET /tasks` | Список доступных задач с фильтрами |
| `GET /tasks/{task_id}` | Карточка задачи |
| `PATCH /tasks/{task_id}` | Изменение заголовка, описания, темы или исполнителя |
| `PATCH /tasks/{task_id}/status` | Смена статуса автором или исполнителем |
| `DELETE /tasks/{task_id}` | Удаление задачи автором |
| `GET /analytics/tasks` | Сводка по доступным задачам |
| `GET /analytics/tasks/chart` | PNG-диаграмма выбранной группировки |

Автор и назначенный исполнитель видят задачу и могут менять её статус. Автор также редактирует поля задачи, назначает исполнителя и удаляет задачу. Чужая задача недоступна по ID, в списке и в аналитике. Снять назначение или удалить описание можно через PATCH, передав `null` соответствующему полю. Статусы - `new`, `in_progress`, `blocked`, `done`. Разрешён переход между любыми из них.

Список поддерживает совместное применение `status`, `topic_id`, `assignee_id` и `q`. Параметр `q` ищет подстроку в заголовке и описании без учёта регистра. Список сортируется по дате создания от новых к старым и поддерживает `limit` (1-100, по умолчанию 50) и `offset` (по умолчанию 0).

## Аналитика и демо

PostgreSQL считает задачи в разрезе статуса, темы и исполнителя. pandas собирает из этих данных три группировки, общее число задач и долю выполненных (`completion_percent`, от 0 до 100). Задачи без назначения входят в отдельную группу. Эндпоинт для диаграммы Matplotlib принимает `group_by=status|topic|assignee` и отображает до 12 групп выбранного разреза. API аналитики принимает те же четыре фильтра, что и список задач.

На запущенном сервисе можно воспроизвести пример из презентации.

```sh
python scripts/demo.py
```

Скрипт через API создаёт две демонстрационные учётные записи, три темы и восемь задач. В `demo-output/` появятся сводка `summary.json` и три PNG-диаграммы. Для другого адреса сервиса используйте `--url`.

## Модель данных и миграции

```mermaid
erDiagram
    USERS ||--o{ TOPICS : "владеет"
    USERS ||--o{ TASKS : "создаёт"
    USERS |o--o{ TASKS : "выполняет"
    TOPICS ||--o{ TASKS : "содержит"

    USERS {
        uuid id PK
        varchar username UK
        text password_hash
        timestamptz created_at
    }

    TOPICS {
        uuid id PK
        uuid owner_id FK
        varchar name
    }

    TASKS {
        uuid id PK
        uuid owner_id FK
        uuid topic_id FK
        uuid assignee_id FK "может быть NULL"
        varchar title
        text description "может быть NULL"
        varchar status
        timestamptz created_at
        timestamptz updated_at
    }
```

- `users.username` уникален. Имя приводится к нижнему регистру перед поиском и сохранением.
- `UNIQUE (owner_id, name)` позволяет разным авторам создавать одноимённые темы.
- Составной внешний ключ `tasks(owner_id, topic_id) → topics(owner_id, id)` связывает задачу с темой её автора. `CHECK` ограничивает значения статуса.
- `tasks.assignee_id` допускает `NULL`. Если удалить пользователя, назначение снимается. Связи с автором и темой защищены `ON DELETE RESTRICT`.

| Ревизия Alembic | Изменение |
| --- | --- |
| `0001` | Таблицы пользователей, тем и задач с ключами и ограничениями |
| `0002` | Индексы задач по автору, исполнителю и теме |

`alembic upgrade head` применяет ревизии. `alembic check` проверяет соответствие БД моделям. `alembic downgrade 0001` снимает индексы. Откат до `base` удаляет таблицы приложения и их данные.

## Аутентификация и запросы к БД

Хэши паролей создаются с Argon2id. API принимает подписанные JWT с ограниченным сроком действия. Проверка доступа выполняется для конкретного пользователя при чтении, записи и построении сводки. Пользовательские значения передаются в параметризованные выражения SQLAlchemy. При поиске символы `%` и `_` обрабатываются как литералы.

## Тесты

Тестам нужен PostgreSQL 18. Можно запустить временную базу в Docker.

```sh
docker run --rm -d --name tracker-pg-test -p 127.0.0.1:55432:5432 -e POSTGRES_DB=tracker_test -e POSTGRES_USER=tracker -e POSTGRES_PASSWORD=tracker-test-only postgres:18-alpine
docker exec tracker-pg-test pg_isready -h 127.0.0.1 -U tracker -d tracker_test
python -m pip install -r requirements-dev.txt
```

После сообщения `accepting connections` задайте переменную подключения и запустите тесты. Для своего экземпляра укажите URL тестовой базы, где роль может создавать схемы.

```sh
export TEST_DATABASE_URL=postgresql+psycopg://tracker:tracker-test-only@127.0.0.1:55432/tracker_test
python -m pytest -q
```

В PowerShell используйте `$env:TEST_DATABASE_URL = 'postgresql+psycopg://tracker:tracker-test-only@127.0.0.1:55432/tracker_test'`. Pytest создаёт отдельную схему со случайным именем, применяет миграции и удаляет эту схему после прогона. Тесты проверяют сохранение CRUD, права доступа, аутентификацию, фильтры, ограничения БД, аналитические ответы и откат миграций. Запущенный тестовый контейнер можно остановить командой `docker stop tracker-pg-test`.
