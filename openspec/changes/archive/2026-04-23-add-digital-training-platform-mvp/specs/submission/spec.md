## ADDED Requirements

### Requirement: Student can submit files for a task
The system SHALL allow student to upload one or more files as a submission. Files MUST match allowed_file_types and be within max_file_size_mb per file. Total submission size MUST NOT exceed 100MB.

**User story:** As a student, I want to upload my work files for a task so that my teacher can review and grade them.

**Permission boundary:** Student only. Must be enrolled in the task's class (student.primary_class_id == task.class_id).

#### Scenario: Successful submission
- **WHEN** student submits POST /api/tasks/:id/submissions with valid files before deadline
- **THEN** system creates submission record with version=1, is_late=false, links files, returns 201

#### Scenario: File type not allowed
- **WHEN** student uploads a .exe file but task allows only .pdf,.doc,.docx
- **THEN** system returns 422 with error "不支持的文件类型"

#### Scenario: File too large
- **WHEN** student uploads a 60MB file but task max_file_size_mb=50
- **THEN** system returns 422 with error "文件大小超过限制"

#### Scenario: Submit after deadline, late not allowed
- **WHEN** student submits after deadline and task.allow_late_submission=false
- **THEN** system returns 400 with error "已过截止时间，不允许提交"

#### Scenario: Submit after deadline, late allowed
- **WHEN** student submits after deadline and task.allow_late_submission=true
- **THEN** system creates submission with is_late=true

#### Scenario: Submit for task not in student's class
- **WHEN** student submits to a task for a class they are not in
- **THEN** system returns 403

#### Edge case: Files uploaded but submission not completed
- **WHEN** student uploads files via /api/files/upload but never submits
- **THEN** uploaded files become orphans, cleaned up by daily cron within 24 hours

#### Edge case: Deadline passes between file upload and submission click
- **WHEN** student uploads files before deadline, but clicks submit after deadline
- **THEN** server validates deadline at submission time (not upload time), applies late policy accordingly

### Requirement: Student can resubmit before deadline
The system SHALL allow student to resubmit (replace files). Version increments. Previous files are replaced.

**User story:** As a student, I want to resubmit my work to correct mistakes, with version tracking so I know which version is current.

**Permission boundary:** Student only, own submission only (enforced by UNIQUE(task_id, student_id) constraint).

#### Scenario: Resubmit before deadline
- **WHEN** student submits POST /api/tasks/:id/submissions again before deadline
- **THEN** system updates existing submission: version++, new files replace old files, submitted_at updates

#### Scenario: Late resubmission follows late policy
- **WHEN** student resubmits after deadline and task.allow_late_submission=true
- **THEN** system updates submission with is_late=true

#### Scenario: Late resubmission when late not allowed
- **WHEN** student resubmits after deadline and task.allow_late_submission=false
- **THEN** system returns 400 with error "已过截止时间，不允许提交"

#### Edge case: Rapid double-click on submit button
- **WHEN** student double-clicks submit rapidly
- **THEN** UNIQUE(task_id, student_id) constraint ensures only one submission row; second request updates the same row (version may increment twice, which is acceptable)

### Requirement: Student can view their own submission
The system SHALL allow student to view submission detail including files and status.

**User story:** As a student, I want to check my submission status and see my grade when it's published.

**Permission boundary:** Student only, own submission only. Grade details visible only when task.grades_published=true.

#### Scenario: View own submission
- **WHEN** student submits GET /api/submissions/:id for their own submission
- **THEN** system returns submission with files, version, is_late, and grade status (score visible only if grades_published)

#### Scenario: View other student's submission
- **WHEN** student attempts GET /api/submissions/:id for another student's submission
- **THEN** system returns 403

### Requirement: Teacher can view all submissions for their task
The system SHALL allow task creator to list all submissions.

**User story:** As a teacher, I want to see all submissions for my task so that I can review and grade student work.

**Permission boundary:** Teacher only, task creator only (task.created_by == current_user.id).

#### Scenario: List submissions
- **WHEN** teacher submits GET /api/tasks/:id/submissions for their own task
- **THEN** system returns list of all submissions with student name, version, is_late, submitted_at, grade status

#### Scenario: List submissions for other teacher's task
- **WHEN** teacher attempts GET /api/tasks/:id/submissions for another teacher's task
- **THEN** system returns 403

### Requirement: Users can download submitted files
The system SHALL allow student to download their own files and teacher to download files from their tasks.

**User story:** As a student, I want to download my submitted files. As a teacher, I want to download student submissions for offline review.

**Permission boundary:** Student downloads own files only. Teacher downloads files from tasks they created. Admin downloads any file.

#### Scenario: Download own file
- **WHEN** student submits GET /api/submissions/:id/files/:fileId for their own submission
- **THEN** system returns file with correct Content-Type and Content-Disposition headers

#### Scenario: Teacher downloads from own task
- **WHEN** teacher submits GET /api/files/:id for a file in their task's submission
- **THEN** system returns file with correct headers

#### Scenario: Unauthorized download
- **WHEN** student attempts to download file from another student's submission
- **THEN** system returns 403
