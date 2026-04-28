"""Tests for Phase 3 PR5: Resource Utilization Statistics.

TDD RED phase — all tests written before implementation.

Covers:
  1. Metric definitions (venue utilization, equipment usage, peak hours)
  2. Cross-day / cross-window clipping
  3. Cancelled booking exclusion
  4. Maintenance / inactive resource handling
  5. Zero available hours
  6. Permission boundaries (admin, fm, teacher, student)
  7. Query window validation and performance guardrails
  8. Regression smoke tests
"""
import datetime

import pytest
from sqlalchemy import select

from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.models.venue_availability import VenueAvailability
from app.models.venue_blackout import VenueBlackout
from app.services.stats_service import StatsService, _available_hours_in_window
from tests.helpers import (
    auth_headers,
    create_test_booking,
    create_test_equipment,
    create_test_user,
    create_test_venue,
    login_user,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

MON = datetime.date(2026, 4, 20)   # Monday
SUN = datetime.date(2026, 4, 26)   # Sunday


async def _admin_token(client, db, username="stat_adm"):
    await create_test_user(db, username=username, password="pw1234", role="admin")
    return await login_user(client, username, "pw1234")


async def _fm_token(client, db, username="stat_fm"):
    await create_test_user(db, username=username, password="pw1234", role="facility_manager")
    return await login_user(client, username, "pw1234")


async def _teacher_token(client, db, username="stat_tch"):
    await create_test_user(db, username=username, password="pw1234", role="teacher")
    return await login_user(client, username, "pw1234")


async def _student_token(client, db, username="stat_stu"):
    await create_test_user(db, username=username, password="pw1234", role="student")
    return await login_user(client, username, "pw1234")


async def _make_user(db, username="stat_user", role="admin"):
    return await create_test_user(db, username=username, password="pw1234", role=role)


# ===================================================================
# 1. Denominator Helper — _available_hours_in_window (6)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_avail_hours_no_slots_no_blackout(db_session):
    """No VenueAvailability rows → assume 24 h/day."""
    venue = await create_test_venue(db_session, name="DenomV1")
    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=MON,
        end_date=SUN,
        availability_slots=[],
        blackout_dates=[],
    )
    assert hours == 168.0  # 7 × 24


@pytest.mark.asyncio(loop_scope="session")
async def test_avail_hours_with_blackout(db_session):
    """Blackout dates fully deducted from available hours."""
    venue = await create_test_venue(db_session, name="DenomV2")
    # Blackout Wed-Fri (Apr 22-24 = 3 days)
    bo = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 22),
        end_date=datetime.date(2026, 4, 24),
    )
    db_session.add(bo)
    await db_session.flush()

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=MON,
        end_date=SUN,
        availability_slots=[],
        blackout_dates=[bo],
    )
    assert hours == 96.0  # (7-3) × 24


@pytest.mark.asyncio(loop_scope="session")
async def test_avail_hours_with_availability_slots(db_session):
    """VenueAvailability defines per-day_of_week operating hours."""
    venue = await create_test_venue(db_session, name="DenomV3")
    # Mon-Fri 08:00-18:00 = 10 h/day
    for dow in range(5):
        db_session.add(VenueAvailability(
            venue_id=venue.id,
            day_of_week=dow,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(18, 0),
        ))
    await db_session.flush()

    slots = list((await db_session.execute(
        select(VenueAvailability).where(VenueAvailability.venue_id == venue.id)
    )).scalars().all())

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=MON,
        end_date=SUN,
        availability_slots=slots,
        blackout_dates=[],
    )
    # Apr 20-26: Mon-Fri (5 days) × 10h = 50h, Sat+Sun no slots → 0h
    assert hours == 50.0


@pytest.mark.asyncio(loop_scope="session")
async def test_avail_hours_all_blacked_out(db_session):
    """Entire window blacked out → 0 available hours."""
    venue = await create_test_venue(db_session, name="DenomV4")
    bo = VenueBlackout(venue_id=venue.id, start_date=MON, end_date=SUN)
    db_session.add(bo)
    await db_session.flush()

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=MON,
        end_date=SUN,
        availability_slots=[],
        blackout_dates=[bo],
    )
    assert hours == 0.0


@pytest.mark.asyncio(loop_scope="session")
async def test_avail_hours_blackout_partial_overlap(db_session):
    """Blackout extends beyond window — only overlapping days deducted."""
    venue = await create_test_venue(db_session, name="DenomV5")
    # Blackout Apr 25-28 (Sat-Tue), window is Mon-Sun → overlap = Sat+Sun
    bo = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 25),
        end_date=datetime.date(2026, 4, 28),
    )
    db_session.add(bo)
    await db_session.flush()

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=MON,
        end_date=SUN,
        availability_slots=[],
        blackout_dates=[bo],
    )
    # 7 days - 2 overlapping (25, 26) = 5 × 24 = 120
    assert hours == 120.0


@pytest.mark.asyncio(loop_scope="session")
async def test_avail_hours_multiple_blackouts(db_session):
    """Two separate blackout periods are both deducted."""
    venue = await create_test_venue(db_session, name="DenomV6")
    bo1 = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 21),
    )
    bo2 = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 24),
        end_date=datetime.date(2026, 4, 25),
    )
    db_session.add_all([bo1, bo2])
    await db_session.flush()

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=MON,
        end_date=SUN,
        availability_slots=[],
        blackout_dates=[bo1, bo2],
    )
    # 7 days - 2 - 2 = 3 × 24 = 72
    assert hours == 72.0


# ===================================================================
# 2. Venue Utilization (8)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_basic(db_session):
    """2 approved bookings, 1 day window, no availability constraints."""
    user = await _make_user(db_session, "vu_adm1")
    venue = await create_test_venue(db_session, name="VU Venue")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base + datetime.timedelta(hours=4),
        end_time=base + datetime.timedelta(hours=6),
    )

    svc = StatsService(db_session)
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["booked_hours"] == 4.0
    assert item["available_hours"] == 24.0
    assert abs(item["utilization_rate"] - 4.0 / 24.0) < 0.001
    assert item["booking_count"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_excludes_cancelled(db_session):
    """Cancelled bookings do not count toward booked_hours."""
    user = await _make_user(db_session, "vu_cxl")
    venue = await create_test_venue(db_session, name="VU CXL")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
        status="approved",
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base + datetime.timedelta(hours=4),
        end_time=base + datetime.timedelta(hours=6),
        status="cancelled",
    )

    svc = StatsService(db_session)
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["booked_hours"] == 2.0
    assert item["booking_count"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_excludes_maintenance(db_session):
    """Venues with status != 'active' are excluded from results."""
    await create_test_venue(db_session, name="ActiveV", status="active")
    await create_test_venue(db_session, name="MaintV", status="maintenance")
    await create_test_venue(db_session, name="InactiveV", status="inactive")

    svc = StatsService(db_session)
    result = await svc.venue_utilization(start_date=MON, end_date=SUN)
    names = {r["venue_name"] for r in result}
    assert "ActiveV" in names
    assert "MaintV" not in names
    assert "InactiveV" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_zero_available_hours(db_session):
    """All days blacked out → rate=None, available_hours=0."""
    user = await _make_user(db_session, "vu_zero")
    venue = await create_test_venue(db_session, name="ZeroV")
    db_session.add(VenueBlackout(venue_id=venue.id, start_date=MON, end_date=SUN))
    await db_session.flush()

    svc = StatsService(db_session)
    result = await svc.venue_utilization(start_date=MON, end_date=SUN)
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["available_hours"] == 0.0
    assert item["utilization_rate"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_clips_to_window(db_session):
    """Booking extending beyond window is clipped to window boundaries."""
    user = await _make_user(db_session, "vu_clip")
    venue = await create_test_venue(db_session, name="ClipV")

    # Booking spans Apr 20 22:00 → Apr 22 10:00 (36h total)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=datetime.datetime(2026, 4, 20, 22, 0),
        end_time=datetime.datetime(2026, 4, 22, 10, 0),
    )

    svc = StatsService(db_session)
    # Window: Apr 21 only → clipped to 24h
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["booked_hours"] == 24.0


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_cross_window_booking(db_session):
    """Booking spanning the full window counts only the window portion."""
    user = await _make_user(db_session, "vu_cross")
    venue = await create_test_venue(db_session, name="CrossV")

    # Booking spans Apr 19 → Apr 27 (8 days = 192h)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=datetime.datetime(2026, 4, 19, 0, 0),
        end_time=datetime.datetime(2026, 4, 27, 0, 0),
    )

    svc = StatsService(db_session)
    # Window: Apr 20-26 (7 days = 168h)
    result = await svc.venue_utilization(start_date=MON, end_date=SUN)
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["booked_hours"] == 168.0


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_no_bookings(db_session):
    """Active venue with zero bookings → booked_hours=0, rate=0."""
    await create_test_venue(db_session, name="EmptyV")

    svc = StatsService(db_session)
    result = await svc.venue_utilization(start_date=MON, end_date=SUN)
    item = next(r for r in result if r["venue_name"] == "EmptyV")
    assert item["booked_hours"] == 0.0
    assert item["utilization_rate"] == 0.0
    assert item["booking_count"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_util_with_availability_slots(db_session):
    """Venue with VenueAvailability: denominator uses slot hours, not 24h."""
    user = await _make_user(db_session, "vu_avail")
    venue = await create_test_venue(db_session, name="AvailV")

    # Mon-Fri 08:00-18:00 = 10h/day
    for dow in range(5):
        db_session.add(VenueAvailability(
            venue_id=venue.id, day_of_week=dow,
            start_time=datetime.time(8, 0), end_time=datetime.time(18, 0),
        ))
    await db_session.flush()

    # One 3h booking on Monday Apr 20
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=datetime.datetime(2026, 4, 20, 9, 0),
        end_time=datetime.datetime(2026, 4, 20, 12, 0),
    )

    svc = StatsService(db_session)
    result = await svc.venue_utilization(start_date=MON, end_date=SUN)
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["booked_hours"] == 3.0
    assert item["available_hours"] == 50.0  # 5 weekdays × 10h
    assert abs(item["utilization_rate"] - 3.0 / 50.0) < 0.001


# ===================================================================
# 3. Equipment Usage (6)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_equip_usage_basic(db_session):
    """Equipment in 2 approved bookings → count=2, hours summed."""
    user = await _make_user(db_session, "eu_adm1")
    venue = await create_test_venue(db_session, name="EU Venue")
    equip = await create_test_equipment(db_session, name="Projector", category="AV")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
        equipment_ids=[equip.id],
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base + datetime.timedelta(hours=4),
        end_time=base + datetime.timedelta(hours=6),
        equipment_ids=[equip.id],
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["equipment_id"] == equip.id)
    assert item["booking_count"] == 2
    assert item["total_hours"] == 4.0


@pytest.mark.asyncio(loop_scope="session")
async def test_equip_usage_excludes_cancelled(db_session):
    """Cancelled booking does not count for equipment."""
    user = await _make_user(db_session, "eu_cxl")
    venue = await create_test_venue(db_session, name="EU CXL")
    equip = await create_test_equipment(db_session, name="Camera")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
        equipment_ids=[equip.id], status="approved",
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base + datetime.timedelta(hours=3),
        end_time=base + datetime.timedelta(hours=5),
        equipment_ids=[equip.id], status="cancelled",
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["equipment_id"] == equip.id)
    assert item["booking_count"] == 1
    assert item["total_hours"] == 2.0


@pytest.mark.asyncio(loop_scope="session")
async def test_equip_usage_no_bookings(db_session):
    """Equipment with no bookings → count=0, hours=0."""
    await create_test_equipment(db_session, name="Unused Dev")

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    item = next(r for r in result if r["equipment_name"] == "Unused Dev")
    assert item["booking_count"] == 0
    assert item["total_hours"] == 0.0


@pytest.mark.asyncio(loop_scope="session")
async def test_equip_usage_multi_equipment_booking(db_session):
    """One booking with 2 equipments → each equipment gets count=1."""
    user = await _make_user(db_session, "eu_multi")
    venue = await create_test_venue(db_session, name="MultiEqV")
    e1 = await create_test_equipment(db_session, name="DevA")
    e2 = await create_test_equipment(db_session, name="DevB")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=3),
        equipment_ids=[e1.id, e2.id],
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item_a = next(r for r in result if r["equipment_id"] == e1.id)
    item_b = next(r for r in result if r["equipment_id"] == e2.id)
    assert item_a["booking_count"] == 1
    assert item_b["booking_count"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_equip_usage_clips_to_window(db_session):
    """Equipment booking extending beyond window is clipped."""
    user = await _make_user(db_session, "eu_clip")
    venue = await create_test_venue(db_session, name="ClipEqV")
    equip = await create_test_equipment(db_session, name="LongDev")

    # Booking spans 2 days, window is 1 day
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=datetime.datetime(2026, 4, 20, 22, 0),
        end_time=datetime.datetime(2026, 4, 22, 10, 0),
        equipment_ids=[equip.id],
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["equipment_id"] == equip.id)
    assert item["total_hours"] == 24.0  # Full day clipped


@pytest.mark.asyncio(loop_scope="session")
async def test_equip_usage_includes_inactive_equipment(db_session):
    """Equipment usage shows all equipment regardless of status."""
    user = await _make_user(db_session, "eu_status")
    venue = await create_test_venue(db_session, name="StatusEqV")
    e_active = await create_test_equipment(db_session, name="ActEq", status="active")
    e_maint = await create_test_equipment(db_session, name="MaintEq", status="maintenance")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
        equipment_ids=[e_active.id, e_maint.id],
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    ids = {r["equipment_id"] for r in result}
    assert e_active.id in ids
    assert e_maint.id in ids


# ===================================================================
# 4. Peak Hours (4)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_basic(db_session):
    """Bookings grouped by start_time hour."""
    user = await _make_user(db_session, "ph_adm1")
    venue = await create_test_venue(db_session, name="PH Venue")

    day = datetime.datetime(2026, 4, 21)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=day.replace(hour=9), end_time=day.replace(hour=11),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=day.replace(hour=14), end_time=day.replace(hour=16),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=day.replace(hour=14, minute=30),
        end_time=day.replace(hour=15, minute=30),
    )

    svc = StatsService(db_session)
    result = await svc.peak_hours(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    hour_map = {h["hour"]: h["booking_count"] for h in result}
    assert hour_map.get(9, 0) == 1
    assert hour_map.get(14, 0) == 2
    assert hour_map.get(22, 0) == 0  # No bookings at 22:00


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_excludes_cancelled(db_session):
    """Cancelled bookings not counted."""
    user = await _make_user(db_session, "ph_cxl")
    venue = await create_test_venue(db_session, name="PH CXL")

    day = datetime.datetime(2026, 4, 21)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=day.replace(hour=10), end_time=day.replace(hour=12),
        status="approved",
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=day.replace(hour=14), end_time=day.replace(hour=16),
        status="cancelled",
    )

    svc = StatsService(db_session)
    result = await svc.peak_hours(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    hour_map = {h["hour"]: h["booking_count"] for h in result}
    assert hour_map.get(10, 0) == 1
    assert 14 not in hour_map


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_no_bookings(db_session):
    """No bookings → empty list."""
    svc = StatsService(db_session)
    result = await svc.peak_hours(start_date=MON, end_date=SUN)
    assert result == []


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_multi_day(db_session):
    """Peak hours aggregates across multiple days."""
    user = await _make_user(db_session, "ph_multi")
    venue = await create_test_venue(db_session, name="PH Multi")

    # 1 booking on Monday at 9h, 2 bookings on Wednesday at 9h
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=datetime.datetime(2026, 4, 20, 9, 0),
        end_time=datetime.datetime(2026, 4, 20, 11, 0),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=datetime.datetime(2026, 4, 22, 9, 0),
        end_time=datetime.datetime(2026, 4, 22, 11, 0),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=datetime.datetime(2026, 4, 22, 9, 30),
        end_time=datetime.datetime(2026, 4, 22, 10, 30),
    )

    svc = StatsService(db_session)
    result = await svc.peak_hours(start_date=MON, end_date=SUN)
    hour_map = {h["hour"]: h["booking_count"] for h in result}
    assert hour_map.get(9, 0) == 3  # 1 + 2 at hour 9


# ===================================================================
# 5. Router — Permissions (6)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_r_venue_stats_admin_ok(client, db_session):
    """Admin can access venue utilization."""
    token = await _admin_token(client, db_session, "rs_adm1")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "window" in data
    assert "items" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_r_venue_stats_fm_ok(client, db_session):
    """Facility manager can access venue utilization."""
    token = await _fm_token(client, db_session, "rs_fm1")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_r_venue_stats_teacher_forbidden(client, db_session):
    """Teacher cannot access stats → 403."""
    token = await _teacher_token(client, db_session, "rs_tch1")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_r_venue_stats_student_forbidden(client, db_session):
    """Student cannot access stats → 403."""
    token = await _student_token(client, db_session, "rs_stu1")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_r_equipment_usage_ok(client, db_session):
    """Equipment usage endpoint returns correct shape."""
    token = await _admin_token(client, db_session, "rs_eq1")
    resp = await client.get(
        "/api/v1/stats/equipment-usage",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_r_peak_hours_ok(client, db_session):
    """Peak hours endpoint returns correct shape."""
    token = await _admin_token(client, db_session, "rs_pk1")
    resp = await client.get(
        "/api/v1/stats/peak-hours",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert "hours" in resp.json()


# ===================================================================
# 6. Router — Validation & Performance Guardrails (5)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_r_rejects_window_over_90_days(client, db_session):
    """Query window > 90 days → 400."""
    token = await _admin_token(client, db_session, "rs_w90")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-01-01", "end_date": "2026-04-30"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_r_rejects_inverted_dates(client, db_session):
    """start_date > end_date → 400."""
    token = await _admin_token(client, db_session, "rs_inv")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-26", "end_date": "2026-04-20"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_r_default_window(client, db_session):
    """No dates provided → defaults to last 7 days."""
    token = await _admin_token(client, db_session, "rs_def")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["window"]["start_date"] is not None
    assert data["window"]["end_date"] is not None
    # Verify window is 7 days
    sd = datetime.date.fromisoformat(data["window"]["start_date"])
    ed = datetime.date.fromisoformat(data["window"]["end_date"])
    assert (ed - sd).days == 6


@pytest.mark.asyncio(loop_scope="session")
async def test_r_limit_param(client, db_session):
    """Limit parameter caps the number of returned resources."""
    # Create more than 2 venues
    for i in range(5):
        await create_test_venue(db_session, name=f"LimitV{i}", status="active")

    token = await _admin_token(client, db_session, "rs_lim")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26", "limit": 2},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2


@pytest.mark.asyncio(loop_scope="session")
async def test_r_rejects_limit_over_100(client, db_session):
    """Limit > 100 is capped or rejected."""
    token = await _admin_token(client, db_session, "rs_biglim")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26", "limit": 500},
        headers=auth_headers(token),
    )
    # Should either accept (capped to 100) or reject
    assert resp.status_code in (200, 422)


# ===================================================================
# 7. Integration — End-to-End Stats Flow (3)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_r_venue_utilization_with_data(client, db_session):
    """Full flow: create bookings → query stats → verify numbers."""
    user = await _make_user(db_session, "e2e_adm")
    venue = await create_test_venue(db_session, name="E2E Venue")

    # 2 bookings on Apr 21, each 2h
    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base + datetime.timedelta(hours=4),
        end_time=base + datetime.timedelta(hours=6),
    )

    token = await login_user(client, "e2e_adm", "pw1234")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-21", "end_date": "2026-04-21"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    item = next(i for i in items if i["venue_id"] == venue.id)
    assert item["booked_hours"] == 4.0
    assert item["booking_count"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_r_equipment_usage_with_data(client, db_session):
    """Full flow: create bookings with equipment → query stats."""
    user = await _make_user(db_session, "e2e_eq")
    venue = await create_test_venue(db_session, name="E2E EqV")
    equip = await create_test_equipment(db_session, name="E2E Dev", category="AV")

    base = datetime.datetime(2026, 4, 21, 10, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=base, end_time=base + datetime.timedelta(hours=3),
        equipment_ids=[equip.id],
    )

    token = await login_user(client, "e2e_eq", "pw1234")
    resp = await client.get(
        "/api/v1/stats/equipment-usage",
        params={"start_date": "2026-04-21", "end_date": "2026-04-21"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["equipment_id"] == equip.id)
    assert item["booking_count"] == 1
    assert item["total_hours"] == 3.0


@pytest.mark.asyncio(loop_scope="session")
async def test_r_peak_hours_with_data(client, db_session):
    """Full flow: create bookings → peak hours returns hourly distribution."""
    user = await _make_user(db_session, "e2e_pk")
    venue = await create_test_venue(db_session, name="E2E PKV")

    day = datetime.datetime(2026, 4, 21)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=day.replace(hour=9), end_time=day.replace(hour=11),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=user.id,
        start_time=day.replace(hour=9, minute=30),
        end_time=day.replace(hour=10, minute=30),
    )

    token = await login_user(client, "e2e_pk", "pw1234")
    resp = await client.get(
        "/api/v1/stats/peak-hours",
        params={"start_date": "2026-04-21", "end_date": "2026-04-21"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    hours = resp.json()["hours"]
    hour_map = {h["hour"]: h["booking_count"] for h in hours}
    assert hour_map.get(9, 0) == 2


# ===================================================================
# 8. Regression Smoke Tests (3)
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_health_still_ok(client, db_session):
    """Health endpoint still works after adding stats routes."""
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_venues_still_ok(client, db_session):
    """Venue list endpoint not broken by stats routes."""
    token = await _admin_token(client, db_session, "rs_ven")
    resp = await client.get("/api/v1/venues", headers=auth_headers(token))
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_bookings_still_ok(client, db_session):
    """Booking list endpoint not broken by stats routes."""
    token = await _admin_token(client, db_session, "rs_bk")
    resp = await client.get("/api/v1/bookings", headers=auth_headers(token))
    assert resp.status_code in (200, 404)  # 404 if no route prefix match
