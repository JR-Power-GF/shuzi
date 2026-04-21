## Why

Teachers at vocational/technical colleges manage practical training (实训) through spreadsheets, WeChat/钉钉 groups, and email. Students submit work in unstructured ways. Teachers track grades in Excel. There is no single system connecting assignment creation, student submission, and grading into one workflow. The result: ~3-5 hours per teacher per week on administrative overhead. This MVP replaces that fragmented workflow with a focused web platform.

## What Changes

- **New web application** with three hardcoded roles: admin, teacher, student
- **Authentication system**: username/password login, account lockout after 5 failed attempts, admin-initiated password reset, forced password change on first login
- **User management**: admin creates/edits/deactivates teacher and student accounts
- **Class management**: flat class list with semester field, teacher assignment, student enrollment (no college/major hierarchy in V1)
- **Task publishing**: teacher creates tasks with deadline, allowed file types, file size limits, and late submission policy; one task assigned to one class
- **Student submission**: file upload with type and size validation, resubmit before deadline (version tracking), late submission flagging
- **Grading and feedback**: teacher enters score (0-100) and text feedback per submission, bulk grading, single-transaction grade publication (publish/unpublish), late penalty auto-calculation
- **File storage**: local filesystem with UUID-prefixed filenames, served via Nginx

## Capabilities

### New Capabilities

- `auth`: Login, logout, password change, password reset, account lockout, JWT Bearer token authentication
- `user-management`: Admin CRUD for teachers and students, self-service profile editing, account deactivation
- `class-management`: Class CRUD with semester, teacher assignment, student enrollment
- `task-management`: Task CRUD with deadline, file constraints, late submission policy, archive capability
- `submission`: File upload, resubmit with version tracking, late flagging, download with ownership validation
- `grading`: Score entry, text feedback, bulk grading, grade publication as single transaction, unpublish, late penalty calculation
- `file-storage`: Upload with type/size validation, atomic rename, download with correct headers

### Modified Capabilities

_(No existing capabilities to modify - this is a greenfield project.)_

## Core User Stories

### Admin Stories

- **US-A1**: As an admin, I want to create teacher and student accounts so that users can access the platform with their designated roles.
- **US-A2**: As an admin, I want to organize students into classes by semester so that teachers can assign tasks to the right group.
- **US-A3**: As an admin, I want to deactivate accounts without losing data so that departed users' historical records remain intact.
- **US-A4**: As an admin, I want to reset a user's password so that locked-out users can regain access.
- **US-A5**: As an admin, I want to view all tasks across classes so that I have oversight of teaching activity.

### Teacher Stories

- **US-T1**: As a teacher, I want to create a task with deadline, file constraints, and late policy for my class so that students know exactly what to submit and when.
- **US-T2**: As a teacher, I want to see all submissions for my task in one list so that I can efficiently review student work.
- **US-T3**: As a teacher, I want to grade submissions individually or in bulk and publish all grades at once so that grading is efficient and fair (all students see results simultaneously).
- **US-T4**: As a teacher, I want to edit a task before submissions arrive, but protect existing submissions from retroactive rule changes so that students aren't surprised by changed requirements.
- **US-T5**: As a teacher, I want to download submitted files so that I can review them offline.

### Student Stories

- **US-S1**: As a student, I want to see all my active tasks ordered by deadline so that I can plan my work.
- **US-S2**: As a student, I want to upload files and resubmit before the deadline so that I can correct mistakes in my submission.
- **US-S3**: As a student, I want to see my grade and feedback only after the teacher publishes them so that grading is fair.
- **US-S4**: As a student, I want to download my submitted files so that I can verify what I turned in.

## Acceptance Criteria

### AC-Auth
- Login returns JWT tokens; 5 failed attempts lock account for 30 minutes
- Password must be >= 8 characters; admin reset forces change on next login
- Logout revokes refresh token; access token expires naturally within 15 minutes
- Deactivated accounts cannot log in

### AC-User
- Admin can create/edit/deactivate any account; duplicate usernames rejected (409)
- Users can view and edit their own name, email, phone; cannot edit role or username
- Deactivation preserves all submissions and grades

### AC-Class
- Admin can create/edit/delete classes; cannot delete class with enrolled students
- Teacher sees only their assigned classes
- Student enrollment is idempotent

### AC-Task
- Teacher can create tasks only for classes they are assigned to
- After submissions exist: cannot change allowed_file_types, cannot reduce deadline before earliest submission
- Archived tasks are hidden from student list but visible to teacher and admin
- Task detail requires class membership (student), ownership (teacher), or admin role

### AC-Submission
- Student can submit only for tasks in their class; file type and size validated
- Resubmit increments version and replaces files
- Late submission flagged (is_late=true) if past deadline and allowed; rejected if not allowed
- Student can view/download only own submissions

### AC-Grading
- Score must be 0-100; late penalty auto-calculated from task.late_penalty_percent
- Cannot modify grades while grades_published=true; must unpublish first
- Publish sets grades_published=true in a single transaction; no partial visibility
- Student sees score/feedback only when grades_published=true; sees "not_graded" status otherwise

### AC-File
- File type validated against whitelist; file size validated against per-task limit
- Concurrent uploads do not collide (UUID prefix)
- Download requires ownership validation; served via Nginx X-Accel-Redirect
- Orphan files (not linked to submission within 24 hours) cleaned up by daily cron

## Impact

- **New codebase**: Python 3.11+ / FastAPI backend, Vue 3 / Element Plus frontend, MySQL 8 database
- **New database**: 6 tables (users, classes, tasks, submissions, submission_files, grades) with Alembic migrations
- **New API surface**: ~18 REST endpoints under /api/
- **New deployment**: Single server with Nginx reverse proxy, uvicorn application server, systemd process management
- **Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, PyJWT, passlib, Pydantic, python-multipart, Vue 3, Element Plus, Pinia, axios
- **Target scale**: ~50 teachers, ~2000 students, ~500 concurrent users, single 4-core/8GB server
