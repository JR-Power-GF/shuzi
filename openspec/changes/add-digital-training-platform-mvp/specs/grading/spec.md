## ADDED Requirements

### Requirement: Teacher can grade a single submission
The system SHALL allow task creator to enter score (0-100) and optional text feedback for a submission. If submission is_late=true and task has late_penalty_percent, penalty is auto-calculated and stored in penalty_applied.

**User story:** As a teacher, I want to grade each student's submission with a score and feedback so that students know how they performed.

**Permission boundary:** Teacher only, task creator only (task.created_by == current_user.id). Cannot grade while grades_published=true.

#### Scenario: Grade submission
- **WHEN** teacher submits POST /api/tasks/:id/grades with submission_id, score=85, feedback="完成良好"
- **THEN** system creates grade with graded_by=teacher, graded_at=NOW, returns 201

#### Scenario: Score out of range
- **WHEN** teacher submits score=150
- **THEN** system returns 422 with error "分数必须在0-100之间"

#### Scenario: Late penalty auto-applied
- **WHEN** teacher grades a late submission (is_late=true) with task.late_penalty_percent=10
- **THEN** system stores score=85, penalty_applied=10, effective score displayed as 75.5

#### Scenario: Grade for other teacher's task
- **WHEN** teacher attempts to grade submission for another teacher's task
- **THEN** system returns 403

#### Edge case: Grade the same submission twice
- **WHEN** teacher grades a submission that already has a grade
- **THEN** system overwrites the existing grade (last editor wins), updates graded_by and graded_at

#### Edge case: Late penalty calculation precision
- **WHEN** score=90, penalty_percent=15
- **THEN** penalty_applied=13.5, effective score = 90 - 13.5 = 76.5 (stored as DECIMAL)

### Requirement: Teacher can bulk grade
The system SHALL allow teacher to apply the same score to multiple submissions at once.

**User story:** As a teacher, I want to give the same score to multiple students at once so that grading is faster when many students performed similarly.

**Permission boundary:** Teacher only, task creator only. Cannot bulk grade while grades_published=true.

#### Scenario: Bulk grade
- **WHEN** teacher submits POST /api/tasks/:id/grades/bulk with submission_ids=[1,2,3] and score=80
- **THEN** system creates/updates grades for all listed submissions with score=80

#### Scenario: Empty submission list
- **WHEN** teacher submits bulk grade with empty submission_ids
- **THEN** system returns 422 with error "提交列表不能为空"

#### Edge case: Bulk grade mix of late and on-time submissions
- **WHEN** teacher bulk grades with score=80, submission 1 is late (penalty=10%), submission 2 is on time
- **THEN** submission 1 gets score=80, penalty_applied=8; submission 2 gets score=80, penalty_applied=null

### Requirement: Teacher can publish all grades at once
The system SHALL allow teacher to publish grades as a single database transaction. All grades for the task become visible to students. If transaction fails, no grades are published.

**User story:** As a teacher, I want to publish all grades at once so that all students see their results simultaneously (fairness).

**Permission boundary:** Teacher only, task creator only. Single transaction ensures atomicity.

#### Scenario: Publish grades
- **WHEN** teacher submits POST /api/tasks/:id/grades/publish
- **THEN** system sets tasks.grades_published=true, grades_published_at=NOW, grades_published_by=teacher in a single transaction, returns 200

#### Scenario: No grades to publish
- **WHEN** teacher publishes but no grades exist for the task
- **THEN** system returns 400 with error "没有可发布的成绩"

### Requirement: Teacher can unpublish grades
The system SHALL allow teacher to unpublish grades to make corrections. Scores are preserved but hidden from students.

**User story:** As a teacher, I want to unpublish grades so that I can correct mistakes before students see them.

**Permission boundary:** Teacher only, task creator only.

#### Scenario: Unpublish grades
- **WHEN** teacher submits POST /api/tasks/:id/grades/unpublish
- **THEN** system sets tasks.grades_published=false, returns 200. Students can no longer see scores.

#### Edge case: Unpublish and republish cycle
- **WHEN** teacher publishes, unpublishes, then republishes
- **THEN** grades_published_at and grades_published_by update on each publish; grades themselves are unchanged

### Requirement: Teacher must unpublish before modifying published grades
The system SHALL prevent grade modification while grades are published.

**User story:** As a teacher, I am prevented from editing published grades so that I don't change scores students have already seen without an explicit unpublish step.

**Permission boundary:** Enforced by grades_published check on all grading endpoints.

#### Scenario: Modify published grade
- **WHEN** teacher attempts POST /api/tasks/:id/grades for a submission whose task has grades_published=true
- **THEN** system returns 400 with error "请先撤回已发布的成绩"

### Requirement: Student can view published grades
The system SHALL allow student to see their score and feedback only when grades are published.

**User story:** As a student, I want to see my grade and feedback after the teacher publishes them so that I know how I performed.

**Permission boundary:** Student only, own submission only. Grade details gated by task.grades_published boolean.

#### Scenario: View published grade
- **WHEN** student views their submission and task.grades_published=true
- **THEN** system returns score, feedback, penalty_applied, and effective score

#### Scenario: View unpublished grade
- **WHEN** student views their submission and task.grades_published=false
- **THEN** system returns grade status as "not_graded" without revealing score or feedback
