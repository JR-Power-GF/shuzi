# PR3: Equipment Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the equipment management CRUD router with permission control, audit logging, and venue association — completing the equipment domain foundation needed for PR4 booking.

**Architecture:** Follow the exact pattern established by `app/routers/venues.py`. Single equipment router with 7 endpoints. No new models or migrations — the Equipment model, schema, and DB table already exist. Add `EquipmentStatusUpdate` and `extra="forbid"` to `EquipmentCreate`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, MySQL 8

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `app/routers/equipment.py` | Create | Equipment CRUD router (7 endpoints) |
| `app/schemas/equipment.py` | Modify | Add `EquipmentStatusUpdate`, `extra="forbid"` to Create |
| `app/main.py` | Modify | Register equipment router |
| `tests/test_equipment.py` | Create | Integration tests (~55 tests) |

No model changes. No migration. The equipment table and model already exist from PR1.

---

## Equipment-to-Venue Relation Decision

**Design:** `venue_id` is an optional FK on Equipment (`SET NULL` on delete). This means:
- A device can be assigned to a venue (fixed equipment like VR headsets in Lab 101)
- A device can be unassigned / mobile (portable projectors, laptops)
- When a venue is deleted, the equipment stays but loses its venue assignment
- The router resolves `venue_name` at query time by joining/lookup on venues table

**Why not a junction table:** One equipment item is physically in one place at a time (or nowhere). A many-to-many would imply simultaneous multi-venue presence, which doesn't match the physical world for individual devices.

---

## Validation Rules & Status Model

**Status values:** `active`, `inactive`, `maintenance` (same as venues)
- `active` → available for booking in PR4
- `inactive` → permanently retired / not bookable
- `maintenance` → temporarily unavailable, expected to return

**Validation rules:**
- `name`: required, 1-100 chars, non-empty
- `category`: optional, max 50 chars (free text, not enum — keep MVP)
- `serial_number`: optional, 1-100 chars, unique across all equipment
- `venue_id`: optional, must reference existing venue if provided
- `status`: validated via regex `^(active|inactive|maintenance)$`
- `extra="forbid"` on both Create and Update schemas

---

## Task 1: Update Equipment Schemas

**Files:**
- Modify: `app/schemas/equipment.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_resource_schemas.py`:

```python
def test_equipment_create_rejects_extra_fields():
    with pytest.raises(ValidationError):
        EquipmentCreate(name="Dev", bogus="bad")

def test_equipment_status_update_valid():
    data = EquipmentStatusUpdate(status="maintenance")
    assert data.status == "maintenance"

def test_equipment_status_update_rejects_invalid():
    with pytest.raises(ValidationError):
        EquipmentStatusUpdate(status="broken")

def test_equipment_status_update_rejects_extra():
    with pytest.raises(ValidationError):
        EquipmentStatusUpdate(status="active", extra="bad")

def test_equipment_status_update_missing_status():
    with pytest.raises(ValidationError):
        EquipmentStatusUpdate()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_resource_schemas.py -x -q`
Expected: FAIL (EquipmentStatusUpdate not defined, EquipmentCreate accepts extra)

- [ ] **Step 3: Update schemas**

In `app/schemas/equipment.py`:

```python
import datetime as _dt
from typing import Optional, List

from pydantic import BaseModel, Field


class EquipmentCreate(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    serial_number: Optional[str] = Field(None, min_length=1, max_length=100)
    venue_id: Optional[int] = None
    description: Optional[str] = None
    external_id: Optional[str] = Field(None, max_length=100)


class EquipmentUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    serial_number: Optional[str] = Field(None, min_length=1, max_length=100)
    venue_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r'^(active|inactive|maintenance)$')
    external_id: Optional[str] = Field(None, max_length=100)


class EquipmentStatusUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    status: str = Field(..., pattern=r'^(active|inactive|maintenance)$')


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
    created_at: _dt.datetime
    updated_at: _dt.datetime


class EquipmentListResponse(BaseModel):
    items: List[EquipmentResponse]
    total: int
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_resource_schemas.py -x -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/equipment.py tests/test_resource_schemas.py
git commit -m "feat: add EquipmentStatusUpdate schema and extra=forbid to EquipmentCreate"
```

---

## Task 2: Create Equipment Router

**Files:**
- Create: `app/routers/equipment.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_equipment.py` with ~55 tests covering all 7 endpoints. See Task 3 for full test file.

Run: `.venv/bin/pytest tests/test_equipment.py -x -q`
Expected: ALL FAIL (module not found: no equipment router)

- [ ] **Step 2: Implement the router**

Create `app/routers/equipment.py` with 7 endpoints following the venue router pattern:

```
POST   /api/v1/equipment               — create (admin, FM)
GET    /api/v1/equipment               — list with filters + pagination (admin, FM, teacher)
GET    /api/v1/equipment/{id}          — detail (admin, FM, teacher)
PUT    /api/v1/equipment/{id}          — update (admin, FM)
PATCH  /api/v1/equipment/{id}/status   — status change (admin, FM)
DELETE /api/v1/equipment/{id}/venue    — unassign from venue (admin, FM)
```

Key implementation details:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.schemas.equipment import (
    EquipmentCreate, EquipmentUpdate, EquipmentResponse,
    EquipmentListResponse, EquipmentStatusUpdate,
)
from app.services.audit import audit_log

router = APIRouter(prefix="/api/v1/equipment", tags=["equipment"])
```

**Helper functions:**

```python
async def _get_equipment_or_404(db: AsyncSession, equipment_id: int) -> Equipment:
    result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
    equip = result.scalar_one_or_none()
    if not equip:
        raise HTTPException(status_code=404, detail="设备不存在")
    return equip


async def _get_venue_name(db: AsyncSession, venue_id: int | None) -> str | None:
    if venue_id is None:
        return None
    result = await db.execute(select(Venue.name).where(Venue.id == venue_id))
    return result.scalar_one_or_none()


def _equip_to_response(equip: Equipment, venue_name: str | None = None) -> dict:
    return {
        "id": equip.id,
        "name": equip.name,
        "category": equip.category,
        "serial_number": equip.serial_number,
        "status": equip.status,
        "venue_id": equip.venue_id,
        "venue_name": venue_name,
        "description": equip.description,
        "external_id": equip.external_id,
        "created_at": equip.created_at,
        "updated_at": equip.updated_at,
    }
```

**Endpoint: POST / — create equipment**

```python
@router.post("", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
async def create_equipment(
    data: EquipmentCreate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    # Validate venue_id references an existing venue
    if data.venue_id is not None:
        result = await db.execute(select(Venue).where(Venue.id == data.venue_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="场地不存在")

    equip = Equipment(
        name=data.name,
        category=data.category,
        serial_number=data.serial_number,
        venue_id=data.venue_id,
        description=data.description,
        external_id=data.external_id,
    )
    db.add(equip)
    await db.flush()

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="create", actor_id=current_user["id"],
        changes={"name": data.name},
    )

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)
```

**Endpoint: GET / — list equipment with filters**

```python
@router.get("", response_model=EquipmentListResponse)
async def list_equipment(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    venue_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Equipment)
    count_query = select(func.count()).select_from(Equipment)

    if current_user["role"] == "teacher":
        query = query.where(Equipment.status == "active")
        count_query = count_query.where(Equipment.status == "active")
    elif current_user["role"] not in ("admin", "facility_manager"):
        raise HTTPException(status_code=403, detail="权限不足")

    if status_filter:
        query = query.where(Equipment.status == status_filter)
        count_query = count_query.where(Equipment.status == status_filter)
    if category:
        query = query.where(Equipment.category == category)
        count_query = count_query.where(Equipment.category == category)
    if venue_id is not None:
        query = query.where(Equipment.venue_id == venue_id)
        count_query = count_query.where(Equipment.venue_id == venue_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Equipment.id).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    # Batch resolve venue names
    venue_ids = {e.venue_id for e in items if e.venue_id is not None}
    venue_names = {}
    if venue_ids:
        vresult = await db.execute(select(Venue.id, Venue.name).where(Venue.id.in_(venue_ids)))
        venue_names = dict(vresult.all())

    response_items = [_equip_to_response(e, venue_names.get(e.venue_id)) for e in items]
    return {"items": response_items, "total": total}
```

**Endpoint: GET /{id} — detail**

```python
@router.get("/{equipment_id}", response_model=EquipmentResponse)
async def get_equipment(
    equipment_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="权限不足")
    if current_user["role"] == "teacher" and equip.status != "active":
        raise HTTPException(status_code=404, detail="设备不存在")

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)
```

**Endpoint: PUT /{id} — update**

```python
@router.put("/{equipment_id}", response_model=EquipmentResponse)
async def update_equipment(
    equipment_id: int,
    data: EquipmentUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    update_data = data.model_dump(exclude_unset=True)

    # Validate venue_id if being changed
    if "venue_id" in update_data and update_data["venue_id"] is not None:
        result = await db.execute(select(Venue).where(Venue.id == update_data["venue_id"]))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="场地不存在")

    for field, value in update_data.items():
        setattr(equip, field, value)
    await db.flush()

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="update", actor_id=current_user["id"],
        changes=update_data,
    )

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)
```

**Endpoint: PATCH /{id}/status — status change**

```python
@router.patch("/{equipment_id}/status", response_model=EquipmentResponse)
async def change_equipment_status(
    equipment_id: int,
    data: EquipmentStatusUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    old_status = equip.status
    equip.status = data.status
    await db.flush()

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="status_change", actor_id=current_user["id"],
        changes={"old_status": old_status, "new_status": data.status},
    )

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)
```

**Endpoint: DELETE /{id}/venue — unassign from venue**

```python
@router.delete("/{equipment_id}/venue", response_model=EquipmentResponse)
async def unassign_equipment_venue(
    equipment_id: int,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    if equip.venue_id is None:
        raise HTTPException(status_code=400, detail="设备未绑定场地")

    old_venue_id = equip.venue_id
    equip.venue_id = None
    await db.flush()

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="unassign_venue", actor_id=current_user["id"],
        changes={"old_venue_id": old_venue_id},
    )

    return _equip_to_response(equip)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_equipment.py -x -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/routers/equipment.py tests/test_equipment.py
git commit -m "feat: add equipment CRUD router with permissions, audit, and venue association"
```

---

## Task 3: Integration — Register Router + Full Suite

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Register equipment router in main.py**

Add import and registration following venue pattern:

```python
from app.routers import equipment as equipment_router
# ...
app.include_router(equipment_router.router)
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/pytest -x -q`
Expected: ALL PASS (403 existing + ~55 new)

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: register equipment router in main app"
```

---

## Test Plan (tests/test_equipment.py)

### 1. CRUD Permission Tests (10 tests)

| Test | Endpoint | Role | Expected |
|------|----------|------|----------|
| `test_create_equipment_admin_allowed` | POST / | admin | 201 |
| `test_create_equipment_fm_allowed` | POST / | FM | 201 |
| `test_create_equipment_teacher_forbidden` | POST / | teacher | 403 |
| `test_create_equipment_student_forbidden` | POST / | student | 403 |
| `test_list_equipment_admin_sees_all` | GET / | admin | 200, all statuses |
| `test_list_equipment_teacher_sees_active_only` | GET / | teacher | 200, only active |
| `test_list_equipment_student_forbidden` | GET / | student | 403 |
| `test_get_equipment_admin_allowed` | GET /{id} | admin | 200 |
| `test_get_equipment_student_forbidden` | GET /{id} | student | 403 |
| `test_get_equipment_teacher_inactive_404` | GET /{id} | teacher | 404 |

### 2. Field Validation Tests (8 tests)

| Test | Input | Expected |
|------|-------|----------|
| `test_create_equipment_minimal` | name only | 201 |
| `test_create_equipment_all_fields` | all fields | 201 |
| `test_create_equipment_name_required` | {} | 422 |
| `test_create_equipment_rejects_empty_name` | name="" | 422 |
| `test_create_equipment_rejects_extra_fields` | name+extra | 422 |
| `test_update_equipment_forbids_extra` | extra field | 422 |
| `test_create_equipment_with_invalid_venue` | venue_id=99999 | 400 |
| `test_create_equipment_with_valid_venue` | venue_id=existing | 201 |

### 3. Status Lifecycle Tests (6 tests)

| Test | Transition | Expected |
|------|-----------|----------|
| `test_status_active_to_inactive` | active→inactive | 200 |
| `test_status_active_to_maintenance` | active→maintenance | 200 |
| `test_status_maintenance_to_active` | maintenance→active | 200 |
| `test_status_invalid_rejected` | status=broken | 422 |
| `test_status_missing_rejected` | {} | 422 |
| `test_status_extra_fields_rejected` | status+extra | 422 |

### 4. Venue Association Tests (5 tests)

| Test | Action | Expected |
|------|--------|----------|
| `test_create_with_venue_shows_venue_name` | create with venue_id | venue_name in response |
| `test_update_venue_id` | change venue_id | 200, new venue_name |
| `test_unassign_venue` | DELETE venue | 200, venue_id=None |
| `test_unassign_already_unassigned` | DELETE venue on unassigned | 400 |
| `test_list_filter_by_venue` | ?venue_id=X | only matching items |

### 5. Query Filtering Tests (4 tests)

| Test | Filter | Expected |
|------|--------|----------|
| `test_filter_by_status` | ?status=active | only active |
| `test_filter_by_category` | ?category=VR | only VR |
| `test_pagination` | limit+offset | correct page |
| `test_response_includes_venue_name` | detail | venue_name resolved |

### 6. Audit Logging Tests (5 tests)

| Test | Action | Audit entry |
|------|--------|-------------|
| `test_audit_create` | POST / | action=create |
| `test_audit_update` | PUT /{id} | action=update |
| `test_audit_status_change` | PATCH status | action=status_change |
| `test_audit_unassign_venue` | DELETE venue | action=unassign_venue |
| `test_audit_changes_content` | create | changes has name |

### 7. Regression Smoke Tests (4 tests)

Same as venue tests: health, auth login, courses, users endpoints still work.

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Serial number uniqueness violation on create/update | DB unique constraint catches it → IntegrityError → 409 |
| venue_id references deleted venue | FK uses SET NULL, equipment stays but loses venue assignment |
| Teacher sees inactive equipment by guessing ID | Return 404 (not 403) to prevent probing, same as venue pattern |
| Category is free text — inconsistent values | Accept for MVP. Can add enum/lookup later without migration |
| Equipment status change doesn't cascade to bookings | Booking engine (PR4) will check equipment status at booking time |
| No hard-delete endpoint | Intentional. Status=inactive is soft-delete for audit trail |

---

## Definition of Done / Merge Bar

- [ ] All 7 endpoints implemented and tested
- [ ] Permission matrix correct: admin/FM write, teacher read-active, student 403
- [ ] All writes produce audit log entries
- [ ] venue_id FK validated on create and update
- [ ] venue_name resolved in list and detail responses
- [ ] Serial number uniqueness enforced (DB constraint)
- [ ] Full test suite passes (403 existing + ~55 new)
- [ ] No regression on Phase 1/2 endpoints
- [ ] Follows venue router pattern exactly (no novel patterns)
- [ ] Code reviewed via CE review before merge
