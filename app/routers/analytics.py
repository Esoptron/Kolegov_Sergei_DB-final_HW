from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.db import DB
from app.schemas import ChartQuery, TaskFilters, TaskSummary
from app.security import CurrentUser
from app.task_analytics import render_chart, summarize_tasks

router = APIRouter(prefix="/analytics/tasks", tags=["Analytics"])


@router.get("")
def task_summary(query: Annotated[TaskFilters, Query()], db: DB, user: CurrentUser) -> TaskSummary:
    return summarize_tasks(db, user.id, query)


@router.get(
    "/chart",
    response_class=Response,
    responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
)
def task_chart(query: Annotated[ChartQuery, Query()], db: DB, user: CurrentUser) -> Response:
    filters = TaskFilters.model_validate(query.model_dump(exclude={"group_by"}))
    summary = summarize_tasks(db, user.id, filters)
    return Response(render_chart(summary, query.group_by), media_type="image/png")
