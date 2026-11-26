from alembic import command
from sqlalchemy import inspect


def test_migrations_can_be_reversed_and_match_models(engine, alembic_config):
    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        try:
            indexes = {index["name"] for index in inspect(connection).get_indexes("tasks")}
            assert indexes == {"ix_tasks_owner_id", "ix_tasks_assignee_id", "ix_tasks_topic_id"}

            command.downgrade(alembic_config, "0001")
            assert inspect(connection).get_indexes("tasks") == []

            command.downgrade(alembic_config, "base")
            assert {"users", "topics", "tasks"}.isdisjoint(inspect(connection).get_table_names())

            command.upgrade(alembic_config, "head")
            command.check(alembic_config)
        finally:
            alembic_config.attributes.pop("connection", None)
