## ADDED Requirements

### Requirement: Teacher can create tasks
The system SHALL allow teacher to create a task assigned to one class with title, description, requirements, deadline, allowed_file_types, max_file_size_mb, allow_late_submission, and optional late_penalty_percent.

**User story:** As a teacher, I want to create a task for my class with clear requirements and deadlines so that students know what to submit.

**Permission boundary:** Teacher only, and only for classes assigned to them (verified by class.teacher_id == current_user.id).

#### Scenario: Create task with all fields
- **WHEN** teacher submits POST /api/tasks with title, description, requirements, class_id, deadline, allowed_file_types, max_file_size_mb, allow_late_submission=false
- **THEN** system creates task with semester copied from class, status=active, grades_published=false, returns 201

#### Scenario: Create task with late penalty
- **WHEN** teacher creates task with allow_late_submission=true and late_penalty_percent=10
- **THEN** system creates task with late penalty configured

#### Scenario: Create task for non-owned class
- **WHEN** teacher creates task for a class they are not assigned to
- **THEN** system returns 403

#### Edge case: Create task for class with semester from class record
- **WHEN** teacher creates a task for class "计算机网络1班" with semester="2025-2026-2"
- **THEN** system copies semester from class record, not from request body (single source of truth)

### Requirement: Teacher can edit their own tasks
The system SHALL allow task creator to edit task details. After submissions exist, teacher CANNOT change allowed_file_types or reduce deadline before existing submission timestamps.

**User story:** As a teacher, I want to edit my tasks, but I cannot retroactively change rules that affect existing submissions.

**Permission boundary:** Teacher only, task creator only (task.created_by == current_user.id).

#### Scenario: Edit task before submissions
- **WHEN** teacher submits PUT /api/tasks/:id with updated fields and no submissions exist
- **THEN** system updates all fields including file types and deadline, returns 200

#### Scenario: Edit task after submissions — extend deadline
- **WHEN** teacher extends deadline and submissions exist
- **THEN** system updates deadline, returns 200

#### Scenario: Edit task after submissions — cannot change file types
- **WHEN** teacher attempts to change allowed_file_types after submissions exist
- **THEN** system returns 400 with error "已有学生提交，不能修改允许的文件类型"

#### Scenario: Edit task after submissions — cannot reduce deadline before submissions
- **WHEN** teacher reduces deadline to before earliest submission timestamp
- **THEN** system returns 400 with error "截止时间不能早于已有提交时间"

#### Scenario: Edit other teacher's task
- **WHEN** teacher attempts PUT /api/tasks/:id on task created by another teacher
- **THEN** system returns 403

### Requirement: Teacher can delete task with no submissions
The system SHALL allow teacher to permanently delete a task only if no submissions exist.

**User story:** As a teacher, I want to delete a task I created by mistake, as long as no students have submitted.

**Permission boundary:** Teacher only, task creator only. Blocked if submissions exist.

#### Scenario: Delete task with no submissions
- **WHEN** teacher submits DELETE /api/tasks/:id and no submissions exist
- **THEN** system deletes task and returns 200

#### Scenario: Delete task with submissions
- **WHEN** teacher submits DELETE /api/tasks/:id and submissions exist
- **THEN** system returns 400 with error "已有学生提交，请改用归档功能"

### Requirement: Teacher can archive task
The system SHALL allow teacher to archive a task (hidden from students, data preserved).

**User story:** As a teacher, I want to archive an old task so that students focus on active work, while preserving all submission data.

**Permission boundary:** Teacher only, task creator only.

#### Scenario: Archive task
- **WHEN** teacher submits POST /api/tasks/:id/archive
- **THEN** system sets status=archived, task no longer appears in student task list, returns 200

#### Edge case: Student views task detail via direct URL after archiving
- **WHEN** student navigates directly to /tasks/:id after it was archived
- **THEN** system returns task detail (task still exists), but it does not appear in the task list

### Requirement: Student can view tasks for their classes
The system SHALL provide students with a list of active tasks for all classes they are enrolled in.

**User story:** As a student, I want to see my pending tasks ordered by deadline so that I can plan my work.

**Permission boundary:** Student only. Only tasks for student's primary_class_id, only status=active.

#### Scenario: View assigned tasks
- **WHEN** student submits GET /api/tasks/my
- **THEN** system returns active tasks for student's primary class, ordered by deadline ascending

### Requirement: Admin can view all tasks
The system SHALL allow admin to view all tasks with optional filters.

**User story:** As an admin, I want to see all tasks across classes for oversight.

**Permission boundary:** Admin only.

#### Scenario: List all tasks
- **WHEN** admin submits GET /api/tasks?class_id=5&semester=2025-2026-2
- **THEN** system returns paginated task list matching filters

### Requirement: Users can view task detail with ownership check
The system SHALL return task detail to authorized users only.

**User story:** As a student, I want to see task details and my submission status so that I know what to do. As a teacher, I want to see my task details.

**Permission boundary:** Student in task's class, teacher who created the task, or admin. Unauthorized users get 403.

#### Scenario: Student views task in own class
- **WHEN** student submits GET /api/tasks/:id for task in their class
- **THEN** system returns task detail with submission status

#### Scenario: Student views task in other class
- **WHEN** student submits GET /api/tasks/:id for task not in their class
- **THEN** system returns 403
