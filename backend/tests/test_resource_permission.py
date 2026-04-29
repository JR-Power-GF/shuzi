"""Tests for resource-domain permission boundaries.

Validates that require_role and require_role_or_owner work correctly
for the resource permission matrix defined in PR1.
"""
import pytest
from fastapi import HTTPException

from app.dependencies.auth import require_role, require_role_or_owner


# ---------------------------------------------------------------------------
# require_role — resource read permissions
# admin, facility_manager, teacher can read resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_role_allows_admin_for_resource_read():
    checker = require_role(["admin", "facility_manager", "teacher"])
    user = {"id": 1, "role": "admin", "username": "admin1"}
    result = await checker(current_user=user)
    assert result["role"] == "admin"


@pytest.mark.asyncio
async def test_require_role_allows_facility_manager_for_resource_read():
    checker = require_role(["admin", "facility_manager", "teacher"])
    user = {"id": 2, "role": "facility_manager", "username": "fm1"}
    result = await checker(current_user=user)
    assert result["role"] == "facility_manager"


@pytest.mark.asyncio
async def test_require_role_allows_teacher_for_resource_read():
    checker = require_role(["admin", "facility_manager", "teacher"])
    user = {"id": 3, "role": "teacher", "username": "teacher1"}
    result = await checker(current_user=user)
    assert result["role"] == "teacher"


@pytest.mark.asyncio
async def test_require_role_denies_student_for_resource_read():
    checker = require_role(["admin", "facility_manager", "teacher"])
    user = {"id": 4, "role": "student", "username": "student1"}
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_role — resource write permissions
# admin, facility_manager can write resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_role_allows_admin_for_resource_write():
    checker = require_role(["admin", "facility_manager"])
    user = {"id": 1, "role": "admin", "username": "admin1"}
    result = await checker(current_user=user)
    assert result is not None


@pytest.mark.asyncio
async def test_require_role_allows_facility_manager_for_resource_write():
    checker = require_role(["admin", "facility_manager"])
    user = {"id": 2, "role": "facility_manager", "username": "fm1"}
    result = await checker(current_user=user)
    assert result is not None


@pytest.mark.asyncio
async def test_require_role_denies_teacher_for_resource_write():
    checker = require_role(["admin", "facility_manager"])
    user = {"id": 3, "role": "teacher", "username": "teacher1"}
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_denies_student_for_resource_write():
    checker = require_role(["admin", "facility_manager"])
    user = {"id": 4, "role": "student", "username": "student1"}
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_role — statistics permissions
# admin, facility_manager can read statistics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_role_allows_admin_for_statistics():
    checker = require_role(["admin", "facility_manager"])
    user = {"id": 1, "role": "admin", "username": "admin1"}
    result = await checker(current_user=user)
    assert result is not None


@pytest.mark.asyncio
async def test_require_role_denies_teacher_for_statistics():
    checker = require_role(["admin", "facility_manager"])
    user = {"id": 3, "role": "teacher", "username": "teacher1"}
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# require_role_or_owner — booking modify/cancel
# admin/facility_manager always, teacher only if owner
# ---------------------------------------------------------------------------


async def _get_owner_id(user: dict, db) -> int | None:
    """Mock owner_id_getter that returns user id as the 'owner'."""
    return user.get("owner_id_of_resource")


@pytest.mark.asyncio
async def test_require_role_or_owner_allows_admin():
    checker = require_role_or_owner(["admin", "facility_manager"], _get_owner_id)
    user = {"id": 1, "role": "admin", "username": "admin1"}
    result = await checker(current_user=user, db=None)
    assert result is not None


@pytest.mark.asyncio
async def test_require_role_or_owner_allows_facility_manager():
    checker = require_role_or_owner(["admin", "facility_manager"], _get_owner_id)
    user = {"id": 2, "role": "facility_manager", "username": "fm1"}
    result = await checker(current_user=user, db=None)
    assert result is not None


@pytest.mark.asyncio
async def test_require_role_or_owner_allows_teacher_as_owner():
    checker = require_role_or_owner(["admin", "facility_manager"], _get_owner_id)
    user = {"id": 5, "role": "teacher", "username": "teacher5", "owner_id_of_resource": 5}
    result = await checker(current_user=user, db=None)
    assert result["id"] == 5


@pytest.mark.asyncio
async def test_require_role_or_owner_denies_teacher_not_owner():
    checker = require_role_or_owner(["admin", "facility_manager"], _get_owner_id)
    user = {"id": 5, "role": "teacher", "username": "teacher5", "owner_id_of_resource": 999}
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user, db=None)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_or_owner_allows_any_owner_regardless_of_role():
    """Current behavior: require_role_or_owner allows ANY owner through.

    For bookings, students can never be owners (blocked at creation by require_role),
    so this is safe in practice. PR4 should tighten this by adding a minimum-role
    check before the owner check if needed.
    """
    checker = require_role_or_owner(["admin", "facility_manager"], _get_owner_id)
    user = {"id": 6, "role": "student", "username": "student6", "owner_id_of_resource": 6}
    result = await checker(current_user=user, db=None)
    assert result["id"] == 6


@pytest.mark.asyncio
async def test_require_role_or_owner_denies_when_owner_id_is_none():
    async def getter(user, db):
        return None

    checker = require_role_or_owner(["admin", "facility_manager"], getter)
    user = {"id": 5, "role": "teacher", "username": "teacher5"}
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user, db=None)
    assert exc_info.value.status_code == 403
