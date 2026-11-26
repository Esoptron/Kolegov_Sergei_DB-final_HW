import os
from pathlib import Path
from secrets import token_hex
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import Settings, get_settings
from app.db import get_db
from app.main import app
from app.models import Base


@pytest.fixture(scope="session")
def alembic_config():
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a PostgreSQL database where the test role can create schemas")
    return url


@pytest.fixture(scope="session")
def engine(database_url, alembic_config):
    schema = f"test_{uuid4().hex}"
    admin = create_engine(database_url)
    test_engine = create_engine(database_url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        try:
            with test_engine.begin() as connection:
                alembic_config.attributes["connection"] = connection
                command.upgrade(alembic_config, "head")
            yield test_engine
        finally:
            alembic_config.attributes.pop("connection", None)
            test_engine.dispose()
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
    finally:
        admin.dispose()


@pytest.fixture
def sessions(engine):
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def settings(database_url):
    return Settings(database_url=database_url, jwt_secret=token_hex(32), jwt_ttl_minutes=30)


@pytest.fixture
def client(sessions, settings):
    def test_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def new_user(client):
    def create(username):
        credentials = {"username": username, "password": "test-password-2026"}
        registered = client.post("/auth/register", json=credentials)
        assert registered.status_code == 201, registered.text
        token = client.post("/auth/token", json=credentials)
        assert token.status_code == 200, token.text
        return registered.json(), {"Authorization": f"Bearer {token.json()['access_token']}"}

    return create


@pytest.fixture
def new_topic(client):
    def create(headers, name):
        response = client.post("/topics", headers=headers, json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return create


@pytest.fixture
def new_task(client):
    def create(headers, topic_id, title, **fields):
        response = client.post(
            "/tasks", headers=headers, json={"topic_id": topic_id, "title": title, **fields},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create
