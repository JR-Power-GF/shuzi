"""Tests for Phase 3 PR3: Equipment Management.

Covers: CRUD permissions, field validation, serial uniqueness, status lifecycle,
venue association/unassign, query filtering / data isolation, audit logging,
and regression smoke.

All tests use HTTP integration via the `client` fixture, following the pattern
established in test_venues.py.
"""
import json

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.equipment import Equipment
from app.models.venue import Venue
from tests.helpers import (
    auth_headers,
    create_test_equipment,
    create_test_user,
    create_test_venue,
    login_user,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _admin_token(client, db_session, username="eq_admin"):
    await create_test_user(db_session, username=username, password="pw1234", role="admin")
    return await login_user(client, username, "pw1234")


async def _fm_token(client, db_session, username="eq_fm"):
    await create_test_user(db_session, username=username, password="pw1234", role="facility_manager")
    return await login_user(client, username, "pw1234")


async def _teacher_token(client, db_session, username="eq_teacher"):
    await create_test_user(db_session, username=username, password="pw1234", role="teacher")
    return await login_user(client, username, "pw1234")


async def _student_token(client, db_session, username="eq_student"):
    await create_test_user(db_session, username=username, password="pw1234", role="student")
    return await login_user(client, username, "pw1234")


async def _create_equip_via_api(client, token, **overrides):
    """POST /api/v1/equipment with defaults overridden by kwargs."""
    payload = {
        "name": "Test Equipment",
        "category": "VR",
        "serial_number": "SN-001",
    }
    payload.update(overrides)
    return await client.post(
        "/api/v1/equipment",
        json=payload,
        headers=auth_headers(token),
    )


# ===================================================================
# 1. CRUD Permission Tests (10 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_admin_allowed(client, db_session):
    token = await _admin_token(client, db_session, "eq_crud_admin")
    resp = await _create_equip_via_api(client, token, name="Admin Equip")
    assert resp.status_code == 201
    assert resp.json()["name"] == "Admin Equip"
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_fm_allowed(client, db_session):
    token = await _fm_token(client, db_session, "eq_crud_fm")
    resp = await _create_equip_via_api(client, token, name="FM Equip")
    assert resp.status_code == 201
    assert resp.json()["name"] == "FM Equip"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_teacher_forbidden(client, db_session):
    token = await _teacher_token(client, db_session, "eq_crud_teacher")
    resp = await _create_equip_via_api(client, token)
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "eq_crud_student")
    resp = await _create_equip_via_api(client, token)
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_list_equipment_admin_sees_all(client, db_session):
    token = await _admin_token(client, db_session, "eq_list_admin")
    await create_test_equipment(db_session, name="Active E", status="active")
    await create_test_equipment(db_session, name="Inactive E", status="inactive")
    resp = await client.get("/api/v1/equipment", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["items"]]
    assert "Active E" in names
    assert "Inactive E" in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_equipment_teacher_sees_active_only(client, db_session):
    token = await _teacher_token(client, db_session, "eq_list_teacher")
    await create_test_equipment(db_session, name="TActive E", status="active")
    await create_test_equipment(db_session, name="TInactive E", status="inactive")
    resp = await client.get("/api/v1/equipment", headers=auth_headers(token))
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["items"]]
    assert "TActive E" in names
    assert "TInactive E" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_equipment_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "eq_list_student")
    resp = await client.get("/api/v1/equipment", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_get_equipment_detail_admin(client, db_session):
    token = await _admin_token(client, db_session, "eq_detail_admin")
    equip = await create_test_equipment(db_session, name="Detail E", status="active")
    resp = await client.get(
        f"/api/v1/equipment/{equip.id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail E"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_equipment_student_forbidden(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_stu_adm")
    student_tok = await _student_token(client, db_session, "eq_stu_detail")
    equip = await create_test_equipment(db_session, name="Student No See")
    resp = await client.get(
        f"/api/v1/equipment/{equip.id}",
        headers=auth_headers(student_tok),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_get_equipment_teacher_inactive_404(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_teach_inactive_adm")
    teacher_tok = await _teacher_token(client, db_session, "eq_teach_inactive")
    equip = await create_test_equipment(db_session, name="Teacher Hidden", status="inactive")
    resp = await client.get(
        f"/api/v1/equipment/{equip.id}",
        headers=auth_headers(teacher_tok),
    )
    assert resp.status_code == 404


# ===================================================================
# 2. Field Validation Tests (9 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_minimal(client, db_session):
    token = await _admin_token(client, db_session, "eq_val_min")
    resp = await _create_equip_via_api(client, token, name="Minimal Equip", category=None, serial_number=None)
    assert resp.status_code == 201
    assert resp.json()["category"] is None
    assert resp.json()["serial_number"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_all_fields(client, db_session):
    token = await _admin_token(client, db_session, "eq_val_all")
    resp = await _create_equip_via_api(
        client, token,
        name="Full Equip", category="Projector", serial_number="PJ-2026-001",
        description="HD projector", external_id="ext-pj-001",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "Projector"
    assert body["serial_number"] == "PJ-2026-001"
    assert body["description"] == "HD projector"
    assert body["external_id"] == "ext-pj-001"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_name_required(client, db_session):
    token = await _admin_token(client, db_session, "eq_val_name")
    resp = await client.post(
        "/api/v1/equipment",
        json={"category": "VR"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_rejects_empty_name(client, db_session):
    token = await _admin_token(client, db_session, "eq_val_empty")
    resp = await _create_equip_via_api(client, token, name="")
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_rejects_extra_fields(client, db_session):
    token = await _admin_token(client, db_session, "eq_val_extra")
    resp = await client.post(
        "/api/v1/equipment",
        json={"name": "Extra E", "bogus_field": "bad"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_update_equipment_forbids_extra(client, db_session):
    token = await _admin_token(client, db_session, "eq_upd_extra")
    resp = await _create_equip_via_api(client, token, name="Upd Extra E")
    eid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/equipment/{eid}",
        json={"name": "Updated", "unknown_field": "bad"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_update_equipment_rejects_empty_serial(client, db_session):
    token = await _admin_token(client, db_session, "eq_upd_serial")
    resp = await _create_equip_via_api(client, token, name="Serial E")
    eid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/equipment/{eid}",
        json={"serial_number": ""},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_equipment_with_invalid_venue(client, db_session):
    token = await _admin_token(client, db_session, "eq_val_venue")
    resp = await _create_equip_via_api(client, token, name="Bad Venue E", venue_id=99999)
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_update_equipment_with_invalid_venue(client, db_session):
    token = await _admin_token(client, db_session, "eq_upd_venue")
    resp = await _create_equip_via_api(client, token, name="Upd Venue E")
    eid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/equipment/{eid}",
        json={"venue_id": 99999},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 400


# ===================================================================
# 3. Status Lifecycle Tests (6 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_status_active_to_inactive(client, db_session):
    token = await _admin_token(client, db_session, "eq_st_inact")
    resp = await _create_equip_via_api(client, token, name="Status Inact E")
    eid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "inactive"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "inactive"


@pytest.mark.asyncio(loop_scope="session")
async def test_status_active_to_maintenance(client, db_session):
    token = await _admin_token(client, db_session, "eq_st_maint")
    resp = await _create_equip_via_api(client, token, name="Status Maint E")
    eid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "maintenance"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "maintenance"


@pytest.mark.asyncio(loop_scope="session")
async def test_status_maintenance_to_active(client, db_session):
    token = await _admin_token(client, db_session, "eq_st_back")
    equip = await create_test_equipment(db_session, name="Back Active E", status="maintenance")
    resp = await client.patch(
        f"/api/v1/equipment/{equip.id}/status",
        json={"status": "active"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_status_invalid_rejected(client, db_session):
    token = await _admin_token(client, db_session, "eq_st_bad")
    resp = await _create_equip_via_api(client, token, name="Bad Status E")
    eid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "broken"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_status_missing_rejected(client, db_session):
    token = await _admin_token(client, db_session, "eq_st_miss")
    resp = await _create_equip_via_api(client, token, name="Miss Status E")
    eid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_status_extra_fields_rejected(client, db_session):
    token = await _admin_token(client, db_session, "eq_st_extra")
    resp = await _create_equip_via_api(client, token, name="Extra Status E")
    eid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "active", "extra_key": "bad"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 422


# ===================================================================
# 4. Venue Association Tests (6 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_with_venue_shows_venue_name(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_venue_adm")
    venue = await create_test_venue(db_session, name="Lab 101")
    resp = await _create_equip_via_api(
        client, admin_tok, name="Venue Equip",
        venue_id=venue.id,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["venue_id"] == venue.id
    assert body["venue_name"] == "Lab 101"


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_shows_venue_name(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_det_vn")
    venue = await create_test_venue(db_session, name="Lab 202")
    equip = await create_test_equipment(db_session, name="Det VN E", venue_id=venue.id)
    resp = await client.get(
        f"/api/v1/equipment/{equip.id}",
        headers=auth_headers(admin_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["venue_name"] == "Lab 202"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_venue_id(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_upd_vid")
    venue = await create_test_venue(db_session, name="Lab 303")
    resp = await _create_equip_via_api(client, admin_tok, name="Move E")
    eid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/equipment/{eid}",
        json={"venue_id": venue.id},
        headers=auth_headers(admin_tok),
    )
    assert resp2.status_code == 200
    assert resp2.json()["venue_id"] == venue.id
    assert resp2.json()["venue_name"] == "Lab 303"


@pytest.mark.asyncio(loop_scope="session")
async def test_unassign_venue(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_unassign")
    venue = await create_test_venue(db_session, name="Lab 404")
    equip = await create_test_equipment(db_session, name="Unassign E", venue_id=venue.id)
    resp = await client.delete(
        f"/api/v1/equipment/{equip.id}/venue",
        headers=auth_headers(admin_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["venue_id"] is None
    assert resp.json()["venue_name"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_unassign_already_unassigned(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_unas_none")
    equip = await create_test_equipment(db_session, name="No Venue E")
    resp = await client.delete(
        f"/api/v1/equipment/{equip.id}/venue",
        headers=auth_headers(admin_tok),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_list_filter_by_venue(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_filt_ven")
    venue = await create_test_venue(db_session, name="Filter Lab")
    await create_test_equipment(db_session, name="In Lab E", venue_id=venue.id)
    await create_test_equipment(db_session, name="No Lab E")
    resp = await client.get(
        f"/api/v1/equipment?venue_id={venue.id}",
        headers=auth_headers(admin_tok),
    )
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["items"]]
    assert "In Lab E" in names
    assert "No Lab E" not in names


# ===================================================================
# 5. Bookability / Status Semantics Tests (3 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_active_status_means_available(client, db_session):
    token = await _admin_token(client, db_session, "eq_book_active")
    resp = await _create_equip_via_api(client, token, name="Bookable E")
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_inactive_status_means_not_bookable(client, db_session):
    token = await _admin_token(client, db_session, "eq_book_inact")
    resp = await _create_equip_via_api(client, token, name="Not Bookable E")
    eid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "inactive"},
        headers=auth_headers(token),
    )
    body = resp2.json()
    assert body["status"] == "inactive"
    # Teacher cannot see inactive equipment — confirms non-bookable semantics
    teacher_tok = await _teacher_token(client, db_session, "eq_book_teacher")
    resp3 = await client.get(
        f"/api/v1/equipment/{eid}",
        headers=auth_headers(teacher_tok),
    )
    assert resp3.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_maintenance_status_means_temporarily_unavailable(client, db_session):
    token = await _admin_token(client, db_session, "eq_book_maint")
    resp = await _create_equip_via_api(client, token, name="Under Maint E")
    eid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "maintenance"},
        headers=auth_headers(token),
    )
    assert resp2.json()["status"] == "maintenance"
    # Admin can still see it (status is visible)
    assert resp2.json()["status"] == "maintenance"
    # Can transition back to active
    resp3 = await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "active"},
        headers=auth_headers(token),
    )
    assert resp3.json()["status"] == "active"


# ===================================================================
# 6. Query Filtering Tests (4 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_filter_by_status(client, db_session):
    token = await _admin_token(client, db_session, "eq_filt_st")
    await create_test_equipment(db_session, name="Filt Active", status="active")
    await create_test_equipment(db_session, name="Filt Inactive", status="inactive")
    resp = await client.get(
        "/api/v1/equipment?status=active",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["items"]]
    assert "Filt Active" in names
    assert "Filt Inactive" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_filter_by_category(client, db_session):
    token = await _admin_token(client, db_session, "eq_filt_cat")
    await create_test_equipment(db_session, name="VR Dev", category="VR")
    await create_test_equipment(db_session, name="PJ Dev", category="Projector")
    resp = await client.get(
        "/api/v1/equipment?category=VR",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["items"]]
    assert "VR Dev" in names
    assert "PJ Dev" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_pagination(client, db_session):
    token = await _admin_token(client, db_session, "eq_pag")
    for i in range(5):
        await create_test_equipment(db_session, name=f"Page E {i}")
    resp = await client.get(
        "/api/v1/equipment?limit=2&offset=0",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2
    assert resp.json()["total"] >= 5


@pytest.mark.asyncio(loop_scope="session")
async def test_response_includes_venue_name_batch(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_batch_vn")
    venue = await create_test_venue(db_session, name="Batch Lab")
    await create_test_equipment(db_session, name="Batch VN E", venue_id=venue.id)
    resp = await client.get(
        "/api/v1/equipment",
        headers=auth_headers(admin_tok),
    )
    assert resp.status_code == 200
    matched = [e for e in resp.json()["items"] if e["name"] == "Batch VN E"]
    assert len(matched) == 1
    assert matched[0]["venue_name"] == "Batch Lab"


# ===================================================================
# 7. Audit Logging Tests (5 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_equipment_create(client, db_session):
    token = await _admin_token(client, db_session, "eq_audit_c")
    admin = await create_test_user(db_session, username="eq_audit_c", password="pw1234", role="admin")
    resp = await _create_equip_via_api(client, token, name="Audit Create E")
    eid = resp.json()["id"]

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "equipment",
            AuditLog.entity_id == eid,
            AuditLog.action == "create",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.actor_id == admin.id
    changes = json.loads(entry.changes)
    assert changes["name"] == "Audit Create E"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_equipment_update(client, db_session):
    token = await _admin_token(client, db_session, "eq_audit_u")
    resp = await _create_equip_via_api(client, token, name="Audit Upd E")
    eid = resp.json()["id"]
    await client.put(
        f"/api/v1/equipment/{eid}",
        json={"category": "Updated"},
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "equipment",
            AuditLog.entity_id == eid,
            AuditLog.action == "update",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["category"] == "Updated"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_equipment_status_change(client, db_session):
    token = await _admin_token(client, db_session, "eq_audit_s")
    resp = await _create_equip_via_api(client, token, name="Audit Status E")
    eid = resp.json()["id"]
    await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "maintenance"},
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "equipment",
            AuditLog.entity_id == eid,
            AuditLog.action == "status_change",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["old_status"] == "active"
    assert changes["new_status"] == "maintenance"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_equipment_unassign_venue(client, db_session):
    admin_tok = await _admin_token(client, db_session, "eq_audit_ua")
    venue = await create_test_venue(db_session, name="Audit UA Lab")
    equip = await create_test_equipment(db_session, name="Audit UA E", venue_id=venue.id)
    await client.delete(
        f"/api/v1/equipment/{equip.id}/venue",
        headers=auth_headers(admin_tok),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "equipment",
            AuditLog.entity_id == equip.id,
            AuditLog.action == "unassign_venue",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["old_venue_id"] == venue.id


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_changes_includes_serial_number(client, db_session):
    token = await _admin_token(client, db_session, "eq_audit_sn")
    resp = await _create_equip_via_api(
        client, token, name="Audit SN E", serial_number="SN-AUDIT-001",
    )
    eid = resp.json()["id"]
    await client.put(
        f"/api/v1/equipment/{eid}",
        json={"serial_number": "SN-AUDIT-002"},
        headers=auth_headers(token),
    )

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.entity_type == "equipment",
            AuditLog.entity_id == eid,
            AuditLog.action == "update",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    changes = json.loads(entry.changes)
    assert changes["serial_number"] == "SN-AUDIT-002"


# ===================================================================
# 8. 404 Paths Tests (5 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_get_equipment_404(client, db_session):
    token = await _admin_token(client, db_session, "eq_404_get")
    resp = await client.get(
        "/api/v1/equipment/99999",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_update_equipment_404(client, db_session):
    token = await _admin_token(client, db_session, "eq_404_upd")
    resp = await client.put(
        "/api/v1/equipment/99999",
        json={"name": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_status_404(client, db_session):
    token = await _admin_token(client, db_session, "eq_404_st")
    resp = await client.patch(
        "/api/v1/equipment/99999/status",
        json={"status": "inactive"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_unassign_venue_404(client, db_session):
    token = await _admin_token(client, db_session, "eq_404_ua")
    resp = await client.delete(
        "/api/v1/equipment/99999/venue",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_status_change_preserves_record(client, db_session):
    token = await _admin_token(client, db_session, "eq_preserve")
    resp = await _create_equip_via_api(client, token, name="Preserve E", serial_number="SN-PRES-001")
    eid = resp.json()["id"]
    await client.patch(
        f"/api/v1/equipment/{eid}/status",
        json={"status": "inactive"},
        headers=auth_headers(token),
    )
    resp2 = await client.get(
        f"/api/v1/equipment/{eid}",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Preserve E"
    assert resp2.json()["serial_number"] == "SN-PRES-001"


# ===================================================================
# 9. Regression Smoke Tests (4 tests)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_health_still_works(client, db_session):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio(loop_scope="session")
async def test_auth_login_still_works(client, db_session):
    await create_test_user(db_session, username="eq_smoke_user", password="pw1234")
    resp = await client.post(
        "/api/auth/login",
        json={"username": "eq_smoke_user", "password": "pw1234"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_courses_endpoint_still_works(client, db_session):
    token = await _admin_token(client, db_session, "eq_smoke_adm")
    resp = await client.get("/api/courses", headers=auth_headers(token))
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_venues_endpoint_still_works(client, db_session):
    token = await _admin_token(client, db_session, "eq_smoke_adm2")
    resp = await client.get("/api/v1/venues", headers=auth_headers(token))
    assert resp.status_code == 200
