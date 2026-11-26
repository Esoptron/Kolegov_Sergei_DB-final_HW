from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import DB
from app.models import User
from app.schemas import Credentials, Token, UserRead, Username
from app.security import (
    AppSettings,
    CurrentUser,
    dummy_hash,
    get_current_user,
    issue_token,
    password_hash,
    unauthorized,
)

router = APIRouter(tags=["Authentication"])


@router.post("/auth/register", response_model=UserRead, status_code=201)
def register(credentials: Credentials, db: DB) -> User:
    statement = (
        insert(User)
        .values(
            username=credentials.username,
            password_hash=password_hash.hash(credentials.password.get_secret_value()),
        )
        .on_conflict_do_nothing(constraint="uq_users_username")
        .returning(User)
    )
    user = db.scalar(statement)
    if user is None:
        raise HTTPException(status_code=409, detail="Username already exists")
    db.commit()
    return user


@router.post("/auth/token")
def login(credentials: Credentials, response: Response, db: DB, settings: AppSettings) -> Token:
    user = db.scalar(select(User).where(User.username == credentials.username))
    digest = user.password_hash if user is not None else dummy_hash
    valid = password_hash.verify(credentials.password.get_secret_value(), digest)
    if user is None or not valid:
        raise unauthorized()

    response.headers["Cache-Control"] = "no-store"
    return issue_token(user.id, settings)


@router.get("/auth/me", response_model=UserRead)
def read_profile(user: CurrentUser) -> User:
    return user


@router.get("/users/{username}", response_model=UserRead, dependencies=[Depends(get_current_user)])
def find_user(username: Username, db: DB) -> User:
    found = db.scalar(select(User).where(User.username == username))
    if found is None:
        raise HTTPException(status_code=404, detail="User not found")
    return found
