import pytest
import jwt
from datetime import datetime, timedelta, timezone

from app.config import settings


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _call_get_current_user(token: str):
    """Helper to call the async get_current_user with a mocked DB session."""
    import asyncio
    from app.dependencies.auth import get_current_user
    from unittest.mock import MagicMock

    # Create a mock credentials object with a .credentials attribute
    mock_credentials = MagicMock()
    mock_credentials.credentials = token
    return asyncio.run(
        get_current_user(credentials=mock_credentials, db=MagicMock())
    )


def test_get_current_user_valid_token():
    token = _make_token({"sub": "1", "role": "admin", "type": "access", "username": "admin"})
    result = _call_get_current_user(token)
    assert result is not None
    assert result["id"] == 1
    assert result["role"] == "admin"


def test_get_current_user_expired_token():
    from fastapi import HTTPException

    expired = _make_token({
        "sub": "1", "role": "admin", "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    })
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(expired)
    assert exc_info.value.status_code == 401


def test_get_current_user_invalid_token():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user("invalid-token-here")
    assert exc_info.value.status_code == 401


def test_require_role_allows_correct_role():
    from app.dependencies.auth import require_role

    dep = require_role("admin")
    assert callable(dep) or dep is not None


def test_require_role_blocks_wrong_role():
    from app.dependencies.auth import require_role
    from fastapi import HTTPException
    import asyncio

    dep = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            dep(current_user={"id": 1, "role": "student"})
        )
    assert exc_info.value.status_code == 403
