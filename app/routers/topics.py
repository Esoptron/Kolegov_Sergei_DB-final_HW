from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import DB
from app.models import Topic
from app.schemas import TopicCreate, TopicRead
from app.security import CurrentUser

router = APIRouter(prefix="/topics", tags=["Topics"])


@router.post("", response_model=TopicRead, status_code=201)
def create_topic(data: TopicCreate, db: DB, user: CurrentUser) -> Topic:
    statement = (
        insert(Topic)
        .values(owner_id=user.id, name=data.name)
        .on_conflict_do_nothing(constraint="uq_topics_owner_name")
        .returning(Topic)
    )
    topic = db.scalar(statement)
    if topic is None:
        raise HTTPException(status_code=409, detail="Topic already exists")
    db.commit()
    return topic


@router.get("", response_model=list[TopicRead])
def list_topics(db: DB, user: CurrentUser) -> list[Topic]:
    statement = select(Topic).where(Topic.owner_id == user.id).order_by(Topic.name, Topic.id)
    return list(db.scalars(statement))
