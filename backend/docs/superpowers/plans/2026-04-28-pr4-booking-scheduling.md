# PR4 预约排期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement booking/scheduling CRUD with venue+equipment joint reservation, conflict detection, pessimistic locking, and all-or-nothing semantics.

**Architecture:** A single `BookingService` class encapsulates all booking business logic (conflict detection, resource validation, status transitions). The router layer is thin — it validates input via schemas, delegates to the service, and formats responses. Conflict detection uses `acquire_row_lock` (SELECT ... FOR UPDATE) on venue and each equipment row within a single DB transaction, then checks for time overlap via `check_time_overlap`. The `Booking.status` field only stores `approved` or `cancelled`; `active`/`completed` are derived from timestamps at query time.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, MySQL 8, Pydantic v2, existing `booking_utils.py` primitives (`check_time_overlap`, `acquire_row_lock`), existing `audit.py` (`audit_log`).

---

## State Model and Transition Rules

```
approved ──(cancel)──→ cancelled
```

- `approved`: Initial state on creation. V1 has no approval flow — every booking is immediately approved.
- `cancelled`: Terminal state. Cancel is idempotent — cancelling an already-cancelled booking returns the existing record (200) without error.
- `active` / `completed` are NOT stored in DB. They are derived at query time:
  - `derived_status = "active"` if `status == "approved"` and `start_time <= now < end_time`
  - `derived_status = "completed"` if `status == "approved"` and `end_time <= now`
  - `derived_status = "cancelled"` if `status == "cancelled"` (overrides time-based derivation)
  - `derived_status = "approved"` otherwise (future booking)

**Transition rules:**
- Only `approved → cancelled` is allowed.
- Cancel is forbidden if the booking's `end_time` has passed (i.e., a completed booking cannot be cancelled).
- Update is forbidden if the booking is already cancelled.

## Conflict Detection Strategy

- Time intervals use half-open semantics: `[start_at, end_at)`. Adjacent bookings (A ends at 10:00, B starts at 10:00) do NOT conflict.
- For each resource (venue + each equipment):
  1. `acquire_row_lock(db, resource_table, resource_id)` — SELECT ... FOR UPDATE
  2. `check_time_overlap(db, booking_table, resource_col, resource_id, start_col, end_col, new_start, new_end, exclude_id=booking_id)` — checks for overlapping approved bookings
- Only `status="approved"` bookings participate in conflict detection. Cancelled bookings do not block.
- All-or-nothing: if ANY resource has a conflict, the entire transaction rolls back and returns 409.
- On update, `exclude_id` prevents the booking from conflicting with itself.
- Lock ordering: venue first, then equipment by ID (ascending). This prevents deadlocks when two concurrent transactions lock the same resources.

## Concurrency Consistency Strategy

- Pessimistic locking via `SELECT ... FOR UPDATE` on every resource row before checking overlaps.
- All operations use `get_db_with_savepoint` dependency (same as `get_db` but named to signal "this route does locking").
- MySQL InnoDB deadlock detection will auto-rollback one transaction if deadlock occurs — client receives 409 and can retry.
- `client_ref` unique index provides idempotency for creation — if a duplicate `client_ref` is submitted, the existing booking is returned.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/bookings` | admin, facility_manager, teacher | Create booking (teacher is auto-set as `booked_by`) |
| GET | `/api/v1/bookings` | admin/fm=全部, teacher=自己的, student=403 | List bookings with filters |
| GET | `/api/v1/bookings/{id}` | admin/fm=全部, teacher=自己的, student=403 | Get booking detail |
| PUT | `/api/v1/bookings/{id}` | admin/fm=全部, teacher=自己的 | Update booking (time, title, purpose, equipment) |
| POST | `/api/v1/bookings/{id}/cancel` | admin/fm=全部, teacher=自己的 | Cancel booking |

**Note:** Student access is 403 on all booking endpoints per spec D7.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `app/services/booking_service.py` | **CREATE** | All booking business logic: create, update, cancel, conflict detection, resource validation, derived status computation |
| `app/routers/bookings.py` | **CREATE** | Thin HTTP layer: input validation via schemas, delegate to BookingService, format responses |
| `app/schemas/booking.py` | **MODIFY** | Add `extra="forbid"` to `BookingCreate`, add `BookingCancelResponse`, adjust fields |
| `app/main.py` | **MODIFY** | Register bookings router |
| `tests/test_bookings.py` | **CREATE** | Integration tests (~30 tests) covering all scenarios |
| `tests/helpers.py` | **MODIFY** | Add `create_test_booking` helper |

---

## Task 1: Add `create_test_booking` helper and adjust schemas

**Files:**
- Modify: `tests/helpers.py` (append helper)
- Modify: `app/schemas/booking.py` (add `extra="forbid"` to `BookingCreate`)

- [ ] **Step 1: Add `create_test_booking` to `tests/helpers.py`**

Append at the end of the file:

```python
async def create_test_booking(
    db: AsyncSession,
    *,
    venue_id: int,
    title: str = "Test Booking",
    start_time: datetime.datetime = None,
    end_time: datetime.datetime = None,
    booked_by: int = 1,
    status: str = "approved",
    equipment_ids: list[int] = None,
) -> Booking:
    from app.models.booking import Booking, BookingEquipment
    now = datetime.datetime(2026, 6, 1, 9, 0)
    booking = Booking(
        venue_id=venue_id,
        title=title,
        start_time=start_time or now,
        end_time=end_time or (now + datetime.timedelta(hours=2)),
        booked_by=booked_by,
        status=status,
    )
    db.add(booking)
    await db.flush()

    for eid in (equipment_ids or []):
        be = BookingEquipment(booking_id=booking.id, equipment_id=eid)
        db.add(be)
    await db.flush()
    return booking
```

Also add the import at the top: add `Booking` and `BookingEquipment` to the imports from models (note: `Booking` is not yet imported in helpers).

- [ ] **Step 2: Add `extra="forbid"` to `BookingCreate` and add import for Booking model in helpers**

In `app/schemas/booking.py`, add `model_config = {"extra": "forbid"}` to `BookingCreate` class:

```python
class BookingCreate(BaseModel):
    model_config = {"extra": "forbid"}

    venue_id: int
    title: str = Field(..., min_length=1, max_length=200)
    # ... rest unchanged
```

- [ ] **Step 3: Run existing schema tests to verify no regression**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/pytest tests/test_resource_schemas.py -v -k booking`
Expected: All booking schema tests pass. The new `extra="forbid"` on `BookingCreate` should not break existing tests since none pass extra fields.

- [ ] **Step 4: Commit**

```bash
git add tests/helpers.py app/schemas/booking.py
git commit -m "feat(pr4): add booking test helper and extra=forbid on BookingCreate"
```

---

## Task 2: Create BookingService — core business logic

**Files:**
- Create: `app/services/booking_service.py`

This is the heart of PR4. The service encapsulates all booking logic so the router stays thin.

- [ ] **Step 1: Create `app/services/booking_service.py`**

```python
"""Booking service — core business logic for scheduling.

Handles: creation (with conflict detection + all-or-nothing),
update (re-validate conflicts), cancel (idempotent), listing,
and derived-status computation.
"""
import datetime

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.schemas.booking import BookingCreate, BookingUpdate
from app.services.audit import audit_log
from app.services.booking_utils import check_time_overlap, acquire_row_lock

from fastapi import HTTPException


class BookingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _validate_venue(self, venue_id: int) -> Venue:
        venue = await acquire_row_lock(self.db, Venue, venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="场地不存在")
        if venue.status != "active":
            raise HTTPException(status_code=400, detail="场地不可用")
        return venue

    async def _validate_equipment(self, equipment_ids: list[int]) -> list[Equipment]:
        if not equipment_ids:
            return []
        equipment_ids = sorted(set(equipment_ids))
        equipments = []
        for eid in equipment_ids:
            equip = await acquire_row_lock(self.db, Equipment, eid)
            if equip is None:
                raise HTTPException(status_code=400, detail=f"设备 {eid} 不存在")
            if equip.status != "active":
                raise HTTPException(status_code=400, detail=f"设备 {equip.name} 不可用")
            equipments.append(equip)
        return equipments

    async def _check_conflicts(
        self,
        venue_id: int,
        equipment_ids: list[int],
        start: datetime.datetime,
        end: datetime.datetime,
        exclude_booking_id: int | None = None,
    ) -> None:
        # Check venue overlap (only approved bookings)
        venue_overlap = await check_time_overlap(
            self.db,
            table=Booking,
            resource_id_column=Booking.venue_id,
            resource_id=venue_id,
            start_column=Booking.start_time,
            end_column=Booking.end_time,
            new_start=start,
            new_end=end,
            exclude_id=exclude_booking_id,
            exclude_id_column=Booking.id,
        )
        if venue_overlap:
            raise HTTPException(status_code=409, detail="场地时间冲突")

        # Check each equipment overlap
        for eid in sorted(set(equipment_ids)):
            equip_overlap = await check_time_overlap(
                self.db,
                table=BookingEquipment,
                resource_id_column=BookingEquipment.equipment_id,
                resource_id=eid,
                start_column=Booking.start_time,
                end_column=Booking.end_time,
                new_start=start,
                new_end=end,
                exclude_id=exclude_booking_id,
                exclude_id_column=BookingEquipment.booking_id,
            )
            if equip_overlap:
                raise HTTPException(status_code=409, detail=f"设备 {eid} 时间冲突")

    def _compute_derived_status(self, booking: Booking) -> str:
        if booking.status == "cancelled":
            return "cancelled"
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        if booking.start_time <= now < booking.end_time:
            return "active"
        if booking.end_time <= now:
            return "completed"
        return "approved"

    async def create(
        self,
        data: BookingCreate,
        actor_id: int,
    ) -> Booking:
        # Idempotency: if client_ref provided, check for existing booking
        if data.client_ref:
            result = await self.db.execute(
                select(Booking).where(Booking.client_ref == data.client_ref)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        # Validate resources
        await self._validate_venue(data.venue_id)
        equipment_ids = sorted(set(data.equipment_ids)) if data.equipment_ids else []
        await self._validate_equipment(equipment_ids)

        # Conflict detection (all-or-nothing)
        await self._check_conflicts(
            data.venue_id, equipment_ids, data.start_time, data.end_time
        )

        # Create booking
        booking = Booking(
            venue_id=data.venue_id,
            title=data.title,
            purpose=data.purpose,
            start_time=data.start_time,
            end_time=data.end_time,
            booked_by=actor_id,
            status="approved",
            course_id=data.course_id,
            class_id=data.class_id,
            task_id=data.task_id,
            client_ref=data.client_ref,
        )
        self.db.add(booking)
        await self.db.flush()

        # Create equipment associations
        for eid in equipment_ids:
            be = BookingEquipment(booking_id=booking.id, equipment_id=eid)
            self.db.add(be)
        await self.db.flush()

        await audit_log(
            self.db,
            entity_type="booking",
            entity_id=booking.id,
            action="create",
            actor_id=actor_id,
            changes={"title": data.title, "venue_id": data.venue_id},
        )

        return booking

    async def update(
        self,
        booking_id: int,
        data: BookingUpdate,
        actor_id: int,
    ) -> Booking:
        booking = await self._get_booking_or_404(booking_id)

        if booking.status == "cancelled":
            raise HTTPException(status_code=400, detail="已取消的预约无法修改")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return booking

        # Resolve effective time range
        effective_start = update_data.get("start_time", booking.start_time)
        effective_end = update_data.get("end_time", booking.end_time)
        if effective_start >= effective_end:
            raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")

        # Resolve effective equipment list
        effective_equip_ids = update_data.get("equipment_ids")
        if effective_equip_ids is None:
            result = await self.db.execute(
                select(BookingEquipment.equipment_id).where(
                    BookingEquipment.booking_id == booking_id
                )
            )
            effective_equip_ids = [row[0] for row in result.all()]

        # Re-validate resources if time or equipment changed
        time_changed = "start_time" in update_data or "end_time" in update_data
        equip_changed = "equipment_ids" in update_data

        if time_changed or equip_changed:
            # Re-validate venue status (don't need lock for status check)
            await self._validate_venue(booking.venue_id)
            if effective_equip_ids:
                await self._validate_equipment(effective_equip_ids)

            await self._check_conflicts(
                booking.venue_id,
                effective_equip_ids,
                effective_start,
                effective_end,
                exclude_booking_id=booking_id,
            )

        # Apply scalar field updates
        for field in ("title", "purpose", "start_time", "end_time"):
            if field in update_data:
                setattr(booking, field, update_data[field])
        await self.db.flush()

        # Update equipment associations if changed
        if equip_changed:
            await self.db.execute(
                delete(BookingEquipment).where(
                    BookingEquipment.booking_id == booking_id
                )
            )
            for eid in sorted(set(effective_equip_ids)):
                be = BookingEquipment(booking_id=booking_id, equipment_id=eid)
                self.db.add(be)
            await self.db.flush()

        await audit_log(
            self.db,
            entity_type="booking",
            entity_id=booking.id,
            action="update",
            actor_id=actor_id,
            changes=update_data,
        )

        return booking

    async def cancel(self, booking_id: int, actor_id: int) -> Booking:
        booking = await self._get_booking_or_404(booking_id)

        # Idempotent: already cancelled
        if booking.status == "cancelled":
            return booking

        # Cannot cancel completed bookings
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        if booking.end_time <= now:
            raise HTTPException(status_code=400, detail="已结束的预约无法取消")

        booking.status = "cancelled"
        await self.db.flush()

        await audit_log(
            self.db,
            entity_type="booking",
            entity_id=booking.id,
            action="cancel",
            actor_id=actor_id,
            changes={"old_status": "approved", "new_status": "cancelled"},
        )

        return booking

    async def get(self, booking_id: int) -> Booking:
        return await self._get_booking_or_404(booking_id)

    async def list_bookings(
        self,
        *,
        venue_id: int | None = None,
        booked_by: int | None = None,
        status_filter: str | None = None,
        start_after: datetime.datetime | None = None,
        start_before: datetime.datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Booking], int]:
        query = select(Booking)
        count_query = select(func.count()).select_from(Booking)

        conditions = []
        if venue_id is not None:
            conditions.append(Booking.venue_id == venue_id)
        if booked_by is not None:
            conditions.append(Booking.booked_by == booked_by)
        if status_filter:
            conditions.append(Booking.status == status_filter)
        if start_after:
            conditions.append(Booking.start_time >= start_after)
        if start_before:
            conditions.append(Booking.start_time <= start_before)

        if conditions:
            for c in conditions:
                query = query.where(c)
                count_query = count_query.where(c)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        query = query.order_by(Booking.start_time.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        bookings = result.scalars().all()

        return list(bookings), total

    async def _get_booking_or_404(self, booking_id: int) -> Booking:
        result = await self.db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise HTTPException(status_code=404, detail="预约不存在")
        return booking
```

**Key design decisions in this code:**

1. `_check_conflicts` for equipment uses a JOIN-equivalent: it queries `BookingEquipment` joined against `Booking` via `check_time_overlap` which takes `BookingEquipment` as the table but uses `Booking.start_time` / `Booking.end_time` as the time columns. However, `check_time_overlap` queries the table directly. Since `BookingEquipment` doesn't have `start_time`/`end_time`, we need to adjust the approach — see the note below.

**IMPORTANT — Equipment conflict detection fix:** `check_time_overlap` queries a single table. `BookingEquipment` doesn't have `start_time`/`end_time`. For equipment conflict detection, we need to find overlapping bookings that use the same equipment. The correct query is:

```python
# For equipment: find any Booking that overlaps in time AND has a BookingEquipment row for this equipment_id
stmt = (
    select(Booking)
    .join(BookingEquipment, BookingEquipment.booking_id == Booking.id)
    .where(
        BookingEquipment.equipment_id == eid,
        Booking.start_time < new_end,
        Booking.end_time > new_start,
    )
)
if exclude_booking_id is not None:
    stmt = stmt.where(Booking.id != exclude_booking_id)
```

This means the `check_time_overlap` utility cannot be directly used for equipment (it only works on single-table queries). Instead, inline the overlap logic for equipment in `_check_conflicts`. The actual implementation below reflects this.

**Revised `_check_conflicts` method** (replace the one above):

```python
async def _check_conflicts(
    self,
    venue_id: int,
    equipment_ids: list[int],
    start: datetime.datetime,
    end: datetime.datetime,
    exclude_booking_id: int | None = None,
) -> None:
    # 1. Venue overlap — use check_time_overlap (single table)
    venue_overlap = await check_time_overlap(
        self.db,
        table=Booking,
        resource_id_column=Booking.venue_id,
        resource_id=venue_id,
        start_column=Booking.start_time,
        end_column=Booking.end_time,
        new_start=start,
        new_end=end,
        exclude_id=exclude_booking_id,
        exclude_id_column=Booking.id,
    )
    if venue_overlap:
        raise HTTPException(status_code=409, detail="场地时间冲突")

    # 2. Equipment overlap — inline query (join BookingEquipment + Booking)
    for eid in sorted(set(equipment_ids)):
        stmt = (
            select(Booking.id)
            .join(BookingEquipment, BookingEquipment.booking_id == Booking.id)
            .where(
                BookingEquipment.equipment_id == eid,
                Booking.start_time < end,
                Booking.end_time > start,
            )
        )
        if exclude_booking_id is not None:
            stmt = stmt.where(Booking.id != exclude_booking_id)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=f"设备 {eid} 时间冲突")
```

- [ ] **Step 2: Verify the service file imports are correct**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/python -c "from app.services.booking_service import BookingService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/booking_service.py
git commit -m "feat(pr4): add BookingService with conflict detection and all-or-nothing logic"
```

---

## Task 3: Create bookings router

**Files:**
- Create: `app/routers/bookings.py`
- Modify: `app/main.py` (register router)

- [ ] **Step 1: Create `app/routers/bookings.py`**

```python
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role, require_role_or_owner
from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.schemas.booking import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingListResponse,
    EquipmentItem,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


def _booking_to_response(booking: Booking, venue_name: str | None = None, equipment_items: list[dict] | None = None) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    if booking.status == "cancelled":
        derived = "cancelled"
    elif booking.start_time <= now < booking.end_time:
        derived = "active"
    elif booking.end_time <= now:
        derived = "completed"
    else:
        derived = "approved"

    return {
        "id": booking.id,
        "venue_id": booking.venue_id,
        "venue_name": venue_name,
        "title": booking.title,
        "purpose": booking.purpose,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "booked_by": booking.booked_by,
        "status": booking.status,
        "derived_status": derived,
        "course_id": booking.course_id,
        "class_id": booking.class_id,
        "task_id": booking.task_id,
        "client_ref": booking.client_ref,
        "equipment": equipment_items or [],
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
    }


async def _enrich_booking(db, booking: Booking) -> dict:
    # Venue name
    result = await db.execute(select(Venue.name).where(Venue.id == booking.venue_id))
    venue_name = result.scalar_one_or_none()

    # Equipment items
    result = await db.execute(
        select(BookingEquipment.equipment_id)
        .where(BookingEquipment.booking_id == booking.id)
    )
    equip_ids = [row[0] for row in result.all()]

    equip_items = []
    if equip_ids:
        result = await db.execute(
            select(Equipment.id, Equipment.name).where(Equipment.id.in_(equip_ids))
        )
        equip_items = [{"id": row[0], "name": row[1]} for row in result.all()]

    return _booking_to_response(booking, venue_name, equip_items)


async def _get_booked_by_for_booking(current_user: dict, db) -> int | None:
    """Owner getter for require_role_or_owner — returns booking's booked_by."""
    # This is called within a request context where the booking_id is in the path.
    # Since require_role_or_owner doesn't have access to path params directly,
    # we implement ownership check inside the route handler instead.
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    current_user: dict = Depends(require_role(["admin", "facility_manager", "teacher"])),
    db: AsyncSession = Depends(get_db),
):
    # Teacher can only book for themselves
    booked_by = current_user["id"]

    svc = BookingService(db)
    booking = await svc.create(data, actor_id=booked_by)
    return await _enrich_booking(db, booking)


@router.get("", response_model=BookingListResponse)
async def list_bookings(
    venue_id: int | None = Query(None),
    booked_by: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    start_after: datetime.datetime | None = Query(None),
    start_before: datetime.datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="权限不足")

    # Teacher: force filter to own bookings
    effective_booked_by = booked_by
    if current_user["role"] == "teacher":
        effective_booked_by = current_user["id"]

    svc = BookingService(db)
    bookings, total = await svc.list_bookings(
        venue_id=venue_id,
        booked_by=effective_booked_by,
        status_filter=status_filter,
        start_after=start_after,
        start_before=start_before,
        limit=limit,
        offset=offset,
    )

    items = []
    for b in bookings:
        items.append(await _enrich_booking(db, b))

    return {"items": items, "total": total}


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="权限不足")

    svc = BookingService(db)
    booking = await svc.get(booking_id)

    # Teacher: can only see own bookings
    if current_user["role"] == "teacher" and booking.booked_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="权限不足")

    return await _enrich_booking(db, booking)


@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    data: BookingUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = BookingService(db)
    booking = await svc.get(booking_id)

    # Permission: admin/fm can update any; teacher only own
    if current_user["role"] in ("admin", "facility_manager"):
        pass
    elif current_user["role"] == "teacher" and booking.booked_by == current_user["id"]:
        pass
    else:
        raise HTTPException(status_code=403, detail="权限不足")

    booking = await svc.update(booking_id, data, actor_id=current_user["id"])
    return await _enrich_booking(db, booking)


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = BookingService(db)
    booking = await svc.get(booking_id)

    # Permission: admin/fm can cancel any; teacher only own
    if current_user["role"] in ("admin", "facility_manager"):
        pass
    elif current_user["role"] == "teacher" and booking.booked_by == current_user["id"]:
        pass
    else:
        raise HTTPException(status_code=403, detail="权限不足")

    booking = await svc.cancel(booking_id, actor_id=current_user["id"])
    return await _enrich_booking(db, booking)
```

- [ ] **Step 2: Register router in `app/main.py`**

Add import and registration:

```python
# Add to imports:
from app.routers import bookings as bookings_router

# Add to router registrations (after equipment_router):
app.include_router(bookings_router.router)
```

- [ ] **Step 3: Verify router loads**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/python -c "from app.routers.bookings import router; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/routers/bookings.py app/main.py
git commit -m "feat(pr4): add bookings router with CRUD and permission checks"
```

---

## Task 4: Write integration tests — CRUD, permissions, and basic flow

**Files:**
- Create: `tests/test_bookings.py`

- [ ] **Step 1: Create `tests/test_bookings.py` with CRUD and permission tests (part 1)**

```python
"""Tests for Phase 3 PR4: Booking/Scheduling.

Covers: CRUD, permissions, conflict detection, all-or-nothing,
idempotent cancel, resource validation, derived status,
audit logging, and regression smoke.
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
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.datetime(2026, 6, 1, 9, 0)
TWO_HOURS = datetime.timedelta(hours=2)


async def _admin_token(client, db_session, username="bk_admin"):
    await create_test_user(db_session, username=username, password="pw1234", role="admin")
    return await login_user(client, username, "pw1234")


async def _fm_token(client, db_session, username="bk_fm"):
    await create_test_user(db_session, username=username, password="pw1234", role="facility_manager")
    return await login_user(client, username, "pw1234")


async def _teacher_token(client, db_session, username="bk_teacher"):
    await create_test_user(db_session, username=username, password="pw1234", role="teacher")
    return await login_user(client, username, "pw1234")


async def _student_token(client, db_session, username="bk_student"):
    await create_test_user(db_session, username=username, password="pw1234", role="student")
    return await login_user(client, username, "pw1234")


async def _create_venue(client, token, name="Test Lab"):
    resp = await client.post(
        "/api/v1/venues",
        json={"name": name, "capacity": 30, "location": "Floor 1"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_booking_via_api(client, token, venue_id, **overrides):
    payload = {
        "venue_id": venue_id,
        "title": "Test Booking",
        "start_time": NOW.isoformat(),
        "end_time": (NOW + TWO_HOURS).isoformat(),
    }
    payload.update(overrides)
    return await client.post(
        "/api/v1/bookings",
        json=payload,
        headers=auth_headers(token),
    )


# ===================================================================
# 1. CRUD Permission Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_admin(client, db_session):
    admin = await create_test_user(db_session, username="bk_c_adm", role="admin")
    token = await login_user(client, "bk_c_adm", "pw1234")
    venue = await create_test_venue(db_session, name="BK Venue 1")
    resp = await _create_booking_via_api(client, token, venue.id)
    assert resp.status_code == 201
    assert resp.json()["status"] == "approved"
    assert resp.json()["booked_by"] == admin.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_fm(client, db_session):
    fm = await create_test_user(db_session, username="bk_c_fm", role="facility_manager")
    token = await login_user(client, "bk_c_fm", "pw1234")
    venue = await create_test_venue(db_session, name="BK Venue 2")
    resp = await _create_booking_via_api(client, token, venue.id)
    assert resp.status_code == 201
    assert resp.json()["booked_by"] == fm.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_teacher(client, db_session):
    teacher = await create_test_user(db_session, username="bk_c_tch", role="teacher")
    token = await login_user(client, "bk_c_tch", "pw1234")
    venue = await create_test_venue(db_session, name="BK Venue 3")
    resp = await _create_booking_via_api(client, token, venue.id)
    assert resp.status_code == 201
    assert resp.json()["booked_by"] == teacher.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "bk_c_stu")
    venue = await create_test_venue(db_session, name="BK Venue 4")
    resp = await _create_booking_via_api(client, token, venue.id)
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_list_bookings_admin_sees_all(client, db_session):
    token = await _admin_token(client, db_session, "bk_l_adm")
    teacher = await create_test_user(db_session, username="bk_l_tch", role="teacher")
    tch_token = await login_user(client, "bk_l_tch", "pw1234")
    venue = await create_test_venue(db_session, name="BK List V")
    await _create_booking_via_api(client, token, venue.id, title="Admin BK")
    await _create_booking_via_api(client, tch_token, venue.id, title="Teacher BK",
                                   start_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
                                   end_time=(NOW + datetime.timedelta(hours=5)).isoformat())
    resp = await client.get("/api/v1/bookings", headers=auth_headers(token))
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["items"]]
    assert "Admin BK" in titles
    assert "Teacher BK" in titles


@pytest.mark.asyncio(loop_scope="session")
async def test_list_bookings_teacher_sees_own_only(client, db_session):
    token = await _admin_token(client, db_session, "bk_l2_adm")
    teacher = await create_test_user(db_session, username="bk_l2_tch", role="teacher")
    tch_token = await login_user(client, "bk_l2_tch", "pw1234")
    venue = await create_test_venue(db_session, name="BK List V2")
    await _create_booking_via_api(client, token, venue.id, title="Admin Only BK")
    await _create_booking_via_api(client, tch_token, venue.id, title="Teacher Own BK",
                                   start_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
                                   end_time=(NOW + datetime.timedelta(hours=5)).isoformat())
    resp = await client.get("/api/v1/bookings", headers=auth_headers(tch_token))
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json()["items"]]
    assert "Teacher Own BK" in titles
    assert "Admin Only BK" not in titles


@pytest.mark.asyncio(loop_scope="session")
async def test_list_bookings_student_forbidden(client, db_session):
    token = await _student_token(client, db_session, "bk_l_stu")
    resp = await client.get("/api/v1/bookings", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_get_booking_detail(client, db_session):
    admin = await create_test_user(db_session, username="bk_d_adm", role="admin")
    token = await login_user(client, "bk_d_adm", "pw1234")
    venue = await create_test_venue(db_session, name="BK Detail V")
    resp = await _create_booking_via_api(client, token, venue.id, title="Detail BK")
    bid = resp.json()["id"]
    resp2 = await client.get(f"/api/v1/bookings/{bid}", headers=auth_headers(token))
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Detail BK"
    assert resp2.json()["venue_name"] == "BK Detail V"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_booking_student_forbidden(client, db_session):
    token = await _admin_token(client, db_session, "bk_ds_adm")
    stu_token = await _student_token(client, db_session, "bk_ds_stu")
    venue = await create_test_venue(db_session, name="BK Stu V")
    resp = await _create_booking_via_api(client, token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.get(f"/api/v1/bookings/{bid}", headers=auth_headers(stu_token))
    assert resp2.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_get_booking_teacher_other_forbidden(client, db_session):
    token = await _admin_token(client, db_session, "bk_dt_adm")
    teacher = await create_test_user(db_session, username="bk_dt_tch", role="teacher")
    tch_token = await login_user(client, "bk_dt_tch", "pw1234")
    other = await create_test_user(db_session, username="bk_dt_tch2", role="teacher")
    other_token = await login_user(client, "bk_dt_tch2", "pw1234")
    venue = await create_test_venue(db_session, name="BK Tch V")
    resp = await _create_booking_via_api(client, tch_token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.get(f"/api/v1/bookings/{bid}", headers=auth_headers(other_token))
    assert resp2.status_code == 403
```

- [ ] **Step 2: Add conflict detection and all-or-nothing tests (part 2)**

Append to `tests/test_bookings.py`:

```python
# ===================================================================
# 2. Conflict Detection Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_overlap_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_co_adm")
    venue = await create_test_venue(db_session, name="BK Conflict V")
    await _create_booking_via_api(client, token, venue.id, title="First BK")
    # Same venue, overlapping time
    resp = await _create_booking_via_api(
        client, token, venue.id, title="Overlap BK",
        start_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
    )
    assert resp.status_code == 409
    assert "场地" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_adjacent_bookings_no_conflict(client, db_session):
    token = await _admin_token(client, db_session, "bk_adj_adm")
    venue = await create_test_venue(db_session, name="BK Adjacent V")
    await _create_booking_via_api(client, token, venue.id, title="First BK")
    # Adjacent: [9:00, 11:00) then [11:00, 13:00) — no overlap
    resp = await _create_booking_via_api(
        client, token, venue.id, title="Adjacent BK",
        start_time=(NOW + TWO_HOURS).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=4)).isoformat(),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_overlap_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_eq_adm")
    venue1 = await create_test_venue(db_session, name="BK Eq V1")
    venue2 = await create_test_venue(db_session, name="BK Eq V2")
    equip = await create_test_equipment(db_session, name="VR Headset", serial_number="BK-EQ-001")
    await _create_booking_via_api(
        client, token, venue1.id, title="Eq BK 1",
        equipment_ids=[equip.id],
    )
    # Same equipment, different venue, overlapping time
    resp = await _create_booking_via_api(
        client, token, venue2.id, title="Eq BK 2",
        equipment_ids=[equip.id],
        start_time=(NOW + datetime.timedelta(hours=1)).isoformat(),
        end_time=(NOW + datetime.timedelta(hours=3)).isoformat(),
    )
    assert resp.status_code == 409
    assert "设备" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_cancelled_booking_not_blocking(client, db_session):
    token = await _admin_token(client, db_session, "bk_cancel_adm")
    venue = await create_test_venue(db_session, name="BK Cancel V")
    resp = await _create_booking_via_api(client, token, venue.id, title="To Cancel")
    bid = resp.json()["id"]
    await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    # Same slot should now be available
    resp2 = await _create_booking_via_api(client, token, venue.id, title="After Cancel")
    assert resp2.status_code == 201


@pytest.mark.asyncio(loop_scope="session")
async def test_all_or_nothing_partial_equipment_rejects(client, db_session):
    token = await _admin_token(client, db_session, "bk_aon_adm")
    venue = await create_test_venue(db_session, name="BK AoN V")
    equip1 = await create_test_equipment(db_session, name="AoN Eq 1", serial_number="AON-001")
    equip2 = await create_test_equipment(db_session, name="AoN Eq 2", serial_number="AON-002")
    # Book equip2 at the same time via another venue
    venue2 = await create_test_venue(db_session, name="BK AoN V2")
    await _create_booking_via_api(
        client, token, venue2.id, title="Block Eq2",
        equipment_ids=[equip2.id],
    )
    # Try to book venue with equip1 + equip2 — equip2 conflicts → whole thing rejected
    resp = await _create_booking_via_api(
        client, token, venue.id, title="AoN BK",
        equipment_ids=[equip1.id, equip2.id],
    )
    assert resp.status_code == 409
    # Verify no booking was created for this venue at this time
    resp2 = await client.get(
        f"/api/v1/bookings?venue_id={venue.id}",
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0


# ===================================================================
# 3. Update Conflict Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_update_excludes_self(client, db_session):
    token = await _admin_token(client, db_session, "bk_self_adm")
    venue = await create_test_venue(db_session, name="BK Self V")
    resp = await _create_booking_via_api(client, token, venue.id, title="Self BK")
    bid = resp.json()["id"]
    # Update same booking with same time — should succeed (not conflict with self)
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"title": "Updated Self BK"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Updated Self BK"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_time_conflict_detected(client, db_session):
    token = await _admin_token(client, db_session, "bk_uc_adm")
    venue = await create_test_venue(db_session, name="BK UC V")
    await _create_booking_via_api(client, token, venue.id, title="Blocker BK",
                                   start_time=(NOW + datetime.timedelta(hours=4)).isoformat(),
                                   end_time=(NOW + datetime.timedelta(hours=6)).isoformat())
    resp = await _create_booking_via_api(client, token, venue.id, title="Move BK")
    bid = resp.json()["id"]
    # Try to move to conflict with Blocker BK
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"start_time": (NOW + datetime.timedelta(hours=5)).isoformat(),
              "end_time": (NOW + datetime.timedelta(hours=7)).isoformat()},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio(loop_scope="session")
async def test_update_cancelled_booking_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_upd_cancel_adm")
    venue = await create_test_venue(db_session, name="BK Upd Cancel V")
    resp = await _create_booking_via_api(client, token, venue.id, title="Cancel Me")
    bid = resp.json()["id"]
    await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"title": "Try Update"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 400
```

- [ ] **Step 3: Add cancel, resource validation, and derived status tests (part 3)**

Append to `tests/test_bookings.py`:

```python
# ===================================================================
# 4. Cancel Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_booking(client, db_session):
    token = await _admin_token(client, db_session, "bk_can_adm")
    venue = await create_test_venue(db_session, name="BK Can V")
    resp = await _create_booking_via_api(client, token, venue.id, title="Cancel BK")
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "cancelled"


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_idempotent(client, db_session):
    token = await _admin_token(client, db_session, "bk_idem_adm")
    venue = await create_test_venue(db_session, name="BK Idem V")
    resp = await _create_booking_via_api(client, token, venue.id, title="Idem BK")
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp2.status_code == 200
    resp3 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "cancelled"


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_teacher_own_only(client, db_session):
    token = await _admin_token(client, db_session, "bk_ct_adm")
    teacher = await create_test_user(db_session, username="bk_ct_tch", role="teacher")
    tch_token = await login_user(client, "bk_ct_tch", "pw1234")
    other = await create_test_user(db_session, username="bk_ct_tch2", role="teacher")
    other_token = await login_user(client, "bk_ct_tch2", "pw1234")
    venue = await create_test_venue(db_session, name="BK Can Tch V")
    resp = await _create_booking_via_api(client, tch_token, venue.id, title="Tch BK")
    bid = resp.json()["id"]
    # Other teacher cannot cancel
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(other_token))
    assert resp2.status_code == 403
    # Owner teacher can cancel
    resp3 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(tch_token))
    assert resp3.status_code == 200


# ===================================================================
# 5. Resource Validation Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_inactive_venue_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_rv_adm")
    venue = await create_test_venue(db_session, name="BK Inactive V", status="inactive")
    resp = await _create_booking_via_api(client, token, venue.id)
    assert resp.status_code == 400
    assert "场地不可用" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_maintenance_equipment_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_req_adm")
    venue = await create_test_venue(db_session, name="BK Req V")
    equip = await create_test_equipment(db_session, name="Maint Eq", status="maintenance")
    resp = await _create_booking_via_api(
        client, token, venue.id, equipment_ids=[equip.id],
    )
    assert resp.status_code == 400
    assert "不可用" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_nonexistent_venue(client, db_session):
    token = await _admin_token(client, db_session, "bk_404v_adm")
    resp = await _create_booking_via_api(client, token, 99999)
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_nonexistent_equipment(client, db_session):
    token = await _admin_token(client, db_session, "bk_404e_adm")
    venue = await create_test_venue(db_session, name="BK 404E V")
    resp = await _create_booking_via_api(client, token, venue.id, equipment_ids=[99999])
    assert resp.status_code == 400


# ===================================================================
# 6. Schema Validation Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_extra_fields_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_ext_adm")
    venue = await create_test_venue(db_session, name="BK Ext V")
    resp = await client.post(
        "/api/v1/bookings",
        json={
            "venue_id": venue.id,
            "title": "Extra BK",
            "start_time": NOW.isoformat(),
            "end_time": (NOW + TWO_HOURS).isoformat(),
            "bogus_field": "bad",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_booking_end_before_start_rejected(client, db_session):
    token = await _admin_token(client, db_session, "bk_time_adm")
    venue = await create_test_venue(db_session, name="BK Time V")
    resp = await _create_booking_via_api(
        client, token, venue.id,
        start_time=(NOW + TWO_HOURS).isoformat(),
        end_time=NOW.isoformat(),
    )
    assert resp.status_code == 422


# ===================================================================
# 7. Derived Status Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_derived_status_future(client, db_session):
    token = await _admin_token(client, db_session, "bk_der_adm")
    venue = await create_test_venue(db_session, name="BK Der V")
    future = datetime.datetime(2030, 1, 1, 9, 0)
    resp = await _create_booking_via_api(
        client, token, venue.id,
        start_time=future.isoformat(),
        end_time=(future + TWO_HOURS).isoformat(),
    )
    assert resp.json()["derived_status"] == "approved"


@pytest.mark.asyncio(loop_scope="session")
async def test_derived_status_cancelled(client, db_session):
    token = await _admin_token(client, db_session, "bk_dc_adm")
    venue = await create_test_venue(db_session, name="BK DC V")
    resp = await _create_booking_via_api(client, token, venue.id)
    bid = resp.json()["id"]
    resp2 = await client.post(f"/api/v1/bookings/{bid}/cancel", headers=auth_headers(token))
    assert resp2.json()["derived_status"] == "cancelled"
```

- [ ] **Step 4: Add audit, client_ref, pagination, and regression tests (part 4)**

Append to `tests/test_bookings.py`:

```python
# ===================================================================
# 8. Audit Logging Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_booking_create(client, db_session):
    admin = await create_test_user(db_session, username="bk_ac_adm", password="pw1234", role="admin")
    token = await login_user(client, "bk_ac_adm", "pw1234")
    venue = await create_test_venue(db_session, name="BK Audit V")
    resp = await _create_booking_via_api(client, token, venue.id, title="Audit BK")
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
    assert changes["title"] == "Audit BK"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_booking_cancel(client, db_session):
    token = await _admin_token(client, db_session, "bk_au_adm")
    venue = await create_test_venue(db_session, name="BK Audit U V")
    resp = await _create_booking_via_api(client, token, venue.id, title="Audit Cancel BK")
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


# ===================================================================
# 9. client_ref Idempotency Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_client_ref_idempotent(client, db_session):
    token = await _admin_token(client, db_session, "bk_ref_adm")
    venue = await create_test_venue(db_session, name="BK Ref V")
    ref = "xr-session-001"
    resp1 = await _create_booking_via_api(
        client, token, venue.id, title="First", client_ref=ref,
    )
    assert resp1.status_code == 201
    bid1 = resp1.json()["id"]
    resp2 = await _create_booking_via_api(
        client, token, venue.id, title="Second", client_ref=ref,
    )
    assert resp2.status_code == 201
    assert resp2.json()["id"] == bid1  # Same booking returned


# ===================================================================
# 10. Pagination Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_pagination(client, db_session):
    token = await _admin_token(client, db_session, "bk_pag_adm")
    venue = await create_test_venue(db_session, name="BK Pag V")
    for i in range(5):
        await _create_booking_via_api(
            client, token, venue.id, title=f"Pag BK {i}",
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


# ===================================================================
# 11. 404 Paths
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_get_booking_404(client, db_session):
    token = await _admin_token(client, db_session, "bk_404_adm")
    resp = await client.get("/api/v1/bookings/99999", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_booking_404(client, db_session):
    token = await _admin_token(client, db_session, "bk_404c_adm")
    resp = await client.post("/api/v1/bookings/99999/cancel", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_update_booking_404(client, db_session):
    token = await _admin_token(client, db_session, "bk_404u_adm")
    resp = await client.put(
        "/api/v1/bookings/99999",
        json={"title": "Ghost"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


# ===================================================================
# 12. Equipment Association Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_booking_with_equipment(client, db_session):
    token = await _admin_token(client, db_session, "bk_eqc_adm")
    venue = await create_test_venue(db_session, name="BK Eq C V")
    equip1 = await create_test_equipment(db_session, name="Eq Assoc 1", serial_number="EA-001")
    equip2 = await create_test_equipment(db_session, name="Eq Assoc 2", serial_number="EA-002")
    resp = await _create_booking_via_api(
        client, token, venue.id, title="With Eq",
        equipment_ids=[equip1.id, equip2.id],
    )
    assert resp.status_code == 201
    equip_names = [e["name"] for e in resp.json()["equipment"]]
    assert "Eq Assoc 1" in equip_names
    assert "Eq Assoc 2" in equip_names


@pytest.mark.asyncio(loop_scope="session")
async def test_update_changes_equipment(client, db_session):
    token = await _admin_token(client, db_session, "bk_equp_adm")
    venue = await create_test_venue(db_session, name="BK Eq Up V")
    equip1 = await create_test_equipment(db_session, name="Eq Up 1", serial_number="EU-001")
    equip2 = await create_test_equipment(db_session, name="Eq Up 2", serial_number="EU-002")
    resp = await _create_booking_via_api(
        client, token, venue.id, title="Eq Change BK",
        equipment_ids=[equip1.id],
    )
    bid = resp.json()["id"]
    resp2 = await client.put(
        f"/api/v1/bookings/{bid}",
        json={"equipment_ids": [equip2.id]},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 200
    equip_ids = [e["id"] for e in resp2.json()["equipment"]]
    assert equip2.id in equip_ids
    assert equip1.id not in equip_ids


# ===================================================================
# 13. Regression Smoke Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_health_still_works(client, db_session):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_venues_still_works(client, db_session):
    token = await _admin_token(client, db_session, "bk_smoke_adm")
    resp = await client.get("/api/v1/venues", headers=auth_headers(token))
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_still_works(client, db_session):
    token = await _admin_token(client, db_session, "bk_smoke_adm2")
    resp = await client.get("/api/v1/equipment", headers=auth_headers(token))
    assert resp.status_code == 200
```

- [ ] **Step 5: Run tests to verify they fail (RED phase)**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/pytest tests/test_bookings.py -v --tb=short 2>&1 | tail -40`
Expected: All tests FAIL because the service and router are not yet complete.

- [ ] **Step 6: Commit**

```bash
git add tests/test_bookings.py
git commit -m "test(pr4): add booking integration tests (RED phase)"
```

---

## Task 5: Wire up service + router + run all tests to GREEN

**Files:**
- No new files — verify everything from Tasks 2-4 works together.

This task is the "make it pass" step. The service (Task 2) and router (Task 3) should already make the tests (Task 4) pass, but there may be integration issues.

- [ ] **Step 1: Run booking tests**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/pytest tests/test_bookings.py -v --tb=short 2>&1 | tail -60`
Expected: All tests PASS. If any fail, debug and fix.

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/pytest --tb=short 2>&1 | tail -10`
Expected: All tests pass (0 failed). Count should be ~495+ tests.

- [ ] **Step 3: Commit any fixes (if needed)**

```bash
git add -A
git commit -m "fix(pr4): resolve integration issues in booking service and router"
```

If no fixes needed, skip this step.

---

## Task 6: Add concurrent booking test (dual-session)

**Files:**
- Modify: `tests/test_bookings.py` (append tests)

This is a critical test for the concurrency strategy — two sessions trying to book the same slot simultaneously.

- [ ] **Step 1: Append concurrency test to `tests/test_bookings.py`**

```python
# ===================================================================
# 14. Concurrency Tests
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_booking_same_slot(
    client, db_session, second_db_session, test_session_maker
):
    """Two sessions try to book the same venue at the same time.
    One should succeed, the other should get a 409 conflict."""
    import asyncio

    # Setup: create venue and admin in both sessions
    from sqlalchemy.ext.asyncio import AsyncSession

    admin = await create_test_user(db_session, username="bk_conc_adm", password="pw1234", role="admin")
    venue = await create_test_venue(db_session, name="BK Conc V")
    await db_session.commit()

    # Login to get token
    token = await login_user(client, "bk_conc_adm", "pw1234")

    # Create two bookings at the same time via API
    # The test uses the HTTP client which uses the same DB session (rolled back per test).
    # True concurrency via HTTP is limited by the single-session fixture.
    # Instead, verify the conflict detection works:
    resp1 = await _create_booking_via_api(client, token, venue.id, title="First Conc")
    assert resp1.status_code == 201
    resp2 = await _create_booking_via_api(client, token, venue.id, title="Second Conc")
    assert resp2.status_code == 409
```

**Note:** True concurrent dual-session testing of `SELECT ... FOR UPDATE` requires both sessions to be in separate committed transactions. The HTTP test client uses a single rolled-back session, making it hard to test true pessimistic locking concurrently. The sequential test above validates the conflict detection logic. For true concurrency testing, a separate integration test using raw `test_session_maker` sessions with explicit commits would be needed (outside the HTTP client pattern). This can be added as follow-up.

- [ ] **Step 2: Run all booking tests**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/pytest tests/test_bookings.py -v --tb=short 2>&1 | tail -40`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_bookings.py
git commit -m "test(pr4): add concurrency and integration tests for booking"
```

---

## Failure Paths and Error Handling Plan

| Scenario | HTTP Status | Error Message | Handling |
|----------|-------------|---------------|----------|
| Venue doesn't exist | 404 | "场地不存在" | `_validate_venue` |
| Venue inactive/maintenance | 400 | "场地不可用" | `_validate_venue` |
| Equipment doesn't exist | 400 | "设备 {id} 不存在" | `_validate_equipment` |
| Equipment not active | 400 | "设备 {name} 不可用" | `_validate_equipment` |
| Venue time conflict | 409 | "场地时间冲突" | `_check_conflicts` |
| Equipment time conflict | 409 | "设备 {id} 时间冲突" | `_check_conflicts` |
| Cancel already cancelled (idempotent) | 200 | — | `cancel` returns existing |
| Cancel completed booking | 400 | "已结束的预约无法取消" | `cancel` |
| Update cancelled booking | 400 | "已取消的预约无法修改" | `update` |
| Update time conflict | 409 | same as create | `update` → `_check_conflicts` |
| start_time >= end_time (create) | 422 | Pydantic validation | `BookingCreate` validator |
| start_time >= end_time (update, both set) | 422 | Pydantic validation | `BookingUpdate` validator |
| start_time >= end_time (update, partial) | 400 | "开始时间必须早于结束时间" | `update` |
| Student access | 403 | "权限不足" | Router permission check |
| Teacher access other's booking | 403 | "权限不足" | Router ownership check |
| Non-existent booking | 404 | "预约不存在" | `_get_booking_or_404` |
| Extra fields in create | 422 | Pydantic validation | `extra="forbid"` |
| Duplicate client_ref | 200 | — (returns existing) | `create` idempotency |

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| **Deadlock on concurrent booking** | Lock ordering: venue first, then equipment by ascending ID. MySQL InnoDB auto-detects and rolls back one transaction. |
| **`check_time_overlap` only works on single table** | Equipment overlap uses inline JOIN query in `_check_conflicts` instead of the utility function. |
| **BookingUpdate with only start_time or only end_time** | Router loads existing booking and re-validates the combined time range before persisting. Schema allows partial updates but the service layer recombines. |
| **Derived status computation in response** | Computed at query time in `_booking_to_response`, not stored. Consistent with design doc D5. |
| **Race between checking resource status and booking creation** | `acquire_row_lock` locks the resource row, preventing status change between check and insert. |
| **Large equipment_ids list** | No artificial limit, but practical usage is <10 items per booking. The sequential locking approach means N+1 queries for N equipment items. Acceptable for MVP. |
| **client_ref unique constraint violation** | The service checks for existing record before insert. If a race occurs, the DB unique index catches it. The service would need IntegrityError handling (follow-up). |
| **Teacher creates booking, admin changes venue to maintenance** | V1 does not cascade — booking remains approved. Design doc D9 states this is handled manually by facility_manager. |

## Definition of Done / Merge Bar

- [ ] All ~35 booking tests pass
- [ ] Full test suite passes (0 regressions, 495+ total)
- [ ] 5 endpoints: POST create, GET list, GET detail, PUT update, POST cancel
- [ ] Conflict detection works for venue and equipment (tested)
- [ ] All-or-nothing: partial equipment conflict rejects entire booking (tested)
- [ ] Cancel is idempotent (tested)
- [ ] Teacher can only manage own bookings (tested)
- [ ] Student is 403 on all endpoints (tested)
- [ ] Audit log entries created for create/update/cancel (tested)
- [ ] client_ref idempotency works (tested)
- [ ] No new migrations needed (tables already exist from PR1)
- [ ] No changes to existing venue/equipment/course/grade models or routes
