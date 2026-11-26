from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
)
from pydantic.json_schema import SkipJsonSchema

from app.models import TaskStatus


def normalize_username(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


Username = Annotated[
    str,
    StringConstraints(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_]*$"),
    BeforeValidator(normalize_username),
]
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160, pattern=r"^[^\x00]*$"),
]
TopicName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[^\x00\r\n]*$"),
]
Description = Annotated[str, StringConstraints(max_length=4000, pattern=r"^[^\x00]*$")]
SearchText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160, pattern=r"^[^\x00]*$"),
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(InputModel):
    username: Username
    password: Annotated[SecretStr, Field(min_length=10, max_length=128)]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TopicCreate(InputModel):
    name: TopicName


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str


class TaskCreate(InputModel):
    title: Title
    description: Description | None = None
    topic_id: UUID
    assignee_id: UUID | None = None


class TaskUpdate(InputModel):
    title: Title | SkipJsonSchema[None] = None
    description: Description | None = None
    topic_id: UUID | SkipJsonSchema[None] = None
    assignee_id: UUID | None = None

    @field_validator("title", "topic_id")
    @classmethod
    def require_value(cls, value: str | UUID | None) -> str | UUID:
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class StatusUpdate(InputModel):
    status: TaskStatus


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    topic_id: UUID
    assignee_id: UUID | None
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


class TaskFilters(InputModel):
    status: TaskStatus | None = None
    topic_id: UUID | None = None
    assignee_id: UUID | None = None
    q: SearchText | None = None


class TaskListQuery(TaskFilters):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=2**63 - 1)


class ChartGroup(StrEnum):
    STATUS = "status"
    TOPIC = "topic"
    ASSIGNEE = "assignee"


class ChartQuery(TaskFilters):
    group_by: ChartGroup = ChartGroup.STATUS


class StatusCount(BaseModel):
    status: TaskStatus
    count: int


class TopicCount(BaseModel):
    topic_id: UUID
    topic: str
    count: int


class AssigneeCount(BaseModel):
    assignee_id: UUID | None
    assignee: str | None
    count: int


class TaskSummary(BaseModel):
    total: int
    completed: int
    completion_percent: float
    by_status: list[StatusCount]
    by_topic: list[TopicCount]
    by_assignee: list[AssigneeCount]
