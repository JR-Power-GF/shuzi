## ADDED Requirements

### Requirement: Venue utilization rate calculation
The system SHALL calculate venue utilization rate per natural week (Monday 00:00 to Sunday 23:59 local interpretation of UTC). The rate is: numerator = total hours of approved (non-cancelled) bookings for the venue in the week; denominator = number of days the venue had status "active" in that week × 24 hours.

#### Scenario: Full week utilization
- **WHEN** a venue has status "active" all 7 days of a week and has approved bookings totaling 40 hours
- **THEN** the utilization rate is 40 / (7 × 24) = 23.8%

#### Scenario: Partial week due to maintenance
- **WHEN** a venue was active for 5 days and in maintenance for 2 days of a week, with approved bookings totaling 30 hours
- **THEN** the utilization rate is 30 / (5 × 24) = 25.0%

#### Scenario: Cancelled bookings excluded from numerator
- **WHEN** a venue has 20 hours of approved bookings and 5 hours of cancelled bookings in a week
- **THEN** the numerator is 20 (cancelled excluded)

### Requirement: Equipment usage frequency
The system SHALL count equipment usage frequency per natural week. The count is the number of approved (non-cancelled) bookings that include the equipment, split across natural weeks for multi-day bookings.

#### Scenario: Equipment used in 3 bookings
- **WHEN** equipment_id=5 appears in 3 approved bookings within a week
- **THEN** the usage frequency for that week is 3

#### Scenario: Multi-day booking split across weeks
- **WHEN** a booking spans from Friday 10:00 to Monday 10:00 and includes equipment_id=2
- **THEN** equipment_id=2 gets count 1 in week 1 (Fri-Sun) and count 1 in week 2 (Mon)

### Requirement: Peak hours distribution
The system SHALL provide a peak hours distribution for the last 30 days, counting the number of approved bookings per hour-of-day bucket (0-23). Cancelled bookings SHALL be excluded.

#### Scenario: Peak hours query
- **WHEN** a facility_manager requests peak hours statistics
- **THEN** the system returns a 24-element array where each element is the count of approved bookings whose time range overlaps that hour

### Requirement: Statistics access control
Statistics endpoints SHALL be restricted to admin and facility_manager roles.

#### Scenario: Teacher denied statistics
- **WHEN** a teacher requests GET /api/v1/dashboard/resource-statistics
- **THEN** the system returns 403

#### Scenario: Facility manager views statistics
- **WHEN** a facility_manager requests resource statistics
- **THEN** the system returns 200 with the computed data

### Requirement: Statistics query performance guard
Statistics queries SHALL apply a LIMIT of 100 resources maximum per request and SHALL require a time range parameter (start_date, end_date). Default time range SHALL be the last 7 days.

#### Scenario: Query without time range
- **WHEN** a facility_manager requests statistics without specifying dates
- **THEN** the system returns data for the last 7 days

#### Scenario: Query exceeds resource limit
- **WHEN** a query would return more than 100 venues
- **THEN** the system returns the top 100 sorted by utilization descending
