## ADDED Requirements

### Requirement: Equipment model and storage
The system SHALL store equipment records with fields: id (auto-increment PK), name (VARCHAR 100, NOT NULL), category (VARCHAR 50, nullable), serial_number (VARCHAR 100, nullable, unique), status (ENUM: active, inactive, maintenance, default active), venue_id (FK → venues, nullable — indicates usual location), external_id (VARCHAR 100, nullable, indexed), description (TEXT, nullable), created_at (naive UTC datetime), updated_at (naive UTC datetime).

#### Scenario: Create equipment with venue assignment
- **WHEN** a facility_manager creates equipment with name "VR Headset #1", category "VR", serial_number "VR-001", venue_id pointing to an active venue
- **THEN** the system creates the equipment record with status "active" and the venue association

#### Scenario: Create equipment without venue
- **WHEN** a facility_manager creates equipment with name "Portable Projector", category "Projector", no venue_id
- **THEN** the system creates the equipment with venue_id null

#### Scenario: Duplicate serial_number rejected
- **WHEN** a facility_manager creates equipment with serial_number that already exists
- **THEN** the system returns 409 Conflict

### Requirement: Equipment CRUD access control
The system SHALL restrict equipment write operations to admin and facility_manager. Read operations SHALL be available to admin, facility_manager, and teacher. Student role SHALL have no access.

#### Scenario: Teacher queries equipment by category
- **WHEN** a teacher requests GET /api/v1/equipment?category=VR
- **THEN** the system returns 200 with equipment filtered by category and status active

#### Scenario: Student denied equipment access
- **WHEN** a student requests any equipment endpoint
- **THEN** the system returns 403

### Requirement: Equipment status management
The system SHALL support equipment status transitions: active → inactive, active → maintenance, inactive → active, maintenance → active.

#### Scenario: Mark equipment as maintenance
- **WHEN** a facility_manager updates equipment status to "maintenance"
- **THEN** the equipment status changes and an audit log is created

#### Scenario: Book maintenance equipment
- **WHEN** a user attempts to include equipment with status "maintenance" in a booking
- **THEN** the system rejects the booking with 400 Bad Request

### Requirement: Equipment audit logging
The system SHALL create an AuditLog entry for every equipment create, update, and status change.

#### Scenario: Equipment update logged
- **WHEN** a facility_manager updates equipment name
- **THEN** an AuditLog entry exists with entity_type "equipment", action "update", changes containing old and new name

### Requirement: Equipment external_id for XR
The system SHALL store an optional external_id field on each equipment record, indexed. This field SHALL NOT affect core booking logic.

#### Scenario: Query equipment by external_id
- **WHEN** a system queries equipment where external_id = "xr-device-0099"
- **THEN** the matching equipment record is returned
