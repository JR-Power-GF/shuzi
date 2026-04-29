## MODIFIED Requirements

### Requirement: Teacher can create tasks
The system SHALL allow teacher to create a task assigned to one class with title, description, requirements, deadline, allowed_file_types, max_file_size_mb, allow_late_submission, and optional late_penalty_percent. The task MAY optionally be assigned to a course via course_id. If course_id is provided, the teacher MUST own the course.

**User story:** As a teacher, I want to create a task for my class with clear requirements and deadlines so that students know what to submit. I also want to optionally organize tasks under courses.

**Permission boundary:** Teacher only, and only for classes assigned to them (verified by class.teacher_id == current_user.id). If course_id provided, course.teacher_id MUST equal current_user.id.

#### Scenario: Create task with all fields
- **WHEN** teacher submits POST /api/tasks with title, description, requirements, class_id, deadline, allowed_file_types, max_file_size_mb, allow_late_submission=false
- **THEN** system creates task with semester copied from class, status=active, grades_published=false, returns 201

#### Scenario: Create task with late penalty
- **WHEN** teacher creates task with allow_late_submission=true and late_penalty_percent=10
- **THEN** system creates task with late penalty configured

#### Scenario: Create task for non-owned class
- **WHEN** teacher creates task for a class they are not assigned to
- **THEN** system returns 403

#### Scenario: Create task with course
- **WHEN** teacher creates task with course_id pointing to their own course
- **THEN** system creates task linked to that course

#### Scenario: Create task with course not owned
- **WHEN** teacher creates task with course_id pointing to another teacher's course
- **THEN** system returns 403

#### Scenario: Create task without course
- **WHEN** teacher creates task without course_id
- **THEN** system creates task with course_id=NULL, all existing behavior preserved

#### Edge case: Create task for class with semester from class record
- **WHEN** teacher creates a task for class "计算机网络1班" with semester="2025-2026-2"
- **THEN** system copies semester from class record, not from request body (single source of truth)

### Requirement: Admin can view all tasks
The system SHALL allow admin to view all tasks with optional filters including course_id.

**User story:** As an admin, I want to see all tasks across classes for oversight.

**Permission boundary:** Admin only.

#### Scenario: List all tasks
- **WHEN** admin submits GET /api/tasks?class_id=5&semester=2025-2026-2
- **THEN** system returns paginated task list matching filters

#### Scenario: List tasks by course
- **WHEN** admin submits GET /api/tasks?course_id=3
- **THEN** system returns paginated task list for the specified course
