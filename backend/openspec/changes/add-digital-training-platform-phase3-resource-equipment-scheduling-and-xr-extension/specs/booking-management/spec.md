## ADDED Requirements

### Requirement: Booking model and storage
The system SHALL store booking records with fields: id (auto-increment PK), venue_id (FK → venues, NOT NULL), title (VARCHAR 200, NOT NULL), purpose (TEXT, nullable), start_time (naive UTC datetime, NOT NULL), end_time (naive UTC datetime, NOT NULL), booked_by (FK → users, NOT NULL), status (VARCHAR 20, default "approved"), course_id (FK → courses, nullable), class_id (FK → classes, nullable), task_id (FK → tasks, nullable), client_reference (VARCHAR 100, unique nullable, indexed), created_at (naive UTC datetime), updated_at (naive UTC datetime).

The system SHALL validate start_time < end_time on creation and update.

#### Scenario: Create a basic booking
- **WHEN** a teacher creates a booking with venue_id=1, title="Robotics Lab Session", start_time="2026-05-01 09:00", end_time="2026-05-01 11:00"
- **THEN** the system creates the booking with status "approved", booked_by set to the teacher's user id

#### Scenario: Create booking with course context
- **WHEN** a teacher creates a booking with venue_id, title, time range, course_id=5, class_id=3
- **THEN** the booking is linked to the course and class for context

#### Scenario: Invalid time range rejected
- **WHEN** a user creates a booking with start_time >= end_time
- **THEN** the system returns 422 Unprocessable Entity

### Requirement: Booking-equipment association
The system SHALL support associating zero or more equipment items with a booking via a join table booking_equipment(booking_id, equipment_id). The association SHALL use all-or-nothing semantics: if any equipment conflict exists, the entire booking creation fails.

#### Scenario: Create booking with equipment
- **WHEN** a teacher creates a booking with venue_id=1 and equipment_ids=[2, 3, 5]
- **THEN** the system creates the booking and three booking_equipment rows

#### Scenario: Equipment conflict fails entire booking
- **WHEN** a teacher creates a booking with equipment_ids=[2, 3] where equipment_id=3 has a time overlap
- **THEN** the system returns 409 Conflict, no booking or booking_equipment rows are created

### Requirement: Time conflict detection
The system SHALL prevent overlapping bookings for the same venue or equipment. Conflict detection SHALL use half-open interval logic: a booking [start, end) conflicts with existing booking [s, e) when start < e AND end > s.

#### Scenario: No conflict for same venue different time
- **WHEN** a booking exists for venue_id=1 from 09:00-11:00 and a new booking is created for venue_id=1 from 11:00-13:00
- **THEN** no conflict is detected (end == start is allowed)

#### Scenario: Conflict detected for same venue overlapping time
- **WHEN** a booking exists for venue_id=1 from 09:00-11:00 and a new booking is attempted for venue_id=1 from 10:30-12:00
- **THEN** the system returns 409 Conflict

#### Scenario: Conflict on equipment across different venues
- **WHEN** a booking exists with equipment_id=5 from 09:00-11:00 and a new booking in a different venue also requests equipment_id=5 from 10:00-12:00
- **THEN** the system returns 409 Conflict on equipment

#### Scenario: Exclude self on update
- **WHEN** a user updates booking id=42 to extend end_time from 11:00 to 12:00
- **THEN** the conflict check excludes booking id=42 from the overlap query

### Requirement: Concurrency control for bookings
The system SHALL use pessimistic row locking (SELECT FOR UPDATE) on venue and equipment rows during booking creation and update. Locks SHALL be acquired in a consistent order (venue first, then equipment by id ascending) to minimize deadlocks.

#### Scenario: Concurrent booking creation
- **WHEN** two users simultaneously create bookings for the same venue in overlapping time slots
- **THEN** one succeeds and the other receives 409 Conflict

### Requirement: Booking status lifecycle
The system SHALL support booking statuses: approved, cancelled. Status active and completed are derived at query time (start_time <= now < end_time → active, end_time <= now → completed). The system SHALL NOT allow modifying the time range of a booking whose start_time is in the past.

#### Scenario: Cancel a future booking
- **WHEN** the booker cancels a booking with future start_time
- **THEN** the booking status changes to "cancelled" and an audit log is created

#### Scenario: Cancel a past booking
- **WHEN** a user attempts to cancel a booking with past end_time
- **THEN** the system returns 400 Bad Request

#### Scenario: Modify past booking rejected
- **WHEN** a user attempts to change start_time of a booking that has already started
- **THEN** the system returns 400 Bad Request

### Requirement: Booking access control
Admin and facility_manager SHALL have full access to all bookings. Teacher SHALL be able to create bookings, view bookings they created or bookings linked to their courses/classes, and cancel their own bookings. Student SHALL have no booking access.

#### Scenario: Teacher views own bookings
- **WHEN** a teacher requests GET /api/v1/bookings?my=true
- **THEN** the system returns only bookings where booked_by matches the teacher's user id

#### Scenario: Teacher cancels another teacher's booking
- **WHEN** teacher A attempts to cancel a booking created by teacher B
- **THEN** the system returns 403 Forbidden

#### Scenario: Admin cancels any booking
- **WHEN** an admin cancels a booking created by a teacher
- **THEN** the booking is cancelled successfully

### Requirement: Booking audit logging
The system SHALL create AuditLog entries for booking create, update, and cancel operations.

#### Scenario: Booking creation logged
- **WHEN** a booking is created
- **THEN** an AuditLog entry exists with entity_type "booking", action "create", entity_id matching the booking id, actor_id matching the booker, changes containing venue_id, start_time, end_time, equipment_ids

### Requirement: Booking client_reference for idempotency
The system SHALL accept an optional client_reference field. If provided and a booking with that client_reference already exists, the system SHALL return the existing booking (200) instead of creating a duplicate.

#### Scenario: Idempotent booking creation
- **WHEN** a booking is created with client_reference="xr-session-123" and that reference already exists
- **THEN** the system returns 200 with the existing booking data

#### Scenario: Unique client_reference
- **WHEN** two different bookings are created with the same client_reference
- **THEN** the second creation returns the first booking (idempotent behavior)

### Requirement: Resource availability check before booking
The system SHALL validate that the venue and all requested equipment have status "active" before allowing a booking. Inactive or maintenance resources SHALL cause a 400 error.

#### Scenario: Book inactive venue
- **WHEN** a user creates a booking for a venue with status "inactive"
- **THEN** the system returns 400 with message about venue availability

#### Scenario: Book maintenance equipment
- **WHEN** a user creates a booking including equipment with status "maintenance"
- **THEN** the system returns 400 with message about equipment availability
