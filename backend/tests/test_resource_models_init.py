"""Tests that all resource-domain models are registered in app.models.__init__."""
import app.models


def test_venue_importable():
    from app.models import Venue
    assert Venue is not None


def test_equipment_importable():
    from app.models import Equipment
    assert Equipment is not None


def test_booking_importable():
    from app.models import Booking
    assert Booking is not None


def test_booking_equipment_importable():
    from app.models import BookingEquipment
    assert BookingEquipment is not None


def test_venue_in_all():
    assert "Venue" in app.models.__all__


def test_equipment_in_all():
    assert "Equipment" in app.models.__all__


def test_booking_in_all():
    assert "Booking" in app.models.__all__


def test_booking_equipment_in_all():
    assert "BookingEquipment" in app.models.__all__


def test_existing_models_still_in_all():
    """Backward compatibility: existing models must remain registered."""
    for name in ["User", "Class", "Course", "Task", "Submission", "Grade", "AuditLog"]:
        assert name in app.models.__all__, f"{name} missing from __all__"
