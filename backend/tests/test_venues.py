"""Tests for Phase 3 PR2: Venue Management.

Covers: CRUD permissions, field validation, availability rules, status lifecycle,
query filtering / data isolation, audit logging, and regression smoke.

All tests use HTTP integration via the `client` fixture, following the pattern
established in test_users.py and test_tasks_extended.py.
"""
import datetime
import json

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.venue import Venue
from tests.helpers import (
    auth_headers,
    create_test_user,
    create_test_venue,
    login_user,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _admin_token(client, db_session, username="v_admin"):
    """Create an admin user and return a valid JWT token."""
    await create_test_user(db_session, username=username, password="pw1234", role="admin")
    return await login_user(client, username, "pw1234")


async def _fm_token(client, db_session, username="v_fm"):
    """Create a facility_manager user and return a valid JWT token."""
    await create_test_user(db_session, username=username, password="pw1234", role="facility_manager")
    return await login_user(client, username, "pw1234")


async def _teacher_token(client, db_session, username="v_teacher"):
    """Create a teacher user and return a valid JWT token."""
    await create_test_user(db_session, username=username, password="pw1234", role="teacher")
    return await login_user(client, username, "pw1234")


async def _student_token(client, db_session, username="v_student"):
    """Create a student user and return a valid JWT token."""
    await create_test_user(db_session, username=username, password="pw1234", role="student")
    return await login_user(client, username, "pw1234")


async def _create_venue_via_api(client, token, **overrides):
    """POST /api/v1/venues with defaults overridden by kwargs."""
    payload = {
        "name": "Test Venue",
        "capacity": 30,
        "location": "Building A Floor 1",
    }
    payload.update(overrides)
    return await client.post(
        "/api/v1/venues",
        json=payload,
        headers=auth_headers(token),
    )


# ===================================================================
# 1. CRUD Permission Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_admin_allowed(client, db_session):
    token = await _admin_token(client, db_session, "v_crud_admin")
    resp = await _create_venue_via_api(client, token, name="Admin Venue")
    assert resp.status_code == 201
    assert resp.json()["name"] == "Admin Venue"
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_facility_manager_allowed(client, db_session):
    token = await _fm_token(client, db_session, "v_crud_fm")
    resp = await _create_venue_via_api(client, token, name="FM Venue")
    assert resp.status_code == 201
    assert resp.json()["name"] == "FM Venue"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_teacher_forbidden(client, db_session):
    token = await _teacher_token(client, db_session, "v_crud_teacher")
    resp = await _create_venue_via_api(client, token)
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "v_crud_student")
    resp = await _create_venue_via_api(client, token)
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_list_venues_admin_sees_all(client, db_session):
    token = await _admin_token(client, db_session, "v_list_admin")
    await create_test_venue(db_session, name="Active V", status="active")
    await create_test_venue(db_session, name="Inactive V", status="inactive")
    resp = await client.get("/api/v1/venues", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [v["name"] for v in resp.json()["items"]]
    assert "Active V" in names
    assert "Inactive V" in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_venues_teacher_sees_active_only(client, db_session):
    token = await _teacher_token(client, db_session, "v_list_teacher")
    await create_test_venue(db_session, name="TActive V", status="active")
    await create_test_venue(db_session, name="TInactive V", status="inactive")
    resp = await client.get("/api/v1/venues", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [v["name"] for v in resp.json()["items"]]
    assert "TActive V" in names
    assert "TInactive V" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_venues_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "v_list_student")
    resp = await client.get("/api/v1/venues", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_get_venue_detail_admin(client, db_session):
    token = await _admin_token(client, db_session, "v_detail_admin")
    venue = await create_test_venue(db_session, name="Detail V", status="active")
    resp = await client.get(f"/api/v1/venues/{venue.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail V"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_venue_detail_teacher_active(client, db_session):
    token = await _teacher_token(client, db_session, "v_detail_teacher")
    venue = await create_test_venue(db_session, name="Teacher Visible V", status="active")
    resp = await client.get(f"/api/v1/venues/{venue.id}", headers=auth_headers(token))
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_get_venue_detail_teacher_inactive_404(client, db_session):
    """Teacher gets 404 (not 403) for inactive venues — prevents existence probing."""
    token = await _teacher_token(client, db_session, "v_detail_teacher2")
    venue = await create_test_venue(db_session, name="Hidden V", status="inactive")
    resp = await client.get(f"/api/v1/venues/{venue.id}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_admin_allowed(client, db_session):
    token = await _admin_token(client, db_session, "v_upd_admin")
    resp = await _create_venue_via_api(client, token, name="Updatable V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}",
        json={"name": "Updated Name", "capacity": 50},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Updated Name"
    assert resp2.json()["capacity"] == 50


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_facility_manager_allowed(client, db_session):
    token = await _fm_token(client, db_session, "v_upd_fm")
    resp = await _create_venue_via_api(client, token, name="FM Upd V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}",
        json={"capacity": 40},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_teacher_forbidden(client, db_session):
    admin_tok = await _admin_token(client, db_session, "v_upd_admin2")
    teacher_tok = await _teacher_token(client, db_session, "v_upd_teacher")
    resp = await _create_venue_via_api(client, admin_tok, name="No Teacher Edit V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}",
        json={"name": "Hacked"},
        headers=auth_headers(teacher_tok),
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_nonexistent_404(client, db_session):
    token = await _admin_token(client, db_session, "v_upd_404")
    resp = await client.put(
        "/api/v1/venues/99999",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ===================================================================
# 2. Field Validation and Uniqueness Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_name_required(client, db_session):
    token = await _admin_token(client, db_session, "v_val_admin")
    resp = await client.post(
        "/api/v1/venues",
        json={"capacity": 30},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_name_empty_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_val_admin2")
    resp = await client.post(
        "/api/v1/venues",
        json={"name": ""},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_name_too_long_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_val_admin3")
    resp = await client.post(
        "/api/v1/venues",
        json={"name": "x" * 101},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_negative_capacity_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_val_admin4")
    resp = await client.post(
        "/api/v1/venues",
        json={"name": "Bad Cap", "capacity": -1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_zero_capacity_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_val_admin5")
    resp = await client.post(
        "/api/v1/venues",
        json={"name": "Zero Cap", "capacity": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_minimal_fields(client, db_session):
    token = await _admin_token(client, db_session, "v_val_min")
    resp = await client.post(
        "/api/v1/venues",
        json={"name": "Minimal V"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["capacity"] is None
    assert data["location"] is None
    assert data["description"] is None
    assert data["status"] == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_with_all_fields(client, db_session):
    token = await _admin_token(client, db_session, "v_val_full")
    resp = await client.post(
        "/api/v1/venues",
        json={
            "name": "Full Venue",
            "capacity": 50,
            "location": "Building B Floor 3",
            "description": "A large XR training lab",
            "external_id": "xr-venue-0042",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["capacity"] == 50
    assert data["location"] == "Building B Floor 3"
    assert data["description"] == "A large XR training lab"
    assert data["external_id"] == "xr-venue-0042"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_forbids_extra_fields(client, db_session):
    token = await _admin_token(client, db_session, "v_val_forbid")
    resp = await _create_venue_via_api(client, token, name="Forbid Extra V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}",
        json={"name": "OK", "bogus_field": "nope"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


# ===================================================================
# 3. Availability Rule Validation Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_set_availability_slots(client, db_session):
    token = await _admin_token(client, db_session, "v_avail_admin")
    resp = await _create_venue_via_api(client, token, name="Avail V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={
            "slots": [
                {"day_of_week": 0, "start_time": "08:00", "end_time": "12:00"},
                {"day_of_week": 0, "start_time": "13:00", "end_time": "17:00"},
                {"day_of_week": 2, "start_time": "09:00", "end_time": "11:00"},
            ]
        },
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert len(resp2.json()["availability"]) == 3


@pytest.mark.asyncio(loop_scope="session")
async def test_availability_replaces_previous(client, db_session):
    token = await _admin_token(client, db_session, "v_avail_replace")
    resp = await _create_venue_via_api(client, token, name="Replace Avail V")
    vid = resp.json()["id"]

    # Set initial
    await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 0, "start_time": "08:00", "end_time": "17:00"}]},
        headers=auth_headers(token),
    )
    # Replace
    resp2 = await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 1, "start_time": "09:00", "end_time": "16:00"}]},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    slots = resp2.json()["availability"]
    assert len(slots) == 1
    assert slots[0]["day_of_week"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_availability_invalid_day_of_week(client, db_session):
    token = await _admin_token(client, db_session, "v_avail_dow")
    resp = await _create_venue_via_api(client, token, name="Bad DOW V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 7, "start_time": "08:00", "end_time": "12:00"}]},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_availability_end_before_start_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_avail_time")
    resp = await _create_venue_via_api(client, token, name="Bad Time V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 0, "start_time": "17:00", "end_time": "08:00"}]},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_availability_equal_start_end_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_avail_eq")
    resp = await _create_venue_via_api(client, token, name="Equal Time V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 0, "start_time": "08:00", "end_time": "08:00"}]},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_availability_teacher_forbidden(client, db_session):
    token = await _teacher_token(client, db_session, "v_avail_teacher")
    admin_tok = await _admin_token(client, db_session, "v_avail_teacher_admin")
    resp = await _create_venue_via_api(client, admin_tok, name="No Teacher Avail V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 0, "start_time": "08:00", "end_time": "12:00"}]},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 403


# ===================================================================
# 4. Blackout (Manual Unavailability) Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_blackout(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_admin")
    resp = await _create_venue_via_api(client, token, name="Blackout V")
    vid = resp.json()["id"]
    resp2 = await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={
            "start_date": "2026-05-01",
            "end_date": "2026-05-03",
            "reason": "Labor Day holiday",
        },
        headers=auth_headers(token),
    )
    assert resp2.status_code == 201
    assert resp2.json()["reason"] == "Labor Day holiday"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_blackouts(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_list")
    resp = await _create_venue_via_api(client, token, name="BO List V")
    vid = resp.json()["id"]
    await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={"start_date": "2026-06-01", "end_date": "2026-06-02", "reason": "Maintenance"},
        headers=auth_headers(token),
    )
    resp2 = await client.get(
        f"/api/v1/venues/{vid}/blackouts",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert len(resp2.json()) >= 1


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_blackout(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_del")
    resp = await _create_venue_via_api(client, token, name="BO Del V")
    vid = resp.json()["id"]
    resp2 = await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={"start_date": "2026-07-01", "end_date": "2026-07-02", "reason": "Temp"},
        headers=auth_headers(token),
    )
    bid = resp2.json()["id"]
    resp3 = await client.delete(
        f"/api/v1/venues/{vid}/blackouts/{bid}",
        headers=auth_headers(token),
    )
    assert resp3.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_blackout_end_before_start_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_bad")
    resp = await _create_venue_via_api(client, token, name="Bad BO V")
    vid = resp.json()["id"]
    resp2 = await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={"start_date": "2026-05-10", "end_date": "2026-05-05"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_blackout_teacher_forbidden_write(client, db_session):
    teacher_tok = await _teacher_token(client, db_session, "v_bo_teacher")
    admin_tok = await _admin_token(client, db_session, "v_bo_teacher_admin")
    resp = await _create_venue_via_api(client, admin_tok, name="No Teacher BO V")
    vid = resp.json()["id"]
    resp2 = await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={"start_date": "2026-08-01", "end_date": "2026-08-02"},
        headers=auth_headers(teacher_tok),
    )
    assert resp2.status_code == 403


# ===================================================================
# 5. Status Lifecycle Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_change_status_active_to_inactive(client, db_session):
    token = await _admin_token(client, db_session, "v_st_admin1")
    resp = await _create_venue_via_api(client, token, name="Status V1")
    vid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={"status": "inactive"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "inactive"


@pytest.mark.asyncio(loop_scope="session")
async def test_change_status_active_to_maintenance(client, db_session):
    token = await _admin_token(client, db_session, "v_st_admin2")
    resp = await _create_venue_via_api(client, token, name="Status V2")
    vid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={"status": "maintenance"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "maintenance"


@pytest.mark.asyncio(loop_scope="session")
async def test_change_status_inactive_to_active(client, db_session):
    token = await _admin_token(client, db_session, "v_st_admin3")
    venue = await create_test_venue(db_session, name="Reactivate V", status="inactive")
    resp = await client.patch(
        f"/api/v1/venues/{venue.id}/status",
        json={"status": "active"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_change_status_invalid_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_st_admin4")
    resp = await _create_venue_via_api(client, token, name="Bad Status V")
    vid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={"status": "demolished"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_change_status_teacher_forbidden(client, db_session):
    teacher_tok = await _teacher_token(client, db_session, "v_st_teacher")
    admin_tok = await _admin_token(client, db_session, "v_st_teacher_admin")
    resp = await _create_venue_via_api(client, admin_tok, name="No Teacher Status V")
    vid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={"status": "maintenance"},
        headers=auth_headers(teacher_tok),
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_deactivate_venue_preserves_record(client, db_session):
    """Deactivating a venue does NOT delete it — the row stays in DB."""
    token = await _admin_token(client, db_session, "v_st_preserve")
    resp = await _create_venue_via_api(client, token, name="Preserve V")
    vid = resp.json()["id"]
    await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={"status": "inactive"},
        headers=auth_headers(token),
    )
    # Admin can still see it in detail
    resp2 = await client.get(f"/api/v1/venues/{vid}", headers=auth_headers(token))
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "inactive"
    assert resp2.json()["name"] == "Preserve V"


# ===================================================================
# 6. Query Filtering and Data Isolation Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_list_venues_filter_by_status(client, db_session):
    token = await _admin_token(client, db_session, "v_filter_admin")
    await create_test_venue(db_session, name="F Active", status="active")
    await create_test_venue(db_session, name="F Inactive", status="inactive")
    await create_test_venue(db_session, name="F Maintenance", status="maintenance")
    resp = await client.get(
        "/api/v1/venues?status=active",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [v["name"] for v in resp.json()["items"]]
    assert "F Active" in names
    assert "F Inactive" not in names
    assert "F Maintenance" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_venues_filter_by_capacity(client, db_session):
    token = await _admin_token(client, db_session, "v_cap_admin")
    await create_test_venue(db_session, name="Small V", capacity=10)
    await create_test_venue(db_session, name="Large V", capacity=100)
    resp = await client.get(
        "/api/v1/venues?capacity_min=50",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [v["name"] for v in resp.json()["items"]]
    assert "Large V" in names
    assert "Small V" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_venues_pagination(client, db_session):
    token = await _admin_token(client, db_session, "v_page_admin")
    for i in range(5):
        await create_test_venue(db_session, name=f"Page V {i}")
    resp = await client.get(
        "/api/v1/venues?limit=2&offset=0",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["total"] >= 5


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_response_includes_availability(client, db_session):
    """GET /venues/:id returns availability slots when configured."""
    token = await _admin_token(client, db_session, "v_resp_avail")
    resp = await _create_venue_via_api(client, token, name="Resp Avail V")
    vid = resp.json()["id"]
    await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 0, "start_time": "08:00", "end_time": "12:00"}]},
        headers=auth_headers(token),
    )
    resp2 = await client.get(f"/api/v1/venues/{vid}", headers=auth_headers(token))
    assert resp2.status_code == 200
    assert len(resp2.json().get("availability", [])) == 1


# ===================================================================
# 7. Audit Logging Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_venue_create(client, db_session):
    token = await _admin_token(client, db_session, "v_audit_create")
    admin = await create_test_user(db_session, username="v_audit_create", password="pw1234", role="admin")
    resp = await _create_venue_via_api(client, token, name="Audit Create V")
    vid = resp.json()["id"]

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "venue",
            AuditLog.entity_id == vid,
            AuditLog.action == "create",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.actor_id == admin.id
    changes = json.loads(entry.changes)
    assert changes["name"] == "Audit Create V"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_venue_update(client, db_session):
    token = await _admin_token(client, db_session, "v_audit_upd")
    resp = await _create_venue_via_api(client, token, name="Audit Upd V")
    vid = resp.json()["id"]

    await client.put(
        f"/api/v1/venues/{vid}",
        json={"capacity": 60},
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "venue",
            AuditLog.entity_id == vid,
            AuditLog.action == "update",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_venue_status_change(client, db_session):
    token = await _admin_token(client, db_session, "v_audit_st")
    resp = await _create_venue_via_api(client, token, name="Audit Status V")
    vid = resp.json()["id"]

    await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={"status": "maintenance"},
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "venue",
            AuditLog.entity_id == vid,
            AuditLog.action == "status_change",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["old_status"] == "active"
    assert changes["new_status"] == "maintenance"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_venue_availability_update(client, db_session):
    token = await _admin_token(client, db_session, "v_audit_avail")
    resp = await _create_venue_via_api(client, token, name="Audit Avail V")
    vid = resp.json()["id"]

    await client.put(
        f"/api/v1/venues/{vid}/availability",
        json={"slots": [{"day_of_week": 0, "start_time": "08:00", "end_time": "12:00"}]},
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "venue",
            AuditLog.entity_id == vid,
            AuditLog.action == "update_availability",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None


# ===================================================================
# 8. Regression Smoke Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_health_still_works(client, db_session):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio(loop_scope="session")
async def test_auth_login_still_works(client, db_session):
    await create_test_user(db_session, username="smoke_user", password="pw1234")
    resp = await client.post(
        "/api/auth/login",
        json={"username": "smoke_user", "password": "pw1234"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_courses_endpoint_still_works(client, db_session):
    token = await _admin_token(client, db_session, "v_smoke_admin")
    resp = await client.get("/api/courses", headers=auth_headers(token))
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_users_endpoint_still_works(client, db_session):
    token = await _admin_token(client, db_session, "v_smoke_admin2")
    resp = await client.get("/api/users", headers=auth_headers(token))
    assert resp.status_code == 200


# ===================================================================
# 9. CE Review Fix Tests
# ===================================================================


# --- B1: Student permission boundaries ---


@pytest.mark.asyncio(loop_scope="session")
async def test_get_venue_student_forbidden(client, db_session):
    admin_tok = await _admin_token(client, db_session, "v_stu_admin")
    student_tok = await _student_token(client, db_session, "v_stu_detail")
    resp = await _create_venue_via_api(client, admin_tok, name="Student No See")
    vid = resp.json()["id"]
    resp2 = await client.get(
        f"/api/v1/venues/{vid}",
        headers=auth_headers(student_tok),
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_list_blackouts_student_forbidden(client, db_session):
    admin_tok = await _admin_token(client, db_session, "v_stu_bo_admin")
    student_tok = await _student_token(client, db_session, "v_stu_bo")
    resp = await _create_venue_via_api(client, admin_tok, name="Student BO V")
    vid = resp.json()["id"]
    resp2 = await client.get(
        f"/api/v1/venues/{vid}/blackouts",
        headers=auth_headers(student_tok),
    )
    assert resp2.status_code == 403


# --- B2: VenueStatusUpdate Pydantic model ---


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_status_missing_status_key(client, db_session):
    token = await _admin_token(client, db_session, "v_st_missing")
    resp = await _create_venue_via_api(client, token, name="Status Missing V")
    vid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_status_extra_fields_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_st_extra")
    resp = await _create_venue_via_api(client, token, name="Status Extra V")
    vid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/venues/{vid}/status",
        json={"status": "active", "extra_key": "bad"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


# --- S1: Blackout audit logging ---


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_blackout_create(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_audit_c")
    resp = await _create_venue_via_api(client, token, name="BO Audit Create V")
    vid = resp.json()["id"]
    await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={"start_date": "2026-09-01", "end_date": "2026-09-02", "reason": "Audit test"},
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "venue",
            AuditLog.entity_id == vid,
            AuditLog.action == "create_blackout",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["start_date"] == "2026-09-01"
    assert changes["reason"] == "Audit test"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_blackout_delete(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_audit_d")
    resp = await _create_venue_via_api(client, token, name="BO Audit Del V")
    vid = resp.json()["id"]
    resp2 = await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={"start_date": "2026-10-01", "end_date": "2026-10-02"},
        headers=auth_headers(token),
    )
    bid = resp2.json()["id"]
    await client.delete(
        f"/api/v1/venues/{vid}/blackouts/{bid}",
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "venue",
            AuditLog.entity_id == vid,
            AuditLog.action == "delete_blackout",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["blackout_id"] == bid


# --- S2: VenueUpdate capacity validation ---


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_capacity_zero_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_cap_zero")
    resp = await _create_venue_via_api(client, token, name="Cap Zero V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}",
        json={"capacity": 0},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_capacity_negative_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_cap_neg")
    resp = await _create_venue_via_api(client, token, name="Cap Neg V")
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}",
        json={"capacity": -5},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


# --- S6: VenueCreate extra fields ---


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_extra_fields_rejected(client, db_session):
    token = await _admin_token(client, db_session, "v_extra_field")
    resp = await client.post(
        "/api/v1/venues",
        json={"name": "Extra V", "bogus_field": "bad"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


# --- 404 paths for availability/blackout ---


@pytest.mark.asyncio(loop_scope="session")
async def test_set_availability_404_nonexistent_venue(client, db_session):
    token = await _admin_token(client, db_session, "v_avail_404")
    resp = await client.put(
        "/api/v1/venues/99999/availability",
        json={"slots": [{"day_of_week": 0, "start_time": "08:00", "end_time": "12:00"}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_create_blackout_404_nonexistent_venue(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_404")
    resp = await client.post(
        "/api/v1/venues/99999/blackouts",
        json={"start_date": "2026-06-01", "end_date": "2026-06-02"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_list_blackouts_404_nonexistent_venue(client, db_session):
    token = await _admin_token(client, db_session, "v_lbo_404")
    resp = await client.get(
        "/api/v1/venues/99999/blackouts",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_status_404_nonexistent_venue(client, db_session):
    token = await _admin_token(client, db_session, "v_st_404")
    resp = await client.patch(
        "/api/v1/venues/99999/status",
        json={"status": "inactive"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# --- Stronger assertions ---


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_blackout_actually_removes(client, db_session):
    token = await _admin_token(client, db_session, "v_bo_gone")
    resp = await _create_venue_via_api(client, token, name="BO Gone V")
    vid = resp.json()["id"]
    resp2 = await client.post(
        f"/api/v1/venues/{vid}/blackouts",
        json={"start_date": "2026-11-01", "end_date": "2026-11-02", "reason": "To delete"},
        headers=auth_headers(token),
    )
    bid = resp2.json()["id"]
    await client.delete(
        f"/api/v1/venues/{vid}/blackouts/{bid}",
        headers=auth_headers(token),
    )
    resp3 = await client.get(
        f"/api/v1/venues/{vid}/blackouts",
        headers=auth_headers(token),
    )
    ids = [b["id"] for b in resp3.json()]
    assert bid not in ids


@pytest.mark.asyncio(loop_scope="session")
async def test_get_venue_teacher_active_checks_fields(client, db_session):
    admin_tok = await _admin_token(client, db_session, "v_teach_fld_adm")
    teacher_tok = await _teacher_token(client, db_session, "v_teach_fld")
    resp = await _create_venue_via_api(client, admin_tok, name="Teacher Fields V", capacity=50)
    vid = resp.json()["id"]
    resp2 = await client.get(
        f"/api/v1/venues/{vid}",
        headers=auth_headers(teacher_tok),
    )
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["name"] == "Teacher Fields V"
    assert body["capacity"] == 50


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_fm_checks_capacity(client, db_session):
    fm_tok = await _fm_token(client, db_session, "v_fm_upd")
    resp = await _create_venue_via_api(client, fm_tok, name="FM Update V", capacity=30)
    vid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/venues/{vid}",
        json={"capacity": 40},
        headers=auth_headers(fm_tok),
    )
    assert resp2.status_code == 200
    assert resp2.json()["capacity"] == 40
