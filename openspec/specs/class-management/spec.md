## ADDED Requirements

### Requirement: Admin can create classes
The system SHALL allow admin to create a class with name, semester, and optional teacher_id (head teacher).

**User story:** As an admin, I want to create classes organized by semester so that students can be grouped and teachers assigned.

**Permission boundary:** Admin only.

#### Scenario: Create class with semester
- **WHEN** admin submits POST /api/classes with name="计算机网络1班" and semester="2025-2026-2"
- **THEN** system creates class and returns 201

#### Scenario: Create class with teacher
- **WHEN** admin submits POST /api/classes with name, semester, and teacher_id
- **THEN** system creates class with assigned teacher, returns 201

#### Edge case: Create class with non-existent teacher_id
- **WHEN** admin creates a class with a teacher_id that does not exist
- **THEN** system returns 422 with foreign key violation error

### Requirement: Admin can edit classes
The system SHALL allow admin to update class name, semester, and teacher_id.

**User story:** As an admin, I want to update class details so that records stay accurate when teachers or semesters change.

**Permission boundary:** Admin only.

#### Scenario: Edit class
- **WHEN** admin submits PUT /api/classes/:id with updated fields
- **THEN** system updates class and returns 200

### Requirement: Admin can delete empty classes
The system SHALL allow admin to delete a class only if it has no students.

**User story:** As an admin, I want to delete a class that was created by mistake, as long as no students are enrolled.

**Permission boundary:** Admin only. Deletion blocked if students enrolled.

#### Scenario: Delete empty class
- **WHEN** admin submits DELETE /api/classes/:id and class has no students
- **THEN** system deletes class and returns 200

#### Scenario: Delete class with students
- **WHEN** admin submits DELETE /api/classes/:id and class has students
- **THEN** system returns 400 with error "班级内还有学生，无法删除"

#### Edge case: Delete class that has tasks but no students
- **WHEN** admin deletes a class that has tasks created by a teacher but no enrolled students
- **THEN** system deletes class and cascades to delete orphaned tasks (no submissions to preserve)

### Requirement: Admin can list all classes
The system SHALL provide paginated class list with optional semester filter.

**User story:** As an admin, I want to see all classes so that I can manage the platform's organization.

**Permission boundary:** Admin only.

#### Scenario: List classes by semester
- **WHEN** admin submits GET /api/classes?semester=2025-2026-2&page=1
- **THEN** system returns paginated class list with teacher name and student count

### Requirement: Teacher can view their own classes
The system SHALL provide an endpoint for teachers to see only classes assigned to them.

**User story:** As a teacher, I want to see my assigned classes so that I can create tasks for the right groups.

**Permission boundary:** Teacher only. Returns only classes where teacher_id matches current user.

#### Scenario: Teacher views assigned classes
- **WHEN** teacher submits GET /api/classes/my
- **THEN** system returns only classes where teacher_id matches current user

### Requirement: Admin can enroll students in a class
The system SHALL allow admin to add students to a class.

**User story:** As an admin, I want to enroll students in classes so that they can see and submit to tasks.

**Permission boundary:** Admin only.

#### Scenario: Enroll student
- **WHEN** admin submits POST /api/classes/:id/students with student_id
- **THEN** system sets student's primary_class_id to this class, returns 200

#### Scenario: Student already in class
- **WHEN** admin submits POST /api/classes/:id/students with student already enrolled
- **THEN** system returns 200 without error (idempotent)

#### Edge case: Enroll student who is already in another class
- **WHEN** admin enrolls a student who has primary_class_id set to a different class
- **THEN** system updates primary_class_id to the new class (student transfers), returns 200

### Requirement: Admin and teacher can view class students
The system SHALL allow admin and the class's teacher to see enrolled students.

**User story:** As a teacher, I want to see my class roster so that I know who should be submitting work.

**Permission boundary:** Admin or assigned teacher only. Other teachers get 403.

#### Scenario: View class roster
- **WHEN** admin or assigned teacher submits GET /api/classes/:id/students
- **THEN** system returns list of students in the class

#### Scenario: Teacher views other class's students
- **WHEN** teacher not assigned to class submits GET /api/classes/:id/students
- **THEN** system returns 403
