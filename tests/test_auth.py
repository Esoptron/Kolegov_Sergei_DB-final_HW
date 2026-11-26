from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest

from app.models import User
from app.security import ALGORITHM, ISSUER


def test_register_login_and_find_user(client, sessions):
    credentials = {"username": "  Reviewer_01  ", "password": "reviewer-password"}
    response = client.post("/auth/register", json=credentials)
    assert response.status_code == 201
    account = response.json()
    assert set(account) == {"id", "username"}
    assert account["username"] == "reviewer_01"

    with sessions() as db:
        stored = db.get(User, UUID(account["id"]))
        assert stored.password_hash.startswith("$argon2id$")
        assert credentials["password"] not in stored.password_hash

    assert client.post("/auth/register", json={**credentials, "username": "reviewer_01"}).status_code == 409

    logged_in = client.post("/auth/token", json=credentials)
    assert logged_in.status_code == 200
    assert logged_in.headers["cache-control"] == "no-store"
    assert logged_in.json()["expires_in"] == 1800
    assert logged_in.json()["token_type"] == "bearer"
    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json() == account
    assert client.get("/users/REVIEWER_01", headers=headers).json() == account
    assert client.get("/users/unknown", headers=headers).status_code == 404


def test_invalid_credentials_have_the_same_response(client, new_user):
    new_user("existing")
    wrong = client.post("/auth/token", json={"username": "existing", "password": "wrong-password"})
    missing = client.post("/auth/token", json={"username": "missing", "password": "wrong-password"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json() == {"detail": "Invalid credentials"}
    assert wrong.headers["www-authenticate"] == "Bearer"

    invalid = client.post("/auth/register", json={"username": "existing", "password": "shortpwd"})
    assert invalid.status_code == 422
    assert "shortpwd" not in invalid.text


@pytest.mark.parametrize(
    "path", ["/auth/me", "/users/someone", "/topics", "/tasks", "/analytics/tasks/chart"],
)
def test_private_endpoints_reject_missing_tokens(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_and_invalid_tokens_are_rejected(client, new_user, settings):
    user, _ = new_user("token_user")
    expires = datetime.now(UTC) - timedelta(seconds=1)
    expired = jwt.encode(
        {
            "sub": user["id"],
            "iss": ISSUER,
            "iat": expires - timedelta(minutes=1),
            "exp": expires,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    for token in ("invalid-token", expired):
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
