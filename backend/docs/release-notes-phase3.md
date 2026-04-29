# Phase 3 Release Notes

Digital Training Teaching Management Platform -- Venue, Equipment, Booking, Stats, and XR Extensions.

---

## 1. Feature Overview

### 1.1 Venue CRUD with Availability and Blackout Management

Full venue lifecycle management with weekly availability schedules and date-range blackout periods.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/venues` | Create venue |
| GET | `/api/v1/venues` | List venues (filter by status, capacity) |
| GET | `/api/v1/venues/{venue_id}` | Get venue detail with availability |
| PUT | `/api/v1/venues/{venue_id}` | Update venue fields |
| PATCH | `/api/v1/venues/{venue_id}/status` | Change venue status (active/inactive/maintenance) |
| PUT | `/api/v1/venues/{venue_id}/availability` | Replace weekly availability slots |
| POST | `/api/v1/venues/{venue_id}/blackouts` | Create blackout period |
| GET | `/api/v1/venues/{venue_id}/blackouts` | List blackout periods |
| DELETE | `/api/v1/venues/{venue_id}/blackouts/{blackout_id}` | Delete blackout period |

All mutating operations emit audit log entries.

### 1.2 Equipment CRUD with Venue Assignment

Equipment management with optional venue binding and serial number uniqueness.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/equipment` | Create equipment |
| GET | `/api/v1/equipment` | List equipment (filter by status, category, venue_id) |
| GET | `/api/v1/equipment/{equipment_id}` | Get equipment detail |
| PUT | `/api/v1/equipment/{equipment_id}` | Update equipment fields |
| PATCH | `/api/v1/equipment/{equipment_id}/status` | Change equipment status |
| POST | `/api/v1/equipment/{equipment_id}/unassign-venue` | Unassign equipment from venue |

Serial number conflicts return 409. Status changes go through a dedicated PATCH endpoint to enforce audit trail.

### 1.3 Booking with Conflict Detection, Idempotent Creation, and Equipment Association

Bookings reserve a venue plus optional equipment for a time range. All conflict checks run before any writes (all-or-nothing). Pessimistic row locks on Venue and Equipment prevent concurrent scheduling races.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bookings` | Create booking (201, or 200 if idempotent replay) |
| GET | `/api/v1/bookings` | List bookings (filter by venue, booker, status, time range) |
| GET | `/api/v1/bookings/{booking_id}` | Get booking detail |
| PUT | `/api/v1/bookings/{booking_id}` | Update booking |
| POST | `/api/v1/bookings/{booking_id}/cancel` | Cancel booking |

Key behaviors:
- **Idempotency**: Sending the same `client_ref` + `booked_by` returns the existing booking with HTTP 200 instead of creating a duplicate.
- **Conflict detection**: Overlapping approved bookings for the same venue or equipment return 409.
- **Equipment validation**: Equipment must be `active` and belong to the booking's venue (if venue-assigned).
- **Completed bookings**: Cannot be modified or cancelled.
- **Derived status**: Response includes a computed `derived_status` (approved / active / completed / cancelled) based on current time.

### 1.4 Utilization Statistics

Aggregated usage metrics for venues and equipment over configurable date windows.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/stats/venue-utilization` | Per-venue utilization rates |
| GET | `/api/v1/stats/equipment-usage` | Per-equipment booking hours |
| GET | `/api/v1/stats/peak-hours` | Booking count per hour-of-day |

All endpoints accept `start_date` / `end_date` query params. Default window is 7 days ending today. Maximum window is 90 days.

### 1.5 XR Extension Stubs

Pluggable XR (extended reality) provider abstraction. Ships with a no-op `NullXRProvider`. All XR behavior is gated behind `XR_ENABLED=false` by default.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/xr/callbacks` | Receive XR provider callback (public, no auth) |
| GET | `/api/v1/xr/sessions` | List XR sessions (filter by status, provider) |
| POST | `/api/v1/xr/sessions/{session_id}/retry` | Retry a failed XR session |

---

## 2. Permission Matrix

| Endpoint Group | admin | facility_manager | teacher | student |
|---|---|---|---|---|
| **Venues** | | | | |
| Create / Update / Status / Availability | full | full | -- | -- |
| List venues | full | full | read (active only) | 403 |
| Get venue detail | full | full | read (active only) | 403 |
| Create / Delete blackouts | full | full | -- | -- |
| List blackouts | full | full | read (active venue only) | 403 |
| **Equipment** | | | | |
| Create / Update / Status / Unassign | full | full | -- | -- |
| List equipment | full | full | read (active only) | 403 |
| Get equipment detail | full | full | read (active only) | 403 |
| **Bookings** | | | | |
| Create booking | full | full | full (own) | -- |
| List bookings | full | all visible | own only | 403 |
| Get booking detail | full | all visible | own only | 403 |
| Update booking | full | full | own only | -- |
| Cancel booking | full | full | own only | -- |
| **Stats** | | | | |
| Venue utilization | full | full | -- | -- |
| Equipment usage | full | full | -- | -- |
| Peak hours | full | full | -- | -- |
| **XR** | | | | |
| Callbacks (public) | n/a | n/a | n/a | n/a |
| List sessions | full | full | -- | -- |
| Retry session | full | full | -- | -- |

Legend: `full` = read and write access, `read` = filtered read-only, `own` = can only access own resources, `--` = denied (403).

---

## 3. Utilization Stats Methodology

### 3.1 Venue Utilization Rate

```
utilization_rate = booked_hours / available_hours
```

**Numerator (booked_hours)**: Sum of overlapping seconds between approved bookings and the query window, converted to hours. Uses `TIMESTAMPDIFF(SECOND, GREATEST(start_time, window_start), LEAST(end_time, window_end))` to clip bookings that extend beyond the window boundaries. Only bookings with `status = 'approved'` are counted.

**Denominator (available_hours)**: Total hours a venue is theoretically available within the window, computed by `_available_hours_in_window`:

1. If no availability slots are configured for a venue, the venue is assumed to be available 24h/day.
2. If availability slots exist, hours are summed per `day_of_week` (0=Monday through 6=Sunday based on Python `datetime.weekday()`).
3. Blackout dates are deducted: any date covered by a blackout period is excluded entirely from the available-hours sum.
4. Blackout ranges are clipped to the query window before exclusion.

If `available_hours` is 0 (e.g., all days are blacked out), `utilization_rate` is returned as `null`.

### 3.2 Cancelled Bookings

Cancelled bookings (`status = 'cancelled'`) are excluded from both the numerator and the denominator calculation. Only `status = 'approved'` bookings contribute to utilization.

### 3.3 Equipment Usage

Equipment usage does not compute a rate. Instead, it returns:
- `booking_count`: distinct number of approved bookings that included the equipment
- `total_hours`: sum of clipped booking hours for those bookings

Equipment of any status is included in results (not limited to `active`).

### 3.4 Time Window Rules

- Default window: 7 days ending today (`end_date - 6 days` to `end_date`)
- Maximum window: 90 days. Requests exceeding this return 400.
- `start_date` must be <= `end_date`
- Both dates are inclusive (the window covers the full end_date day)

---

## 4. XR Extension Architecture

### 4.1 Provider Abstraction

The XR integration uses a Protocol-based provider pattern (`app/services/xr_provider.py`):

- **`XRProvider` (Protocol)**: Defines the interface all providers must implement:
  - `name` property
  - `create_session(booking_id)` -> `XRResult`
  - `cancel_session(session_id)` -> `XRResult`
  - `update_session(session_id, updates)` -> `XRResult`

- **`XRResult` (dataclass)**: Standardized return type with `success`, `external_session_id`, `error`, and `raw_response` fields.

- **`NullXRProvider`**: No-op implementation. All methods return `XRResult(success=True)` with no external calls. This is the default when `XR_PROVIDER=null`.

- **`_PROVIDER_REGISTRY`**: Dictionary mapping provider name strings to provider classes. Currently contains `{"null": NullXRProvider}`.

- **`get_xr_provider()`**: Factory function that reads `settings.XR_PROVIDER` and instantiates the registered class. Raises `ValueError` for unknown providers.

### 4.2 Booking-XR Session Binding Lifecycle

1. **On booking creation** (`POST /bookings`): If `XR_ENABLED=true` and the booking is not an idempotent replay, a background task (`create_xr_session_for_booking`) is scheduled. This task:
   - Opens its own DB session (runs outside request lifecycle)
   - Checks for existing session (idempotent guard)
   - Creates an `XRSession` record with `status='pending'`
   - Calls the provider's `create_session`
   - Updates the session to `completed` or `failed` based on the result

2. **On booking cancellation** (`POST /bookings/{id}/cancel`): If `XR_ENABLED=true`, a background task (`cancel_xr_session_for_booking`) calls the provider's `cancel_session` and sets the session status to `cancelled`.

### 4.3 Callback Event Processing

The `POST /api/v1/xr/callbacks` endpoint receives asynchronous events from XR providers:

1. **Signature verification**: If `XR_CALLBACK_SECRET` is configured, the `X-XR-Signature` header is validated using HMAC-SHA256.
2. **Deduplication**: Two levels:
   - By `event_id` (unique in `xr_events` table)
   - By `idempotency_key` (optional, also unique-indexed)
   - Duplicate events return `{status: "already_processed"}` instead of erroring.
3. **Session status update**: If the event payload contains a `booking_id` that maps to an existing `XRSession`, the session status is updated based on `event_type`:
   - `session.started` -> `active`
   - `session.completed` -> `completed`
   - `session.failed` -> `failed`
   - `session.cancelled` -> `cancelled`
4. **Event recording**: All events (new or duplicate) are recorded in the `xr_events` table with `processed=True`.

### 4.4 Feature Flag Isolation

All XR behavior is gated by `XR_ENABLED` (default: `false`):

- Background tasks return immediately if `XR_ENABLED=false`
- The callback endpoint returns 503 if `XR_ENABLED=false`
- The retry endpoint returns 503 if `XR_ENABLED=false`
- Session listing works regardless of the flag (read-only, no provider calls)

This means Phase 3 can be deployed with zero XR impact. The `xr_sessions` and `xr_events` tables are created but remain empty.

### 4.5 Adding a Real Provider

To integrate a real XR platform:

1. Create a new class implementing the `XRProvider` protocol in `app/services/xr_provider.py`.
2. Register it in `_PROVIDER_REGISTRY` with a unique key (e.g., `"unity"`).
3. Set environment variables: `XR_ENABLED=true`, `XR_PROVIDER=unity`, `XR_CALLBACK_SECRET=<shared-secret>`.
4. Run the existing test suite -- NullXRProvider tests verify the contract is preserved.

The provider class only needs async methods. No changes to routers, schemas, or the session lifecycle are required.

---

## 5. Deployment / Rollback / Troubleshooting Runbook

### 5.1 Migration Chain

Phase 3 adds three sequential migrations on top of the existing chain:

```
59e37cad18dd (add audit logs)
  -> eaa79625a9ad (add venues, equipment, bookings tables)
    -> c1a2b3d4e5f6 (add venue_availability, venue_blackout tables)
      -> a1b2c3d4e5f7 (add xr_sessions, xr_events tables)
```

### 5.2 Upgrade Procedure

```bash
# Review pending migrations
alembic current
alembic history

# Apply all pending migrations
alembic upgrade head

# Verify
alembic current   # Should show: a1b2c3d4e5f7
```

### 5.3 Rollback Procedure

```bash
# Roll back XR tables only
alembic downgrade a1b2c3d4e5f7   # to c1a2b3d4e5f6

# Roll back XR + availability/blackout
alembic downgrade c1a2b3d4e5f6   # to eaa79625a9ad

# Roll back all Phase 3 tables (venues, equipment, bookings, availability, blackout, XR)
alembic downgrade eaa79625a9ad   # to 59e37cad18dd

# Nuclear: roll back everything
alembic downgrade base
```

**Warning**: Downgrading drops tables with CASCADE. All data in those tables is lost. Backup before rolling back.

### 5.4 Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `mysql+aiomysql://root:rootpassword@127.0.0.1:3306/training_platform` | yes | Async database connection |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | yes | JWT signing key (MUST change in production) |
| `XR_ENABLED` | `false` | no | Enable XR integration |
| `XR_PROVIDER` | `null` | no | Provider name (currently only `null`) |
| `XR_CALLBACK_SECRET` | `""` | no | HMAC-SHA256 secret for callback verification |

Standard variables from earlier phases still apply: `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `UPLOAD_DIR`, `LOCKOUT_THRESHOLD`, `LOCKOUT_DURATION_MINUTES`, `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`.

### 5.5 Key Monitoring Points

- **Booking conflict rate**: Monitor 409 responses on `POST /bookings`. A high rate may indicate UI not showing live availability.
- **XR session failure rate**: Monitor `xr_sessions` where `status = 'failed'`. Retry via `POST /xr/sessions/{id}/retry`.
- **Duplicate callback rate**: Check `xr_events` for repeated `event_id` values. High duplicate rate suggests provider misconfiguration.
- **Utilization stats latency**: The stats queries use `TIMESTAMPDIFF` and aggregation. Monitor response times for windows approaching the 90-day limit.
- **Audit log growth**: Phase 3 writes audit entries for all venue, equipment, and booking mutations. Monitor table size.

### 5.6 Common Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 409 on booking creation | Time conflict with existing approved booking | Check existing bookings for that venue/equipment in the time range |
| 409 on equipment create | Duplicate `serial_number` | Use a unique serial number or omit it |
| 200 instead of 201 on booking create | Idempotent replay of same `client_ref` | Expected behavior; first call returns 201, replays return 200 |
| 503 on XR callback | `XR_ENABLED=false` | Set `XR_ENABLED=true` if XR integration is desired |
| 400 "已结束的预约无法修改" | Attempting to modify a past booking | Only future bookings can be updated or cancelled |
| 400 "设备不属于该场地" | Equipment assigned to venue A, booking on venue B | Assign equipment to the correct venue first, or use unassigned equipment |
| Utilization rate is null | No availability slots configured AND all days blacked out, OR venue is inactive | Check venue status and availability/blackout configuration |
| Stats return empty results | No approved bookings in the window | Verify bookings exist and have `status='approved'` |

---

## 6. Known Limitations

1. **No recurring bookings**: Each booking is a single time range. Recurring schedules must be created as individual bookings.

2. **Availability is advisory only**: Weekly availability slots (`VenueAvailability`) are used by stats to compute utilization rate but are NOT enforced during booking creation. A booking can be made outside configured availability hours.

3. **Blackout periods are not enforced at booking time**: Similar to availability, blackouts are used in stats calculations but do not block booking creation. Enforcement is expected in a future phase.

4. **Equipment conflict detection is per-unit**: Equipment is tracked as individual units (with serial numbers). There is no quantity-based booking (e.g., "5 headsets"). Each equipment item can only be in one approved booking at a time.

5. **XR is a stub**: The `NullXRProvider` makes no external calls. All XR sessions are immediately marked `completed`. A real provider must be implemented and registered before XR functionality is meaningful.

6. **No booking approval workflow**: All valid bookings are immediately set to `approved` status. There is no pending-approval state for admin review.

7. **Stats window limit**: Maximum 90-day query window. Longer-range analytics require exporting data to an external tool.

8. **Teacher list filtering**: Teachers can only see their own bookings in the list endpoint. This is by design (data isolation) but means teachers cannot check venue availability by browsing bookings.

9. **Cascade deletes**: Deleting a venue cascades to its availability, blackouts, and unassigns equipment. Deleting a booking cascades to its equipment links and XR session. These are hard deletes with no soft-delete recovery.

10. **No pagination for blackouts**: The `GET /venues/{id}/blackouts` endpoint returns all blackouts without pagination. This is acceptable for typical data volumes but may need pagination if blackout records grow large.

11. **Callback endpoint has no rate limiting**: The `POST /xr/callbacks` endpoint is public and has no built-in rate limiting. Deploy behind a reverse proxy or API gateway with rate limiting in production.

12. **Audit log is append-only with no cleanup**: All Phase 3 mutations write to the `audit_logs` table. No automatic cleanup or archival mechanism exists.
