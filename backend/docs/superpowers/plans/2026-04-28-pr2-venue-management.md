# Phase 3 PR2: Venue Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the minimum-viable venue management loop — CRUD, status lifecycle, availability configuration, permission enforcement, and audit integration — so that PR4 (booking) can depend on venue status and availability windows.

**Architecture:** Single new router (`app/routers/venues.py`) following the flat CRUD pattern established in `courses.py`. No new service layer needed for PR2 — all logic fits within the router handlers. Availability configuration uses a simple `venue_availability` table (weekly recurring time windows + manual blackout periods). The venue model from PR1 gains `venue_type` and `metadata_json` fields via a new migration.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, MySQL 8, Alembic

---

## Availability Model Decision

**Chosen approach: Fixed weekly slots + manual blackout intervals**

- A `venue_availability` table stores recurring weekly time windows per venue (e.g., Mon 08:00–12:00, Mon 13:00–17:00)
- A `venue_blackout` table stores date-range exceptions (e.g., 2026-05-01 ~ 2026-05-03 holiday)
- PR4's booking conflict check will: (1) verify the requested slot falls within a weekly window, (2) verify no blackout overlaps the requested period

**Why not a rule engine:** The user explicitly warned against evolving into a scheduling rule engine. Weekly slots + blackouts cover 90% of real training venue scenarios (labs open fixed hours, closed on holidays, occasional maintenance shutdowns) without introducing recurrence rules, cron expressions, or exception hierarchies.

**Why not venue_calendar / iCal:** Would require parsing external formats, timezone handling complexity, and synchronization logic — all out of scope for MVP.

**Trade-off:** Adding `venue_type` and `metadata_json` to the venue model means a new migration. This is justified because (a) the user explicitly asked for "venue type" and "notes/metadata", and (b) these fields are cheap (nullable columns, no FK) and enable future filtering without schema changes.

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `app/models/venue.py` | Add `venue_type`, `metadata_json` columns |
| Create | `app/models/venue_availability.py` | Weekly recurring availability windows |
| Create | `app/models/venue_blackout.py` | Manual blackout date ranges |
| Modify | `app/models/__init__.py` | Register new models |
| Create | `alembic/versions/<hash>_add_venue_type_availability_blackout.py` | Migration for new columns + 2 new tables |
| Modify | `app/schemas/venue.py` | Add venue_type, metadata, availability schemas |
| Create | `app/routers/venues.py` | All venue CRUD endpoints |
| Modify | `app/main.py` | Register venue router |
| Modify | `tests/helpers.py` | Add availability/blackout helpers |
| Create | `tests/test_venues.py` | Full CRUD + permission + audit + availability tests |

---

## Task 1: Extend Venue model with venue_type and metadata_json

**Files:**
- Modify: `app/models/venue.py`
- Modify: `app/models/__init__.py` (if needed — already registered)

- [ ] **Step 1: Write the failing test**

In `tests/test_venues.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_venue_with_type_and_metadata(db_session: AsyncSession):
    venue = Venue(
        name="XR Lab A",
        venue_type="lab",
        metadata_json='{"projector": true, "whiteboard": false}',
    )
    db_session.add(venue)
    await db_session.flush()

    result = await db_session.execute(select(Venue).where(Venue.id == venue.id))
    found = result.scalar_one()
    assert found.venue_type == "lab"
    assert found.metadata_json == '{"projector": true, "whiteboard": false}'
    assert found.status == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_venues.py::test_venue_with_type_and_metadata -v`
Expected: FAIL — `Venue` has no attribute `venue_type`

- [ ] **Step 3: Implement model changes**

In `app/models/venue.py`, add after `external_id`:

```python
venue_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_venues.py::test_venue_with_type_and_metadata -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/venue.py tests/test_venues.py
git commit -m "feat: add venue_type and metadata_json columns to Venue model"
```

---

## Task 2: Create VenueAvailability and VenueBlackout models

**Files:**
- Create: `app/models/venue_availability.py`
- Create: `app/models/venue_blackout.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_venues.py`:

```python
from app.models.venue_availability import VenueAvailability
from app.models.venue_blackout import VenueBlackout


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_availability_create(db_session: AsyncSession):
    venue = await create_test_venue(db_session, name="Avail Test Venue")
    avail = VenueAvailability(
        venue_id=venue.id,
        day_of_week=1,  # Monday
        start_time=datetime.time(8, 0),
        end_time=datetime.time(12, 0),
    )
    db_session.add(avail)
    await db_session.flush()
    assert avail.id is not None
    assert avail.day_of_week == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_blackout_create(db_session: AsyncSession):
    venue = await create_test_venue(db_session, name="Blackout Test Venue")
    blackout = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 5, 1),
        end_date=datetime.date(2026, 5, 3),
        reason="Labor Day holiday",
    )
    db_session.add(blackout)
    await db_session.flush()
    assert blackout.id is not None
    assert blackout.reason == "Labor Day holiday"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_venues.py::test_venue_availability_create -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create VenueAvailability model**

Create `app/models/venue_availability.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Time, Date, Text, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VenueAvailability(Base):
    __tablename__ = "venue_availability"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="chk_availability_dow"),
        UniqueConstraint("venue_id", "day_of_week", "start_time", "end_time", name="uq_availability_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
```

- [ ] **Step 4: Create VenueBlackout model**

Create `app/models/venue_blackout.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Date, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VenueBlackout(Base):
    __tablename__ = "venue_blackout"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="chk_blackout_date_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
```

- [ ] **Step 5: Register in `app/models/__init__.py`**

Add imports and `__all__` entries for `VenueAvailability` and `VenueBlackout`.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/test_venues.py::test_venue_availability_create tests/test_venues.py::test_venue_blackout_create -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/models/venue_availability.py app/models/venue_blackout.py app/models/__init__.py tests/test_venues.py
git commit -m "feat: add VenueAvailability and VenueBlackout models"
```

---

## Task 3: Create Alembic migration

**Files:**
- Create: `alembic/versions/<hash>_add_venue_type_availability_blackout.py`

- [ ] **Step 1: Generate migration**

Run: `.venv/bin/python -m alembic revision --autogenerate -m "add venue_type availability and blackout tables"`

- [ ] **Step 2: Review and fix the generated migration**

Verify:
- `down_revision` points to `eaa79625a9ad` (the current head for resource tables)
- Adds `venue_type` VARCHAR(50) NULL and `metadata_json` TEXT NULL to `venues`
- Creates `venue_availability` table with FK, CHECK on day_of_week, unique constraint
- Creates `venue_blackout` table with FK, CHECK on date range
- Downgrade drops `venue_availability` and `venue_blackout` tables, then drops the 2 new columns from `venues`

- [ ] **Step 3: Verify migration up/down**

Run:
```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic downgrade -1
.venv/bin/python -m alembic upgrade head
```
Expected: No errors on any step.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add migration for venue_type, availability, and blackout tables"
```

---

## Task 4: Update Venue schemas

**Files:**
- Modify: `app/schemas/venue.py`

- [ ] **Step 1: Write the failing schema tests**

In `tests/test_venues.py`:

```python
from app.schemas.venue import VenueCreate, VenueUpdate, VenueResponse
from app.schemas.venue import AvailabilitySlot, AvailabilitySlotsUpdate
from app.schemas.venue import BlackoutCreate, BlackoutResponse


def test_venue_create_with_type():
    data = VenueCreate(name="Lab", venue_type="lab")
    assert data.venue_type == "lab"


def test_venue_create_rejects_invalid_type():
    with pytest.raises(ValidationError):
        VenueCreate(name="Bad", venue_type="x" * 51)


def test_availability_slot_valid():
    slot = AvailabilitySlot(day_of_week=0, start_time="08:00", end_time="12:00")
    assert slot.day_of_week == 0


def test_availability_slot_rejects_invalid_dow():
    with pytest.raises(ValidationError):
        AvailabilitySlot(day_of_week=7, start_time="08:00", end_time="12:00")


def test_availability_slot_rejects_end_before_start():
    with pytest.raises(ValidationError):
        AvailabilitySlot(day_of_week=0, start_time="12:00", end_time="08:00")


def test_blackout_create_valid():
    data = BlackoutCreate(
        start_date="2026-05-01",
        end_date="2026-05-03",
        reason="Holiday",
    )
    assert data.reason == "Holiday"


def test_blackout_rejects_end_before_start():
    with pytest.raises(ValidationError):
        BlackoutCreate(start_date="2026-05-03", end_date="2026-05-01")
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement schema changes**

Update `app/schemas/venue.py` to add:

1. `venue_type` field to VenueCreate/Update/Response (Optional, max_length=50, validated against a set of known types: `"lab"`, `"classroom"`, `"workshop"`, `"meeting_room"`, `"outdoor"`, `"other"`)
2. `metadata_json` field to VenueCreate/Update/Response (Optional[str], max_length=5000)
3. New schemas:

```python
class AvailabilitySlot(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str = Field(..., pattern=r'^\d{2}:\d{2}$')
    end_time: str = Field(..., pattern=r'^\d{2}:\d{2}$')

    @model_validator(mode="after")
    def validate_time_order(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class AvailabilitySlotsUpdate(BaseModel):
    slots: List[AvailabilitySlot]


class BlackoutCreate(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


class BlackoutResponse(BaseModel):
    id: int
    venue_id: int
    start_date: date
    end_date: date
    reason: Optional[str] = None
```

4. Add `availability` and `blackouts` fields to VenueResponse
5. `venue_type` is free-text with max_length constraint only — no fixed enum, to allow flexible categorization

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```bash
git add app/schemas/venue.py tests/test_venues.py
git commit -m "feat: update venue schemas with type, metadata, availability, and blackout"
```

---

## Task 5: Create Venue CRUD router

**Files:**
- Create: `app/routers/venues.py`
- Modify: `app/main.py`

This is the core task. The router implements 7 endpoints:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/venues` | admin, facility_manager | Create venue |
| GET | `/api/v1/venues` | admin, facility_manager, teacher | List venues (with filters) |
| GET | `/api/v1/venues/{id}` | admin, facility_manager, teacher | Get venue detail |
| PUT | `/api/v1/venues/{id}` | admin, facility_manager | Update venue fields |
| PATCH | `/api/v1/venues/{id}/status` | admin, facility_manager | Change venue status |
| PUT | `/api/v1/venues/{id}/availability` | admin, facility_manager | Replace weekly availability slots |
| POST | `/api/v1/venues/{id}/blackouts` | admin, facility_manager | Add blackout period |
| GET | `/api/v1/venues/{id}/blackouts` | admin, facility_manager, teacher | List blackouts |
| DELETE | `/api/v1/venues/{id}/blackouts/{bid}` | admin, facility_manager | Delete blackout |

- [ ] **Step 1: Write the failing endpoint tests**

In `tests/test_venues.py`, write integration tests using the `client` fixture:

```python
# --- CRUD ---
async def test_create_venue_admin(client, db_session):
async def test_create_venue_facility_manager(client, db_session):
async def test_create_venue_teacher_forbidden(client, db_session):
async def test_create_venue_student_forbidden(client, db_session):
async def test_list_venues_teacher_sees_active_only(client, db_session):
async def test_list_venues_student_forbidden(client, db_session):
async def test_get_venue_detail(client, db_session):
async def test_update_venue_admin(client, db_session):
async def test_update_venue_teacher_forbidden(client, db_session):
async def test_change_venue_status(client, db_session):

# --- Availability ---
async def test_set_availability(client, db_session):
async def test_set_availability_replaces_previous(client, db_session):

# --- Blackout ---
async def test_create_blackout(client, db_session):
async def test_list_blackouts(client, db_session):
async def test_delete_blackout(client, db_session):

# --- Audit ---
async def test_create_venue_audit_logged(client, db_session):
async def test_status_change_audit_logged(client, db_session):
```

Each test creates users via helpers, logs in to get a token, and makes HTTP requests. Follow the pattern in existing tests (`tests/test_users.py`, `tests/test_tasks_extended.py`).

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement the router**

Create `app/routers/venues.py`:

```python
router = APIRouter(prefix="/api/v1/venues", tags=["venues"])
```

Key implementation details:

**Create (POST /):**
- `require_role(["admin", "facility_manager"])`
- Validate `venue_type` against allowed set if provided
- Validate `capacity >= 0` if provided
- Create Venue with status="active"
- `audit_log(entity_type="venue", action="create", ...)`
- Return 201

**List (GET /):**
- `require_role(["admin", "facility_manager", "teacher"])`
- Teachers see only `status="active"` venues (no inactive/maintenance leakage)
- Admin/facility_manager see all statuses
- Filter params: `status`, `venue_type`, `capacity_min`, `capacity_max`
- Pagination: `offset`/`limit` (default limit=20, max=100)
- Return `VenueListResponse` with `total`

**Detail (GET /{id}):**
- Same role gating as list
- Teachers can only see active venues (404 for inactive, avoiding info leak)
- Include availability slots in response

**Update (PUT /{id}):**
- `require_role(["admin", "facility_manager"])`
- `VenueUpdate` with `extra="forbid"`
- `model_dump(exclude_unset=True)` + setattr loop
- If status changes in this endpoint, still allowed but triggers audit with `action="status_change"`
- `audit_log(entity_type="venue", action="update", ...)`

**Status change (PATCH /{id}/status):**
- `require_role(["admin", "facility_manager"])`
- Accept `{"status": "inactive"|"maintenance"|"active"}`
- Validate transition: any → any is allowed (no state machine enforcement in V1)
- Special handling for inactive/maintenance: warn in audit log changes that existing future bookings may be affected
- `audit_log(entity_type="venue", action="status_change", ...)`

**Availability (PUT /{id}/availability):**
- `require_role(["admin", "facility_manager"])`
- Accept `AvailabilitySlotsUpdate` with list of slots
- Delete existing availability for this venue, insert new slots (full replacement)
- Validate no duplicate day_of_week+start_time+end_time within the request
- `audit_log(entity_type="venue", action="update_availability", ...)`

**Blackout CRUD:**
- Create: `require_role(["admin", "facility_manager"])`, accept `BlackoutCreate`
- List: same roles as venue read
- Delete: `require_role(["admin", "facility_manager"])`, only the creator or admin can delete

- [ ] **Step 4: Register router in `app/main.py`**

```python
from app.routers import venues as venues_router
app.include_router(venues_router.router)
```

- [ ] **Step 5: Run tests**

- [ ] **Step 6: Commit**

```bash
git add app/routers/venues.py app/main.py tests/test_venues.py
git commit -m "feat: add venue CRUD router with availability and blackout management"
```

---

## Task 6: Teacher read scope validation

This is a focused sub-task within the router to ensure no cross-organization data leakage.

**Validation rules:**
- Teachers calling `GET /api/v1/venues` only see `status="active"` venues — they cannot discover inactive or maintenance venues
- Teachers calling `GET /api/v1/venues/{id}` get 404 (not 403) for non-active venues — prevents existence probing
- No course/class context filtering for venue reads — venues are global resources, not scoped to courses. Teachers see ALL active venues regardless of which course they teach. The course/class/task FKs on bookings handle data isolation at the booking level (PR4).

**Implementation:** Already covered in Task 5's list/detail endpoints. This task ensures the tests explicitly verify these behaviors.

- [ ] **Step 1: Add explicit scope tests**

```python
async def test_teacher_cannot_see_inactive_venue_in_list(client, db_session):
    # Create inactive venue, verify it doesn't appear in teacher's list
    
async def test_teacher_gets_404_for_inactive_venue_detail(client, db_session):
    # Create inactive venue, request detail as teacher, expect 404
```

- [ ] **Step 2: Run tests**

- [ ] **Step 3: Commit (if separate from Task 5)**

---

## Task 7: Deactivation semantics and booking compatibility

**Key decision: Soft status, not soft delete**

Venues are never hard-deleted. Status transitions handle lifecycle:
- `active` → `inactive`: Venue is removed from teacher-visible lists but remains in DB
- `active` → `maintenance`: Same visibility as inactive, but semantically different (temporary)
- `inactive` / `maintenance` → `active`: Re-enable

**Booking compatibility (for PR4):**
- When a venue is set to `inactive` or `maintenance`, existing approved bookings are NOT cancelled (per design decision D5 in the OpenSpec design doc)
- PR4's booking creation will check `venue.status == "active"` before creating a booking
- The audit log records the status change with the old and new status, enabling future tooling to identify affected bookings

**No additional code needed for this task** — the status field already exists, the transition is handled in the PATCH endpoint, and the audit log captures the change. This task exists to validate the semantics are correct.

- [ ] **Step 1: Write validation test**

```python
async def test_deactivate_venue_does_not_delete(client, db_session):
    # Create venue, set to inactive, verify it still exists in DB
    # Verify audit log entry with old_status and new_status
```

- [ ] **Step 2: Run tests**

---

## Task 8: Full regression and verification

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass (336 existing + ~25 new venue tests)

- [ ] **Step 2: Verify migration chain**

Run:
```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic downgrade -1
.venv/bin/python -m alembic upgrade head
```

- [ ] **Step 3: Verify no existing API regression**

Spot-check that existing endpoints still work:
- `GET /api/auth/login`
- `GET /api/courses`
- `GET /api/tasks`
- `GET /health`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete PR2 venue management with availability and audit"
```

---

## Validation Rules Summary

| Field | Rule | Enforced At |
|-------|------|-------------|
| `name` | Required, 1-100 chars | Schema |
| `venue_type` | Optional, max 50 chars, no fixed enum (free-text for MVP) | Schema |
| `capacity` | Optional int, `>= 0` if provided | Schema + Route |
| `location` | Optional, max 200 chars | Schema |
| `description` | Optional text | Schema |
| `status` | `active`/`inactive`/`maintenance`, default `active` | Schema (update only) + DB CHECK |
| `external_id` | Optional, max 100 chars | Schema |
| `metadata_json` | Optional, max 5000 chars | Schema |
| `day_of_week` | 0-6 (Mon-Sun) | Schema + DB CHECK |
| `start_time`/`end_time` | HH:MM format, start < end | Schema + DB CHECK |
| `blackout.start_date`/`end_date` | Valid dates, end >= start | Schema + DB CHECK |
| `blackout.reason` | Optional, max 200 chars | Schema |

## Risks and Edge Cases

| Risk | Mitigation |
|------|------------|
| Teacher sees inactive venue name via booking detail (PR4) | Booking response includes `venue_name` — this is acceptable since the teacher already had a relationship with the venue when the booking was made |
| Availability slots with overlapping time ranges on same day | UniqueConstraint `(venue_id, day_of_week, start_time, end_time)` prevents duplicates; route validates no overlaps within request |
| Blackout date range spans months | No artificial limit — facility managers own this. Audit log tracks who set it |
| Concurrent availability replacement (two admins editing same venue) | `acquire_row_lock` on venue row before deleting/reinserting availability slots |
| `metadata_json` contains invalid JSON | Route handler validates `json.loads()` succeeds before persisting |
| Venue with future bookings is set to inactive | Design decision: do NOT auto-cancel bookings. Audit log records the change for manual follow-up |

## Definition of Done / Merge Bar

- [ ] All 7 endpoints work with correct HTTP status codes
- [ ] Permission matrix enforced: admin/facility_manager write, teacher read active-only, student 403
- [ ] All write operations produce AuditLog entries with correct entity_type and action
- [ ] Availability slots can be set, replaced, and queried
- [ ] Blackout periods can be created, listed, and deleted
- [ ] `venue_type` and `metadata_json` fields persist correctly
- [ ] Teacher cannot discover inactive/maintenance venues via list or detail endpoints
- [ ] Migration up/down verified clean
- [ ] All existing tests pass (zero regression)
- [ ] New test count >= 20 covering CRUD, permissions, availability, blackouts, and audit
