"""Create users, topics and tasks."""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_topics_owner", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("owner_id", "name", name="uq_topics_owner_name"),
        sa.UniqueConstraint("owner_id", "id", name="uq_topics_owner_id"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), server_default="new", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_tasks_owner", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "topic_id"], ["topics.owner_id", "topics.id"],
            name="fk_tasks_owner_topic", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["users.id"], name="fk_tasks_assignee", ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('new', 'in_progress', 'blocked', 'done')", name="ck_tasks_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("topics")
    op.drop_table("users")
