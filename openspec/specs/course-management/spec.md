## ADDED Requirements

### Requirement: Teacher can create courses
The system SHALL allow teachers to create courses with name, description, and semester. The creating teacher SHALL be the course owner.

**User story:** As a teacher, I want to organize my teaching content into courses so that tasks are grouped by subject.

**Permission boundary:** Teacher and admin only.

#### Scenario: Create course with all fields
- **WHEN** teacher submits POST /api/courses with name="Python程序设计", description="Python基础编程", semester="2026-2027-1"
- **THEN** system creates course with teacher_id=current user, status=active, returns 200 with course data

#### Scenario: Student creates course
- **WHEN** student submits POST /api/courses
- **THEN** system returns 403

#### Scenario: Duplicate course name in same semester
- **WHEN** teacher creates course with name that already exists in the same semester by the same teacher
- **THEN** system returns 409 with message "同一学期已存在同名课程"

### Requirement: Teacher can edit their own courses
The system SHALL allow course owner (teacher) to edit course details. Admin can edit any course.

**User story:** As a teacher, I want to update my course information.

**Permission boundary:** Course owner teacher, or admin.

#### Scenario: Teacher edits own course
- **WHEN** teacher submits PUT /api/courses/:id on their own course
- **THEN** system updates course fields, returns 200

#### Scenario: Teacher edits another teacher's course
- **WHEN** teacher submits PUT /api/courses/:id on a course they don't own
- **THEN** system returns 403

#### Scenario: Admin edits any course
- **WHEN** admin submits PUT /api/courses/:id
- **THEN** system updates course, returns 200

### Requirement: Teacher can archive courses
The system SHALL allow course owner to archive a course. Archived courses and their tasks are hidden from students but visible to the teacher and admin. Courses SHALL NOT have a delete endpoint.

**User story:** As a teacher, I want to archive last semester's courses to declutter the current view.

#### Scenario: Archive course
- **WHEN** teacher submits POST /api/courses/:id/archive on their own active course
- **THEN** system sets status=archived, course and its tasks hidden from student views, returns 200

#### Scenario: Student cannot see archived courses
- **WHEN** student submits GET /api/courses
- **THEN** system returns only active courses, excluding archived ones. Tasks belonging to archived courses are also excluded from student task listings (GET /api/tasks/my filters out tasks where course status = archived).

#### Scenario: No delete endpoint exists
- **WHEN** any user submits DELETE /api/courses/:id
- **THEN** system returns 405 Method Not Allowed

### Requirement: Users can list and view courses
The system SHALL provide course listing with role-appropriate visibility. Teachers see their own courses. Students see courses for their enrolled classes. Admin sees all courses.

**User story:** As a student, I want to see my courses. As a teacher, I want to see my courses.

#### Scenario: Teacher lists own courses
- **WHEN** teacher submits GET /api/courses
- **THEN** system returns courses where teacher_id=current user, ordered by semester desc, name asc

#### Scenario: Student lists courses for enrolled classes
- **WHEN** student submits GET /api/courses
- **THEN** system returns active courses where a task exists in that course with class_id matching the student's primary_class_id. Course visibility is derived through the task-class relationship; there is no direct student-course enrollment table.

#### Scenario: Admin lists all courses
- **WHEN** admin submits GET /api/courses
- **THEN** system returns all courses with optional filters (semester, teacher_id, status)

#### Scenario: View course detail with task list
- **WHEN** authorized user submits GET /api/courses/:id
- **THEN** system returns course detail with list of tasks belonging to this course

### Requirement: Students see course cards with progress
The system SHALL provide students with a card-based home view showing their courses with task completion progress.

**User story:** As a student, I want to see my courses at a glance with my progress in each.

#### Scenario: Student course cards
- **WHEN** student submits GET /api/courses/my
- **THEN** system returns active courses with task counts (total, submitted, graded) and nearest deadline badge for each course

#### Scenario: Student with no courses
- **WHEN** student submits GET /api/courses/my and no active courses have tasks in their class
- **THEN** system returns empty list with friendly message

### Requirement: Tasks can be assigned to courses
The system SHALL allow teachers to optionally assign tasks to a course when creating or editing tasks. Tasks without a course continue to function normally.

**User story:** As a teacher, I want to organize my tasks under courses for better structure.

#### Scenario: Create task with course
- **WHEN** teacher creates a task with course_id set to one of their own courses
- **THEN** system creates task linked to that course

#### Scenario: Create task with course not owned
- **WHEN** teacher creates a task with course_id belonging to another teacher
- **THEN** system returns 403

#### Scenario: Create task without course (backward compatible)
- **WHEN** teacher creates a task without course_id
- **THEN** system creates task with course_id=NULL, task works as before

#### Scenario: List tasks filtered by course
- **WHEN** user submits GET /api/tasks?course_id=5
- **THEN** system returns only tasks belonging to course 5 (with permission check)
