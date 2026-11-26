from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TaskStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_topics_owner_name"),
        UniqueConstraint("owner_id", "id", name="uq_topics_owner_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", name="fk_topics_owner", ondelete="RESTRICT"),
    )
    name: Mapped[str] = mapped_column(String(80))


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "topic_id"],
            ["topics.owner_id", "topics.id"],
            name="fk_tasks_owner_topic",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('new', 'in_progress', 'blocked', 'done')",
            name="ck_tasks_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", name="fk_tasks_owner", ondelete="RESTRICT"),
        index=True,
    )
    topic_id: Mapped[UUID] = mapped_column(index=True)
    assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", name="fk_tasks_assignee", ondelete="SET NULL"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default=TaskStatus.NEW.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(UTC),
    )
