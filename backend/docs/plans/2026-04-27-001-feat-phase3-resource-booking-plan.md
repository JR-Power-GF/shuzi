---
title: "Phase 3: Resource Management, Booking Scheduling & XR Extension Stubs"
type: feat
status: active
date: 2026-04-27
origin: openspec/changes/add-digital-training-platform-phase3-resource-equipment-scheduling-and-xr-extension/proposal.md
deepened: 2026-04-27
---

# Phase 3: Resource Management, Booking Scheduling & XR Extension Stubs

## Overview

Add venue management, equipment management, booking scheduling with conflict detection, utilization statistics, and XR integration stubs to the Digital Training Teaching Management Platform. This is the third iteration of the platform, building on Phase 1 (core teaching loop) and Phase 2 (courses + AI assistance).

## Problem Frame

Phases 1-2 established the digital teaching loop (users → courses/classes → tasks → submissions → grades) and AI-assisted learning. However, practical training requires physical resources — venues and equipment — and coordinated scheduling. Without resource management, teachers cannot reserve labs or XR rooms, there is no conflict prevention for double-booking, and no utilization data to inform capacity planning.

## Requirements Trace

- R1. Venue CRUD with status management (active/inactive/maintenance) and audit logging
- R2. Equipment CRUD with serial number uniqueness, status management, and audit logging
- R3. Booking CRUD with time conflict detection, pessimistic locking, all-or-nothing venue+equipment binding
- R4. Booking status lifecycle (approved → cancelled; active/completed derived from time)
- R5. Booking access control: admin/facility_manager full access, teacher own-bookings + course-linked, student none
- R6. Venue utilization rate by natural week (cancelled excluded, maintenance days excluded from denominator)
- R7. Equipment usage frequency by natural week
- R8. Peak hours distribution (last 30 days, hourly buckets)
- R9. XR extension stubs: XRProvider protocol, NullXRProvider, external_id on resources, client_reference on bookings
- R10. All write operations produce AuditLog entries
- R11. facility_manager role activated for actual route access

## Scope Boundaries

- No approval workflow engine
- No notification system
- No IoT real-time monitoring
- No XR vendor integration (stubs only)
- No student self-service booking
- No equipment lifecycle (procurement/repair/depreciation)
- No BI-grade analytics

## Context & Research

### Relevant Code and Patterns

- **Models**: `app/models/course.py` — flat table pattern, `Mapped` columns, no `relationship()`, `_utcnow_naive` for timestamps, `CheckConstraint` in `__table_args__`
- **Routers**: `app/routers/courses.py` — `APIRouter(prefix="/api/courses")`, `Depends(require_role(...))`, `select().where()` queries, `db.flush()` + auto-commit, Chinese error messages
- **Schemas**: `app/schemas/course.py` — `BaseModel` with `Field(...)`, `Create`/`Update`/`Response` pattern, `extra: "forbid"` on Update
- **Auth**: `app/dependencies/auth.py` — `require_role(roles)` and `require_role_or_owner(roles, owner_getter)`
- **Booking utils**: `app/services/booking_utils.py` — `check_time_overlap()`, `acquire_row_lock()`, `handle_integrity_error()`
- **Audit**: `app/services/audit.py` — `audit_log(db, entity_type, entity_id, action, actor_id, changes)`
- **Tests**: `tests/test_courses.py` — `@pytest.mark.asyncio(loop_scope="session")`, `client` + `db_session` fixtures, helper functions in `tests/helpers.py`
- **Migrations**: `alembic/versions/` — FK naming `fk_<table>_<col>`, index naming `ix_<table>_<col>`, downgrade reverses all operations
- **Registration**: `app/main.py` — `from app.routers import X; app.include_router(X.router)`

### Institutional Learnings

No prior learnings for booking/scheduling domain. Patterns from existing CRUD (courses, tasks, classes) apply directly.

## Key Technical Decisions

- **D1**: Flat Venue table (no building/floor/room nesting) — no organizational hierarchy exists to anchor it
- **D2**: Equipment is independent catalog with optional venue_id — devices may move between venues
- **D3**: Single Booking entity + join table for equipment — venue required, equipment optional, all-or-nothing semantics
- **D4**: Pessimistic locking + half-open interval `[start, end)` for conflict detection — high write-conflict probability in scheduling
- **D5**: Simplified status: only `approved` and `cancelled` persisted; `active`/`completed` derived at query time
- **D6**: Utilization stats: real-time aggregation, no materialized views, LIMIT 100 resources max. V1 denominator simplification: fixed 7×24h per week (no status-history tracking — would require audit-log replay). Multi-day bookings clipped to week boundaries. Equipment metric is "booking frequency" (count), not utilization rate.
- **D7**: XRProvider Protocol with NullXRProvider — code paths exist but no external dependency. XR calls happen fire-and-forget after transaction commit, never within the transaction. Provider swappable via `app/config.py` setting.
- **D8**: facility_manager gets full resource CRUD + booking access; teacher gets read-only on resources, create/cancel own bookings
- **D9**: Two migrations: resources (venues + equipment) then bookings (bookings + booking_equipment)
- **D10**: AuditLog integration for all writes — entity_type uses `"venue"`, `"equipment"`, `"booking"`
- **D11**: Equipment conflict detection uses a JOIN query (bookings + booking_equipment), not the generic `check_time_overlap()` — a dedicated `check_equipment_time_overlap()` utility function is needed in `booking_utils.py`
- **D12**: Equipment table name is `"equipment"` (uncountable noun, consistent with SQLAlchemy `__tablename__` convention)
- **D13**: All-or-nothing booking creation: savepoint via `db.begin_nested()` encompasses lock acquisition AND inserts. On any conflict, rollback to savepoint then raise HTTP error. Lock order is venue first, then equipment sorted by ID ascending.

## Open Questions

### Resolved During Planning

- Student booking: resolved — no student access to booking (see D8)
- Approval flow: resolved — V1 all bookings are auto-approved (see D5)
- Equipment-venue binding: resolved — optional venue_id on equipment, not required (see D2)
- All-or-nothing: resolved — if any equipment conflicts, entire booking fails (see D3)

### Deferred to Implementation

- Exact statistics query performance: depends on data volume at runtime; mitigate with LIMIT and time-range filtering
- Whether to add `available_hours` concept to venues: deferred to post-V1 if utilization denominator accuracy becomes an issue
- `get_db_with_savepoint` test override: if booking routers use `Depends(get_db_with_savepoint)`, conftest must add `dependency_overrides[get_db_with_savepoint]` mapping to prevent test pollution. Alternatively, booking routers use `Depends(get_db)` and the service layer manages `db.begin_nested()` explicitly within the same session.

## Implementation Units

This plan delivers 7 PRs in dependency order.

---

### PR 5a: Resource Domain Foundation — Models, Schemas, Migrations, Permissions, Audit

**PR Goal:** Establish the data layer, permission boundaries, and audit infrastructure for the entire resource domain. This is the load-bearing foundation — every subsequent PR depends on it.

**In scope:** All models, migrations, schemas, test helpers, permission policy constants, audit field mapping
**Out of scope:** Business logic, routers, UI, statistics, XR integration, complex validation rules

- [ ] **Unit 1: Venue and Equipment models + migrations**

**Goal:** Create the data layer for venues and equipment, with all required indexes and constraints.

**Requirements:** R1 (partial — model only), R2 (partial — model only), R10 (structural readiness), R11 (model readiness)

**Dependencies:** None — builds on existing `app/database.py` Base

**Files:**
- Create: `app/models/venue.py`
- Create: `app/models/equipment.py`
- Modify: `app/models/__init__.py` — register Venue and Equipment
- Create: `alembic/versions/<hash>_add_venues_and_equipment_tables.py`

**Approach:**
- Venue model: id, name (VARCHAR 100 NOT NULL), capacity (Integer nullable), location (VARCHAR 200 nullable), description (Text nullable), status (VARCHAR 20, CheckConstraint for active/inactive/maintenance, default "active"), external_id (VARCHAR 100 nullable, indexed), created_at, updated_at
- Equipment model: id, name (VARCHAR 100 NOT NULL), category (VARCHAR 50 nullable), serial_number (VARCHAR 100 nullable, unique), status (same CheckConstraint pattern), venue_id (FK → venues, nullable, ondelete="SET NULL"), external_id (VARCHAR 100 nullable, indexed), description (Text nullable), created_at, updated_at
- Follow model conventions from `app/models/course.py`: `Mapped` types, `_utcnow_naive` for timestamps, no `relationship()`
- Single migration creating both tables (they are independent, no circular FK)
- Equipment FK to Venue: `ondelete="SET NULL"` — if venue is deleted, equipment stays but loses location reference

**Patterns to follow:**
- `app/models/course.py` — class structure, imports, constraint naming
- `app/models/audit_log.py` — index naming conventions (`ix_audit_entity`, `ix_audit_actor`)
- `app/constants.py` — resource status constants to be added later

**Test scenarios:**
- Happy path: Create Venue with all fields, create Equipment with all fields
- Edge case: Create Venue with minimal fields (name only)
- Edge case: Create Equipment without venue_id (nullable FK)
- Error path: Duplicate serial_number raises IntegrityError
- Integration: Equipment.venue_id references existing venue

**Verification:**
- `alembic upgrade head` succeeds
- `alembic downgrade -1 && alembic upgrade head` succeeds
- Existing 232 tests pass unchanged
- New model instances can be created in test session

---

- [ ] **Unit 2: Venue and Equipment Pydantic schemas**

**Goal:** Create request/response schemas for venue and equipment CRUD.

**Requirements:** R1 (partial), R2 (partial)

**Dependencies:** Unit 1 (models must exist for response field alignment)

**Files:**
- Create: `app/schemas/venue.py`
- Create: `app/schemas/equipment.py`

**Approach:**
- VenueCreate: name (required, min 1, max 100), capacity (optional int), location (optional str max 200), description (optional str), external_id (optional str max 100)
- VenueUpdate: `extra: "forbid"`, all fields optional
- VenueResponse: all fields + id, created_at, updated_at
- VenueListResponse: items + total
- EquipmentCreate: name (required), category (optional), serial_number (optional), venue_id (optional), description (optional), external_id (optional)
- EquipmentUpdate: `extra: "forbid"`, all fields optional
- EquipmentResponse: all fields + id, venue_name (optional enriched field), created_at, updated_at
- EquipmentListResponse: items + total
- Follow `app/schemas/course.py` conventions exactly

**Patterns to follow:**
- `app/schemas/course.py` — Field validation, optional fields, response enrichment

**Test expectation: none — schemas are validated through router integration tests in PR 5b/5c.**

**Verification:**
- Schema files import without errors
- Field types align with model column types

---

- [ ] **Unit 3: Test helpers for venues and equipment**

**Goal:** Add test helper functions for creating venues and equipment in tests.

**Requirements:** Structural — enables PR 5b/5c/5d testing

**Dependencies:** Unit 1

**Files:**
- Modify: `tests/helpers.py` — add `create_test_venue()`, `create_test_equipment()`

**Approach:**
- Follow existing `create_test_user()`, `create_test_class()` patterns: direct model instantiation, `db.add() + await db.flush()`, return the instance
- `create_test_venue(db, name, **kwargs)` — default status="active"
- `create_test_equipment(db, name, **kwargs)` — default status="active"

**Patterns to follow:**
- `tests/helpers.py` — existing helper functions

**Test expectation: none — helpers validated through downstream test files.**

**Verification:**
- Helpers can be imported and used in test files without errors

**Review focus:**
- Is any model over-designed? (extra fields, premature constraints, unnecessary indexes)
- Are permission boundaries clear? (role constants match DB CHECK constraint)
- Are migrations safe? (no data loss on upgrade, clean downgrade)
- Do schemas match model types exactly? (field names, types, constraints)

**Merge bar:** All 232 existing tests pass + migration up/down clean + no import errors

---

### PR 5b: Venue Management CRUD

**PR Goal:** Complete venue CRUD and basic availability management — the first functional feature on the foundation.

**In scope:** Venue list, detail, create, edit, status change (active/inactive/maintenance), permission control, audit logging
**Out of scope:** Floor/map visualization, advanced scheduling rules, booking integration (that's PR 5d)

- [ ] **Unit 4: Venue CRUD router with permissions and audit**

**Goal:** Implement full venue CRUD with role-based access control and audit logging.

**Requirements:** R1, R10, R11

**Dependencies:** PR 5a (models, schemas, helpers must be merged)

**Files:**
- Create: `app/routers/venues.py`
- Modify: `app/main.py` — register venue router
- Create: `tests/test_venues.py`

**Approach:**
- Router: `APIRouter(prefix="/api/venues", tags=["venues"])`
- Endpoints:
  - `POST /api/venues` — create (admin, facility_manager)
  - `GET /api/venues` — list with pagination + status filter (admin, facility_manager, teacher)
  - `GET /api/venues/{id}` — detail (admin, facility_manager, teacher)
  - `PUT /api/venues/{id}` — update (admin, facility_manager)
  - `PATCH /api/venues/{id}/status` — status change (admin, facility_manager)
- Permission: `require_role(["admin", "facility_manager"])` for writes, `require_role(["admin", "facility_manager", "teacher"])` for reads
- Status validation: only allow valid transitions (active↔inactive, active↔maintenance)
- Audit: `audit_log()` for create, update, status_change
- Response helper: `_venue_to_response()` following `_course_to_response()` pattern
- List endpoint: pagination with skip/limit, optional `status` query filter

**Patterns to follow:**
- `app/routers/courses.py` — endpoint structure, dependency injection, error handling, pagination
- `app/routers/classes.py` — status update pattern

**Test scenarios:**
- Happy path: facility_manager creates venue → 201, reads → 200, updates → 200, changes status → 200
- Happy path: admin performs all CRUD operations → success
- Happy path: teacher reads venue list → 200
- Happy path: teacher reads venue detail → 200
- Error path: teacher creates venue → 403
- Error path: student reads venues → 403
- Error path: update nonexistent venue → 404
- Error path: invalid status transition → 400
- Integration: audit log created on venue create, update, status change

**Verification:**
- All venue endpoints return correct status codes
- Audit log entries exist for all write operations
- Existing tests pass

**Review focus:**
- Venue status management: are transitions well-defined? Can you recover from inactive/maintenance back to active?
- Impact of venue deactivation on future bookings: is it clear that status change does NOT cascade-cancel existing bookings?
- Data isolation: can a teacher see only what they should? Can a student see nothing?
- Are status-filtered list queries using the index efficiently?

**Merge bar:** All venue CRUD operations work + permissions enforced + audit verified + existing tests pass

---

### PR 5c: Equipment Management CRUD

**PR Goal:** Complete equipment CRUD, status management, and venue association. Can be developed and merged in parallel with PR 5b.

**In scope:** Equipment catalog (create/edit/list/detail), category, serial number uniqueness, status management, venue binding, bookability check field (status), permission control, audit
**Out of scope:** Repair workflow, procurement lifecycle, IoT online monitoring, booking conflict logic

- [ ] **Unit 5: Equipment CRUD router with permissions and audit**

**Goal:** Implement full equipment CRUD with serial number uniqueness and audit logging.

**Requirements:** R2, R10, R11

**Dependencies:** PR 5a (models, schemas, helpers) — does NOT depend on PR 5b; only needs the Venue model for FK validation

**Files:**
- Create: `app/routers/equipment.py`
- Modify: `app/main.py` — register equipment router
- Create: `tests/test_equipment.py`

**Approach:**
- Router: `APIRouter(prefix="/api/equipment", tags=["equipment"])`
- Same endpoint structure as venues (POST, GET list, GET detail, PUT, PATCH status)
- Additional validation: serial_number uniqueness caught via IntegrityError → 409
- venue_id FK validation: if provided, check venue exists → 404 if not
- Permission: same as venues (admin/facility_manager write, +teacher read)
- Audit: `audit_log()` for create, update, status_change
- List endpoint: pagination + optional `category` and `status` filters
- Response enrichment: include venue_name when venue_id is set (optional join)

**Patterns to follow:**
- `app/routers/venues.py` (from PR 5b) — nearly identical structure, adapt for equipment
- `app/routers/courses.py` — response enrichment with joined data

**Test scenarios:**
- Happy path: create equipment with all fields → 201
- Happy path: create equipment without venue_id → 201
- Happy path: filter by category → returns matching equipment
- Error path: duplicate serial_number → 409
- Error path: invalid venue_id → 404
- Error path: teacher writes → 403, student reads → 403
- Integration: audit log created on all write operations
- Integration: equipment response includes venue_name when associated

**Verification:**
- All equipment endpoints work correctly
- Serial number uniqueness enforced
- Existing tests pass

**Review focus:**
- Equipment status transitions: are they the same as venue? Is "maintenance" the right way to mark unbookable?
- Venue binding relationship: what happens when equipment is unbound from a venue (venue_id → null)? Does that affect anything?
- Constraints under inactive/maintenance status: is it clear that only status="active" equipment can be booked (enforced in PR 5d, but the field must be present here)?
- Serial_number uniqueness: does the 409 error message help the user identify the conflict?

**Merge bar:** All equipment CRUD + status management + serial uniqueness + audit + existing tests pass

---

### PR 5d: Booking Scheduling with Conflict Detection

**PR Goal:** Complete the core booking capability — create, modify, cancel, conflict detection, concurrency control. This is the highest-risk PR in Phase 3.

**In scope:** Booking CRUD, time conflict detection, pessimistic locking, all-or-nothing venue+equipment binding, status lifecycle, idempotent client_reference, basic schedule queries, permissions (admin/facility_manager/teacher), audit
**Out of scope:** Approval workflow, notification center, drag-and-drop scheduler, recurring bookings, booking conflict for equipment (V1 scope — venue conflict first, equipment as bonus if time allows)

- [ ] **Unit 6: Booking and BookingEquipment models + migration**

**Goal:** Create the booking data layer with all indexes for conflict detection queries.

**Requirements:** R3 (partial — model), R4 (partial — status field), R5 (partial — FK structure), R9 (partial — client_reference field)

**Dependencies:** PR 5a (venue and equipment models must exist). **GATE: PR 5b AND PR 5c must both be merged first** — booking FKs reference both venues and equipment tables.

**Files:**
- Create: `app/models/booking.py` — Booking + BookingEquipment models
- Modify: `app/models/__init__.py` — register new models
- Create: `alembic/versions/<hash>_add_bookings_tables.py`

**Approach:**
- Booking model: id, venue_id (FK → venues NOT NULL, ondelete="RESTRICT"), title (VARCHAR 200 NOT NULL), purpose (Text nullable), start_time (DateTime NOT NULL), end_time (DateTime NOT NULL), booked_by (FK → users NOT NULL, ondelete="RESTRICT"), status (VARCHAR 20, CheckConstraint for "approved"/"cancelled", default "approved"), course_id (FK → courses nullable, ondelete="SET NULL"), class_id (FK → classes nullable, ondelete="SET NULL"), task_id (FK → tasks nullable, ondelete="SET NULL"), client_reference (VARCHAR 100 nullable, unique, indexed), created_at, updated_at
- BookingEquipment model: booking_id (FK → bookings, ondelete="CASCADE"), equipment_id (FK → equipment table, ondelete="CASCADE"), composite PK. Equipment model `__tablename__ = "equipment"` (uncountable, see D12).
- Indexes: `ix_bookings_venue_time` on (venue_id, start_time, end_time) for conflict queries, `ix_bookings_booked_by` on booked_by, `ix_bookings_status` on status, `ix_bookings_client_ref` on client_reference
- `ix_booking_equipment_equipment` on (equipment_id, booking_id) for equipment conflict queries

**Patterns to follow:**
- `app/models/course.py` — model structure
- `app/models/audit_log.py` — composite index naming

**Test scenarios:**
- Happy path: create Booking with required fields
- Happy path: create BookingEquipment association
- Edge case: booking with nullable context fields (course_id, class_id, task_id all null)
- Edge case: booking with client_reference null vs set
- Error path: start_time >= end_time validation at application level (not DB constraint)

**Verification:**
- Migration applies and rolls back cleanly
- Existing tests pass

---

- [ ] **Unit 7: Booking schemas**

**Goal:** Create booking request/response schemas with time validation.

**Requirements:** R3 (partial), R4 (partial)

**Dependencies:** Unit 6

**Files:**
- Create: `app/schemas/booking.py`

**Approach:**
- BookingCreate: venue_id (required int), title (required str), purpose (optional), start_time (required datetime), end_time (required datetime), equipment_ids (optional list[int], default []), course_id/class_id/task_id (optional), client_reference (optional str max 100)
  - Validator: `start_time < end_time` via Pydantic model_validator
- BookingUpdate: `extra: "forbid"`, title/purpose/start_time/end_time/equipment_ids optional. Validator: if both times provided, start < end
- BookingResponse: all fields + equipment list (list of id+name dicts), derived status (computed from time), venue_name
- BookingListResponse: items + total

**Patterns to follow:**
- `app/schemas/course.py` — schema conventions
- Pydantic v2 `model_validator` for cross-field validation

**Verification:**
- Schemas validate correctly for valid and invalid time ranges

---

- [ ] **Unit 8: Booking service layer with conflict detection**

**Goal:** Implement the booking business logic — conflict detection, resource validation, all-or-nothing creation.

**Requirements:** R3, R4, R5, R9 (idempotency), R10

**Dependencies:** Unit 6, Unit 7, existing `booking_utils.py` and `audit.py`

**Files:**
- Create: `app/services/booking_service.py`
- Modify: `tests/helpers.py` — add `create_test_booking()` helper

**Approach:**
- `create_booking(db, data, current_user)`:
  1. Check client_reference idempotency — if exists, return existing booking
  2. Validate `start_time > _utcnow_naive()` → 400 if in the past
  3. Validate venue exists and status="active" → 400 if not
  4. Validate all equipment exist and status="active" → 400 if not
  5. `db.begin_nested()` — create savepoint encompassing all locks and inserts
  6. `acquire_row_lock(Venue, venue_id)` — lock venue row
  7. `check_time_overlap(Venue, venue_id, start_time, end_time)` → 409 if conflict
  8. For each equipment_id **in sorted order** (prevent deadlocks, see D13): `acquire_row_lock(Equipment, eid)` + `check_equipment_time_overlap(db, eid, start_time, end_time)` → 409 if conflict
  9. Create Booking row + BookingEquipment rows
  10. `audit_log(entity_type="booking", action="create", ...)`
  11. Release savepoint (auto on flush); return booking
  12. On any conflict/error: rollback to savepoint, then raise HTTP error
- `update_booking(db, booking_id, data, current_user)`:
  1. Fetch booking, 404 if not found
  2. Permission check: admin/facility_manager can edit any; teacher only own
  3. Check start_time not in past → 400
  4. If time OR equipment_ids changed: begin savepoint, re-run conflict detection excluding self using the **new** equipment list and **new** time range atomically
  5. If equipment_ids changed: delete existing booking_equipment rows, insert new set (atomic replacement)
  6. Update fields, flush
  7. `audit_log(action="update")`
- `cancel_booking(db, booking_id, current_user)`:
  1. Fetch booking, 404/403 checks
  2. Check start_time not in past → 400
  3. Set status="cancelled"
  4. `audit_log(action="cancel")`
- New utility function needed: `check_equipment_time_overlap(db, equipment_id, start_time, end_time, exclude_booking_id=None)` in `booking_utils.py` — handles the JOIN between bookings and booking_equipment tables (see D11)

**Technical design:**
> Equipment conflict query — directional guidance, not implementation specification:
> SELECT b.id FROM bookings b JOIN booking_equipment be ON b.id = be.booking_id
> WHERE be.equipment_id = :eid AND b.status = 'approved'
> AND b.start_time < :new_end AND b.end_time > :new_start
> AND b.id != :exclude_id
>
> Note: The existing `check_time_overlap()` works for single-table queries (venue).
> Equipment conflicts require a JOIN, so a dedicated `check_equipment_time_overlap()` is needed.

**Patterns to follow:**
- `app/services/booking_utils.py` — extend with `check_equipment_time_overlap()`, reuse `acquire_row_lock()`, `handle_integrity_error()`
- `app/services/audit.py` — `audit_log()` for all writes
- `app/dependencies/auth.py` — `require_role_or_owner()` for permission
- `app/database.py` — `_utcnow_naive()` for time comparisons

**Test scenarios:**
- Happy path: create booking for available venue → success
- Happy path: create booking with equipment → success, booking_equipment rows created
- Happy path: idempotent create with same client_reference → returns existing
- Happy path: cancel future booking → status becomes "cancelled"
- Error path: create booking with start_time in the past → 400
- Error path: venue time conflict → 409
- Error path: equipment time conflict across different venues → 409
- Error path: adjacent bookings (end == start) → no conflict, success
- Error path: inactive venue → 400
- Error path: maintenance equipment → 400
- Error path: cancel past booking → 400
- Error path: modify started booking → 400
- Error path: teacher cancels another teacher's booking → 403
- Edge case: update booking with simultaneous time + equipment change → conflict check uses new values
- Edge case: update replaces equipment_ids → old booking_equipment rows deleted, new ones inserted
- Integration: audit log entries created for create, update, cancel
- Integration: savepoint rollback on conflict leaves no partial booking rows

**Verification:**
- All conflict detection scenarios work
- All-or-nothing: equipment conflict rolls back entire booking
- Existing tests pass

---

- [ ] **Unit 9: Booking CRUD router**

**Goal:** Expose booking service via REST API endpoints.

**Requirements:** R3, R4, R5, R9

**Dependencies:** Unit 8 (booking service)

**Files:**
- Create: `app/routers/bookings.py`
- Modify: `app/main.py` — register booking router
- Create: `tests/test_bookings.py`

**Approach:**
- Router: `APIRouter(prefix="/api/bookings", tags=["bookings"])`
- Endpoints:
  - `POST /api/bookings` — create (admin, facility_manager, teacher)
  - `GET /api/bookings` — list with filters: `my` (teacher's own), `venue_id`, `status`, date range, pagination
  - `GET /api/bookings/{id}` — detail with equipment list
  - `PUT /api/bookings/{id}` — update time/title/equipment
  - `POST /api/bookings/{id}/cancel` — cancel
- Permission via `require_role_or_owner()` for teacher access, `require_role(["admin", "facility_manager"])` for admin-level access
- Teacher list: filter by booked_by = current_user.id when `my=true`
- Admin/facility_manager list: can see all, with optional filters
- Response includes: derived status (active if start<=now<end, completed if end<=now, otherwise persisted status)

**Patterns to follow:**
- `app/routers/courses.py` — endpoint structure, pagination, response enrichment
- `app/routers/submissions.py` — filtered list pattern

**Test scenarios:**
- Happy path: teacher creates booking → 201
- Happy path: facility_manager creates booking → 201
- Happy path: teacher lists own bookings → only theirs
- Happy path: admin lists all bookings → all visible
- Happy path: get booking detail with equipment list
- Happy path: update booking time range → 200
- Happy path: cancel booking → 200
- Error path: student creates booking → 403
- Error path: teacher views another teacher's booking → depends on list/direct access rules
- Error path: time conflict on update → 409
- Error path: cancel already cancelled → 400 or idempotent 200
- Integration: booking detail includes equipment names
- Integration: derived status correct (approved/active/completed/cancelled)

**Verification:**
- All booking endpoints return correct status codes
- Permission boundaries enforced
- Existing tests pass

**Review focus (CRITICAL — this is the highest-risk PR):**
- Conflict detection accuracy: does the half-open interval `[start, end)` correctly handle edge cases (adjacent bookings, exact overlap, partial overlap)?
- Modify/cancel consistency: does updating a booking re-check conflicts atomically? Does cancelling a started booking correctly fail?
- Concurrent double-booking: are the pessimistic locks + savepoint sufficient? Does the sorted lock order prevent deadlocks?
- All-or-nothing semantics: if equipment_id=3 conflicts after equipment_id=2 was locked, does the savepoint rollback clean up everything (no partial rows)?
- Are there any paths where a booking row is committed without all its booking_equipment rows?

**Merge bar:** All 17+ test scenarios pass (including concurrent conflict and savepoint rollback) + existing tests pass + no deadlocks under concurrent load

---

### PR 5e: Utilization Statistics

**PR Goal:** Provide basic venue and equipment utilization statistics with clear, documented statistical definitions.

**In scope:** Time-range filtering, venue utilization rate, equipment booking frequency, peak hours distribution, permission gating, performance guards
**Out of scope:** BI custom analysis, complex chart systems, predictive analytics, real-time dashboards

- [ ] **Unit 10: Statistics service and endpoints**

**Goal:** Implement venue utilization, equipment usage frequency, and peak hours statistics.

**Requirements:** R6, R7, R8

**Dependencies:** PR 5d (bookings must exist to aggregate)

**Files:**
- Create: `app/services/stats_service.py`
- Modify: `app/routers/dashboard.py` — add 3 statistics endpoints
- Create: `tests/test_resource_statistics.py`

**Approach:**

**Statistics definitions (from design.md D6, simplified for V1):**
- Venue utilization: per natural week (Mon 00:00 - Sun 23:59 UTC). Numerator = SUM of approved booking hours (clipped to week boundary). Denominator = 7 × 24 = 168 hours (fixed, regardless of venue status changes). Cancelled bookings excluded from numerator. Multi-day bookings clipped: hours in each week counted separately (e.g., Fri 22:00→Mon 06:00 = 2h in Week 1, 6h in Week 2).
- Equipment booking frequency: per natural week. Count of approved bookings containing the equipment. Cancelled excluded. Multi-day bookings counted once per week they span.
- Peak hours: last 30 days, 24 hourly buckets (0-23). For each hour, count approved bookings whose `[start, end)` interval overlaps that hour. Cancelled excluded.

**Endpoints (added to existing dashboard router):**
- `GET /api/dashboard/venue-utilization?start_date=&end_date=` → returns list of {venue_id, venue_name, week_start, utilization_rate}
- `GET /api/dashboard/equipment-usage?start_date=&end_date=` → returns list of {equipment_id, equipment_name, week_start, usage_count}
- `GET /api/dashboard/peak-hours` → returns array of 24 {hour, count} objects

**Permission:** `require_role(["admin", "facility_manager"])` for all statistics endpoints

**Performance guards:**
- Default time range: last 7 days
- Maximum 100 resources per response (sorted by metric descending)
- All queries use existing indexes on (venue_id, start_time, end_time) and booking_equipment

**Service layer** (`app/services/stats_service.py`): separate service for stats computation, keeping dashboard router thin.

**Patterns to follow:**
- `app/routers/dashboard.py` — existing dashboard pattern
- Real-time aggregation (consistent with Phase 2 D6 decision)

**Test scenarios:**
- Happy path: venue utilization calculated correctly for a week with bookings
- Happy path: cancelled bookings excluded from numerator
- Happy path: equipment booking frequency matches booking associations
- Happy path: peak hours distribution shows correct hourly counts
- Edge case: empty week → utilization 0% (denominator still 168h)
- Edge case: multi-day booking split across weeks (clipped hours)
- Edge case: multi-hour booking counts in multiple hour buckets (half-open interval)
- Error path: teacher accesses statistics → 403
- Error path: no date range → defaults to last 7 days
- Integration: LIMIT 100 enforced on large result sets

**Verification:**
- Statistics calculations match manual computation
- Permission enforced
- Query performance acceptable (<500ms for 1000 bookings)
- Existing tests pass

**Review focus:**
- Statistical definitions clearly written: numerator, denominator, what's excluded (cancelled), how multi-day is split, fixed 168h denominator rationale
- Permission scope correct: only admin + facility_manager can see stats
- Performance: are queries using indexes? Is the LIMIT 100 guard effective? Any full-table scans?
- UTC consistency: are week boundaries computed in UTC (not MySQL server timezone)?

**Merge bar:** All statistics endpoints return correct results + permission denied for teacher/student + query time <500ms + existing tests pass

---

### PR 5f: XR Extension Stubs

**PR Goal:** Establish stable extension points for future XR vendor integration — without coupling to any specific vendor.

**In scope:** XRProvider/adapter abstraction, NullXRProvider (no-op), external_id fields on resources, client_reference on bookings, event recording via AuditLog, isolation switch (settings-based provider swap)
**Out of scope:** Real vendor SDK integration, coupled business flows, XR-specific API endpoints

- [ ] **Unit 11: XRProvider protocol and NullXRProvider**

**Goal:** Define the XR integration contract with a no-op default implementation.

**Requirements:** R9

**Dependencies:** PR 5d (booking model must exist for XRProvider method signatures)

**Files:**
- Create: `app/services/xr_provider.py` — XRProvider Protocol + NullXRProvider
- Create: `tests/test_xr_provider.py`

**Approach:**
- XRProvider Protocol class with async methods:
  - `async def on_booking_created(self, booking_id: int, venue_id: int, equipment_ids: list[int], start_time: datetime, end_time: datetime, client_reference: str | None) -> None`
  - `async def on_booking_updated(self, booking_id: int, updated_fields: dict[str, Any]) -> None`
  - `async def on_booking_cancelled(self, booking_id: int) -> None`
- NullXRProvider: implements all methods as `pass` (no-op)
- Factory function: `get_xr_provider() -> XRProvider` — returns NullXRProvider by default, reads from `settings.XR_PROVIDER_CLASS` to allow swapping without modifying service code
- **Critical**: XR provider calls happen in the **router layer after the service returns and the session commits**, never inside the transaction. The booking service does NOT call XR directly. This prevents XR failures from holding transactions open.
- Router wraps XR call in try/except, logs failures but never propagates to client — local booking must never fail due to XR

**Patterns to follow:**
- Python `typing.Protocol` for interface definition
- No external dependency introduced

**Test scenarios:**
- Happy path: NullXRProvider.on_booking_created returns None without error
- Happy path: NullXRProvider.on_booking_cancelled returns None without error
- Integration: booking creation succeeds even if XR provider raises (future-proofing test with a mock that raises)
- Integration: booking service calls XR provider after successful create/cancel

**Verification:**
- NullXRProvider is the default provider
- Booking operations still work identically (no external dependency)
- Existing tests pass

**Review focus:**
- Main booking flow does NOT depend on external XR success — booking commits even if XR fails silently
- Idempotency: client_reference ensures retries don't create duplicates
- Event traceability: all booking state changes are in AuditLog, queryable by entity_type="booking"
- Provider swap mechanism: can you swap to a real provider by changing one config value, without touching booking service code?
- Failure isolation: if a future XR provider throws, does it get caught and logged without breaking the HTTP response?

**Merge bar:** Booking flow works identically with and without XR provider + NullXRProvider returns cleanly + XR failure doesn't break booking + existing tests pass

---

### PR 5g: Integration Verification, Polish, and Release

**PR Goal:** Final Phase 3 release gate — verify nothing is broken, fill documentation gaps, ensure production readiness.

**In scope:** Full regression test suite, migration chain verification, permission/boundary re-check, seed/mock data for demos, monitoring/log verification, documentation updates
**Out of scope:** New features, significant refactors

- [ ] **Unit 12: Full regression and integration verification**

**Goal:** Verify the entire Phase 3 works end-to-end with no regressions.

**Requirements:** All (R1-R11)

**Dependencies:** All previous PRs merged

**Files:**
- Create: `tests/test_phase3_integration.py` — end-to-end integration tests
- Modify: `docs/plans/2026-04-27-001-feat-phase3-resource-booking-plan.md` — mark units complete

**Approach:**
- Full regression: `pytest -v` — target ≥270 tests, all passing
- Migration chain: fresh `alembic upgrade head` from empty database
- API surface: verify all existing endpoints unchanged
- Audit completeness: verify all Phase 3 write paths produce AuditLog entries
- Cross-cutting integration test:
  1. Create venue + equipment
  2. Create booking with equipment
  3. Verify conflict detection prevents double-booking
  4. Verify statistics reflect the booking
  5. Verify XR provider is called (NullXRProvider)
  6. Cancel booking, verify audit log
- Seed data: create a small demo dataset (1 venue, 3 equipment, 5 bookings) for development/testing
- Documentation: verify OpenSpec change is complete, update README if needed

**Test scenarios:**
- Integration: full booking lifecycle (create → view → statistics → cancel → audit)
- Integration: venue status change prevents new bookings but existing ones persist
- Integration: equipment removed from venue doesn't break existing bookings
- Regression: all Phase 1/2 test suites pass

**Verification:**
- Zero test failures
- Migration chain clean
- All OpenSpec requirements traceable to passing tests

**Review focus:**
- Has Phase 3 truly reached releasable quality? Are there any remaining blockers?
- Does Phase 3 break any Phase 1 or Phase 2 flows? Run the full test suite and verify no regressions.
- Are there unclosed blockers or half-implemented features that should be tracked as tech debt?
- Is the seed data realistic enough for demos?

**Merge bar:** 100% test pass rate + migration chain clean + no regressions in Phase 1/2 + OpenSpec verification passes

---

## System-Wide Impact

- **Interaction graph:** New routers (venues, equipment, bookings) are independent of existing routers. No existing router is modified except `dashboard.py` (adds endpoints) and `main.py` (registers routers). Booking service calls existing `booking_utils.py`, `audit.py`, and new `xr_provider.py`.
- **Error propagation:** Booking conflicts → 409; resource unavailable → 400; permission denied → 403; not found → 404. All consistent with existing patterns.
- **State lifecycle risks:** Booking status transitions are simple (approved → cancelled). No partial-write risk due to all-or-nothing transaction strategy. Venue/equipment status changes don't cascade to bookings (by design — facility manager handles manually).
- **API surface parity:** New endpoints follow existing conventions exactly (prefix, pagination, error format). No existing API surface changes.
- **Integration coverage:** Booking conflict detection requires real database testing (not mockable). Statistics require actual booking data. Both covered by integration tests.
- **Unchanged invariants:** Existing auth flow (JWT, login, refresh), user/class/course/task/submission/grade CRUD, AI features, file handling — all untouched. The facility_manager role gains actual route access but was already in the DB CHECK constraint.

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Booking conflict detection performance with many bookings | Low | Medium | Composite index on (venue_id, start_time, end_time); LIMIT on queries |
| Deadlock on concurrent booking creation | Low | Medium | Consistent lock order (venue → equipment by id); MySQL auto-detects deadlocks |
| Statistics query slow on large dataset | Medium | Low | LIMIT 100, required date range, indexed queries |
| Equipment overlap query complexity (join booking + booking_equipment) | Low | Medium | Pre-built query pattern in booking_service, tested with concurrent fixtures |
| facility_manager role has broad access, no scoping | Medium | Low | AuditLog tracks all operations; fine-grained permissions deferred |
| Migration chain breakage if PRs merge out of order | Low | High | Each PR's migration references the correct down_revision; test downgrade explicitly |
| MySQL `WEEK()` uses server timezone, not UTC | Low | Medium | Statistics queries use explicit UTC date math in Python/application layer, not MySQL date functions |
| Venue `ondelete="RESTRICT"` means venues with booking history cannot be deleted | Low | Low | Acceptable for V1 — decommissioned venues set status="inactive". Soft-delete only. |

## PR Dependency Graph

```
PR 5a (foundation)
├── PR 5b (venues) ───────────┐
├── PR 5c (equipment) ────────┤  ← independent of 5b
│                              ├── PR 5d (bookings) ← GATE: requires BOTH 5b+5c
│                              │   ├── PR 5e (statistics) ──┐
│                              │   ├── PR 5f (XR stubs) ────┤  ← independent of 5e
│                              │   └── PR 5g (integration) ←┘
```

**Recommended merge order:** 5a → 5b + 5c (parallel) → 5d → 5e + 5f (parallel) → 5g

**Parallelizable:** PR 5b and 5c can be developed and merged in parallel after 5a (they are independent routers). PR 5e and 5f can be developed and merged in parallel after 5d (independent features). PR 5d is the critical-path gate — it requires both 5b and 5c to be merged first.

## Sources & References

- **Origin document:** `openspec/changes/add-digital-training-platform-phase3-resource-equipment-scheduling-and-xr-extension/proposal.md`
- **Design document:** `openspec/changes/add-digital-training-platform-phase3-resource-equipment-scheduling-and-xr-extension/design.md`
- **Tasks document:** `openspec/changes/add-digital-training-platform-phase3-resource-equipment-scheduling-and-xr-extension/tasks.md`
- **Specs:** `openspec/changes/add-digital-training-platform-phase3-resource-equipment-scheduling-and-xr-extension/specs/`
- **Phase 3 prerequisites plan:** `docs/plans/2026-04-21-001-feat-phase3-foundation-ai-assist-plan.md` (already completed)
- **Existing patterns:** `app/routers/courses.py`, `app/models/course.py`, `app/schemas/course.py`, `app/services/booking_utils.py`
