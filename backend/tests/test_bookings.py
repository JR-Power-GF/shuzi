"""Tests for Phase 3 PR4: Booking / Scheduling.

TDD RED phase — all tests written before implementation.

Covers: permissions, CRUD, conflict detection boundaries,
all-or-nothing joint booking, cancel semantics, resource validation,
derived status, audit logging, concurrency, and regression smoke.
"""
import datetime
import json

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from tests.helpers import (
    auth_headers,
    create_test_booking,
    create_test_equipment,
    create_test_user,
    create_test_venue,
    login_user,
)


# ---------------------------------------------------------------------------
# Shared constants and helpers
# ---------------------------------------------------------------------------

NOW = datetime.datetime(2026, 6, 1, 9, 0)
TWO_H = datetime.timedelta(hours=2)


async def _admin_token(client, db, username="bk_admin"):
    await create_test_user(db, username=username, password="pw1234", role="admin")
    return await login_user(client, username, "pw1234")


async def _fm_token(client, db, username="bk_fm"):
    await create_test_user(db, username=username, password="pw1234", role="facility_manager")
    return await login_user(client, username, "pw1234")


async def _teacher_token(client, db, username="bk_tch"):
    await create_test_user(db, username=username, password="pw1234", role="teacher")
    return await login_user(client, username, "pw1234")


async def _student_token(client, db, username="bk_stu"):
    await create_test_user(db, username=username, password="pw1234", role="student")
    return await login_user(client, username, "pw1234")


async def _make_venue(db, name="BK Venue"):
    return await create_test_venue(db, name=name)


async def _make_booking(client, token, venue_id, **overrides):
    payload = {
        "venue_id": venue_id,
        "title": "Test Booking",
        "start_time": NOW.isoformat(),
        "end_time": (NOW + TWO_H).isoformat(),
    }
    payload.update(overrides)
    return await client.post(
        "/api/v1/bookings",
        json=payload,
        headers=auth_headers(token),
    )


# ===================================================================
# 1. Permission Tests (10)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_admin_ok(client, db_session):
    admin = await create_test_user(db_session, username="bk_p1_adm", password="pw1234", role="admin")
    token = await login_user(client, "bk_p1_adm", "pw1234")
    venue = await _make_venue(db_session, "P1 Venue")
    resp = await _make_booking(client, token, venue.id)
    assert resp.status_code == 201
    assert resp.json()["booked_by"] == admin.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_fm_ok(client, db_session):
    fm = await create_test_user(db_session, username="bk_p2_fm", password="pw1234", role="facility_manager")
    token = await login_user(client, "bk_p2_fm", "pw1234")
    venue = await _make_venue(db_session, "P2 Venue")
    resp = await _make_booking(client, token, venue.id)
    assert resp.status_code == 201
    assert resp.json()["booked_by"] == fm.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_teacher_auto_booked_by(client, db_session):
    teacher = await create_test_user(db_session, username="bk_p3_tch", password="pw1234", role="teacher")
    token = await login_user(client, "bk_p3_tch", "pw1234")
    venue = await _make_venue(db_session, "P3 Venue")
    resp = await _make_booking(client, token, venue.id)
    assert resp.status_code == 201
    assert resp.json()["booked_by"] == teacher.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "bk_p4_stu")
    venue = await _make_venue(db_session, "P4 Venue")
    resp = await _make_booking(client, token, venue.id)
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_list_admin_sees_all(client, db_session):
    adm_token = await _admin_token(client, db_session, "bk_p5_adm")
    tch = await create_test_user(db_session, username="bk_p5_tch", password="pw1234", role="teacher")
    tch_token = await login_user(client, "bk_p5_tch", "pw1234")
    venue = await _make_venue(db_session, "P5 Venue")
    await _make_booking(client, adm_token, venue.id, title="Admin BK")
    await _make_booking(
        client, tch_token, venue.id, title="Teacher BK",
        start_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=5)).isoformat(),
    )
    resp = await client.get("/api/v1/bookings", headers=auth_headers(adm_token))
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["items"]]
    assert "Admin BK" in titles
    assert "Teacher BK" in titles


@pytest.mark.asyncio(loop_scope="session")
async def test_list_teacher_own_only(client, db_session):
    adm_token = await _admin_token(client, db_session, "bk_p6_adm")
    tch = await create_test_user(db_session, username="bk_p6_tch", password="pw1234", role="teacher")
    tch_token = await login_user(client, "bk_p6_tch", "pw1234")
    venue = await _make_venue(db_session, "P6 Venue")
    await _make_booking(client, adm_token, venue.id, title="Admin Only")
    await _make_booking(
        client, tch_token, venue.id, title="Tch Own",
        start_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=5)).isoformat(),
    )
    resp = await client.get("/api/v1/bookings", headers=auth_headers(tch_token))
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["items"]]
    assert "Tch Own" in titles
    assert "Admin Only" not in titles


@pytest.mark.asyncio(loop_scope="session")
async def test_list_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "bk_p7_stu")
    resp = await client.get("/api/v1/bookings", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_teacher_other_forbidden(client, db_session):
    tch1 = await create_test_user(db_session, username="bk_p8a", password="pw1234", role="teacher")
    tch1_token = await login_user(client, "bk_p8a", "pw1234")
    tch2 = await create_test_user(db_session, username="bk_p8b", password="pw1234", role="teacher")
    tch2_token = await login_user(client, "bk_p8b", "pw1234")
    venue = await _make_venue(db_session, "P8 Venue")
    resp = await _make_booking(client, tch1_token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.get(f"/api/v1/bookings/{bid}", headers=auth_headers(tch2_token))
    assert resp2.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_student_forbidden(client, db_session):
    adm_token = await _admin_token(client, db_session, "bk_p9_adm")
    stu_token = await _student_token(client, db_session, "bk_p9_stu")
    venue = await _make_venue(db_session, "P9 Venue")
    resp = await _make_booking(client, adm_token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.get(f"/api/v1/bookings/{bid}", headers=auth_headers(stu_token))
    assert resp2.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_teacher_other_forbidden(client, db_session):
    tch1 = await create_test_user(db_session, username="bk_p10a", password="pw1234", role="teacher")
    tch1_token = await login_user(client, "bk_p10a", "pw1234")
    tch2 = await create_test_user(db_session, username="bk_p10b", password="pw1234", role="teacher")
    tch2_token = await login_user(client, "bk_p10b", "pw1234")
    venue = await _make_venue(db_session, "P10 Venue")
    resp = await _make_booking(client, tch1_token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(tch2_token))
    assert resp2.status_code == 403


# ===================================================================
# 2. Create Success / Failure Tests (6)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_only(client, db_session):
    token = await _admin_token(client, db_session, "bk_c1_adm")
    venue = await _make_venue(db_session, "C1 Venue")
    resp = await _make_booking(client, token, venue.id, title="Venue Only BK")
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "approved"
    assert body["venue_name"] == "C1 Venue"
    assert body["equipment"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_create_venue_with_equipment(client, db_session):
    token = await _admin_token(client, db_session, "bk_c2_adm")
    venue = await _make_venue(db_session, "C2 Venue")
    e1 = await create_test_equipment(db_session, name="VR-1", serial_number="C2-E1")
    e2 = await create_test_equipment(db_session, name="Proj-1", serial_number="C2-E2")
    resp = await _make_booking(
        client, token, venue.id, title="With Eq BK",
        equipment_ids=[e1.id, e2.id],
    )
    assert resp.status_code == 201
    names = [e["name"] for e in resp.json()["equipment"]]
    assert "VR-1" in names
    assert "Proj-1" in names


@pytest.mark.asyncio(loop_scope="session")
async def test_create_with_all_optional_fields(client, db_session):
    token = await _admin_token(client, db_session, "bk_c3_adm")
    venue = await _make_venue(db_session, "C3 Venue")
    resp = await _make_booking(
        client, token, venue.id,
        title="Full BK", purpose="training",
        course_id=1, class_id=1, task_id=1,
        client_ref="xr-session-001",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["purpose"] == "training"
    assert body["client_ref"] == "xr-session-001"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_rejects_extra_fields(client, db_session):
    token = await _admin_token(client, db_session, "bk_c4_adm")
    venue = await _make_venue(db_session, "C4 Venue")
    resp = await client.post(
        "/api/v1/bookings",
        json={
            "venue_id": venue.id, "title": "Extra",
            "start_time": NOW.isoformat(),
            "end_time": (NOW + TWO_H).isoformat(),
            "bogus": "bad",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_rejects_end_before_start(client, db_session):
    token = await _admin_token(client, db_session, "bk_c5_adm")
    venue = await _make_venue(db_session, "C5 Venue")
    resp = await _make_booking(
        client, token, venue.id,
        start_time=(NOW + TWO_H).isoformat(),
        end_time=NOW.isoformat(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_rejects_equal_start_end(client, db_session):
    token = await _admin_token(client, db_session, "bk_c6_adm")
    venue = await _make_venue(db_session, "C6 Venue")
    resp = await _make_booking(
        client, token, venue.id,
        start_time=NOW.isoformat(),
        end_time=NOW.isoformat(),
    )
    assert resp.status_code == 422


# ===================================================================
# 3. Conflict Detection Boundary Tests (8)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_conflict_full_overlap(client, db_session):
    """Exact same [start, end) on same venue → 409."""
    token = await _admin_token(client, db_session, "bk_cf1_adm")
    venue = await _make_venue(db_session, "CF1 Venue")
    await _make_booking(client, token, venue.id, title="Blocker")
    resp = await _make_booking(client, token, venue.id, title="Challenger")
    assert resp.status_code == 409
    assert "场地" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_conflict_partial_overlap_start(client, db_session):
    """Existing [9,11). New [10,12) → overlap at [10,11)."""
    token = await _admin_token(client, db_session, "bk_cf2_adm")
    venue = await _make_venue(db_session, "CF2 Venue")
    await _make_booking(client, token, venue.id)
    resp = await _make_booking(
        client, token, venue.id,
        start_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_conflict_partial_overlap_end(client, db_session):
    """Existing [9,11). New [8,10) → overlap at [9,10)."""
    token = await _admin_token(client, db_session, "bk_cf3_adm")
    venue = await _make_venue(db_session, "CF3 Venue")
    await _make_booking(client, token, venue.id)
    resp = await _make_booking(
        client, token, venue.id,
        start_time=(NOW - datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_conflict_contained(client, db_session):
    """Existing [9,13). New [10,12) → fully contained → overlap."""
    token = await _admin_token(client, db_session, "bk_cf4_adm")
    venue = await _make_venue(db_session, "CF4 Venue")
    await _make_booking(
        client, token, venue.id,
        end_time=(NOW + datetime.timedelta(hours=4)).isoformat(),
    )
    resp = await _make_booking(
        client, token, venue.id,
        start_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_conflict_containing(client, db_session):
    """Existing [10,11). New [9,13) → new contains existing → overlap."""
    token = await _admin_token(client, db_session, "bk_cf5_adm")
    venue = await _make_venue(db_session, "CF5 Venue")
    await _make_booking(
        client, token, venue.id,
        start_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=2)).isoformat(),
    )
    resp = await _make_booking(
        client, token, venue.id,
        start_time=NOW.isoformat(),
        end_time=(NOW + datetime.timedelta(hours=4)).isoformat(),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_adjacent_end_equals_start_no_conflict(client, db_session):
    """Existing [9,11). New [11,13) — end==start → no overlap (half-open)."""
    token = await _admin_token(client, db_session, "bk_cf6_adm")
    venue = await _make_venue(db_session, "CF6 Venue")
    await _make_booking(client, token, venue.id, title="First")
    resp = await _make_booking(
        client, token, venue.id, title="Adjacent After",
        start_time=(NOW + TWO_H).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=4)).isoformat(),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio(loop_scope="session")
async def test_adjacent_start_equals_end_no_conflict(client, db_session):
    """Existing [9,11). New [7,9) — end==start → no overlap (half-open)."""
    token = await _admin_token(client, db_session, "bk_cf7_adm")
    venue = await _make_venue(db_session, "CF7 Venue")
    await _make_booking(client, token, venue.id, title="First")
    resp = await _make_booking(
        client, token, venue.id, title="Adjacent Before",
        start_time=(NOW - TWO_H).isoformat(),
        end_time=NOW.isoformat(),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio(loop_scope="session")
async def test_conflict_equipment_across_venues(client, db_session):
    """Same equipment, different venues, overlapping time → 409."""
    token = await _admin_token(client, db_session, "bk_cf8_adm")
    v1 = await _make_venue(db_session, "CF8 V1")
    v2 = await _make_venue(db_session, "CF8 V2")
    equip = await create_test_equipment(db_session, name="Shared Eq", serial_number="CF8-EQ")
    await _make_booking(client, token, v1.id, equipment_ids=[equip.id])
    resp = await _make_booking(
        client, token, v2.id,
        equipment_ids=[equip.id],
        start_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
    )
    assert resp.status_code == 409
    assert "设备" in resp.json()["detail"]


# ===================================================================
# 4. Update Tests (6)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_update_title(client, db_session):
    token = await _admin_token(client, db_session, "bk_u1_adm")
    venue = await _make_venue(db_session, "U1 Venue")
    resp = await _make_booking(client, token, venue.id, title="Old Title")
    bid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"title": "New Title"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "New Title"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_time_no_conflict(client, db_session):
    token = await _admin_token(client, db_session, "bk_u2_adm")
    venue = await _make_venue(db_session, "U2 Venue")
    resp = await _make_booking(client, token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={
            "start_time": (NOW + datetime.timedelta(hours=5)).isoformat(),
            "end_time": (NOW + datetime.timedelta(hours=7)).isoformat(),
        },
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_update_time_conflict_with_other(client, db_session):
    token = await _admin_token(client, db_session, "bk_u3_adm")
    venue = await _make_venue(db_session, "U3 Venue")
    # Blocker at [13:00, 15:00)
    await _make_booking(
        client, token, venue.id, title="Blocker",
        start_time=(NOW + datetime.timedelta(hours=4)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=6)).isoformat(),
    )
    resp = await _make_booking(client, token, venue.id, title="Mover")
    bid = resp.json()["id"]
    # Move Mover to overlap with Blocker
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={
            "start_time": (NOW + datetime.timedelta(hours=5)).isoformat(),
            "end_time": (NOW + datetime.timedelta(hours=7)).isoformat(),
        },
        headers=auth_headers(token),
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_update_excludes_self_from_conflict(client, db_session):
    """Update booking to same time range → should succeed (not conflict with self)."""
    token = await _admin_token(client, db_session, "bk_u4_adm")
    venue = await _make_venue(db_session, "U4 Venue")
    resp = await _make_booking(client, token, venue.id, title="Self BK")
    bid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"title": "Updated Self BK"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Updated Self BK"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_equipment_list(client, db_session):
    token = await _admin_token(client, db_session, "bk_u5_adm")
    venue = await _make_venue(db_session, "U5 Venue")
    e1 = await create_test_equipment(db_session, name="U5-E1", serial_number="U5-E1")
    e2 = await create_test_equipment(db_session, name="U5-E2", serial_number="U5-E2")
    resp = await _make_booking(client, token, venue.id, equipment_ids=[e1.id])
    bid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"equipment_ids": [e2.id]},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    eq_ids = [e["id"] for e in resp2.json()["equipment"]]
    assert e2.id in eq_ids
    assert e1.id not in eq_ids


@pytest.mark.asyncio(loop_scope="session")
async def test_update_cancelled_booking_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_u6_adm")
    venue = await _make_venue(db_session, "U6 Venue")
    resp = await _make_booking(client, token, venue.id)
    bid = resp.json()["id"]
    await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"title": "Try Update"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 400


# ===================================================================
# 5. Cancel Tests (4)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_approved(client, db_session):
    token = await _admin_token(client, db_session, "bk_x1_adm")
    venue = await _make_venue(db_session, "X1 Venue")
    resp = await _make_booking(client, token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "cancelled"


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_idempotent(client, db_session):
    token = await _admin_token(client, db_session, "bk_x2_adm")
    venue = await _make_venue(db_session, "X2 Venue")
    resp = await _make_booking(client, token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp2.status_code == 200
    resp3 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "cancelled"


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_teacher_own_ok(client, db_session):
    tch = await create_test_user(db_session, username="bk_x3_tch", password="pw1234", role="teacher")
    tch_token = await login_user(client, "bk_x3_tch", "pw1234")
    venue = await _make_venue(db_session, "X3 Venue")
    resp = await _make_booking(client, tch_token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(tch_token))
    assert resp2.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_cancelled_booking_frees_slot(client, db_session):
    """After cancellation, same slot should be bookable again."""
    token = await _admin_token(client, db_session, "bk_x4_adm")
    venue = await _make_venue(db_session, "X4 Venue")
    resp = await _make_booking(client, token, venue.id, title="To Cancel")
    bid = resp.json()["id"]
    await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    resp2 = await _make_booking(client, token, venue.id, title="Reuse Slot")
    assert resp2.status_code == 201


# ===================================================================
# 6. All-or-Nothing Joint Booking Tests (3)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_aon_partial_equipment_rejects_entire(client, db_session):
    """One equipment conflicts → no booking created at all."""
    token = await _admin_token(client, db_session, "bk_aon1_adm")
    venue = await _make_venue(db_session, "AON1 Venue")
    v2 = await _make_venue(db_session, "AON1 V2")
    e1 = await create_test_equipment(db_session, name="AON-E1", serial_number="AON-E1")
    e2 = await create_test_equipment(db_session, name="AON-E2", serial_number="AON-E2")
    # Block e2 via another venue
    await _make_booking(client, token, v2.id, equipment_ids=[e2.id])
    # Try venue + [e1, e2] — e2 conflicts
    resp = await _make_booking(client, token, venue.id, equipment_ids=[e1.id, e2.id])
    assert resp.status_code == 409
    # Verify no booking was created for this venue
    resp2 = await client.get(
        f"/api/v1/bookings?venue_id={venue.id}",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_aon_no_booking_equipment_rows_after_reject(client, db_session):
    """After all-or-nothing rejection, no BookingEquipment rows should exist."""
    token = await _admin_token(client, db_session, "bk_aon2_adm")
    venue = await _make_venue(db_session, "AON2 Venue")
    v2 = await _make_venue(db_session, "AON2 V2")
    e1 = await create_test_equipment(db_session, name="AON2-E1", serial_number="AON2-E1")
    e2 = await create_test_equipment(db_session, name="AON2-E2", serial_number="AON2-E2")
    await _make_booking(client, token, v2.id, equipment_ids=[e2.id])
    await _make_booking(client, token, venue.id, equipment_ids=[e1.id, e2.id])
    # No BookingEquipment for e1 in this session
    result = await db_session.execute(
        select(BookingEquipment).where(BookingEquipment.equipment_id == e1.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio(loop_scope="session")
async def test_aon_venue_conflict_rejects_even_with_available_equip(client, db_session):
    """Venue conflict rejects even if all equipment is free."""
    token = await _admin_token(client, db_session, "bk_aon3_adm")
    venue = await _make_venue(db_session, "AON3 Venue")
    e1 = await create_test_equipment(db_session, name="AON3-E1", serial_number="AON3-E1")
    # Block the venue
    await _make_booking(client, token, venue.id)
    # Try with available equipment → still rejected
    resp = await _make_booking(
        client, token, venue.id, equipment_ids=[e1.id],
        start_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
    )
    assert resp.status_code == 409


# ===================================================================
# 7. Concurrency / Sequential Conflict Test (2)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_sequential_conflict_first_wins(client, db_session):
    """First booking at slot succeeds, second at same slot gets 409."""
    token = await _admin_token(client, db_session, "bk_cc1_adm")
    venue = await _make_venue(db_session, "CC1 Venue")
    resp1 = await _make_booking(client, token, venue.id, title="First")
    assert resp1.status_code == 201
    resp2 = await _make_booking(client, token, venue.id, title="Second")
    assert resp2.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_sequential_equipment_conflict(client, db_session):
    """First booking takes equipment, second with same equipment gets 409."""
    token = await _admin_token(client, db_session, "bk_cc2_adm")
    v1 = await _make_venue(db_session, "CC2 V1")
    v2 = await _make_venue(db_session, "CC2 V2")
    equip = await create_test_equipment(db_session, name="CC2-EQ", serial_number="CC2-EQ")
    resp1 = await _make_booking(client, token, v1.id, equipment_ids=[equip.id])
    assert resp1.status_code == 201
    resp2 = await _make_booking(client, token, v2.id, equipment_ids=[equip.id])
    assert resp2.status_code == 409


# ===================================================================
# 8. Resource Validation Tests (5)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_inactive_venue(client, db_session):
    token = await _admin_token(client, db_session, "bk_rv1_adm")
    venue = await create_test_venue(db_session, name="Inactive V", status="inactive")
    resp = await _make_booking(client, token, venue.id)
    assert resp.status_code == 400
    assert "不可用" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_maintenance_venue(client, db_session):
    token = await _admin_token(client, db_session, "bk_rv2_adm")
    venue = await create_test_venue(db_session, name="Maint V", status="maintenance")
    resp = await _make_booking(client, token, venue.id)
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_maintenance_equipment(client, db_session):
    token = await _admin_token(client, db_session, "bk_rv3_adm")
    venue = await _make_venue(db_session, "RV3 Venue")
    equip = await create_test_equipment(db_session, name="Maint Eq", status="maintenance")
    resp = await _make_booking(client, token, venue.id, equipment_ids=[equip.id])
    assert resp.status_code == 400
    assert "不可用" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_nonexistent_venue(client, db_session):
    token = await _admin_token(client, db_session, "bk_rv4_adm")
    resp = await _make_booking(client, token, 99999)
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_reject_nonexistent_equipment(client, db_session):
    token = await _admin_token(client, db_session, "bk_rv5_adm")
    venue = await _make_venue(db_session, "RV5 Venue")
    resp = await _make_booking(client, token, venue.id, equipment_ids=[99999])
    assert resp.status_code == 400


# ===================================================================
# 9. Derived Status Tests (3)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_derived_future_is_approved(client, db_session):
    token = await _admin_token(client, db_session, "bk_ds1_adm")
    venue = await _make_venue(db_session, "DS1 Venue")
    future = datetime.datetime(2030, 1, 1, 9, 0)
    resp = await _make_booking(
        client, token, venue.id,
        start_time=future.isoformat(),
        end_time=(future + TWO_H).isoformat(),
    )
    assert resp.json()["derived_status"] == "approved"


@pytest.mark.asyncio(loop_scope="session")
async def test_derived_cancelled_is_cancelled(client, db_session):
    token = await _admin_token(client, db_session, "bk_ds2_adm")
    venue = await _make_venue(db_session, "DS2 Venue")
    resp = await _make_booking(client, token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp2.json()["derived_status"] == "cancelled"


@pytest.mark.asyncio(loop_scope="session")
async def test_derived_status_in_list(client, db_session):
    token = await _admin_token(client, db_session, "bk_ds3_adm")
    venue = await _make_venue(db_session, "DS3 Venue")
    future = datetime.datetime(2030, 1, 1, 9, 0)
    await _make_booking(
        client, token, venue.id, title="Future BK",
        start_time=future.isoformat(),
        end_time=(future + TWO_H).isoformat(),
    )
    resp = await client.get("/api/v1/bookings", headers=auth_headers(token))
    items = [b for b in resp.json()["items"] if b["title"] == "Future BK"]
    assert len(items) == 1
    assert items[0]["derived_status"] == "approved"


# ===================================================================
# 10. Audit Logging Tests (3)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_create(client, db_session):
    admin = await create_test_user(db_session, username="bk_al1_adm", password="pw1234", role="admin")
    token = await login_user(client, "bk_al1_adm", "pw1234")
    venue = await _make_venue(db_session, "AL1 Venue")
    resp = await _make_booking(client, token, venue.id, title="Audit Create BK")
    bid = resp.json()["id"]
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "booking",
            AuditLog.entity_id == bid,
            AuditLog.action == "create",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.actor_id == admin.id
    changes = json.loads(entry.changes)
    assert changes["title"] == "Audit Create BK"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_cancel(client, db_session):
    token = await _admin_token(client, db_session, "bk_al2_adm")
    venue = await _make_venue(db_session, "AL2 Venue")
    resp = await _make_booking(client, token, venue.id)
    bid = resp.json()["id"]
    await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "booking",
            AuditLog.entity_id == bid,
            AuditLog.action == "cancel",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["old_status"] == "approved"
    assert changes["new_status"] == "cancelled"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_update(client, db_session):
    token = await _admin_token(client, db_session, "bk_al3_adm")
    venue = await _make_venue(db_session, "AL3 Venue")
    resp = await _make_booking(client, token, venue.id, title="Audit Upd BK")
    bid = resp.json()["id"]
    await client.put(
        f"/api/v1/bookings/{bid}",
        json={"title": "Updated Audit BK"},
        headers=auth_headers(token),
    )
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "booking",
            AuditLog.entity_id == bid,
            AuditLog.action == "update",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["title"] == "Updated Audit BK"


# ===================================================================
# 11. client_ref Idempotency (1)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_client_ref_idempotent(client, db_session):
    token = await _admin_token(client, db_session, "bk_ref_adm")
    venue = await _make_venue(db_session, "Ref Venue")
    ref = "xr-session-abc"
    resp1 = await _make_booking(client, token, venue.id, title="First", client_ref=ref)
    assert resp1.status_code == 201
    bid1 = resp1.json()["id"]
    resp2 = await _make_booking(client, token, venue.id, title="Second", client_ref=ref)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == bid1


# ===================================================================
# 12. Pagination and Filtering (2)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_pagination(client, db_session):
    token = await _admin_token(client, db_session, "bk_pg_adm")
    venue = await _make_venue(db_session, "PG Venue")
    for i in range(5):
        await _make_booking(
            client, token, venue.id, title=f"PG BK {i}",
            start_time=(NOW + datetime.timedelta(hours=i * 3)).isoformat(),
            end_time=(NOW + datetime.timedelta(hours=i * 3 + 2)).isoformat(),
        )
    resp = await client.get(
        "/api/v1/bookings?limit=2&offset=0",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2
    assert resp.json()["total"] >= 5


@pytest.mark.asyncio(loop_scope="session")
async def test_filter_by_venue(client, db_session):
    token = await _admin_token(client, db_session, "bk_fv_adm")
    v1 = await _make_venue(db_session, "FV1")
    v2 = await _make_venue(db_session, "FV2")
    await _make_booking(client, token, v1.id, title="V1 BK")
    await _make_booking(
        client, token, v2.id, title="V2 BK",
        start_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=5)).isoformat(),
    )
    resp = await client.get(
        f"/api/v1/bookings?venue_id={v1.id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["items"]]
    assert "V1 BK" in titles
    assert "V2 BK" not in titles


# ===================================================================
# 13. 404 Paths (3)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_get_404(client, db_session):
    token = await _admin_token(client, db_session, "bk_404g_adm")
    resp = await client.get("/api/v1/bookings/99999", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_404(client, db_session):
    token = await _admin_token(client, db_session, "bk_404c_adm")
    resp = await client.post("/api/v1/bookings/99999/cancel", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_update_404(client, db_session):
    token = await _admin_token(client, db_session, "bk_404u_adm")
    resp = await client.put(
        "/api/v1/bookings/99999",
        json={"title": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ===================================================================
# 14. Regression Smoke (3)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_health_ok(client, db_session):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_venues_still_ok(client, db_session):
    token = await _admin_token(client, db_session, "bk_smoke_adm")
    resp = await client.get("/api/v1/venues", headers=auth_headers(token))
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_still_ok(client, db_session):
    token = await _admin_token(client, db_session, "bk_smoke_adm2")
    resp = await client.get("/api/v1/equipment", headers=auth_headers(token))
    assert resp.status_code == 200
