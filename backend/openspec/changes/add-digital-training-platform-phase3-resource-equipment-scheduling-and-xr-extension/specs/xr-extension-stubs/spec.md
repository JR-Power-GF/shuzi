## ADDED Requirements

### Requirement: XRProvider protocol abstraction
The system SHALL define an abstract XRProvider protocol (Python Protocol class) with methods for creating, updating, and cancelling XR sessions. V1 SHALL provide a NullXRProvider that performs no external calls and returns success for all operations.

#### Scenario: NullXRProvider on booking creation
- **WHEN** a booking is created and the system calls xr_provider.on_booking_created(booking)
- **THEN** NullXRProvider returns success without making any external call

### Requirement: External ID fields on resources
The system SHALL include an external_id field (VARCHAR, nullable, indexed) on Venue and Equipment models. This field stores the corresponding resource identifier in an external XR system. The field SHALL NOT be required for any core booking operation.

#### Scenario: Venue with external_id
- **WHEN** a venue is created with external_id="xr-room-0042"
- **THEN** the external_id is stored and can be queried by exact match

#### Scenario: Booking works without external_id
- **WHEN** a venue has null external_id and a booking is created for it
- **THEN** the booking succeeds normally

### Requirement: Client reference for idempotent booking
The system SHALL accept an optional client_reference field on Booking. When provided, the system SHALL enforce uniqueness. If a booking with the same client_reference already exists, the system SHALL return the existing booking instead of creating a duplicate.

#### Scenario: XR system retries booking creation
- **WHEN** an external XR system creates a booking with client_reference="xr-session-abc" and the booking already exists
- **THEN** the system returns 200 with the existing booking, no new booking is created

### Requirement: Audit trail for XR event tracking
The system SHALL record all booking state transitions in AuditLog. XR systems can poll AuditLog entries with entity_type="booking" to detect changes. No webhook or push mechanism is required in V1.

#### Scenario: XR system queries booking events
- **WHEN** an external system queries AuditLog for entity_type="booking" and action="create" after a given timestamp
- **THEN** all booking creation events after that timestamp are returned

### Requirement: XR provider injection
The system SHALL inject the XRProvider via dependency injection. Default injection uses NullXRProvider. The provider can be swapped in configuration without modifying booking logic code.

#### Scenario: Swap XR provider
- **WHEN** the application configuration specifies a concrete XRProvider implementation
- **THEN** all booking operations use that provider instead of NullXRProvider
