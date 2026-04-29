---
title: "feat: Digital Training Platform MVP — 4-PR Incremental Delivery"
type: feat
status: active
date: 2026-04-21
origin: openspec/changes/add-digital-training-platform-mvp/proposal.md
---

# Digital Training Platform MVP — 4-PR Delivery Plan

## Overview

Build the Digital Training Teaching Management Platform (数字实训教学管理平台) as 4 incremental PRs. Each PR lands a verifiable, self-contained slice. After PR 3, the core loop (login → teacher creates task → student submits → teacher grades → student sees score) works end-to-end in a browser. PR 4 adds admin features, enhanced flows, and production deployment.

## Problem Frame

Vocational college teachers manage practical training through spreadsheets, WeChat, and email. No single system connects assignment creation, student submission, and grading. This MVP replaces that fragmented workflow with a focused web platform serving ~50 teachers and ~2000 students on a single server.

## Requirements Trace

- R1. Authentication: login, lockout, password change/reset, JWT Bearer tokens (US-A4, US-S1, AC-Auth)
- R2. User management: admin CRUD for teachers/students, self-service profile (US-A1, US-A3, AC-User)
- R3. Class management: flat class list with semester, teacher assignment, student enrollment (US-A2, AC-Class)
- R4. Task publishing: teacher creates tasks with deadline, file constraints, late policy for own class (US-T1, US-T4, AC-Task)
- R5. Student submission: file upload, resubmit with version tracking, late flagging (US-S2, US-S4, AC-Submission)
- R6. Grading: score entry, feedback, bulk grade, publish/unpublish as single transaction (US-T3, US-S3, AC-Grading)
- R7. File storage: local filesystem, UUID prefix, Nginx X-Accel-Redirect (AC-File)
- R8. Deployment: Nginx + uvicorn + systemd, single 4-core/8GB server

## Scope Boundaries

- No AI grading (V2 extension point: `backend/app/grader/`)
- No XR/VR sessions (V2 extension point: `submission_type` column)
- No device management (V2 extension point: new `devices` table)
- No org hierarchy, course management, statistics dashboard, notifications, batch import, multi-class tasks
- No mobile app (responsive web only)
- No SSO/CAS integration
- No video upload/streaming

## Key Technical Decisions

- **Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic** — async, auto OpenAPI docs, Pydantic validation (see origin: design.md D1)
- **Vue 3 + Element Plus + Pinia + Vue Router** — standard Chinese edtech stack (see origin: design.md D1)
- **MySQL 8** — school infrastructure already has it (see origin: design.md D1)
- **JWT Bearer in localStorage** — no CSRF vector, simpler than httpOnly cookie (see origin: design.md D2)
- **6 tables, no V2 columns** — users, classes, tasks, submissions, submission_files, grades (see origin: design.md D3)
- **1 task = 1 class** — no M:N, simplifies all queries (see origin: design.md D4)
- **No grading lock** — last editor wins, audit trail via graded_by + graded_at (see origin: design.md D5)
- **Atomic file rename** — upload to tmp/, rename to final path (see origin: design.md D6)
- **Single boolean for grade publication** — grades_published on tasks table (see origin: design.md D7)

## PR Strategy

```
PR 1: Backend skeleton + Auth + Seed        ──▶  API starts, login works, demo data exists
PR 2: Core API loop                          ──▶  Full loop works via curl/Postman
PR 3: Frontend minimum loop                  ──▶  Full loop works in browser
PR 4: Full features + Deployment             ──▶  Production-ready with admin pages
```

---

## PR 1: Backend Skeleton + Authentication + Seed Data

### PR Goal

A running FastAPI server with database migrations, JWT authentication, role-based access control, and a seed script that creates demo accounts. After merging, any developer can `alembic upgrade head && python seed_demo.py` and immediately test login via curl.

### Modules / Files

| Area | Files |
|------|-------|
| Project scaffold | `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/database.py` |
| Auth dependency | `backend/app/dependencies/auth.py` |
| Data models | `backend/app/models/user.py`, `backend/app/models/class_.py`, `backend/app/models/task.py`, `backend/app/models/submission.py`, `backend/app/models/submission_file.py`, `backend/app/models/grade.py`, `backend/app/models/__init__.py` |
| Migrations | `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/001_initial_tables.py` |
| Auth routes | `backend/app/routers/auth.py` |
| Seed script | `backend/scripts/seed_demo.py` |
| Tests | `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_auth.py` |
| Config | `backend/requirements.txt`, `backend/.env.example` |

### Risk Points

| Risk | Mitigation |
|------|------------|
| Alembic migration fails on MySQL 8 | Test migration on MySQL 8 specifically; use VARCHAR+CHECK not ENUM |
| JWT secret leaked in version control | `.env.example` only, `.env` in `.gitignore` |
| bcrypt hashing too slow in tests | Use a fast hasher in test config override |

### Test Strategy

- **Happy path:** login returns 200 with access+refresh tokens; `GET /api/users/me` returns user profile
- **Edge cases:** lockout after 5 failures; lockout expires at exact moment (strict greater-than); concurrent logins from multiple devices each get valid tokens; deactivated user gets rejected
- **Error paths:** wrong password returns 401; expired token returns 401; invalid token returns 401; access protected route without token returns 401
- **Integration:** refresh token flow — use refresh token to get new pair, old refresh token is revoked

### Demo / Verification

```bash
cd backend
pip install -r requirements.txt
# Configure .env with DATABASE_URL and SECRET_KEY
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload

# Verify login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# Should return tokens + must_change_password: true

# Verify protected route
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer <access_token>"
```

### Rollback

Single Alembic downgrade: `alembic downgrade base`. All backend files are new — delete `backend/` directory. No frontend changes in this PR.

---

## PR 2: Core API Loop (Task → Submit → Grade)

### PR Goal

All REST endpoints for the minimum closed loop work via API. After merging, a developer can walk through the full workflow using curl: teacher creates task → student uploads file and submits → teacher grades and publishes → student sees grade.

### Modules / Files

| Area | Files |
|------|-------|
| Class routes (minimum) | `backend/app/routers/classes.py` (POST, GET /my, GET /:id/students) |
| Task routes | `backend/app/routers/tasks.py` (POST, GET /my, GET /:id) |
| File routes | `backend/app/routers/files.py` (POST upload, GET download) |
| Submission routes | `backend/app/routers/submissions.py` (POST submit, GET /:id, GET /tasks/:id/submissions, GET /:id/files/:fileId) |
| Grade routes | `backend/app/routers/grades.py` (POST grade, POST publish, POST unpublish) |
| File cleanup | `backend/app/services/file_cleanup.py` |
| Tests | `backend/tests/test_min_loop.py`, `backend/tests/test_files.py`, `backend/tests/test_submissions.py` |
| Upload dirs | `/uploads/`, `/uploads/tmp/` (gitignored) |

### Risk Points

| Risk | Mitigation |
|------|------------|
| File upload race condition (two files same name) | UUID prefix guarantees uniqueness |
| Deadline check at wrong time | Validate at submission time, not upload time — explicit comment in code |
| UNIQUE constraint violation on double-click | Catch IntegrityError, update existing row instead of failing |
| X-Accel-Redirect doesn't work in dev | In dev mode (no Nginx), use FastAPI's FileResponse directly as fallback |

### Test Strategy

- **Happy path (test_min_loop.py):** seed demo → login as teacher → create task → login as student → upload file → submit → login as teacher → view submissions → grade → publish → login as student → view grade. Assert each step's status code and response shape
- **Edge cases:** deadline passes between upload and submit (server rejects or flags late); resubmit increments version; double-click submit handled by UNIQUE constraint; file upload with Chinese characters in filename; late penalty auto-calculation with DECIMAL precision
- **Error paths:** student submits to task not in their class (403); file type not allowed (422); file too large (422); grade score out of range (422); grade while published (400)
- **Integration:** file upload → submission → download chain works end-to-end; grade publish → student query → score visible; grade unpublish → student query → score hidden

### Demo / Verification

```bash
# After seed_demo.py:
# 1. Login as teacher, create task
TEACHER_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d '{"username":"teacher1","password":"teacher123"}' | jq -r .access_token)
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TEACHER_TOKEN" \
  -d '{"title":"网络协议实验报告","description":"...","class_id":1,"deadline":"2026-06-01T23:59:00","allowed_file_types":["pdf","doc","docx"],"max_file_size_mb":50,"allow_late_submission":true,"late_penalty_percent":10}'

# 2. Login as student, upload + submit
STUDENT_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d '{"username":"student1","password":"student123"}' | jq -r .access_token)
FILE_ID=$(curl -s -X POST http://localhost:8000/api/files/upload \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -F "file=@test_report.pdf" | jq -r .file_id)
curl -X POST http://localhost:8000/api/tasks/1/submissions \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -d '{"file_ids":["'$FILE_ID'"]}'

# 3. Teacher grades + publishes
curl -X POST http://localhost:8000/api/tasks/1/grades \
  -H "Authorization: Bearer $TEACHER_TOKEN" \
  -d '{"submission_id":1,"score":85,"feedback":"完成良好"}'
curl -X POST http://localhost:8000/api/tasks/1/grades/publish \
  -H "Authorization: Bearer $TEACHER_TOKEN"

# 4. Student checks grade
curl http://localhost:8000/api/submissions/1 \
  -H "Authorization: Bearer $STUDENT_TOKEN"
# Should show score:85, penalty_applied:null, feedback:"完成良好"
```

### Rollback

No schema changes in this PR (tables created in PR 1). New route files only — delete the route files and remove router includes from `main.py`. Upload directory files are non-destructive (gitignored).

---

## PR 3: Frontend Minimum Loop

### PR Goal

A browser-based UI that completes the full closed loop. After merging, a user can open the app, log in, and walk through: teacher creates task, student submits files, teacher grades and publishes, student sees score.

### Modules / Files

| Area | Files |
|------|-------|
| Frontend scaffold | `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`, `frontend/.env` |
| App shell | `frontend/src/App.vue`, `frontend/src/main.js` |
| Router | `frontend/src/router/index.js` |
| Auth store | `frontend/src/stores/auth.js` |
| API layer | `frontend/src/api/index.js` (axios instance with interceptor) |
| Login page | `frontend/src/views/Login.vue` |
| Layout | `frontend/src/layouts/MainLayout.vue` |
| Teacher pages | `frontend/src/views/teacher/TaskList.vue`, `frontend/src/views/teacher/TaskCreate.vue`, `frontend/src/views/teacher/SubmissionReview.vue` |
| Student pages | `frontend/src/views/student/TaskList.vue`, `frontend/src/views/student/TaskDetail.vue`, `frontend/src/views/student/SubmissionDetail.vue` |
| Components | `frontend/src/components/GradingDialog.vue`, `frontend/src/components/FileUpload.vue` |

### Risk Points

| Risk | Mitigation |
|------|------------|
| CORS issues between Vue dev server and FastAPI | Configure CORS in FastAPI main.py (done in PR 1) and proxy in vite.config.js |
| Token refresh race (multiple 401s at once) | Use a single refresh promise that all interceptors await |
| File upload progress not shown | Use axios onUploadProgress callback; Element Plus el-progress component |
| Large bundle size | Vite handles tree-shaking; Element Plus supports on-demand import |

### Test Strategy

- **Test expectation: none — this PR is frontend UI.** End-to-end browser testing is deferred to the integration verification step. The backend tests in PR 2 already cover the API contracts this UI consumes
- **Manual verification:** walk through the complete loop in browser (see Demo section)

### Demo / Verification

1. `cd frontend && npm install && npm run dev`
2. Open http://localhost:5173
3. Login as `teacher1` / `teacher123` → change password → see teacher dashboard
4. Create a new task with deadline, file types, late policy
5. Logout, login as `student1` / `student123` → change password → see student task list
6. Open task → upload a file → submit
7. Logout, login as `teacher1` → view submissions → grade 85 with feedback → publish grades
8. Logout, login as `student1` → view submission → see score 85, feedback, published status

### Rollback

Delete `frontend/` directory. Backend is unaffected. No database changes.

---

## PR 4: Full Features + Deployment

### PR Goal

Complete the platform: admin user/class management pages, enhanced teacher and student flows, production deployment configuration. After merging, the platform is ready for pilot deployment on the school server.

### Modules / Files

| Area | Files |
|------|-------|
| Auth enhancements | `backend/app/routers/auth.py` (add logout, change-password, reset-password, refresh) |
| User management routes | `backend/app/routers/users.py` (full CRUD + deactivate) |
| Class management routes | `backend/app/routers/classes.py` (add PUT, DELETE, GET all, POST enroll) |
| Task management routes | `backend/app/routers/tasks.py` (add PUT, DELETE, POST archive, GET admin list) |
| Grade bulk route | `backend/app/routers/grades.py` (add POST bulk) |
| Admin pages | `frontend/src/views/admin/UserManage.vue`, `frontend/src/views/admin/ClassManage.vue`, `frontend/src/views/admin/ClassRoster.vue` |
| Teacher enhancements | Update `TaskList.vue` (edit, archive, delete buttons), `SubmissionReview.vue` (bulk grade), `GradingDialog.vue` (effective score display) |
| Student enhancements | Update `TaskDetail.vue` (resubmit confirmation with version), `SubmissionDetail.vue` (version history) |
| Tests | `backend/tests/test_users.py`, `backend/tests/test_classes.py`, `backend/tests/test_tasks.py`, `backend/tests/test_grades.py` |
| Deployment | `deploy/nginx.conf`, `deploy/training-platform.service`, `deploy/deploy.sh`, `deploy/cleanup-cron.sh` |

### Risk Points

| Risk | Mitigation |
|------|------------|
| Nginx X-Accel-Redirect misconfigured | Test with real Nginx before merging; include Nginx config in repo |
| Deleting class with orphaned tasks | Database cascade + application-level check: reject if class has students |
| Admin deactivating self | Explicit server-side check: reject if target user == current user |
| Bulk grade on mixed late/on-time | Auto-calculate penalty per submission individually, not once for all |
| File cleanup cron deletes active file | Only clean /uploads/tmp/ (never /uploads/), only files older than 24 hours |

### Test Strategy

- **Users (test_users.py):** create student without class; change class after submissions exist; deactivate teacher with tasks; duplicate username rejected; admin cannot deactivate self
- **Classes (test_classes.py):** create with non-existent teacher_id; delete class with tasks but no students; enroll student already in another class (transfers); delete class with students (rejected)
- **Tasks (test_tasks.py):** edit after submissions — extend deadline OK, change file types rejected, reduce deadline rejected; archive while student viewing; semester copied from class not request body; delete with submissions (rejected)
- **Grades (test_grades.py):** grade same submission twice (overwrite); late penalty DECIMAL precision (85 × 10% = 8.5); bulk grade mix of late/on-time; publish-unpublish-republish cycle; grade while published (rejected)

### Demo / Verification

**Admin flow:**
1. Login as `admin` → create a teacher account → create a class → assign teacher → enroll students
2. Deactivate a test account → verify data preserved

**Enhanced teacher flow:**
3. Edit task after student submitted → verify deadline extension works but file type change is rejected
4. Archive a task → verify student can no longer see it in list
5. Bulk grade 5 submissions → verify late penalty applied individually
6. Unpublish grades → verify students see "not_graded" → republish → scores visible again

**Deployment:**
```bash
cd deploy
# Review nginx.conf, adjust server_name
sudo cp nginx.conf /etc/nginx/sites-available/training-platform
sudo ln -s /etc/nginx/sites-available/training-platform /etc/nginx/sites-enabled/
sudo cp training-platform.service /etc/systemd/system/
sudo systemctl daemon-reload
bash deploy.sh
sudo nginx -t && sudo systemctl reload nginx
```

### Rollback

- **Backend routes:** new endpoints, no schema changes. Remove route files and router includes
- **Frontend pages:** new Vue components. Remove views and routes
- **Deployment configs:** static files. `sudo rm /etc/nginx/sites-enabled/training-platform && sudo systemctl reload nginx`
- **Database:** no migrations in this PR. All tables from PR 1 are unchanged

---

## Dependency Graph

```
PR 1 (Skeleton + Auth)
 └──▶ PR 2 (Core API Loop)
       └──▶ PR 3 (Frontend Loop)
             └──▶ PR 4 (Full Features + Deploy)
```

Each PR depends only on the previous one. PR 2 and PR 3 could theoretically be developed in parallel by two people (backend dev + frontend dev), but PR 3 needs PR 2's endpoints to integrate against.

## Open Questions

### Resolved During Planning

- **How to split 4 PRs?** Resolved: skeleton/auth → core API → frontend → full features. Each PR is a vertical slice that adds capability without requiring the next PR to function.
- **Where does seed data go?** Resolved: PR 1 includes seed script so PR 2 tests can run immediately.
- **Should file download use Nginx in dev?** Resolved: no. Dev mode uses FastAPI FileResponse directly. Nginx X-Accel-Redirect only in production (PR 4).

### Deferred to Implementation

- **Exact Element Plus component choices** — implementation detail, not architectural
- **Axios interceptor retry count and backoff** — can be tuned during PR 3 implementation
- **Nginx worker_connections and keepalive settings** — depends on actual load testing
- **File cleanup cron schedule** — daily is sufficient for V1, exact time is ops decision

## Sources & References

- **Origin document:** [proposal.md](../../openspec/changes/add-digital-training-platform-mvp/proposal.md)
- **Design document:** [design.md](../../openspec/changes/add-digital-training-platform-mvp/design.md)
- **Task breakdown:** [tasks.md](../../openspec/changes/add-digital-training-platform-mvp/tasks.md)
