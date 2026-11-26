from uuid import UUID

from sqlalchemy import ColumnElement, or_

from app.models import Task
from app.schemas import TaskFilters


def visible_to(user_id: UUID) -> ColumnElement[bool]:
    return or_(Task.owner_id == user_id, Task.assignee_id == user_id)


def task_conditions(user_id: UUID, filters: TaskFilters) -> list[ColumnElement[bool]]:
    conditions = [visible_to(user_id)]
    if filters.status is not None:
        conditions.append(Task.status == filters.status.value)
    if filters.topic_id is not None:
        conditions.append(Task.topic_id == filters.topic_id)
    if filters.assignee_id is not None:
        conditions.append(Task.assignee_id == filters.assignee_id)
    if filters.q is not None:
        conditions.append(
            or_(
                Task.title.collate("pg_unicode_fast").icontains(filters.q, autoescape=True),
                Task.description.collate("pg_unicode_fast").icontains(filters.q, autoescape=True),
            )
        )
    return conditions
