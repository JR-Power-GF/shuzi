## ADDED Requirements

### Requirement: Venue model and storage
The system SHALL store venue records with fields: id (auto-increment PK), name (VARCHAR 100, NOT NULL), capacity (INTEGER, nullable), location (VARCHAR 200, nullable), description (TEXT, nullable), status (ENUM: active, inactive, maintenance, default active), external_id (VARCHAR 100, nullable, indexed), created_at (naive UTC datetime), updated_at (naive UTC datetime).

#### Scenario: Create a venue with all fields
- **WHEN** a facility_manager or admin submits a venue with name "XR Lab A", capacity 30, location "Building 3 Floor 2"
- **THEN** the system creates a venue record with status "active" and returns 201 with the venue data

#### Scenario: Create a venue with minimal fields
- **WHEN** a facility_manager submits a venue with only name "Workshop B"
- **THEN** the system creates a venue with null capacity, location, description, status "active"

### Requirement: Venue CRUD access control
The system SHALL restrict venue write operations (create, update, delete) to users with role admin or facility_manager. Read operations SHALL be available to admin, facility_manager, and teacher roles. Student role SHALL have no access to venue endpoints.

#### Scenario: Teacher reads venue list
- **WHEN** a teacher requests GET /api/v1/venues
- **THEN** the system returns 200 with a list of venues with status active

#### Scenario: Student attempts venue access
- **WHEN** a student requests GET /api/v1/venues
- **THEN** the system returns 403 Forbidden

#### Scenario: Facility manager creates venue
- **WHEN** a facility_manager submits POST /api/v1/venues with valid data
- **THEN** the system creates the venue and returns 201

### Requirement: Venue status management
The system SHALL support venue status transitions: active → inactive, active → maintenance, inactive → active, maintenance → active. Status SHALL NOT be deleted; venues use soft status changes.

#### Scenario: Mark venue as maintenance
- **WHEN** a facility_manager updates a venue status to "maintenance"
- **THEN** the venue status changes and an audit log entry is created with entity_type "venue", action "status_change"

#### Scenario: Create booking for inactive venue
- **WHEN** a user attempts to create a booking for a venue with status "maintenance"
- **THEN** the system returns 400 Bad Request with message indicating venue is not available

### Requirement: Venue audit logging
The system SHALL create an AuditLog entry for every venue create, update, and status change operation. The changes field SHALL contain the modified fields and their new values.

#### Scenario: Venue creation logged
- **WHEN** a venue is created
- **THEN** an AuditLog entry exists with entity_type "venue", action "create", entity_id matching the venue id, and changes containing the venue name

### Requirement: Venue external_id for XR integration
The system SHALL store an optional external_id field on each venue, indexed for lookup. This field SHALL NOT affect core booking logic.

#### Scenario: Set external_id on venue
- **WHEN** a facility_manager updates a venue with external_id "xr-venue-0042"
- **THEN** the venue record stores the external_id and it can be queried by exact match
