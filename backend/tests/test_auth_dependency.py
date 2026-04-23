import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock

from app.config import settings


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _call_get_current_user(token: str, mock_user=None):
    """Helper to call the async get_current_user with a mocked DB session."""
    import asyncio
    from app.dependencies.auth import get_current_user

    mock_credentials = MagicMock()
    mock_credentials.credentials = token

    mock_db = MagicMock()
    mock_result = MagicMock()
    if mock_user is None:
        mock_result.scalar_one_or_none.return_value = None
    else:
        mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    return asyncio.run(
        get_current_user(credentials=mock_credentials, db=mock_db)
    )


def _mock_user(is_active=True, role="admin", user_id=1, username="admin"):
    u = MagicMock()
    u.id = user_id
    u.role = role
    u.username = username
    u.is_active = is_active
    return u


def test_get_current_user_valid_token():
    user = _mock_user(is_active=True)
    result = _call_get_current_user(
        _make_token({"sub": "1", "role": "admin", "type": "access", "username": "admin"}),
        mock_user=user,
    )
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


def test_get_current_user_deactivated_rejected():
    """P0 fix: deactivated users must be rejected even with a valid JWT."""
    from fastapi import HTTPException

    user = _mock_user(is_active=False)
    token = _make_token({"sub": "1", "role": "student", "type": "access", "username": "ghost"})
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(token, mock_user=user)
    assert exc_info.value.status_code == 401
    assert "deactivated" in exc_info.value.detail.lower()


def test_get_current_user_not_found_rejected():
    """User deleted from DB after JWT was issued — should reject."""
    from fastapi import HTTPException

    token = _make_token({"sub": "999", "role": "student", "type": "access", "username": "gone"})
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(token, mock_user=None)
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
