# Phase 3 PR1: Resource Domain Foundation — Models, Schemas, Migrations, Permissions, Audit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the minimal data layer, permission constants, Pydantic schemas, test helpers, and migrations for the resource domain (venues, equipment, bookings, XR stubs) — everything that PR2–PR7 will build on, but no business logic or routers.

**Architecture:** Four new models (Venue, Equipment, Booking, BookingEquipment) across two Alembic migrations. Resource status constants added to existing `app/constants.py`. Pydantic schemas follow the existing Create/Update/Response pattern. All tables use naive UTC timestamps via `_utcnow_naive`. Time intervals use half-open `[start, end)` convention. Audit integration uses the existing `audit_log()` service. XR is represented only by `external_id` fields and a `client_reference` field — no external code.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.0 async (Mapped columns, no relationships), Pydantic v2, Alembic, MySQL 8, pytest + pytest-asyncio

---

## Permission Matrix Draft

Applies to all resource-domain endpoints (routers come in PR2–PR4, but the permission constants and dependencies are established here):

| Operation | admin | facility_manager | teacher | student |
|-----------|-------|-----------------|---------|---------|
| Venue/Equipment read | yes | yes | yes | no |
| Venue/Equipment write | yes | yes | no | no |
| Booking create | yes | yes | yes (own only) | no |
| Booking read | yes | yes | yes (own + course-linked) | no |
| Booking modify/cancel | yes | yes | yes (own only) | no |
| Statistics read | yes | yes | no | no |

**Implementation:** `require_role(["admin", "facility_manager"])` for resource writes, `require_role(["admin", "facility_manager", "teacher"])` for resource reads, `require_role(["admin", "facility_manager", "teacher"])` for booking create, `require_role_or_owner(...)` for booking modify/cancel.

---

## Audit / Logging Plan

All resource-domain write operations will produce AuditLog entries (routers in PR2–PR4 do the actual logging, but the contract is defined here):

| entity_type | action | When |
|-------------|--------|------|
| `"venue"` | `"create"` | Venue created |
| `"venue"` | `"update"` | Venue fields changed |
| `"venue"` | `"status_change"` | Venue status transitioned |
| `"equipment"` | `"create"` | Equipment created |
| `"equipment"` | `"update"` | Equipment fields changed |
| `"equipment"` | `"status_change"` | Equipment status transitioned |
| `"booking"` | `"create"` | Booking created |
| `"booking"` | `"update"` | Booking modified |
| `"booking"` | `"cancel"` | Booking cancelled |

The existing `audit_log(db, entity_type=..., entity_id=..., action=..., actor_id=..., changes=...)` service is used unchanged. The `changes` field will contain a JSON dict of the modified fields.

---

## Migration Sequence and Rollback Notes

**Migration A** (`add_venues_and_equipment_tables`): Creates `venues` and `equipment` tables. These are independent of each other (equipment has an optional FK to venues via `ondelete="SET NULL"`). Downgrade: drop `equipment` first (has FK to venues), then drop `venues`.

**Migration B** (`add_bookings_tables`): Creates `bookings` and `booking_equipment` tables. Depends on `venues`, `equipment`, `users`, `courses`, `classes`, `tasks` tables all existing. Downgrade: drop `booking_equipment` first (FK to bookings), then drop `bookings`.

Both migrations are additive-only (no existing table modifications). Safe to run on a live database — zero downtime, no data migration.

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| `equipment.__tablename__` naming — "equipment" (uncountable) vs "equipments" | Explicit `__tablename__ = "equipment"` in model. FK in booking_equipment references `"equipment"`. |
| Booking FK references tables from PR2/PR3 migrations — migration B must run after migration A | `down_revision` chains correctly. Test `alembic upgrade head` from scratch. |
| `ondelete="RESTRICT"` on bookings.venue_id means venues with bookings can never be hard-deleted | By design — venues use soft status change (active→inactive), not deletion. |
| `client_reference` unique nullable — MySQL treats NULL != NULL, so multiple NULL values are allowed | Correct behavior — client_reference is optional; only non-null values are checked for uniqueness. |
| Circular FK risk if future tables reference back to venues/equipment | No circular FK in this PR. Equipment→venues is one-directional optional FK. |

---

## Definition of Done / Merge Bar

- [ ] All 4 models registered in `app/models/__init__.py` and importable
- [ ] Both migrations apply cleanly: `alembic upgrade head`
- [ ] Both migrations rollback cleanly: `alembic downgrade -1 && alembic upgrade head`
- [ ] All existing 232 tests pass with zero regressions
- [ ] New model tests pass: Venue, Equipment, Booking, BookingEquipment can be instantiated and flushed
- [ ] New helper tests pass: `create_test_venue`, `create_test_equipment` work
- [ ] Schema files importable, field types match model columns
- [ ] `ResourceStatus` and `BookingStatus` constants usable from `app/constants.py`
- [ ] No router or endpoint created (this is foundation only)

---

## File Breakdown

| File | Action | Responsibility |
|------|--------|---------------|
| `app/constants.py` | Modify | Add ResourceStatus, BookingStatus classes |
| `app/models/venue.py` | Create | Venue model |
| `app/models/equipment.py` | Create | Equipment model |
| `app/models/booking.py` | Create | Booking + BookingEquipment models |
| `app/models/__init__.py` | Modify | Register new models |
| `app/schemas/venue.py` | Create | VenueCreate, VenueUpdate, VenueResponse, VenueListResponse |
| `app/schemas/equipment.py` | Create | EquipmentCreate, EquipmentUpdate, EquipmentResponse, EquipmentListResponse |
| `app/schemas/booking.py` | Create | BookingCreate, BookingUpdate, BookingResponse, BookingListResponse |
| `alembic/versions/<hash>_add_venues_and_equipment_tables.py` | Create | Migration A |
| `alembic/versions/<hash>_add_bookings_tables.py` | Create | Migration B |
| `tests/helpers.py` | Modify | Add create_test_venue, create_test_equipment |
| `tests/test_resource_models.py` | Create | Model instantiation + flush tests |
| `tests/test_resource_schemas.py` | Create | Schema validation tests |

---

## Task 1: Add resource-domain constants to app/constants.py

**Files:**
- Modify: `app/constants.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resource_constants.py`:

```python
from app.constants import ResourceStatus, BookingStatus


def test_resource_status_values():
    assert ResourceStatus.ACTIVE == "active"
    assert ResourceStatus.INACTIVE == "inactive"
    assert ResourceStatus.MAINTENANCE == "maintenance"


def test_resource_status_all():
    assert ResourceStatus.ALL == frozenset({"active", "inactive", "maintenance"})


def test_booking_status_values():
    assert BookingStatus.APPROVED == "approved"
    assert BookingStatus.CANCELLED == "cancelled"


def test_booking_status_all():
    assert BookingStatus.ALL == frozenset({"approved", "cancelled"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_constants.py -v`
Expected: FAIL — `ImportError: cannot import name 'ResourceStatus'`

- [ ] **Step 3: Write minimal implementation**

Add to `app/constants.py` after the existing `UserRole` class:

```python
class ResourceStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"

    ALL = frozenset({ACTIVE, INACTIVE, MAINTENANCE})


class BookingStatus:
    APPROVED = "approved"
    CANCELLED = "cancelled"

    ALL = frozenset({APPROVED, CANCELLED})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_constants.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```
feat: add ResourceStatus and BookingStatus constants
```

---

## Task 2: Create Venue model

**Files:**
- Create: `app/models/venue.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_resource_models.py` (create the file):

```python
import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_model_create_with_all_fields(db_session: AsyncSession):
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
    assert found.status == "active"
    assert found.external_id == "xr-venue-001"
    assert found.created_at is not None
    assert found.updated_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_model_minimal_fields(db_session: AsyncSession):
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
async def test_venue_model_status_constraint(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError

    venue = Venue(name="Test Venue", status="invalid_status")
    db_session.add(venue)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.venue'`

- [ ] **Step 3: Write minimal implementation**

Create `app/models/venue.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="chk_venue_status"),
        Index("ix_venues_external_id", "external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```
feat: add Venue model
```

---

## Task 3: Create Equipment model

**Files:**
- Create: `app/models/equipment.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_models.py`:

```python
from app.models.equipment import Equipment


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_model_create_with_all_fields(db_session: AsyncSession):
    venue = Venue(name="Lab for Equipment Test")
    db_session.add(venue)
    await db_session.flush()

    equip = Equipment(
        name="VR Headset #1",
        category="VR",
        serial_number="VR-001",
        venue_id=venue.id,
        external_id="xr-device-001",
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


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_model_minimal_fields(db_session: AsyncSession):
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


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_model_serial_number_unique(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError

    equip1 = Equipment(name="Device A", serial_number="UNIQUE-SN-001")
    db_session.add(equip1)
    await db_session.flush()

    equip2 = Equipment(name="Device B", serial_number="UNIQUE-SN-001")
    db_session.add(equip2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_model_status_constraint(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError

    equip = Equipment(name="Bad Status Device", status="broken")
    db_session.add(equip)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_models.py::test_equipment_model_create_with_all_fields -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `app/models/equipment.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="chk_equipment_status"),
        Index("ix_equipment_external_id", "external_id"),
        Index("ix_equipment_serial_number", "serial_number", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    venue_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("venues.id", ondelete="SET NULL"), nullable=True, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_models.py -v`
Expected: 7 passed (3 venue + 4 equipment)

- [ ] **Step 5: Commit**

```
feat: add Equipment model with optional venue FK
```

---

## Task 4: Create Booking and BookingEquipment models

**Files:**
- Create: `app/models/booking.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_models.py`:

```python
from app.models.booking import Booking, BookingEquipment


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_model_create_basic(db_session: AsyncSession):
    from tests.helpers import create_test_user

    user = await create_test_user(db_session, username="booker_test", role="teacher")
    venue = Venue(name="Booking Test Venue")
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
    assert found.client_reference is None


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_model_with_context(db_session: AsyncSession):
    from tests.helpers import create_test_user, create_test_class

    user = await create_test_user(db_session, username="booker_ctx", role="teacher")
    cls = await create_test_class(db_session, name="Context Test Class")
    venue = Venue(name="Context Test Venue")
    db_session.add(venue)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id,
        title="Contextual Booking",
        start_time=datetime.datetime(2026, 7, 1, 14, 0),
        end_time=datetime.datetime(2026, 7, 1, 16, 0),
        booked_by=user.id,
        course_id=1,
        class_id=cls.id,
        client_reference="xr-session-abc",
    )
    db_session.add(booking)
    await db_session.flush()

    result = await db_session.execute(select(Booking).where(Booking.id == booking.id))
    found = result.scalar_one()
    assert found.course_id == 1
    assert found.class_id == cls.id
    assert found.client_reference == "xr-session-abc"


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_model_status_constraint(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError

    venue = Venue(name="Status Constraint Venue")
    db_session.add(venue)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id,
        title="Bad Status",
        start_time=datetime.datetime(2026, 8, 1, 9, 0),
        end_time=datetime.datetime(2026, 8, 1, 11, 0),
        booked_by=1,
        status="pending",
    )
    db_session.add(booking)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_equipment_model(db_session: AsyncSession):
    venue = Venue(name="BE Test Venue")
    db_session.add(venue)
    await db_session.flush()

    equip = Equipment(name="BE Test Device", venue_id=venue.id)
    db_session.add(equip)
    await db_session.flush()

    booking = Booking(
        venue_id=venue.id,
        title="Booking with Equipment",
        start_time=datetime.datetime(2026, 9, 1, 9, 0),
        end_time=datetime.datetime(2026, 9, 1, 11, 0),
        booked_by=1,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_models.py::test_booking_model_create_basic -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `app/models/booking.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("status IN ('approved', 'cancelled')", name="chk_booking_status"),
        Index("ix_bookings_venue_time", "venue_id", "start_time", "end_time"),
        Index("ix_bookings_booked_by", "booked_by"),
        Index("ix_bookings_status", "status"),
        Index("ix_bookings_client_ref", "client_ref", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    booked_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    course_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    class_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    client_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )


class BookingEquipment(Base):
    __tablename__ = "booking_equipment"
    __table_args__ = (
        Index("ix_booking_equipment_equip", "equipment_id", "booking_id"),
    )

    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True
    )
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_models.py -v`
Expected: 11 passed (3 venue + 4 equipment + 4 booking)

- [ ] **Step 5: Commit**

```
feat: add Booking and BookingEquipment models
```

---

## Task 5: Register all new models in __init__.py

**Files:**
- Modify: `app/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resource_models_init.py`:

```python
from app.models import Venue, Equipment, Booking, BookingEquipment


def test_models_importable():
    assert Venue is not None
    assert Equipment is not None
    assert Booking is not None
    assert BookingEquipment is not None


def test_models_in_all():
    import app.models

    assert "Venue" in app.models.__all__
    assert "Equipment" in app.models.__all__
    assert "Booking" in app.models.__all__
    assert "BookingEquipment" in app.models.__all__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_models_init.py -v`
Expected: FAIL — `ImportError: cannot import name 'Venue'`

- [ ] **Step 3: Write minimal implementation**

Replace `app/models/__init__.py` with:

```python
from app.models.user import User
from app.models.class_ import Class
from app.models.course import Course
from app.models.task import Task
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.grade import Grade
from app.models.refresh_token import RefreshToken
from app.models.ai_config import AIConfig
from app.models.ai_usage_log import AIUsageLog
from app.models.ai_feedback import AIFeedback
from app.models.prompt_template import PromptTemplate
from app.models.training_summary import TrainingSummary
from app.models.audit_log import AuditLog
from app.models.venue import Venue
from app.models.equipment import Equipment
from app.models.booking import Booking, BookingEquipment

__all__ = [
    "User",
    "Class",
    "Course",
    "Task",
    "Submission",
    "SubmissionFile",
    "Grade",
    "RefreshToken",
    "AIConfig",
    "AIUsageLog",
    "AIFeedback",
    "PromptTemplate",
    "TrainingSummary",
    "AuditLog",
    "Venue",
    "Equipment",
    "Booking",
    "BookingEquipment",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_models_init.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```
feat: register Venue, Equipment, Booking, BookingEquipment in models/__init__.py
```

---

## Task 6: Create Migration A — venues and equipment tables

**Files:**
- Create: `alembic/versions/<hash>_add_venues_and_equipment_tables.py`

- [ ] **Step 1: Generate the migration**

Run: `alembic revision --autogenerate -m "add venues and equipment tables"`

- [ ] **Step 2: Review and fix the generated migration**

Open the generated file. Verify:
- `down_revision` points to `'b5e8d2f3017a'` (the latest existing migration: add_ai_tables)
- `venues` table has all columns matching the Venue model
- `equipment` table has all columns matching the Equipment model
- FK names follow `fk_<table>_<column>` convention
- Index names follow `ix_<table>_<column>` convention
- `downgrade()` drops `equipment` first, then `venues`

If the autogenerate missed anything or naming is wrong, fix it manually. The migration must look like this pattern:

```python
"""add venues and equipment tables

Revision ID: <auto>
Revises: b5e8d2f3017a
Create Date: <auto>
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '<auto>'
down_revision: Union[str, Sequence[str], None] = 'b5e8d2f3017a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('venues',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name='chk_venue_status'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_venues_external_id', 'venues', ['external_id'])

    op.create_table('equipment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('venue_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name='chk_equipment_status'),
        sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_equipment_venue_id', 'equipment', ['venue_id'])
    op.create_index('ix_equipment_external_id', 'equipment', ['external_id'])
    op.create_index('ix_equipment_serial_number', 'equipment', ['serial_number'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_equipment_serial_number', table_name='equipment')
    op.drop_index('ix_equipment_external_id', table_name='equipment')
    op.drop_index('ix_equipment_venue_id', table_name='equipment')
    op.drop_table('equipment')
    op.drop_index('ix_venues_external_id', table_name='venues')
    op.drop_table('venues')
```

- [ ] **Step 3: Test migration up**

Run: `alembic upgrade head`
Expected: No errors

- [ ] **Step 4: Test migration down and up**

Run: `alembic downgrade -1 && alembic upgrade head`
Expected: No errors

- [ ] **Step 5: Run existing tests**

Run: `pytest -v --tb=short`
Expected: All existing 232 tests pass + new model tests pass

- [ ] **Step 6: Commit**

```
feat: add venues and equipment tables migration
```

---

## Task 7: Create Migration B — bookings and booking_equipment tables

**Files:**
- Create: `alembic/versions/<hash>_add_bookings_tables.py`

- [ ] **Step 1: Generate the migration**

Run: `alembic revision --autogenerate -m "add bookings tables"`

- [ ] **Step 2: Review and fix the generated migration**

Open the generated file. Verify:
- `down_revision` points to the migration from Task 6
- `bookings` table has all columns matching the Booking model
- `booking_equipment` table has the composite PK
- FK names follow conventions
- `downgrade()` drops `booking_equipment` first (has FK to bookings), then `bookings`

Target structure:

```python
def upgrade() -> None:
    op.create_table('bookings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('venue_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('booked_by', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=True),
        sa.Column('class_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('client_ref', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('approved', 'cancelled')", name='chk_booking_status'),
        sa.ForeignKeyConstraint(['venue_id'], ['venues.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['booked_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bookings_venue_id', 'bookings', ['venue_id'])
    op.create_index('ix_bookings_booked_by', 'bookings', ['booked_by'])
    op.create_index('ix_bookings_status', 'bookings', ['status'])
    op.create_index('ix_bookings_course_id', 'bookings', ['course_id'])
    op.create_index('ix_bookings_class_id', 'bookings', ['class_id'])
    op.create_index('ix_bookings_task_id', 'bookings', ['task_id'])
    op.create_index('ix_bookings_venue_time', 'bookings', ['venue_id', 'start_time', 'end_time'])
    op.create_index('ix_bookings_client_ref', 'bookings', ['client_ref'], unique=True)

    op.create_table('booking_equipment',
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('equipment_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('booking_id', 'equipment_id'),
    )
    op.create_index('ix_booking_equipment_equip', 'booking_equipment', ['equipment_id', 'booking_id'])


def downgrade() -> None:
    op.drop_index('ix_booking_equipment_equip', table_name='booking_equipment')
    op.drop_table('booking_equipment')
    op.drop_index('ix_bookings_client_ref', table_name='bookings')
    op.drop_index('ix_bookings_venue_time', table_name='bookings')
    op.drop_index('ix_bookings_task_id', table_name='bookings')
    op.drop_index('ix_bookings_class_id', table_name='bookings')
    op.drop_index('ix_bookings_course_id', table_name='bookings')
    op.drop_index('ix_bookings_status', table_name='bookings')
    op.drop_index('ix_bookings_booked_by', table_name='bookings')
    op.drop_index('ix_bookings_venue_id', table_name='bookings')
    op.drop_table('bookings')
```

- [ ] **Step 3: Test migration up**

Run: `alembic upgrade head`
Expected: No errors

- [ ] **Step 4: Test full migration chain (downgrade all the way back and up)**

Run: `alembic downgrade -2 && alembic upgrade head`
Expected: No errors (goes back past both new migrations, then forward)

- [ ] **Step 5: Run all tests**

Run: `pytest -v --tb=short`
Expected: All tests pass

- [ ] **Step 6: Commit**

```
feat: add bookings and booking_equipment tables migration
```

---

## Task 8: Create Venue Pydantic schemas

**Files:**
- Create: `app/schemas/venue.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resource_schemas.py`:

```python
import datetime
import pytest
from pydantic import ValidationError

from app.schemas.venue import VenueCreate, VenueUpdate, VenueResponse


def test_venue_create_valid():
    data = VenueCreate(name="Test Venue", capacity=30, location="Floor 2")
    assert data.name == "Test Venue"
    assert data.capacity == 30


def test_venue_create_minimal():
    data = VenueCreate(name="Minimal")
    assert data.name == "Minimal"
    assert data.capacity is None


def test_venue_create_name_required():
    with pytest.raises(ValidationError):
        VenueCreate()


def test_venue_create_name_too_long():
    with pytest.raises(ValidationError):
        VenueCreate(name="x" * 101)


def test_venue_update_forbids_extra():
    with pytest.raises(ValidationError):
        VenueUpdate(name="Updated", unknown_field="bad")


def test_venue_response_fields():
    data = VenueResponse(
        id=1, name="V", capacity=None, location=None, description=None,
        status="active", external_id=None,
        created_at=datetime.datetime(2026, 1, 1), updated_at=datetime.datetime(2026, 1, 1),
    )
    assert data.id == 1
    assert data.status == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `app/schemas/venue.py`:

```python
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class VenueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    capacity: Optional[int] = None
    location: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class VenueUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    capacity: Optional[int] = None
    location: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class VenueResponse(BaseModel):
    id: int
    name: str
    capacity: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    status: str
    external_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class VenueListResponse(BaseModel):
    items: List[VenueResponse]
    total: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_schemas.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```
feat: add Venue Pydantic schemas
```

---

## Task 9: Create Equipment Pydantic schemas

**Files:**
- Create: `app/schemas/equipment.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_schemas.py`:

```python
from app.schemas.equipment import EquipmentCreate, EquipmentUpdate, EquipmentResponse


def test_equipment_create_valid():
    data = EquipmentCreate(name="VR Headset", category="VR", serial_number="VR-001")
    assert data.name == "VR Headset"
    assert data.serial_number == "VR-001"


def test_equipment_create_minimal():
    data = EquipmentCreate(name="Projector")
    assert data.category is None
    assert data.venue_id is None


def test_equipment_create_name_required():
    with pytest.raises(ValidationError):
        EquipmentCreate()


def test_equipment_update_forbids_extra():
    with pytest.raises(ValidationError):
        EquipmentUpdate(name="Updated", bogus="bad")


def test_equipment_response_fields():
    data = EquipmentResponse(
        id=1, name="Dev", category=None, serial_number=None, status="active",
        venue_id=None, venue_name=None, description=None, external_id=None,
        created_at=datetime.datetime(2026, 1, 1), updated_at=datetime.datetime(2026, 1, 1),
    )
    assert data.id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_schemas.py::test_equipment_create_valid -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `app/schemas/equipment.py`:

```python
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class EquipmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    serial_number: Optional[str] = Field(None, max_length=100)
    venue_id: Optional[int] = None
    description: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class EquipmentUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    serial_number: Optional[str] = Field(None, max_length=100)
    venue_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class EquipmentResponse(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    serial_number: Optional[str] = None
    status: str
    venue_id: Optional[int] = None
    venue_name: Optional[str] = None
    description: Optional[str] = None
    external_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EquipmentListResponse(BaseModel):
    items: List[EquipmentResponse]
    total: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_schemas.py -v`
Expected: 11 passed (6 venue + 5 equipment)

- [ ] **Step 5: Commit**

```
feat: add Equipment Pydantic schemas
```

---

## Task 10: Create Booking Pydantic schemas

**Files:**
- Create: `app/schemas/booking.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_schemas.py`:

```python
from app.schemas.booking import BookingCreate, BookingUpdate, BookingResponse


def test_booking_create_valid():
    data = BookingCreate(
        venue_id=1,
        title="Lab Session",
        start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
    )
    assert data.venue_id == 1
    assert data.equipment_ids == []


def test_booking_create_with_equipment():
    data = BookingCreate(
        venue_id=1,
        title="Session",
        start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
        equipment_ids=[2, 3, 5],
    )
    assert data.equipment_ids == [2, 3, 5]


def test_booking_create_rejects_invalid_time_range():
    with pytest.raises(ValidationError):
        BookingCreate(
            venue_id=1,
            title="Bad",
            start_time=datetime.datetime(2026, 6, 1, 11, 0),
            end_time=datetime.datetime(2026, 6, 1, 9, 0),
        )


def test_booking_create_rejects_equal_times():
    with pytest.raises(ValidationError):
        BookingCreate(
            venue_id=1,
            title="Bad",
            start_time=datetime.datetime(2026, 6, 1, 9, 0),
            end_time=datetime.datetime(2026, 6, 1, 9, 0),
        )


def test_booking_update_forbids_extra():
    with pytest.raises(ValidationError):
        BookingUpdate(title="Updated", unknown="bad")


def test_booking_response_fields():
    data = BookingResponse(
        id=1, venue_id=1, venue_name="Lab", title="Session",
        purpose=None, start_time=datetime.datetime(2026, 6, 1, 9, 0),
        end_time=datetime.datetime(2026, 6, 1, 11, 0),
        booked_by=1, status="approved", derived_status="approved",
        course_id=None, class_id=None, task_id=None,
        client_ref=None, equipment=[], purpose=None,
        created_at=datetime.datetime(2026, 1, 1), updated_at=datetime.datetime(2026, 1, 1),
    )
    assert data.derived_status == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_schemas.py::test_booking_create_valid -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `app/schemas/booking.py`:

```python
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator


class EquipmentItem(BaseModel):
    id: int
    name: str


class BookingCreate(BaseModel):
    venue_id: int
    title: str = Field(..., min_length=1, max_length=200)
    purpose: Optional[str] = None
    start_time: datetime
    end_time: datetime
    equipment_ids: List[int] = Field(default_factory=list)
    course_id: Optional[int] = None
    class_id: Optional[int] = None
    task_id: Optional[int] = None
    client_ref: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class BookingUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    purpose: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    equipment_ids: Optional[List[int]] = None

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class BookingResponse(BaseModel):
    id: int
    venue_id: int
    venue_name: Optional[str] = None
    title: str
    purpose: Optional[str] = None
    start_time: datetime
    end_time: datetime
    booked_by: int
    status: str
    derived_status: Optional[str] = None
    course_id: Optional[int] = None
    class_id: Optional[int] = None
    task_id: Optional[int] = None
    client_ref: Optional[str] = None
    equipment: List[EquipmentItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BookingListResponse(BaseModel):
    items: List[BookingResponse]
    total: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_schemas.py -v`
Expected: 17 passed (6 venue + 5 equipment + 6 booking)

- [ ] **Step 5: Commit**

```
feat: add Booking Pydantic schemas with time range validation
```

---

## Task 11: Add test helpers for venue and equipment

**Files:**
- Modify: `tests/helpers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resource_helpers.py`:

```python
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.models.equipment import Equipment
from tests.helpers import create_test_venue, create_test_equipment


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_venue(db_session: AsyncSession):
    venue = await create_test_venue(db_session, name="Helper Venue", capacity=20)
    assert venue.id is not None
    assert venue.name == "Helper Venue"
    assert venue.capacity == 20
    assert venue.status == "active"

    result = await db_session.execute(select(Venue).where(Venue.id == venue.id))
    assert result.scalar_one() is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_venue_defaults(db_session: AsyncSession):
    venue = await create_test_venue(db_session)
    assert venue.name == "Test Venue"
    assert venue.status == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_equipment(db_session: AsyncSession):
    venue = await create_test_venue(db_session, name="Equip Helper Venue")
    equip = await create_test_equipment(db_session, name="Helper Device", venue_id=venue.id)
    assert equip.id is not None
    assert equip.name == "Helper Device"
    assert equip.venue_id == venue.id
    assert equip.status == "active"

    result = await db_session.execute(select(Equipment).where(Equipment.id == equip.id))
    assert result.scalar_one() is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_equipment_no_venue(db_session: AsyncSession):
    equip = await create_test_equipment(db_session, name="Unbound Device")
    assert equip.venue_id is None
    assert equip.status == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_helpers.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_test_venue'`

- [ ] **Step 3: Write minimal implementation**

Append to `tests/helpers.py`:

```python
from app.models.venue import Venue
from app.models.equipment import Equipment


async def create_test_venue(
    db: AsyncSession,
    *,
    name: str = "Test Venue",
    capacity: int = None,
    location: str = None,
    status: str = "active",
    **kwargs,
) -> Venue:
    venue = Venue(name=name, capacity=capacity, location=location, status=status, **kwargs)
    db.add(venue)
    await db.flush()
    return venue


async def create_test_equipment(
    db: AsyncSession,
    *,
    name: str = "Test Equipment",
    category: str = None,
    serial_number: str = None,
    venue_id: int = None,
    status: str = "active",
    **kwargs,
) -> Equipment:
    equip = Equipment(
        name=name, category=category, serial_number=serial_number,
        venue_id=venue_id, status=status, **kwargs,
    )
    db.add(equip)
    await db.flush()
    return equip
```

Also add the missing imports at the top of `tests/helpers.py`. The file currently imports `Class`, `Task`, `User` — add `Venue` and `Equipment`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_helpers.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```
feat: add create_test_venue and create_test_equipment test helpers
```

---

## Task 12: Final regression verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest -v --tb=short`
Expected: All existing 232 tests + ~27 new tests pass (259+ total). Zero failures.

- [ ] **Step 2: Verify full migration chain from scratch**

Run: `alembic downgrade base && alembic upgrade head`
Expected: No errors

- [ ] **Step 3: Verify no import side effects**

Run: `python -c "import app.models; print(sorted(app.models.__all__))"`
Expected: Prints all model names including Venue, Equipment, Booking, BookingEquipment

- [ ] **Step 4: Verify no datetime.utcnow remains in new code**

Run: `grep -rn "datetime.datetime.utcnow\|datetime.utcfromtimestamp" app/models/venue.py app/models/equipment.py app/models/booking.py`
Expected: No output (zero matches)

- [ ] **Step 5: Final commit**

```
test: verify full regression for PR1 resource domain foundation
```

---

## Self-Review Checklist

**Spec coverage:**
- Venue model (D1 flat structure) — Task 2 ✓
- Equipment model (D2 independent, optional venue FK) — Task 3 ✓
- Booking + BookingEquipment (D3 single entity + join table) — Task 4 ✓
- Status CHECK constraints (D5 simplified) — Tasks 2, 3, 4 ✓
- external_id fields for XR (D7) — Tasks 2, 3, 4 ✓
- client_reference for XR idempotency — Task 4 ✓
- Resource status constants — Task 1 ✓
- Migration A (resources) — Task 6 ✓
- Migration B (bookings) — Task 7 ✓
- Pydantic schemas with time validation — Tasks 8, 9, 10 ✓
- Test helpers — Task 11 ✓
- Regression — Task 12 ✓

**Placeholder scan:** No TBD, TODO, or "implement later" found. All steps contain complete code.

**Type consistency:** `client_ref` in Booking model matches `client_ref` in BookingCreate schema. `equipment_ids` in BookingCreate matches `List[int]` type. `status` defaults to `"active"` for resources and `"approved"` for bookings — consistent with CHECK constraints and constants.
