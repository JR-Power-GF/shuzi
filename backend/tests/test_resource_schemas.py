"""Tests for resource-domain Pydantic schemas: Venue, Equipment, Booking.

Covers: field validation, required fields, extra=forbid on Update schemas,
time range validation on Booking schemas.
"""
import datetime

import pytest
from pydantic import ValidationError

from app.schemas.venue import VenueCreate, VenueUpdate, VenueResponse, VenueListResponse
from app.schemas.equipment import EquipmentCreate, EquipmentUpdate, EquipmentResponse
from app.schemas.booking import BookingCreate, BookingUpdate, BookingResponse


# ---------------------------------------------------------------------------
# Venue schemas
# ---------------------------------------------------------------------------


def test_venue_create_valid():
    data = VenueCreate(name="Test Venue", capacity=30, location="Floor 2")
    assert data.name == "Test Venue"
    assert data.capacity == 30
    assert data.location == "Floor 2"


def test_venue_create_minimal():
    data = VenueCreate(name="Minimal")
    assert data.name == "Minimal"
    assert data.capacity is None
    assert data.location is None
    assert data.description is None
    assert data.external_id is None


def test_venue_create_name_required():
    with pytest.raises(ValidationError):
        VenueCreate()


def test_venue_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        VenueCreate(name="")


def test_venue_create_rejects_name_too_long():
    with pytest.raises(ValidationError):
        VenueCreate(name="x" * 101)


def test_venue_create_with_external_id():
    data = VenueCreate(name="XR Room", external_id="xr-room-0042")
    assert data.external_id == "xr-room-0042"


def test_venue_update_forbids_extra_fields():
    with pytest.raises(ValidationError):
        VenueUpdate(name="Updated", unknown_field="bad")


def test_venue_update_all_optional():
    data = VenueUpdate()
    assert data.name is None
    assert data.status is None


def test_venue_update_rejects_invalid_status():
    with pytest.raises(ValidationError):
        VenueUpdate(status="garbage")


def test_venue_update_accepts_valid_statuses():
    for s in ("active", "inactive", "maintenance"):
        data = VenueUpdate(status=s)
        assert data.status == s


def test_venue_response_fields():
    data = VenueResponse(
        id=1, name="V", capacity=None, location=None, description=None,
        status="active", external_id=None,
        created_at=datetime.datetime(2026, 1, 1), updated_at=datetime.datetime(2026, 1, 1),
    )
    assert data.id == 1
    assert data.status == "active"


def test_venue_list_response():
    data = VenueListResponse(items=[], total=0)
    assert data.total == 0


# ---------------------------------------------------------------------------
# Equipment schemas
# ---------------------------------------------------------------------------


def test_equipment_create_valid():
    data = EquipmentCreate(name="VR Headset", category="VR", serial_number="VR-001")
    assert data.name == "VR Headset"
    assert data.serial_number == "VR-001"


def test_equipment_create_minimal():
    data = EquipmentCreate(name="Projector")
    assert data.category is None
    assert data.venue_id is None
    assert data.serial_number is None


def test_equipment_create_name_required():
    with pytest.raises(ValidationError):
        EquipmentCreate()


def test_equipment_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        EquipmentCreate(name="")


def test_equipment_create_with_venue_id():
    data = EquipmentCreate(name="Device", venue_id=5)
    assert data.venue_id == 5


def test_equipment_create_rejects_empty_serial_number():
    with pytest.raises(ValidationError):
        EquipmentCreate(name="Device", serial_number="")


def test_equipment_update_rejects_empty_serial_number():
    with pytest.raises(ValidationError):
        EquipmentUpdate(serial_number="")


def test_equipment_update_rejects_invalid_status():
    with pytest.raises(ValidationError):
        EquipmentUpdate(status="broken")


def test_equipment_update_accepts_valid_statuses():
    for s in ("active", "inactive", "maintenance"):
        data = EquipmentUpdate(status=s)
        assert data.status == s


def test_equipment_update_forbids_extra_fields():
    with pytest.raises(ValidationError):
        EquipmentUpdate(name="Updated", bogus="bad")


def test_equipment_response_fields():
    data = EquipmentResponse(
        id=1, name="Dev", category=None, serial_number=None, status="active",
        venue_id=None, venue_name=None, description=None, external_id=None,
        created_at=datetime.datetime(2026, 1, 1), updated_at=datetime.datetime(2026, 1, 1),
    )
    assert data.id == 1
    assert data.status == "active"


# ---------------------------------------------------------------------------
# Booking schemas
# ---------------------------------------------------------------------------


def test_booking_create_valid():
    data = BookingCreate(
        venue_id=1,
        title="Lab Session",
        start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
    )
    assert data.venue_id == 1
    assert data.equipment_ids == []


def test_booking_create_with_equipment_ids():
    data = BookingCreate(
        venue_id=1,
        title="Session",
        start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
        equipment_ids=[2, 3, 5],
    )
    assert data.equipment_ids == [2, 3, 5]


def test_booking_create_with_context_fields():
    data = BookingCreate(
        venue_id=1,
        title="Context Session",
        start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
        course_id=10,
        class_id=20,
        task_id=30,
        client_ref="xr-session-xyz",
    )
    assert data.course_id == 10
    assert data.class_id == 20
    assert data.task_id == 30
    assert data.client_ref == "xr-session-xyz"


def test_booking_create_rejects_end_before_start():
    with pytest.raises(ValidationError):
        BookingCreate(
            venue_id=1,
            title="Bad",
            start_time=datetime.datetime(2026, 6, 1, 11, 0),
            end_time=datetime.datetime(2026, 6, 1, 9, 0),
        )


def test_booking_create_rejects_equal_start_end():
    with pytest.raises(ValidationError):
        BookingCreate(
            venue_id=1,
            title="Bad",
            start_time=datetime.datetime(2026, 6, 1, 9, 0),
            end_time=datetime.datetime(2026, 6, 1, 9, 0),
        )


def test_booking_create_title_required():
    with pytest.raises(ValidationError):
        BookingCreate(
            venue_id=1,
            start_time=datetime.datetime(2026, 6, 1, 9, 0),
            end_time=datetime.datetime(2026, 6, 1, 11, 0),
        )


def test_booking_update_forbids_extra_fields():
    with pytest.raises(ValidationError):
        BookingUpdate(title="Updated", unknown="bad")


def test_booking_update_rejects_inverted_time_range():
    with pytest.raises(ValidationError):
        BookingUpdate(
            start_time=datetime.datetime(2026, 6, 1, 11, 0),
            end_time=datetime.datetime(2026, 6, 1, 9, 0),
        )


def test_booking_update_allows_partial_start_only():
    data = BookingUpdate(start_time=datetime.datetime(2026, 6, 1, 10, 0))
    assert data.start_time is not None
    assert data.end_time is None


def test_booking_update_allows_partial_end_only():
    data = BookingUpdate(end_time=datetime.datetime(2026, 6, 1, 12, 0))
    assert data.start_time is None
    assert data.end_time is not None


def test_booking_response_fields():
    data = BookingResponse(
        id=1, venue_id=1, venue_name="Lab", title="Session",
        purpose=None, start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
        booked_by=1, status="approved", derived_status="approved",
        course_id=None, class_id=None, task_id=None,
        client_ref=None, equipment=[],
        created_at=datetime.datetime(2026, 1, 1), updated_at=datetime.datetime(2026, 1, 1),
    )
    assert data.derived_status == "approved"
    assert data.equipment == []
