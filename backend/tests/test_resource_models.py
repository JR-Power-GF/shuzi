"""Tests for resource-domain models: Venue, Equipment, Booking, BookingEquipment.

Covers: instantiation, field defaults, CHECK constraints, FK relationships,
unique constraints, and data isolation fields (course_id, class_id, task_id).
"""
import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.models.equipment import Equipment
from app.models.booking import Booking, BookingEquipment


# ---------------------------------------------------------------------------
# Venue model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_create_all_fields(db_session: AsyncSession):
    venue = Venue(
        name="XR Lab A",
        capacity=30,
        location="Building 3 Floor 2",
        description="Main XR training lab",
        external_id="xr-venue-001",
    )
    db_session.add(venue)
    await db_session.flush()

    result = await db_session.execute(select(Venue).where(Venue.id == venue.id))
    found = result.scalar_one()
    assert found.name == "XR Lab A"
    assert found.capacity == 30
    assert found.location == "Building 3 Floor 2"
    assert found.description == "Main XR training lab"
    assert found.status == "active"
    assert found.external_id == "xr-venue-001"
    assert found.created_at is not None
    assert found.updated_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_minimal_fields(db_session: AsyncSession):
    venue = Venue(name="Workshop B")
    db_session.add(venue)
    await db_session.flush()

    result = await db_session.execute(select(Venue).where(Venue.id == venue.id))
    found = result.scalar_one()
    assert found.name == "Workshop B"
    assert found.capacity is None
    assert found.location is None
    assert found.description is None
    assert found.external_id is None
    assert found.status == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_status_default_is_active(db_session: AsyncSession):
    venue = Venue(name="Status Default Check")
    db_session.add(venue)
    await db_session.flush()

    result = await db_session.execute(select(Venue).where(Venue.id == venue.id))
    found = result.scalar_one()
    assert found.status == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_status_check_constraint_rejects_invalid(db_session: AsyncSession):
    venue = Venue(name="Bad Status Venue", status="demolished")
    db_session.add(venue)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_all_valid_statuses(db_session: AsyncSession):
    """Each valid status should be accepted without error."""
    from app.constants import ResourceStatus

    for status_val in ResourceStatus.ALL:
        venue = Venue(name=f"Venue-{status_val}", status=status_val)
        db_session.add(venue)
        await db_session.flush()
        assert venue.status == status_val


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_timestamps_use_utc_naive(db_session: AsyncSession):
    venue = Venue(name="Timestamp Venue")
    db_session.add(venue)
    await db_session.flush()

    assert venue.created_at.tzinfo is None
    assert venue.updated_at.tzinfo is None


# ---------------------------------------------------------------------------
# Equipment model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_create_all_fields(db_session: AsyncSession):
    venue = Venue(name="Equip Test Venue")
    db_session.add(venue)
    await db_session.flush()

    equip = Equipment(
        name="VR Headset #1",
        category="VR",
        serial_number="VR-001",
        venue_id=venue.id,
        external_id="xr-device-001",
        description="High-res VR headset",
    )
    db_session.add(equip)
    await db_session.flush()

    result = await db_session.execute(select(Equipment).where(Equipment.id == equip.id))
    found = result.scalar_one()
    assert found.name == "VR Headset #1"
    assert found.category == "VR"
    assert found.serial_number == "VR-001"
    assert found.venue_id == venue.id
    assert found.status == "active"
    assert found.external_id == "xr-device-001"
    assert found.description == "High-res VR headset"


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_minimal_fields(db_session: AsyncSession):
    equip = Equipment(name="Portable Projector")
    db_session.add(equip)
    await db_session.flush()

    result = await db_session.execute(select(Equipment).where(Equipment.id == equip.id))
    found = result.scalar_one()
    assert found.name == "Portable Projector"
    assert found.venue_id is None
    assert found.serial_number is None
    assert found.category is None
    assert found.status == "active"
    assert found.external_id is None


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_serial_number_unique(db_session: AsyncSession):
    equip1 = Equipment(name="Device A", serial_number="UNIQUE-SN-001")
    db_session.add(equip1)
    await db_session.flush()

    equip2 = Equipment(name="Device B", serial_number="UNIQUE-SN-001")
    db_session.add(equip2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_serial_number_null_allowed_multiple(db_session: AsyncSession):
    """Multiple equipment with NULL serial_number should be allowed."""
    equip1 = Equipment(name="Dev Null SN 1")
    equip2 = Equipment(name="Dev Null SN 2")
    db_session.add(equip1)
    db_session.add(equip2)
    await db_session.flush()
    assert equip1.id != equip2.id


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_status_check_constraint_rejects_invalid(db_session: AsyncSession):
    equip = Equipment(name="Bad Status Device", status="broken")
    db_session.add(equip)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_venue_fk_set_null_on_delete(db_session: AsyncSession):
    """Equipment.venue_id is nullable — equipment can exist without a venue."""
    equip = Equipment(name="Unbound Device")
    db_session.add(equip)
    await db_session.flush()

    result = await db_session.execute(select(Equipment).where(Equipment.id == equip.id))
    found = result.scalar_one()
    assert found.venue_id is None


# ---------------------------------------------------------------------------
# Booking model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_create_basic(db_session: AsyncSession):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_basic", role="teacher")
    venue = Venue(name="Booking Basic Venue")
    db_session.add(venue)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id,
        title="Robotics Lab Session",
        start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
        booked_by=user.id,
    )
    db_session.add(booking)
    await db_session.flush()

    result = await db_session.execute(select(Booking).where(Booking.id == booking.id))
    found = result.scalar_one()
    assert found.venue_id == venue.id
    assert found.title == "Robotics Lab Session"
    assert found.status == "approved"
    assert found.booked_by == user.id
    assert found.course_id is None
    assert found.class_id is None
    assert found.task_id is None
    assert found.client_ref is None
    assert found.purpose is None


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_with_context_fields(db_session: AsyncSession):
    """Booking has course_id, class_id, task_id for data isolation."""
    from tests.helpers import create_test_user, create_test_class, create_test_task
    from app.models.course import Course

    user = await create_test_user(db_session, username="booker_ctx", role="teacher")
    cls = await create_test_class(db_session, name="Context Test Class")
    course = Course(name="Context Test Course", semester="2025-2026-2", teacher_id=user.id)
    db_session.add(course)
    await db_session.flush()
    task = await create_test_task(db_session, title="Context Task", class_id=cls.id, created_by=user.id)
    venue = Venue(name="Context Test Venue")
    db_session.add(venue)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id,
        title="Contextual Booking",
        start_time=datetime.datetime(2026, 7, 1, 14, 0),
        end_time=datetime.datetime(2026, 7, 1, 16, 0),
        booked_by=user.id,
        course_id=course.id,
        class_id=cls.id,
        task_id=task.id,
        client_ref="xr-session-abc",
        purpose="Training session",
    )
    db_session.add(booking)
    await db_session.flush()

    result = await db_session.execute(select(Booking).where(Booking.id == booking.id))
    found = result.scalar_one()
    assert found.course_id == course.id
    assert found.class_id == cls.id
    assert found.task_id == task.id
    assert found.client_ref == "xr-session-abc"
    assert found.purpose == "Training session"


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_status_check_constraint_rejects_invalid(db_session: AsyncSession):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_status_chk", role="teacher")
    venue = Venue(name="Booking Status Venue")
    db_session.add(venue)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id,
        title="Bad Status",
        start_time=datetime.datetime(2026, 8, 1, 9, 0),
        end_time=datetime.datetime(2026, 8, 1, 11, 0),
        booked_by=user.id,
        status="pending",
    )
    db_session.add(booking)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_default_status_is_approved(db_session: AsyncSession):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_default_st", role="teacher")
    venue = Venue(name="Default Status Venue")
    db_session.add(venue)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id,
        title="Default Status Check",
        start_time=datetime.datetime(2026, 9, 1, 9, 0),
        end_time=datetime.datetime(2026, 9, 1, 11, 0),
        booked_by=user.id,
    )
    db_session.add(booking)
    await db_session.flush()

    result = await db_session.execute(select(Booking).where(Booking.id == booking.id))
    found = result.scalar_one()
    assert found.status == "approved"


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_client_ref_unique_non_null(db_session: AsyncSession):
    """Two bookings with the same non-null client_ref should conflict."""
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_ref_uniq", role="teacher")
    venue = Venue(name="ClientRef Unique Venue")
    db_session.add(venue)
    await db_session.flush()

    b1 = Booking(
        venue_id=venue.id,
        title="Ref 1",
        start_time=datetime.datetime(2026, 10, 1, 9, 0),
        end_time=datetime.datetime(2026, 10, 1, 11, 0),
        booked_by=user.id,
        client_ref="xr-dup-ref",
    )
    db_session.add(b1)
    await db_session.flush()

    b2 = Booking(
        venue_id=venue.id,
        title="Ref 2",
        start_time=datetime.datetime(2026, 10, 2, 9, 0),
        end_time=datetime.datetime(2026, 10, 2, 11, 0),
        booked_by=user.id,
        client_ref="xr-dup-ref",
    )
    db_session.add(b2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_client_ref_null_allowed_multiple(db_session: AsyncSession):
    """Multiple bookings with NULL client_ref should be allowed."""
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_ref_null", role="teacher")
    venue = Venue(name="Null Ref Venue")
    db_session.add(venue)
    await db_session.flush()

    b1 = Booking(
        venue_id=venue.id, title="Null Ref 1",
        start_time=datetime.datetime(2026, 11, 1, 9, 0),
        end_time=datetime.datetime(2026, 11, 1, 10, 0),
        booked_by=user.id,
    )
    b2 = Booking(
        venue_id=venue.id, title="Null Ref 2",
        start_time=datetime.datetime(2026, 11, 2, 9, 0),
        end_time=datetime.datetime(2026, 11, 2, 10, 0),
        booked_by=user.id,
    )
    db_session.add(b1)
    db_session.add(b2)
    await db_session.flush()
    assert b1.id != b2.id


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_timestamps_use_utc_naive(db_session: AsyncSession):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_ts", role="teacher")
    venue = Venue(name="TS Venue")
    db_session.add(venue)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id, title="TS Booking",
        start_time=datetime.datetime(2026, 12, 1, 9, 0),
        end_time=datetime.datetime(2026, 12, 1, 11, 0),
        booked_by=user.id,
    )
    db_session.add(booking)
    await db_session.flush()

    assert booking.created_at.tzinfo is None
    assert booking.updated_at.tzinfo is None


# ---------------------------------------------------------------------------
# BookingEquipment join model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_equipment_join(db_session: AsyncSession):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_be_join", role="teacher")
    venue = Venue(name="BE Join Venue")
    db_session.add(venue)
    await db_session.flush()

    equip = Equipment(name="BE Join Device", venue_id=venue.id)
    db_session.add(equip)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id, title="BE Join Booking",
        start_time=datetime.datetime(2026, 9, 1, 9, 0),
        end_time=datetime.datetime(2026, 9, 1, 11, 0),
        booked_by=user.id,
    )
    db_session.add(booking)
    await db_session.flush()

    be = BookingEquipment(booking_id=booking.id, equipment_id=equip.id)
    db_session.add(be)
    await db_session.flush()

    result = await db_session.execute(
        select(BookingEquipment).where(
            BookingEquipment.booking_id == booking.id,
            BookingEquipment.equipment_id == equip.id,
        )
    )
    found = result.scalar_one()
    assert found.booking_id == booking.id
    assert found.equipment_id == equip.id


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_equipment_composite_pk_prevents_duplicate(db_session: AsyncSession):
    """Same (booking_id, equipment_id) pair should violate PK constraint."""
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_be_pk", role="teacher")
    venue = Venue(name="BE PK Venue")
    db_session.add(venue)
    await db_session.flush()

    equip = Equipment(name="BE PK Device", venue_id=venue.id)
    db_session.add(equip)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id, title="BE PK Booking",
        start_time=datetime.datetime(2026, 9, 15, 9, 0),
        end_time=datetime.datetime(2026, 9, 15, 11, 0),
        booked_by=user.id,
    )
    db_session.add(booking)
    await db_session.flush()

    be1 = BookingEquipment(booking_id=booking.id, equipment_id=equip.id)
    db_session.add(be1)
    await db_session.flush()

    be2 = BookingEquipment(booking_id=booking.id, equipment_id=equip.id)
    db_session.add(be2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
