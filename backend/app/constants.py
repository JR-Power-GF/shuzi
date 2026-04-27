class UserRole:
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    FACILITY_MANAGER = "facility_manager"

    ALL_CURRENT = frozenset({ADMIN, TEACHER, STUDENT})
    ALL = frozenset({ADMIN, TEACHER, STUDENT, FACILITY_MANAGER})


class ResourceStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"

    ALL = frozenset({ACTIVE, INACTIVE, MAINTENANCE})


class BookingStatus:
    APPROVED = "approved"
    CANCELLED = "cancelled"

    ALL = frozenset({APPROVED, CANCELLED})
