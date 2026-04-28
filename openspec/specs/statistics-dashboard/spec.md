## ADDED Requirements

### Requirement: Admin can view platform-wide statistics
The system SHALL provide admin with aggregate platform metrics including: total users by role, total classes, total courses (active/archived), total tasks (active/archived), total submissions, pending grades count, graded count, and average score.

**User story:** As an admin, I want to see the overall health of the platform at a glance.

**Permission boundary:** Admin only.

#### Scenario: Admin views dashboard
- **WHEN** admin submits GET /api/stats/dashboard
- **THEN** system returns aggregate counts: users{admin,teacher,student}, classes, courses{active,archived}, tasks{active,archived}, submissions{total,pending_grade,graded}, average_score

#### Scenario: Non-admin views dashboard
- **WHEN** non-admin submits GET /api/stats/dashboard
- **THEN** system returns 403

#### Scenario: Empty platform
- **WHEN** admin views dashboard on a fresh platform with no data
- **THEN** system returns all counts as 0, average_score as null

### Requirement: Teacher can view their own class statistics
The system SHALL provide teachers with statistics scoped to their own classes and tasks: total classes, total tasks (active/archived), total submissions, pending grades, graded count, and average score.

**User story:** As a teacher, I want to see how my classes and tasks are performing.

**Permission boundary:** Teacher only. Data scoped to classes where teacher_id = current user.

#### Scenario: Teacher views their stats
- **WHEN** teacher submits GET /api/stats/dashboard
- **THEN** system returns counts scoped to classes where teacher_id=current user: classes, tasks{active,archived}, submissions{total,pending_grade,graded}, average_score

#### Scenario: Teacher with no classes
- **WHEN** teacher views stats and has no classes
- **THEN** system returns all counts as 0

### Requirement: Statistics include course-level breakdown
The system SHALL provide a breakdown of statistics per course when requested.

**User story:** As a teacher/admin, I want to compare activity across courses.

#### Scenario: Course-level breakdown
- **WHEN** admin submits GET /api/stats/courses
- **THEN** system returns per-course stats: course_id, course_name, task_count, submission_count, pending_grade_count, graded_count, average_score, ordered by submission count descending

#### Scenario: Teacher sees own courses only
- **WHEN** teacher submits GET /api/stats/courses
- **THEN** system returns per-course stats for courses where teacher_id=current user

### Requirement: Statistical scope definitions
All statistics SHALL use the following definitions:

- **total users by role**: COUNT from users table grouped by role, where is_active=true
- **total classes**: COUNT from classes table
- **courses active/archived**: COUNT from courses table grouped by status
- **tasks active/archived**: COUNT from tasks table grouped by status
- **total submissions**: COUNT from submissions table
- **pending_grade**: submissions without a corresponding grade record
- **graded**: submissions with a corresponding grade record
- **average_score**: AVG of grade.score for all graded submissions, rounded to 1 decimal. NULL if no grades exist.
- **nearby deadline**: nearest future deadline among active tasks for a given scope

#### Scenario: Pending grade count is accurate
- **WHEN** there are 10 submissions and 7 have grade records
- **THEN** pending_grade = 3, graded = 7

#### Scenario: Average score with no grades
- **WHEN** there are submissions but no grade records
- **THEN** average_score = null
