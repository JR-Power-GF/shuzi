---
title: "feat: Digital Training Platform MVP — 4-PR Incremental Delivery"
type: feat
status: active
date: 2026-04-21
origin: openspec/changes/add-digital-training-platform-mvp/proposal.md
deepened: 2026-04-21
---

# feat: Digital Training Platform MVP — 4-PR Incremental Delivery

## Overview

Build the Digital Training Teaching Management Platform (数字实训教学管理平台) as 4 incremental, independently reviewable PRs. Each PR forms a verifiable increment — from skeleton to full production deployment. The MVP replaces fragmented spreadsheet/WeChat workflows with a single web platform for task assignment, student submission, and teacher grading.

## Problem Frame

Vocational/technical college teachers spend 3-5 hours/week on admin overhead managing practical training (实训) via spreadsheets, WeChat/钉钉, and email. Students submit work in unstructured ways. Teachers track grades in Excel. There is no single system connecting assignment creation, student submission, and grading. This MVP provides that single system for ~50 teachers and ~2000 students on a single 4-core/8GB server. (see origin: proposal.md)

## Requirements Trace

- R1. Authentication with JWT Bearer tokens, account lockout (5 fails / 30 min), forced password change on first login (AC-Auth, US-A4)
- R2. Admin user management: CRUD teachers/students, account deactivation preserving data (AC-User, US-A1, US-A3)
- R3. Class management with semester field, teacher assignment, student enrollment (AC-Class, US-A2)
- R4. Task publishing with deadline, file constraints, late submission policy; 1 task = 1 class (AC-Task, US-T1, US-T4)
- R5. Student submission with file upload, resubmit with version tracking, late flagging (AC-Submission, US-S1, US-S2, US-S4)
- R6. Grading with score 0-100, feedback, bulk grading, single-transaction publish/unpublish, late penalty (AC-Grading, US-T3, US-S3)
- R7. File storage with type/size validation, atomic rename, Nginx X-Accel-Redirect download (AC-File, US-S2, US-T5)
- R8. Teacher submission review: list all submissions, download files, grade individually or in bulk (US-T2, US-T5)
- R9. Deployment: Nginx reverse proxy, systemd, deployment script, orphan file cleanup cron (Phase F)

## Scope Boundaries

- No AI grading, no XR/VR, no device management (V2)
- No org hierarchy (College > Major > Class) (V2)
- No course management, no training project templates (V2)
- No statistics dashboard, no notification system, no batch CSV import (V2)
- No multi-class task assignment (V2)
- No SSO/CAS, no video upload/streaming, no report export (V2)
- No mobile app — responsive web only
- Single-tenant, single-server deployment

## Context & Research

### Relevant Code and Patterns

- Greenfield project — no existing code. All patterns defined in design.md decisions D1-D7.
- Planned architecture: `backend/app/` (models, routers, dependencies, grader/) + `frontend/` (Vue 3 + Element Plus)
- 7 database tables: users, classes, tasks, submissions, submission_files, grades, refresh_tokens
- Auth pattern: JWT Bearer in Authorization header, `require_role()` FastAPI dependency
- File validation: two-phase — global type/size check at upload (config.py), task-specific constraints enforced at submission time

### Phase-to-PR Mapping

| PR | tasks.md Phase(s) | Focus |
|----|--------------------|-------|
| PR1 | Phase A | Backend skeleton, database, Alembic |
| PR2 | Phase B + parts of D.1 | Minimum closed-loop API + auth refresh/change-password |
| PR3 | Phase C | Minimum closed-loop frontend |
| PR4 | Phases D + E + F | Full CRUD, admin pages, deployment |

### Institutional Learnings

- No institutional learnings exist yet — `docs/solutions/` is empty.

### External References

- FastAPI + SQLAlchemy 2.0 async patterns (design.md D1)
- Element Plus form/table components for Chinese edtech (design.md D1)

## Key Technical Decisions

All decisions carried forward from design.md (D1-D7), with amendments from deepening review:
- **D1**: Python 3.11+ / FastAPI / Vue 3 + Element Plus / MySQL 8 / SQLAlchemy 2.0 + Alembic
- **D2**: JWT Bearer token (15 min access + 7 day refresh), localStorage, no CSRF needed. Refresh token revocation requires server-side state → `refresh_tokens` table added (amended from origin)
- **D3**: 7 tables (amended: +`refresh_tokens`), no pre-built V2 columns
- **D4**: 1 task = 1 class (no M:N)
- **D5**: No grading lock — last editor wins, audit via `graded_by` + `graded_at`
- **D6**: File upload: two-phase — upload to `/uploads/tmp/`, rename to `/uploads/` only at submission creation. Orphan cleanup scans `/uploads/tmp/` only (amended from origin: files stay in tmp until linked)
- **D7**: Grade publication via single `grades_published` boolean flip on tasks
- **D8** (new): Late penalty formula: `penalty_applied = score * late_penalty_percent / 100`. Effective score = `score - penalty_applied`. Computed at display time, never stored as a separate column
- **D9** (new): Dependencies: use `PyJWT` (not `python-jose`), `bcrypt` standalone (not `passlib[bcrypt]`), `aiomysql` for async MySQL driver

## Open Questions

### Resolved During Planning

- PR split strategy: 4 PRs aligned to dependency boundaries (skeleton → API loop → frontend loop → full features + deploy)
- Testing posture: integration tests for API loop (PR2), component testing for frontend (PR3)
- Refresh token revocation: server-side `refresh_tokens` table with revoked flag (see D2 amendment)
- Late penalty arithmetic: `penalty_applied = score * percent / 100`, not the raw percentage (see D8)
- File upload lifecycle: files remain in `/uploads/tmp/` until submission links them, then renamed to `/uploads/` (see D6 amendment)
- Auth endpoint placement: `POST /api/auth/refresh` and `POST /api/auth/change-password` moved to PR2 (PR3 frontend needs both)
- FK cascade behavior: `RESTRICT` on all foreign keys; application-level checks before delete operations

### Deferred to Implementation

- Exact Python dependency versions: deferred to `pip install` at implementation time
- Exact Vue 3 / Element Plus component choices per page: deferred to implementation
- Nginx config specifics for the school's internal server: deferred to deployment phase
- Resubmit file retention: whether old submission files are deleted from disk on resubmit or retained for audit — deferred. Version history always shows metadata (version, timestamp); file availability depends on this choice

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### PR Dependency Flow

```
PR1 (Skeleton) ──> PR2 (API Loop) ──> PR3 (Frontend Loop) ──> PR4 (Full + Deploy)
  │                   │                    │                       │
  │                   │                    │                       ├─ Full CRUD
  │                   │                    │                       ├─ Admin pages
  │                   │                    │                       ├─ Teacher/Student enhancements
  │                   │                    │                       └─ Nginx + systemd + deploy
  │                   │                    │
  │                   │                    ├─ Vue 3 app shell
  │                   │                    ├─ Login page
  │                   │                    ├─ Teacher: create/list/review/grade
  │                   │                    └─ Student: list/submit/view grade
  │                   │
  │                   ├─ POST /api/auth/login
  │                   ├─ Seed script (demo data)
  │                   ├─ Class/Task/File/Submission/Grade endpoints
  │                   └─ End-to-end test
  │
  ├─ backend/ structure
  ├─ config.py, database.py
  ├─ 7 SQLAlchemy models
  ├─ Alembic migration (async template)
  ├─ Auth dependency
  └─ main.py + CORS
```

### Data Model (7 Tables)

```
users ──< submissions (student_id)
  │            │
  │            ├──< submission_files
  │            │
  │            └──> grades (1:1)
  │
  ├──< tasks (created_by) ──< submissions (task_id)
  │         │
  │         └──> classes (class_id FK, ON DELETE RESTRICT)
  │
  ├── primary_class_id ──> classes
  │
  └──< refresh_tokens (user_id, token_hash, revoked, expires_at)

classes ──< tasks (class_id)
   │
   └──< users (primary_class_id, for students)

Key constraints:
- UNIQUE(task_id, student_id) on submissions
- submission_id UNIQUE on grades (1:1)
- grades_published boolean on tasks
- primary_class_id: NOT NULL for students, NULL for teachers/admins
- All FKs use RESTRICT; application code checks before delete
- Late penalty: penalty_applied = score * late_penalty_percent / 100 (stored in grades.penalty_applied as DECIMAL)
```

## Implementation Units

---

### PR1: Backend Skeleton + Database Foundation

**PR Goal:** Project starts, database has tables, auth dependency works, health endpoint responds. No business logic yet — pure infrastructure.

**Requirements:** Foundation for R1-R9. No user-facing requirements satisfied directly.

**Dependencies:** None (first PR)

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py` — FastAPI app, CORS middleware, CSP headers, health endpoint
- Create: `backend/app/config.py` — DATABASE_URL, SECRET_KEY, token expiry, UPLOAD_DIR, MAX_FILE_SIZE_MB, ALLOWED_FILE_TYPES
- Create: `backend/app/database.py` — SQLAlchemy 2.0 async engine, sessionmaker, Base
- Create: `backend/app/models/__init__.py` — import all models for Alembic detection
- Create: `backend/app/models/user.py` — users table (id, username, password_hash, real_name, role, is_active, locked_until, failed_login_attempts, must_change_password, primary_class_id, email, phone, created_at, updated_at)
- Create: `backend/app/models/class_.py` — classes table (id, name, semester, teacher_id, created_at, updated_at)
- Create: `backend/app/models/task.py` — tasks table (id, title, description, requirements, class_id, created_by, deadline, allowed_file_types, max_file_size_mb, allow_late_submission, late_penalty_percent, status, grades_published, grades_published_at, grades_published_by, created_at, updated_at)
- Create: `backend/app/models/submission.py` — submissions table (id, task_id, student_id, version, is_late, submitted_at, updated_at); UNIQUE(task_id, student_id)
- Create: `backend/app/models/submission_file.py` — submission_files table (id, submission_id, file_name, file_path, file_size, file_type, uploaded_at)
- Create: `backend/app/models/grade.py` — grades table (id, submission_id, score, penalty_applied, feedback, graded_by, graded_at); submission_id UNIQUE
- Create: `backend/app/models/refresh_token.py` — refresh_tokens table (id, user_id, token_hash, revoked, expires_at, created_at)
- Create: `backend/app/dependencies/auth.py` — `get_current_user` (decode JWT), `require_role` factory
- Create: `backend/app/grader/__init__.py` — empty, AI grading extension point
- Create: `backend/alembic.ini` — Alembic configuration pointing to database.py
- Create: `backend/alembic/env.py` — async Alembic env.py (from async template), import Base and all models for autogenerate
- Create: `backend/alembic/versions/` — initial migration (auto-generated)
- Create: `backend/requirements.txt` — fastapi, uvicorn[standard], sqlalchemy>=2.0, alembic, aiomysql, pymysql (for sync Alembic migrations), PyJWT, bcrypt, python-multipart, pydantic>=2.0
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py` — test database fixture, async test client
- Create: `docker-compose.yml` — MySQL 8 with utf8mb4, volume for persistence, exposed port 3306

**Approach:**
- Initialize project structure with `backend/` as the root for Python code
- Configure SQLAlchemy 2.0 with `aiomysql` async driver
- Create all 7 models matching design.md D3 + D2 amendment (refresh_tokens) constraints exactly
- All foreign keys use `ondelete="RESTRICT"`; application-level checks prevent orphaned references
- Initialize Alembic with async template: `alembic init -t async` (or write env.py from async template pattern with `asyncio.run()` and `run_sync`)
- Alembic's synchronous `env.py` uses `pymysql` for migrations; application runtime uses `aiomysql` for async queries
- Generate initial migration and verify all tables, columns, types, constraints, indexes
- Auth dependency decodes JWT but login endpoint is not yet created (PR2)
- FastAPI main.py includes CORS for Vue dev server, CSP headers, health endpoint
- Docker compose provides MySQL 8 for local development

**Patterns to follow:**
- SQLAlchemy 2.0 mapped_column style (not legacy Column)
- Pydantic v2 models for config validation
- Async database session pattern

**Test scenarios:**
- Test expectation: none — PR1 is infrastructure scaffolding. Tests begin in PR2 when business logic exists.
- The conftest.py provides test fixtures but no test files are needed until endpoints exist.

**Risks:**
| Risk | Mitigation |
|------|------------|
| MySQL async driver compatibility | `aiomysql` is the established choice; `asyncmy` as fallback |
| Alembic async env.py misconfiguration | Use official async template; sync pymysql for migration runner |
| UTF-8/Chinese character handling in MySQL | Set `charset=utf8mb4` on connection |

**Demo / Verification:**
1. `docker compose up -d` starts MySQL
2. `cd backend && pip install -r requirements.txt` succeeds
3. `alembic upgrade head` creates all 7 tables in MySQL
4. `uvicorn app.main:app` starts without errors
5. `GET /health` returns 200
6. Inspect MySQL: all 7 tables present with correct columns and constraints

**Rollback:** Delete `backend/` directory, drop database. No state to preserve.

---

### PR2: Minimum Closed-Loop Backend API

**PR Goal:** The entire training workflow works via API: login → teacher creates task → student submits file → teacher grades → teacher publishes → student sees grade. Testable end-to-end via curl or API client.

**Requirements:** R1 (login + refresh + change-password), R3 (minimal), R4, R5, R6 (individual grading only — bulk deferred to PR4), R7, R8

**Dependencies:** PR1 (backend skeleton, database models, auth dependency)

**Files:**
- Create: `backend/app/routers/auth.py` — POST /api/auth/login, POST /api/auth/refresh, POST /api/auth/change-password
- Create: `backend/app/routers/classes.py` — POST /api/classes, GET /api/classes/my, GET /api/classes/:id/students
- Create: `backend/app/routers/tasks.py` — POST /api/tasks, GET /api/tasks/my, GET /api/tasks/:id
- Create: `backend/app/routers/files.py` — POST /api/files/upload, GET /api/files/:id
- Create: `backend/app/routers/submissions.py` — POST /api/tasks/:id/submissions, GET /api/submissions/:id, GET /api/tasks/:id/submissions (teacher), GET /api/submissions/:id/files/:fileId
- Create: `backend/app/routers/grades.py` — POST /api/tasks/:id/grades, POST /api/tasks/:id/grades/publish, POST /api/tasks/:id/grades/unpublish
- Create: `backend/scripts/seed_demo.py` — demo admin, teacher, student, class data
- Create: `backend/tests/test_min_loop.py` — end-to-end integration test
- Create: `backend/app/schemas/` — Pydantic request/response schemas for all endpoints
- Modify: `backend/app/main.py` — include all new routers

**Approach:**
- Build routers in dependency order: auth → classes → tasks → files → submissions → grades
- Each endpoint enforces role-based access via `require_role()` dependency and resource-level ownership checks per the permission matrix in design.md
- Auth: login issues access+refresh tokens (stores token hash in `refresh_tokens` table); refresh issues new pair, revokes old; change-password validates current password, enforces 8-char minimum
- File upload: validate type/size against global config (config.py), write to `/uploads/tmp/{uuid}_{filename}`. Files stay in `/uploads/tmp/` until submission links them, then renamed to `/uploads/{uuid}_{filename}` at submission creation time. Task-specific constraints (allowed_file_types, max_file_size_mb) enforced at submission time, not upload time
- Submission: UNIQUE(task_id, student_id) handles double-click; version++ on resubmit; is_late calculated against deadline; total submission size ≤ 100MB
- Grading: score 0-100, penalty_applied = score * late_penalty_percent / 100 (DECIMAL stored in grades table), last editor wins
- Grade publish: single `UPDATE tasks SET grades_published=true WHERE id=X`
- Seed script creates: admin/admin123, teacher1/teacher123 with class "计算机网络1班" semester=2025-2026-2, student1/student123 enrolled. All with `must_change_password=true`

**Test scenarios:**
- **Happy path — login**: POST /api/auth/login with valid admin credentials → 200 + access_token + refresh_token + must_change_password=true
- **Happy path — token refresh**: POST /api/auth/refresh with valid refresh_token → 200 + new access_token + new refresh_token (old refresh_token revoked)
- **Happy path — change password**: POST /api/auth/change-password with valid current password + new password (8+ chars) → 200, must_change_password=false
- **Happy path — create task**: Login as teacher → POST /api/tasks with title, description, class_id (own class), deadline → 201
- **Happy path — student sees tasks**: Login as student → GET /api/tasks/my → returns tasks for primary_class_id, ordered by deadline
- **Happy path — file upload**: POST /api/files/upload with valid file → 200 + file_id
- **Happy path — submit**: POST /api/tasks/:id/submissions with file_ids → 201, version=1
- **Happy path — resubmit**: POST /api/tasks/:id/submissions again → 200, version=2, previous files replaced
- **Happy path — teacher sees submissions**: Login as teacher → GET /api/tasks/:id/submissions → list with student names, versions, is_late
- **Happy path — grade**: POST /api/tasks/:id/grades with submission_id, score=85 → 200
- **Happy path — publish**: POST /api/tasks/:id/grades/publish → 200, grades_published=true
- **Happy path — student sees grade**: Login as student → GET /api/submissions/:id → includes grade with score, feedback
- **Edge case — account lockout**: 5 failed login attempts → 403 with lockout message, 6th attempt (within 30 min) → 403
- **Edge case — late submission**: Submit after deadline with `allow_late_submission=true` → is_late=true, penalty_applied = score * late_penalty_percent / 100 (e.g., score=85, percent=10 → penalty_applied=8.5, effective=76.5)
- **Edge case — late submission rejected**: Submit after deadline with `allow_late_submission=false` → 400
- **Edge case — wrong class student**: Student from class A submits to task for class B → 403
- **Edge case — grade before publish**: Student views submission before grades_published → grade section is null/hidden
- **Edge case — file type rejected**: Upload .exe when not in global ALLOWED_FILE_TYPES → 400
- **Edge case — file too large**: Upload 200MB file when max is 50MB → 400
- **Edge case — task-specific file type rejected at submission**: Upload a .pdf (globally allowed), but task only allows .docx → submission returns 400
- **Edge case — total submission size exceeds 100MB**: Submit files totaling > 100MB → 400
- **Error path — expired token**: Request with expired access token → 401
- **Error path — wrong role**: Student tries POST /api/tasks → 403
- **Error path — score out of range**: Grade with score=150 → 422 validation error
- **Integration — full loop**: login teacher → create task → login student → upload → submit → login teacher → view submissions → grade → publish → login student → view grade. Verify each step returns expected data

**Verification:**
- `pytest backend/tests/test_min_loop.py` passes all scenarios
- Seed script runs successfully and data is queryable
- Full loop works via curl/httpie: login → create task → submit → grade → publish → view

**Risks:**
| Risk | Mitigation |
|------|------------|
| File upload race condition on atomic rename | UUID-based filenames prevent collision |
| Deadline edge case (submit at exact second) | Server compares `submitted_at` against deadline, not upload time |
| JWT secret management | config.py reads from env var with dev fallback |

**Demo / Verification:**
1. Run seed script: `cd backend && python scripts/seed_demo.py`
2. Start server: `cd backend && uvicorn app.main:app`
3. Run: `cd backend && pytest tests/test_min_loop.py` — all pass
4. Manual curl demo: login as teacher → create task → login as student → upload file → submit → login as teacher → grade → publish → login as student → see grade

**Rollback:** Revert all files added in PR2. Database tables remain (from PR1). Run `DELETE FROM` on seed data if needed.

---

### PR3: Minimum Closed-Loop Frontend

**PR Goal:** The entire training workflow works in a browser. Teacher creates tasks, student submits files and views grades, teacher grades and publishes. Chinese-language UI with Element Plus.

**Requirements:** R4, R5, R6 (individual grading only — bulk grading deferred to PR4), R8 (frontend for PR2 endpoints)

**Dependencies:** PR2 (all backend API endpoints working)

**Files:**
- Create: `frontend/` — Vue 3 + Vite project scaffold
- Create: `frontend/src/router/index.js` — route config with role-based guards
- Create: `frontend/src/stores/auth.js` — Pinia auth store (login/logout, token refresh interceptor)
- Create: `frontend/src/api/` — axios instance with Bearer token interceptor + 401 refresh logic
- Create: `frontend/src/views/Login.vue` — login form with error handling (locked, deactivated, must_change_password)
- Create: `frontend/src/layouts/AppLayout.vue` — sidebar nav (role-based), top bar, router-view
- Create: `frontend/src/views/teacher/TaskCreate.vue` — task creation form (US-T1)
- Create: `frontend/src/views/teacher/TaskList.vue` — teacher's own tasks table (US-T1)
- Create: `frontend/src/views/teacher/SubmissionReview.vue` — submissions table for a task (US-T2)
- Create: `frontend/src/views/teacher/GradingDialog.vue` — score/feedback dialog + publish button (US-T3)
- Create: `frontend/src/views/student/TaskList.vue` — active tasks cards/table (US-S1)
- Create: `frontend/src/views/student/TaskDetail.vue` — task info + file upload + submit (US-S2)
- Create: `frontend/src/views/student/SubmissionDetail.vue` — files list, grade result (US-S3, US-S4)
- Create: `frontend/src/views/ChangePassword.vue` — forced password change on first login
- Create: `frontend/package.json` — Vue 3, Element Plus, Pinia, Vue Router, axios

**Approach:**
- Initialize Vue 3 project with Vite, configure proxy to backend dev server
- Axios interceptor attaches Bearer token from localStorage, catches 401 → refresh → retry
- Pinia auth store manages token pair, user info, role-based routing
- Vue Router guards: `/admin/*` requires admin, `/teacher/*` requires teacher, `/student/*` requires student
- Login page: username + password form, handles locked/deactivated/must_change_password states
- App layout: Element Plus container with sidebar (role-based menu visibility), top bar with user info + logout
- Teacher pages: task creation form (class selector from own classes, datetime picker for deadline, file type multi-select), task list with status badges, submission review table, grading dialog
- Student pages: task list ordered by deadline, task detail with drag-and-drop upload, submission detail with grade visibility gated by grades_published

**Test scenarios:**
- **Happy path — login and redirect**: Enter valid credentials → redirect to role-appropriate home page
- **Happy path — teacher creates task**: Fill form, select class, set deadline → task appears in task list
- **Happy path — student sees tasks**: Student dashboard shows active tasks for their class
- **Happy path — student submits**: Open task → upload file → submit → see version=1 confirmation
- **Happy path — student resubmits**: Submit again → confirmation shows "replaces version N"
- **Happy path — teacher reviews**: Open task submissions → see student list with status → download file
- **Happy path — teacher grades**: Click submission → enter score + feedback → save
- **Happy path — teacher publishes**: Click publish → confirmation dialog → all students can now see grades
- **Happy path — student sees grade**: Open submission → grade section visible with score and feedback
- **Edge case — forced password change**: First login with must_change_password=true → redirect to change password form
- **Edge case — account locked**: Login with 5 failed attempts → error message shows lockout timer
- **Edge case — file type validation feedback**: Student uploads .exe → UI shows "file type not allowed" immediately
- **Edge case — late submission badge**: Student submits after deadline → "late" badge shown
- **Error path — session expired**: 401 during any request → automatic token refresh → retry; if refresh fails → redirect to login
- **Error path — wrong role access**: Student navigates to /teacher/* → redirected to student home

**Verification:**
- `npm run build` succeeds with no errors
- Full browser demo works: login → create task → submit → grade → publish → view grade
- Responsive layout works at 1280px and 768px widths

**Risks:**
| Risk | Mitigation |
|------|------------|
| Token refresh race condition | Axios interceptor queues concurrent 401s, refreshes once |
| Element Plus version compatibility | Pin specific Element Plus version in package.json |
| CORS issues in development | Vite proxy configured to forward /api to backend |

**Demo / Verification:**
1. `cd frontend && npm install && npm run dev`
2. Backend running from PR2
3. Browser: login as teacher → create task → login as student → upload file → submit → login as teacher → review → grade → publish → login as student → see grade
4. Verify Chinese-language UI renders correctly

**Rollback:** Delete `frontend/` directory. Backend remains fully functional.

---

### PR4: Full Features + Admin + Deployment

**PR Goal:** Complete all remaining MVP features — admin CRUD pages, teacher/student enhancements, and production deployment configuration. The system is ready for production use.

**Requirements:** R1 (full: logout, reset-password), R2, R3 (full), R4 (full), R6 (bulk), R7 (cleanup), R9

**Dependencies:** PR3 (frontend loop working)

**Files:**
- Create: `backend/app/routers/users.py` — POST/GET/PUT/DELETE /api/users, GET/PUT /api/users/me
- Modify: `backend/app/routers/auth.py` — add logout, reset-password endpoints (refresh and change-password already in PR2)
- Modify: `backend/app/routers/classes.py` — add PUT, DELETE, GET (admin list), POST enroll student
- Modify: `backend/app/routers/tasks.py` — add PUT, DELETE, POST archive, GET (admin list)
- Modify: `backend/app/routers/grades.py` — add bulk grade endpoint
- Create: `backend/app/services/file_cleanup.py` — orphan file cleanup service
- Create: `backend/tests/test_auth.py` — auth edge cases
- Create: `backend/tests/test_users.py` — user CRUD edge cases
- Create: `backend/tests/test_classes.py` — class CRUD edge cases
- Create: `backend/tests/test_tasks.py` — task edit/delete/archive edge cases
- Create: `backend/tests/test_grades.py` — grading edge cases including bulk
- Create: `backend/tests/test_files.py` — file upload/download/cleanup edge cases
- Create: `frontend/src/views/admin/UserManagement.vue` — user CRUD table with pagination, reset-password button
- Create: `frontend/src/views/admin/ClassManagement.vue` — class management with semester filter
- Create: `frontend/src/views/admin/ClassRoster.vue` — enrolled students, enroll/transfer
- Create: `frontend/src/views/admin/TaskList.vue` — admin task oversight across all classes (US-A5)
- Create: `frontend/src/views/ProfileEdit.vue` — self-service profile viewing/editing (GET/PUT /api/users/me)
- Modify: `frontend/src/views/teacher/TaskList.vue` — add edit, archive, delete buttons
- Modify: `frontend/src/views/teacher/SubmissionReview.vue` — add bulk grade, penalty display
- Modify: `frontend/src/views/student/SubmissionDetail.vue` — version history display
- Create: `deploy/nginx.conf` — reverse proxy config, X-Accel-Redirect, gzip, CSP headers
- Create: `deploy/training-platform.service` — systemd unit file for uvicorn
- Create: `deploy/deploy.sh` — deployment script
- Create: `deploy/cleanup-cron.sh` — daily orphan file cleanup cron

**Approach:**

**Backend enhancements (D-phase):**
- Auth: logout revokes refresh token (sets revoked=true in refresh_tokens table); admin reset sets temp password + must_change_password=true; refresh and change-password already in PR2
- Users: admin CRUD with pagination, role filter, name/username search; deactivation sets is_active=false, preserves all data; /users/me for self-service profile
- Classes: full CRUD for admin; delete rejects if students enrolled; delete also rejects if tasks exist (RESTRICT FK); semester filter on list; enroll/transfer students
- Tasks: edit rejects file type change after submissions; edit rejects deadline reduction before earliest submission; delete rejects if submissions exist; archive sets status; admin gets paginated list with semester/class filter
- Grades: bulk grade applies same score to selected submissions, auto-calculates late penalty per submission
- File cleanup: service function deletes files in `/uploads/tmp/` older than 24 hours with no submission_files record. Files already renamed to `/uploads/` (linked to submissions) are never touched

**Frontend enhancements (E-phase):**
- Admin user management: Element Plus table with pagination, role filter, search, create/edit dialog, deactivate button, reset-password button
- Admin class management: table with semester filter, create/edit dialog, teacher assignment, roster link
- Admin roster: enrolled students table, search + enroll, transfer confirmation
- Admin task oversight: paginated task list across all classes with semester/class filter (US-A5)
- Profile editing: self-service page for viewing/editing own name, email, phone (GET/PUT /api/users/me)
- Teacher task list: edit button (pre-filled form), archive button, delete button (disabled if submissions exist)
- Teacher grading: bulk grade button with multi-select + score input, penalty_applied and effective score display
- Student submission: resubmit confirmation with version info, version history in detail (metadata: version, timestamp, is_late)

**Deployment (F-phase):**
- Nginx: reverse proxy /api to uvicorn:8000, serve Vue dist/, /uploads/ with internal + X-Accel-Redirect, gzip, CSP headers
- Systemd: uvicorn service with auto-restart
- Deploy script: install deps → run migrations → build frontend → copy dist → restart services
- Cron: daily cleanup of orphan files in /uploads/tmp/

**Test scenarios:**
- **Happy path — logout**: POST /api/auth/logout → refresh token revoked, subsequent refresh fails with 401
- **Happy path — change password**: POST /api/auth/change-password with valid current + new (8+ chars) → 200, must_change_password=false
- **Happy path — admin creates user**: POST /api/users with role=teacher → 201, user can login
- **Happy path — admin deactivates user**: PUT /api/users/:id/deactivate → user cannot login, submissions/grades preserved
- **Happy path — admin class CRUD**: Create, edit, list with semester filter, view roster
- **Happy path — admin delete empty class**: DELETE /api/classes/:id (no students) → 204
- **Edge case — admin delete non-empty class**: DELETE /api/classes/:id (has students) → 409
- **Happy path — edit task (no submissions)**: PUT /api/tasks/:id → 200, changes applied
- **Edge case — edit task file types after submission**: PUT /api/tasks/:id with changed allowed_file_types → 409
- **Edge case — reduce deadline before earliest submission**: PUT /api/tasks/:id with earlier deadline → 409
- **Happy path — delete task (no submissions)**: DELETE /api/tasks/:id → 204
- **Edge case — delete task with submissions**: DELETE /api/tasks/:id → 409
- **Happy path — archive task**: POST /api/tasks/:id/archive → 200, status=archived, hidden from student list
- **Happy path — bulk grade**: POST /api/tasks/:id/grades/bulk with submission_ids + score=80 → all graded, late ones have penalty_applied
- **Edge case — bulk grade mix late/on-time**: Score 80 applied to 3 submissions (1 late, 2 on-time) → late one gets penalty calculated, others get 80
- **Happy path — file cleanup**: Run cleanup service → /uploads/tmp/ files older than 24h with no submission_files link deleted
- **Edge case — file cleanup preserves linked files**: Recent /uploads/tmp/ file with submission_files link → not deleted
- **Error path — password too short**: Change password with 5-char new password → 422
- **Error path — wrong current password**: Change password with wrong current → 401
- **Error path — admin deactivates self**: PUT /api/users/:id/deactivate where :id == current_user.id → 400 "不能停用自己的账户"
- **Error path — duplicate username**: POST /api/users with existing username → 409
- **Happy path — admin lists all tasks**: GET /api/tasks with optional semester/class_id filter → 200, paginated results (US-A5)
- **Happy path — user profile**: GET /api/users/me → 200, returns name, email, phone (not password_hash)
- **Happy path — user edits profile**: PUT /api/users/me with new email → 200
- **Error path — student with no class login**: Student with primary_class_id=null → login succeeds, GET /api/tasks/my returns empty list
- **Edge case — class delete with tasks**: DELETE /api/classes/:id (has tasks) → 409

**Verification:**
- All test files pass: `pytest backend/tests/`
- Admin can manage users and classes through browser
- Teacher can edit/archive/delete tasks through browser
- Teacher can bulk grade through browser
- Student sees version history and resubmit confirmation
- Nginx config tested with `nginx -t`
- Deploy script runs without errors on a clean server
- Cleanup cron runs and removes orphan files

**Risks:**
| Risk | Mitigation |
|------|------------|
| Deployment script assumes specific server paths | Use configurable environment variables |
| Nginx X-Accel-Redirect misconfiguration | Test with `nginx -t` and manual file download |
| Bulk grade partial failure | Transaction wraps all grades; all-or-nothing |
| Admin self-deactivation | Explicit check in handler prevents it |

**Demo / Verification:**
1. Run all tests: `pytest backend/tests/`
2. Admin flow: login as admin → create teacher → create class → assign teacher → create student → enroll student
3. Teacher full flow: login → create task → edit task → view submissions → bulk grade → publish → archive task
4. Student full flow: login → view tasks → submit → resubmit (see version) → view grade after publish
5. Deployment: `bash deploy/deploy.sh` on target server → verify Nginx serves frontend, API responds, file download works

**Rollback:**
- Backend: revert code, no database migration needed (only adding data, not schema)
- Frontend: revert code, rebuild and redeploy
- Deployment: restore previous Nginx config, restart services

---

## System-Wide Impact

- **Interaction graph:** FastAPI routers → SQLAlchemy models → MySQL. Axios interceptors → backend API. No webhooks, no background jobs (except cron for file cleanup).
- **Error propagation:** HTTP status codes propagate from router → client. 401 triggers token refresh. 403 shows permission error. 400 shows invalid request (e.g., self-deactivation). 422 shows validation errors.
- **State lifecycle risks:** File upload without submission creates orphan in `/uploads/tmp/` (mitigated by daily cron scanning tmp only). Grade publish is atomic single boolean (no partial visibility). Refresh token revocation via database flag (survives server restart).
- **API surface parity:** All 3 roles (admin/teacher/student) access the same API surface with different permissions enforced at router level.
- **Integration coverage:** PR2 end-to-end test covers the full backend loop. PR3 browser testing covers the full frontend loop. PR4 extends both with complete CRUD.
- **Unchanged invariants:** No external systems integrated. No shared databases. No cross-service communication.

### Known Spec Contradictions (for implementer awareness)

- **Penalty arithmetic**: The grading spec first example (score=85, penalty_applied=10, effective=75.5) has no valid arithmetic path. The correct formula per design.md is `penalty_applied = score * percent / 100` → `penalty_applied=8.5, effective=76.5`. Follow design.md, not the first grading spec example.
- **Effective score storage**: design.md says "displayed, not stored separately." The grading spec says "stored as DECIMAL." The `penalty_applied` column IS stored as DECIMAL; the effective score (= `score - penalty_applied`) is computed at display time and never persisted.

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MySQL not available in dev environment | Low | High | Docker compose in PR1 provides MySQL 8 with utf8mb4 |
| JWT secret leaks | Low | High | Read from env var, never committed |
| File upload fills disk | Medium | Medium | Monitor disk usage, daily cleanup cron in PR4 |
| Concurrent grade overwrite (2 teachers) | Low | Low | Accept per design.md D5; audit via graded_by/graded_at |
| Extension-based file type spoofing | Medium | Low | Trusted internal network per design.md; magic-byte check in V2 |
| Vue build size too large | Low | Low | Element Plus tree-shaking; Vite code splitting |
| passlib incompatibility with bcrypt 5.x | High | High | Use standalone `bcrypt` library, not `passlib[bcrypt]` (D9) |
| python-jose unmaintained | High | Medium | Use `PyJWT` instead (D9) |

## Documentation / Operational Notes

- Seed script (`backend/scripts/seed_demo.py`) provides demo data for testing all 3 roles
- Nginx config requires `internal` directive on `/uploads/` location for X-Accel-Redirect security
- Systemd service requires absolute path to uvicorn and working directory
- Deploy script should be run as root or with sudo for Nginx/systemd restart
- Cron job runs as application user, not root

## Sources & References

- **Origin document:** [proposal.md](openspec/changes/add-digital-training-platform-mvp/proposal.md)
- **Design decisions:** [design.md](openspec/changes/add-digital-training-platform-mvp/design.md)
- **Task breakdown:** [tasks.md](openspec/changes/add-digital-training-platform-mvp/tasks.md)
- **Feature specs:** [specs/](openspec/changes/add-digital-training-platform-mvp/specs/)
