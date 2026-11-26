from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import DB
from app.models import Task, Topic, User
from app.schemas import StatusUpdate, TaskCreate, TaskListQuery, TaskRead, TaskUpdate
from app.security import CurrentUser
from app.task_queries import task_conditions, visible_to

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_visible_task(db: Session, user_id: UUID, task_id: UUID, *, for_update: bool = False) -> Task:
    statement = select(Task).where(Task.id == task_id, visible_to(user_id))
    if for_update:
        statement = statement.with_for_update()
    task = db.scalar(statement)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def require_owner(task: Task, user_id: UUID) -> None:
    if task.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the task owner may do this")


def validate_topic(db: Session, owner_id: UUID, topic_id: UUID) -> None:
    topic = db.scalar(select(Topic.id).where(Topic.id == topic_id, Topic.owner_id == owner_id))
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")


def validate_assignee(db: Session, assignee_id: UUID | None) -> None:
    if assignee_id is not None and db.get(User, assignee_id) is None:
        raise HTTPException(status_code=404, detail="Assignee not found")


@router.post("", response_model=TaskRead, status_code=201)
def create_task(data: TaskCreate, db: DB, user: CurrentUser) -> Task:
    validate_topic(db, user.id, data.topic_id)
    validate_assignee(db, data.assignee_id)
    task = Task(owner_id=user.id, **data.model_dump())
    db.add(task)
    db.commit()
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(query: Annotated[TaskListQuery, Query()], db: DB, user: CurrentUser) -> list[Task]:
    statement = (
        select(Task)
        .where(*task_conditions(user.id, query))
        .order_by(Task.created_at.desc(), Task.id.desc())
        .limit(query.limit)
        .offset(query.offset)
    )
    return list(db.scalars(statement))


@router.get("/{task_id}", response_model=TaskRead)
def read_task(task_id: UUID, db: DB, user: CurrentUser) -> Task:
    return get_visible_task(db, user.id, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, data: TaskUpdate, db: DB, user: CurrentUser) -> Task:
    task = get_visible_task(db, user.id, task_id, for_update=True)
    require_owner(task, user.id)
    if data.topic_id is not None:
        validate_topic(db, user.id, data.topic_id)
    if data.assignee_id is not None:
        validate_assignee(db, data.assignee_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    return task


@router.patch("/{task_id}/status", response_model=TaskRead)
def update_status(task_id: UUID, data: StatusUpdate, db: DB, user: CurrentUser) -> Task:
    task = get_visible_task(db, user.id, task_id, for_update=True)
    task.status = data.status.value
    db.commit()
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: UUID, db: DB, user: CurrentUser) -> Response:
    task = get_visible_task(db, user.id, task_id, for_update=True)
    require_owner(task, user.id)
    db.delete(task)
    db.commit()
    return Response(status_code=204)
