## MODIFIED Requirements

### Requirement: Teacher can create tasks
The system SHALL allow teacher to create a task assigned to one class with title, description, requirements, deadline, allowed_file_types, max_file_size_mb, allow_late_submission, and optional late_penalty_percent. The system SHALL also accept an optional `course_id` parameter. If provided, the course MUST belong to the teacher (course.teacher_id == current_user.id).

**User story:** As a teacher, I want to create a task for my class with clear requirements and deadlines so that students know what to submit. I also want to optionally associate the task with a course.

**Permission boundary:** Teacher only, and only for classes assigned to them (verified by class.teacher_id == current_user.id). If course_id is provided, the course must be owned by the teacher.

#### Scenario: Create task with all fields
- **WHEN** teacher submits POST /api/tasks with title, description, requirements, class_id, deadline, allowed_file_types, max_file_size_mb, allow_late_submission=false
- **THEN** system creates task with semester copied from class, status=active, grades_published=false, returns 201

#### Scenario: Create task with late penalty
- **WHEN** teacher creates task with allow_late_submission=true and late_penalty_percent=10
- **THEN** system creates task with late penalty configured

#### Scenario: Create task for non-owned class
- **WHEN** teacher creates task for a class they are not assigned to
- **THEN** system returns 403

#### Scenario: Create task with course_id
- **WHEN** teacher creates task with course_id set to one of their own courses
- **THEN** system creates task linked to that course, returns 201

#### Scenario: Create task with course not owned
- **WHEN** teacher creates task with course_id belonging to another teacher
- **THEN** system returns 403

#### Scenario: Create task without course (backward compatible)
- **WHEN** teacher creates task without course_id
- **THEN** system creates task with course_id=NULL, task works as before

#### Edge case: Create task for class with semester from class record
- **WHEN** teacher creates a task for class "计算机网络1班" with semester="2025-2026-2"
- **THEN** system copies semester from class record, not from request body (single source of truth)

### Requirement: Student can view tasks for their classes
The system SHALL provide students with a list of active tasks for all classes they are enrolled in. Tasks belonging to archived courses SHALL be excluded from this listing.

**User story:** As a student, I want to see my pending tasks ordered by deadline so that I can plan my work. I should not see tasks from archived courses.

**Permission boundary:** Student only. Only tasks for student's primary_class_id, only status=active, excluding tasks where the associated course has status=archived.

#### Scenario: View assigned tasks
- **WHEN** student submits GET /api/tasks/my
- **THEN** system returns active tasks for student's primary class, ordered by deadline ascending, excluding tasks where course.status = 'archived'

#### Scenario: Tasks from archived courses hidden
- **WHEN** student has tasks in both active and archived courses
- **THEN** only tasks from active courses appear in the listing

### Requirement: Admin can view all tasks
The system SHALL allow admin to view all tasks with optional filters, including course_id filter.

**User story:** As an admin, I want to see all tasks across classes for oversight, filterable by course.

**Permission boundary:** Admin only.

#### Scenario: List all tasks with course filter
- **WHEN** admin submits GET /api/tasks?course_id=5&semester=2025-2026-2
- **THEN** system returns paginated task list matching filters, including course_id in response

#### Scenario: List all tasks without filter
- **WHEN** admin submits GET /api/tasks
- **THEN** system returns paginated task list with all filters optional
