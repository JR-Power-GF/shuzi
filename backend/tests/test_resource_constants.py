"""Tests for resource-domain constants: ResourceStatus and BookingStatus."""
from app.constants import ResourceStatus, BookingStatus


def test_resource_status_active():
    assert ResourceStatus.ACTIVE == "active"


def test_resource_status_inactive():
    assert ResourceStatus.INACTIVE == "inactive"


def test_resource_status_maintenance():
    assert ResourceStatus.MAINTENANCE == "maintenance"


def test_resource_status_all_contains_three_values():
    assert ResourceStatus.ALL == frozenset({"active", "inactive", "maintenance"})
    assert len(ResourceStatus.ALL) == 3


def test_booking_status_approved():
    assert BookingStatus.APPROVED == "approved"


def test_booking_status_cancelled():
    assert BookingStatus.CANCELLED == "cancelled"


def test_booking_status_all_contains_two_values():
    assert BookingStatus.ALL == frozenset({"approved", "cancelled"})
    assert len(BookingStatus.ALL) == 2


def test_resource_status_values_are_strings():
    for val in ResourceStatus.ALL:
        assert isinstance(val, str)


def test_booking_status_values_are_strings():
    for val in BookingStatus.ALL:
        assert isinstance(val, str)
