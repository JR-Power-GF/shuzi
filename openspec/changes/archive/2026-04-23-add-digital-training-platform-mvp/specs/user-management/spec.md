## ADDED Requirements

### Requirement: Admin can create user accounts
The system SHALL allow admin to create teacher and student accounts with username, password, name, and role. Admin MAY also set email, phone, and primary_class_id (for students). No self-registration.

**User story:** As an admin, I want to create user accounts so that teachers and students can access the platform.

**Permission boundary:** Admin only. No self-registration endpoint exists.

#### Scenario: Create teacher account
- **WHEN** admin submits POST /api/users with role=teacher, username, password, name
- **THEN** system creates user with hashed password, is_active=true, must_change_password=true, returns 201

#### Scenario: Create student account with class
- **WHEN** admin submits POST /api/users with role=student, username, password, name, primary_class_id
- **THEN** system creates user and enrolls in specified class, returns 201

#### Scenario: Duplicate username
- **WHEN** admin submits POST /api/users with username that already exists
- **THEN** system returns 409 with error "用户名已存在"

#### Scenario: Non-admin attempts to create user
- **WHEN** teacher or student attempts POST /api/users
- **THEN** system returns 403

#### Edge case: Create student without primary_class_id
- **WHEN** admin creates a student without specifying primary_class_id
- **THEN** system creates user with primary_class_id=null (student can see no tasks until enrolled)

### Requirement: Admin can list and search users
The system SHALL provide paginated user list with filtering by role and searching by name/username.

**User story:** As an admin, I want to search and filter users so that I can find specific accounts quickly.

**Permission boundary:** Admin only.

#### Scenario: List with filters
- **WHEN** admin submits GET /api/users?role=student&search=张&page=1
- **THEN** system returns paginated list of matching users (default 20 per page)

### Requirement: Admin can edit user accounts
The system SHALL allow admin to update name, email, phone, primary_class_id, and role of any user.

**User story:** As an admin, I want to edit user details so that I can keep records accurate.

**Permission boundary:** Admin only.

#### Scenario: Edit user
- **WHEN** admin submits PUT /api/users/:id with updated fields
- **THEN** system updates user and returns 200

#### Edge case: Change student's primary_class_id after they have submissions
- **WHEN** admin changes a student's class while they have submissions in the old class
- **THEN** existing submissions remain linked to the original task/class (data integrity preserved), student sees new class tasks going forward

### Requirement: Admin can deactivate user accounts
The system SHALL allow admin to deactivate a user. Deactivated users cannot log in. All data (submissions, grades) is preserved.

**User story:** As an admin, I want to deactivate a user's account without deleting their data so that historical records are preserved.

**Permission boundary:** Admin only, cannot deactivate self.

#### Scenario: Deactivate user
- **WHEN** admin submits PUT /api/users/:id/deactivate
- **THEN** system sets is_active=false, user cannot log in, all existing data remains visible to teachers

#### Scenario: Cannot deactivate self
- **WHEN** admin attempts to deactivate their own account
- **THEN** system returns 400 with error "不能停用自己的账户"

#### Edge case: Deactivate teacher who created tasks
- **WHEN** admin deactivates a teacher who has created tasks with submissions
- **THEN** tasks and submissions remain visible to students and admin, grades remain accessible

### Requirement: Users can view and edit their own profile
The system SHALL allow any authenticated user to view their own profile and edit name, email, phone.

**User story:** As any user, I want to view and update my profile information so that my contact details are current.

**Permission boundary:** Any authenticated user, own account only. Cannot change role, username, or is_active.

#### Scenario: View own profile
- **WHEN** user submits GET /api/users/me
- **THEN** system returns user profile without password hash

#### Scenario: Edit own profile
- **WHEN** user submits PUT /api/users/me with updated name, email, phone
- **THEN** system updates user and returns 200
