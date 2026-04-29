## Context

Vocational/technical colleges in China need a web platform to manage practical training (实训). Currently teachers use spreadsheets, WeChat/钉钉 groups, and email to distribute tasks, collect submissions, and track grades. This MVP replaces that fragmented workflow.

This is a greenfield project. No existing codebase, no existing database. Single deployment on a school's internal server. Chinese-language UI only. ~50 teachers, ~2000 students, ~500 concurrent users.

The scope was reduced through CEO review: 6.5 features kept, 7 deferred to V2 (org hierarchy, course management, training project templates, statistics dashboard, notification system, batch CSV import, multi-class task assignment).

## Goals / Non-Goals

**Goals:**

- Single-page web app with role-based access (admin, teacher, student)
- Complete training workflow: task creation → student submission → teacher grading → grade publication
- File upload/download with type and size validation
- Semester-aware task and class organization
- Single-transaction grade publication
- Single-server deployment (4-core / 8GB RAM)

**Non-Goals:**

- XR / large-space VR access — V2 (extension point: `submission_type` field + `/api/xr` routes)
- Device management (loan, return, status) — V2 (extension point: new `devices` module via Alembic migration)
- Cross-school sharing — out of scope for this product
- Complex AI agents — V2 (extension point: `grader/` directory + `grading_type` field on grades table)
- Competency/skill graph — V2 (extension point: new `competencies` module)
- Project proposal/approval workflow — V2
- Complex approval chains — V2
- Org hierarchy (College > Major > Class) — V2
- Course management — V2
- Training project templates — V2
- Statistics dashboard — V2
- Notification system (email/SMS/push) — V2
- Batch CSV import — V2
- Multi-class task assignment — V2 (extension point: `task_classes` M:N table)
- Mobile app — responsive web only
- Email/SMS notifications — in-app only
- Multi-tenant — single deployment
- SSO/CAS integration — V2
- Video upload/streaming — V2
- Report export (CSV/PDF) — V2

## Decisions

### D1: Tech Stack — Python + FastAPI + Vue 3 + MySQL

**Choice:** Python 3.11+ with FastAPI backend, Vue 3 + Element Plus frontend, MySQL 8 database, SQLAlchemy 2.0 + Alembic ORM.

**Rationale:**
- FastAPI: async support, automatic OpenAPI docs, Pydantic validation built-in, simpler than NestJS for this scope
- Vue 3 + Element Plus: most common combo in Chinese edtech, form/table components out of the box
- MySQL 8: schools typically have MySQL infrastructure already, ops team is familiar
- SQLAlchemy 2.0 + Alembic: type-safe ORM with auto-generated migrations

**Alternatives considered:**
- Node.js + Express: rejected — user preference for Python
- PostgreSQL: rejected — adds one more new thing for ops team, MySQL is already available
- Django: rejected — too heavy for 18 endpoints, FastAPI is lighter
- React + Ant Design: viable alternative, but Vue+Element Plus has more Chinese documentation

### D2: Authentication — JWT Bearer Token

**Choice:** Short-lived access token (15 min) + long-lived refresh token. Both stored in localStorage on the frontend, sent via `Authorization: Bearer <token>` header.

**Rationale:**
- No CSRF vulnerability (browser doesn't auto-send Authorization header)
- Logout = mark refresh token as revoked server-side
- Account lockout: access token expires naturally in ≤15 minutes
- Simpler than httpOnly cookie + CSRF middleware

**Alternatives considered:**
- httpOnly cookie: rejected — requires CSRF protection, adds complexity
- Session-based: rejected — requires server-side session store (Redis), adds infrastructure

### D3: Data Model — 6 Tables, No V2 Columns

**Choice:** 6 tables (users, classes, tasks, submissions, submission_files, grades). No pre-built columns for V2 features.

**Rationale:**
- Pre-building columns = pre-building mistakes. V2 requirements will change.
- Alembic migration to add a column is one command: `alembic revision --autogenerate`
- Clean separation: V1 tables are stable, V2 adds via migration

**Key constraints:**
- `UNIQUE(task_id, student_id)` on submissions — one record per student per task, resubmit updates same row with version++
- `submission_id UNIQUE` on grades — 1:1 with submissions
- `grades_published` boolean on tasks — denormalized source of truth for grade visibility (avoids partial-visibility bugs)
- `primary_class_id` on users — student's main class (functional), teacher/admin = null

### D4: 1 Task = 1 Class (Not Multi-Class)

**Choice:** Each task belongs to exactly one class. `tasks.class_id` is a required FK.

**Rationale:**
- Simplifies all queries: no M:N join table, no deduplication logic
- Matches the CEO review decision: if a teacher wants the same task for 2 classes, they create 2 tasks
- V2 multi-class support: add `task_classes` M:N table + Alembic migration

### D5: No Grading Lock

**Choice:** No grading lock mechanism. Last editor wins. Frontend shows `graded_by` name and `graded_at` timestamp.

**Rationale:**
- 50-teacher system: probability of two teachers grading the same task simultaneously is near zero
- Lock mechanism (status field + 30-min timeout) is ~40 lines of code for a problem that barely exists
- `graded_by` and `graded_at` on grades table provide audit trail if conflict occurs

### D6: File Upload — Atomic Rename, Local Filesystem

**Choice:** Upload to `/uploads/tmp/{uuid}`, atomic rename to `/uploads/{uuid}_{filename}`. Nginx serves downloads via X-Accel-Redirect.

**Rationale:**
- Atomic rename prevents partial-file corruption
- UUID prefix prevents filename collisions
- Nginx X-Accel-Redirect: FastAPI doesn't stream files, Nginx handles it efficiently
- No cleanup job needed: files that aren't linked to a submission within 24 hours are cleaned by a simple cron find-delete

**File type validation:** Extension-based whitelist in V1. Magic-byte check is V2.

### D7: Grade Publication — Single Boolean Flip

**Choice:** `tasks.grades_published` boolean. Teacher publishes → `UPDATE tasks SET grades_published=true WHERE id=X`. Student queries join through task to check visibility.

**Rationale:**
- Single source of truth: one boolean, not per-grade visibility flags
- No partial visibility bugs: all grades visible or none
- Unpublish: flip boolean back to false
- Modify after publish: requires unpublish first (audit trail preserved via graded_at)

## Edge Cases

### Auth Edge Cases
- User logs in exactly at the moment their lockout expires → lockout check uses `locked_until > NOW()`, so if equal, login proceeds
- Access token expires mid-request → response is 401, frontend interceptor refreshes and retries
- Concurrent login attempts from different devices → each gets its own token pair, both valid
- Password change while another session is active → other session's access token still valid for up to 15 minutes (acceptable for internal system)

### Submission Edge Cases
- Student uploads files, then deadline passes before they click submit → server validates deadline at submission time, not upload time
- Student resubmits at exact deadline moment (same second) → server compares deadline against `submitted_at`, not upload time
- Two students upload files with identical filenames → UUID prefix prevents collision
- Student is enrolled in a class after a task was created → they can see and submit to the task (class membership checked at submission time, not task creation time)
- File upload succeeds but submission creation fails → file becomes orphan, cleaned up by daily cron within 24 hours

### Grading Edge Cases
- Teacher grades a submission, then another teacher grades the same submission (same task creator constraint prevents this for other teachers, but same teacher could grade twice) → second grade overwrites first, audit via `graded_by` + `graded_at`
- Teacher publishes grades, then unpublishes, then republishes → `grades_published_at` and `grades_published_by` update on each publish
- Late penalty calculation: score=85, penalty=10% → `penalty_applied=8.5`, effective score = 85 - 8.5 = 76.5 (displayed, not stored separately)
- Bulk grade with mix of late and on-time submissions → same score applied to all, late penalty auto-calculated per submission individually

### Task Edge Cases
- Teacher archives a task while a student is actively viewing it → student's already-loaded page continues to work, but the task disappears from their list on next refresh
- Teacher changes deadline to be later after some students already submitted late → those submissions remain `is_late=true` (historical record, not recalculated)
- Admin deactivates a teacher who created tasks → tasks and submissions remain visible, grades remain accessible

### Concurrent Access Edge Cases
- Student submits and resubmits rapidly (double-click) → UNIQUE constraint on `(task_id, student_id)` ensures only one submission row; version increment is serialized at database level
- Teacher bulk-grades while another teacher publishes for the same task → publish checks `grades_published` flag, rejects if already published; if not, transaction serializes the operations

## Permission Boundaries

### Permission Matrix

| Resource | Admin | Teacher | Student |
|----------|-------|---------|---------|
| **Users** |
| Create user | YES | NO | NO |
| List/search users | YES | NO | NO |
| Edit any user | YES | NO | NO |
| Deactivate user | YES (not self) | NO | NO |
| View own profile | YES | YES | YES |
| Edit own profile | YES | YES | YES |
| **Classes** |
| Create class | YES | NO | NO |
| Edit class | YES | NO | NO |
| Delete class | YES (empty only) | NO | NO |
| List all classes | YES | NO | NO |
| View own classes | NO | YES | NO |
| Enroll student | YES | NO | NO |
| View class roster | YES | Assigned teacher only | NO |
| **Tasks** |
| Create task | NO | YES (own class only) | NO |
| Edit task | NO | YES (creator only) | NO |
| Delete task | NO | YES (no submissions) | NO |
| Archive task | NO | YES (creator only) | NO |
| View own tasks | NO | YES | NO |
| View assigned tasks | NO | NO | YES (own class) |
| View all tasks | YES | NO | NO |
| View task detail | YES | Creator only | YES (own class) |
| **Submissions** |
| Submit/resubmit | NO | NO | YES (own class, own only) |
| View own submission | NO | NO | YES |
| List task submissions | NO | YES (creator only) | NO |
| Download files | NO | YES (own task) | YES (own submission) |
| **Grades** |
| Grade submission | NO | YES (creator only) | NO |
| Bulk grade | NO | YES (creator only) | NO |
| Publish grades | NO | YES (creator only) | NO |
| Unpublish grades | NO | YES (creator only) | NO |
| View own grade | NO | NO | YES (published only) |

### Authorization Implementation
- **Route-level**: FastAPI dependency `require_role("admin")`, `require_role("teacher")`, etc.
- **Resource-level**: ownership check inside handler (e.g., `task.created_by == current_user.id`)
- **Class membership**: student's `primary_class_id` matched against `task.class_id`
- **No row-level security**: application code enforces all access control, not database policies

## Extension Points (AI / XR / Device Management)

### AI Grading Extension
- **Location**: `backend/app/grader/` directory (empty in V1)
- **Schema**: `grades` table gets `grading_type` column via migration (V1 default: `"manual"`, V2 option: `"ai-assisted"`)
- **API**: `POST /api/tasks/:id/grades/ai-suggest` (V2) returns AI-proposed scores for teacher review
- **Integration**: teacher still clicks "confirm" for each AI-graded submission; no auto-publish
- **Migration path**: `alembic revision --autogenerate -m "add grading_type to grades"`

### XR / Virtual Lab Extension
- **Location**: `backend/app/routers/xr.py` (new file, V2)
- **Schema**: `submission_files.file_type` already supports arbitrary types; add `"xr-scene"` to allowed types
- **API**: `POST /api/xr/sessions` creates a VR session, `GET /api/xr/sessions/:id` returns session state
- **Data**: `submissions` table gets `submission_type` column via migration (V1 default: `"file"`, V2 option: `"xr"`)
- **Migration path**: `alembic revision --autogenerate -m "add submission_type to submissions"`

### Device Management Extension
- **Location**: `backend/app/models/device.py`, `backend/app/routers/devices.py` (new files, V2)
- **Schema**: new `devices` table (id, name, type, status, location, current_holder_id) via Alembic migration
- **API**: `POST /api/devices`, `GET /api/devices`, `POST /api/devices/:id/loan`, `POST /api/devices/:id/return`
- **Integration**: device loans linked to tasks/submissions via optional FK
- **Migration path**: `alembic revision --autogenerate -m "add devices table"`

### Multi-Class Task Extension
- **Location**: new `task_classes` M:N table via migration
- **Change**: `tasks.class_id` becomes nullable; `task_classes` table stores (task_id, class_id) pairs
- **Migration path**: `alembic revision --autogenerate -m "add task_classes for multi-class tasks"`

### Extension Point Summary

| Extension | Where to Add | Schema Change | API Surface |
|-----------|-------------|---------------|-------------|
| AI grading | `grader/` directory | `grades.grading_type` column | `/api/tasks/:id/grades/ai-suggest` |
| XR sessions | `routers/xr.py` | `submissions.submission_type` column | `/api/xr/sessions` |
| Device mgmt | `models/device.py`, `routers/devices.py` | new `devices` table | `/api/devices/*` |
| Multi-class | migration only | `task_classes` M:N table | modify existing task endpoints |
| Batch import | `routers/import.py` | none | `/api/import/users`, `/api/import/students` |
| Notifications | `services/notification.py` | `notifications` table | `/api/notifications` |
| Statistics | `routers/stats.py` | none (read-only aggregation) | `/api/stats/*` |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| File type validation by extension only — students rename malicious files | V2 adds magic-byte check. V1 runs on trusted internal network |
| No grading lock — rare concurrent edits overwrite | graded_by + graded_at provide audit. 50-teacher scale makes this near-zero probability |
| Extension-based file validation — future types require code change | Whitelist is a config constant, easy to update |
| No disk quota enforcement — server runs out of space | Monitor disk usage via cron + alert admin at 80% capacity |
| Single-server deployment — no redundancy | School infrastructure. Acceptable for V1. V2 can add replication |
| MySQL enum ALTER TABLE requires table lock | Use VARCHAR + CHECK constraint instead of ENUM for status fields |
| Bearer token in localStorage — XSS could steal it | XSS prevention via Content-Security-Policy headers, input sanitization on all user text |
