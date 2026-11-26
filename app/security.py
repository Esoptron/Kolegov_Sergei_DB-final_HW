from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from app.config import Settings, get_settings
from app.db import DB
from app.models import User
from app.schemas import Token

ALGORITHM = "HS256"
ISSUER = "db-final-task-tracker"
bearer = HTTPBearer(auto_error=False)
password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash("unused placeholder for unknown accounts")

AppSettings = Annotated[Settings, Depends(get_settings)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"},
    )


def issue_token(user_id: UUID, settings: Settings) -> Token:
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.jwt_ttl_minutes)
    token = jwt.encode(
        {"sub": str(user_id), "iss": ISSUER, "iat": now, "exp": now + lifetime},
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    return Token(access_token=token, expires_in=int(lifetime.total_seconds()))


def get_current_user(credentials: BearerCredentials, db: DB, settings: AppSettings) -> User:
    if credentials is None:
        raise unauthorized()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["sub", "iss", "iat", "exp"]},
        )
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized() from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
