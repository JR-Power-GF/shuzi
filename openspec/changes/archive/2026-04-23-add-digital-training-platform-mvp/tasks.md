## Phase A — 后端骨架 (Backend Skeleton)

> 目标：项目能启动，数据库有表，认证依赖就绪。

- [ ] A.1 Initialize FastAPI project structure: `backend/app/` with `main.py`, `config.py`, `database.py`, `__init__.py`; `backend/alembic/` for migrations; `backend/tests/` for test files; create empty `backend/app/grader/` directory as AI grading extension point
- [ ] A.2 Add Python dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `alembic`, `pymysql`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `pydantic>=2.0`
- [ ] A.3 Create `backend/app/config.py` with settings: `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_EXPIRE_DAYS=7`, `UPLOAD_DIR=/uploads`, `MAX_FILE_SIZE_MB`, `ALLOWED_FILE_TYPES`
- [ ] A.4 Create `backend/app/database.py` with SQLAlchemy 2.0 async engine, `sessionmaker`, and `Base` declarative base
- [ ] A.5 Create all 6 database models: `backend/app/models/user.py` (users), `backend/app/models/class_.py` (classes), `backend/app/models/task.py` (tasks), `backend/app/models/submission.py` (submissions), `backend/app/models/submission_file.py` (submission_files), `backend/app/models/grade.py` (grades), and `backend/app/models/__init__.py` importing all models so Alembic autogenerate detects them
- [ ] A.6 Create `backend/alembic.ini` and initialize Alembic with `alembic init`, configure `env.py` to import `database.Base` and all models, generate initial migration: `alembic revision --autogenerate -m "initial tables"` and verify all 6 tables with correct columns, types, constraints, and indexes
- [ ] A.7 Create `backend/app/dependencies/auth.py`: `get_current_user` dependency that decodes JWT from Authorization Bearer header, validates token, returns user object; `require_role` dependency factory for role-based access control
- [ ] A.8 Create `backend/app/main.py` with FastAPI app, CORS middleware (allow Vue dev server origin), Content-Security-Policy headers for XSS prevention, include all routers with `/api` prefix

## Phase B — 最小闭环后端 (Minimum Loop Backend)

> 最小闭环：登录 → 教师建任务 → 学生提交 → 教师评分 → 学生查分
> 完成此 Phase 后，整个闭环可通过 curl/API 客户端跑通。

- [ ] B.1 **登录** — Create `backend/app/routers/auth.py` with `POST /api/auth/login`: validate username/password, check is_active/locked_until, handle failed_login_attempts (lock after 5 fails for 30 min), issue access+refresh JWT tokens, return must_change_password flag (US-A4, US-S1)
- [ ] B.2 **数据初始化** — Create seed script `backend/scripts/seed_demo.py`: insert demo admin (admin/admin123), demo teacher (teacher1/teacher123) with class "计算机网络1班" semester="2025-2026-2", demo student (student1/student123) enrolled in that class. Must_change_password=true for all. This enables immediate end-to-end testing
- [ ] B.3 **班级最小集** — Create `backend/app/routers/classes.py` with: `POST /api/classes` (admin only), `GET /api/classes/my` (teacher only, return classes where teacher_id matches current user), `GET /api/classes/:id/students` (admin or assigned teacher). These 3 endpoints support the minimum loop (US-A2, US-T2)
- [ ] B.4 **任务创建+查看** — Create `backend/app/routers/tasks.py` with: `POST /api/tasks` (teacher only, copy semester from class, validate teacher owns class), `GET /api/tasks/my` (student only, active tasks for primary_class_id ordered by deadline), `GET /api/tasks/:id` (authorized users: student in class, teacher creator, admin). These 3 endpoints support task creation and student viewing (US-T1, US-S1)
- [ ] B.5 **文件上传** — Create `backend/app/routers/files.py` with `POST /api/files/upload`: validate file type/size, write to `/uploads/tmp/{uuid}`, atomic rename to `/uploads/{uuid}_{filename}`, return file_id and metadata. Handle filenames with special/unicode characters. And `GET /api/files/:id`: validate ownership, return X-Accel-Redirect header with correct Content-Type and Content-Disposition (US-S2, US-T5)
- [ ] B.6 **学生提交** — Create `backend/app/routers/submissions.py` with: `POST /api/tasks/:id/submissions` (student only, validate class membership, validate deadline, handle is_late, version++ on resubmit, UNIQUE handles double-click, link files), `GET /api/submissions/:id` (student sees own only, grade status visible only if grades_published=true), `GET /api/submissions/:id/files/:fileId` (validate ownership, return file) (US-S2, US-S4)
- [ ] B.7 **教师查看提交** — Add to submissions router: `GET /api/tasks/:id/submissions` (teacher only, task creator, list all submissions with student name, version, is_late, submitted_at, grade status) (US-T2)
- [ ] B.8 **评分+发布** — Create `backend/app/routers/grades.py` with: `POST /api/tasks/:id/grades` (teacher only, task creator, validate score 0-100, auto-calculate late penalty, last editor wins), `POST /api/tasks/:id/grades/publish` (validate grades exist, set grades_published=true in single transaction), `POST /api/tasks/:id/grades/unpublish` (set grades_published=false) (US-T3, US-S3)
- [ ] B.9 **闭环测试** — Create `backend/tests/test_min_loop.py`: seed demo data, test full loop via API calls — login as teacher → create task → login as student → upload file → submit → login as teacher → view submissions → grade → publish → login as student → view grade. Verify each step returns expected status and data

## Phase C — 最小闭环前端 (Minimum Loop Frontend)

> 完成此 Phase 后，整个闭环可通过浏览器完整跑通。

- [ ] C.1 Initialize Vue 3 + Element Plus frontend: `frontend/` with Vite, Vue Router, Pinia, Element Plus, axios with interceptor for Bearer token attachment and 401 refresh logic
- [ ] C.2 Create Vue Router config with route guards: `/login` (public), `/admin/*` (admin only), `/teacher/*` (teacher only), `/student/*` (student only), `/` redirect by role
- [ ] C.3 Create Pinia auth store: login/logout actions, token storage in localStorage, refresh token logic (axios interceptor catches 401, refreshes, retries original request)
- [ ] C.4 Create login page: username + password form with Element Plus, call login API, redirect by role on success, show must_change_password prompt if flagged, display account locked/deactivated error messages
- [ ] C.5 Create app layout with Element Plus: sidebar navigation (role-based menu items), top bar with user info, change password link, and logout button, main content area with `<router-view>`
- [ ] C.6 Create teacher task creation form (US-T1): title, description, requirements (textarea), class selector (only teacher's classes from GET /api/classes/my), deadline (datetime picker), allowed_file_types (multi-select), max_file_size_mb (number input), allow_late_submission (switch), late_penalty_percent (conditional number input)
- [ ] C.7 Create teacher task list page (US-T1 view): table of own tasks with status badge, deadline, submission count, grades_published status, actions (view submissions, manage grades)
- [ ] C.8 Create student task list page (US-S1): cards/table of active tasks for student's class, show deadline, submission status (not submitted / submitted version N), is_late badge, click to view task detail
- [ ] C.9 Create student task detail + submission page (US-S2): task info (title, description, requirements, deadline, allowed file types), file upload area with drag-and-drop, file type/size validation feedback, submit button, resubmit updates version with confirmation
- [ ] C.10 Create teacher submission review page (US-T2): table of submissions for a task with student name, version, is_late badge, submitted_at, grade status; click row to open grading dialog; download file buttons
- [ ] C.11 Create teacher grading dialog (US-T3): score input (0-100), feedback textarea, save button; publish/unpublish grades buttons with confirmation dialog
- [ ] C.12 Create student submission detail page (US-S3, US-S4): submitted files list with download links, version info, is_late badge, grade result section (visible only when grades_published=true, shows score, feedback, penalty_applied, effective score)

## Phase D — 完整后端功能 (Full Backend Features)

> 补全 Phase B 中省略的完整 CRUD、安全增强、边界处理。

- [ ] D.1 **Auth 增强** — Add to auth router: `POST /api/auth/logout` (revoke refresh token), `POST /api/auth/change-password` (validate current password, enforce 8-char minimum), `POST /api/auth/reset-password/:id` (admin only, set temp password), `POST /api/auth/refresh` (issue new pair, revoke old). Create `backend/tests/test_auth.py` with all edge cases (lockout timing, concurrent login, password change during session, token expiry mid-request)
- [ ] D.2 **用户管理** — Create `backend/app/routers/users.py`: `POST /api/users` (admin only), `GET /api/users` (admin, paginated, filter by role, search), `PUT /api/users/:id` (admin), `PUT /api/users/:id/deactivate` (admin), `GET /api/users/me`, `PUT /api/users/me`. Create `backend/tests/test_users.py` with edge cases (US-A1, US-A3)
- [ ] D.3 **班级完整** — Add to classes router: `PUT /api/classes/:id` (admin), `DELETE /api/classes/:id` (admin, reject if has students), `GET /api/classes` (admin, paginated, semester filter), `POST /api/classes/:id/students` (admin, enroll/transfer student). Create `backend/tests/test_classes.py` with edge cases (US-A2)
- [ ] D.4 **任务完整** — Add to tasks router: `PUT /api/tasks/:id` (teacher, reject file type change after submissions, reject deadline reduction before earliest submission), `DELETE /api/tasks/:id` (teacher, reject if submissions exist), `POST /api/tasks/:id/archive` (teacher, set status=archived), `GET /api/tasks` (admin, paginated). Create `backend/tests/test_tasks.py` with edge cases (US-T1, US-T4)
- [ ] D.5 **批量评分** — Add to grades router: `POST /api/tasks/:id/grades/bulk` (apply same score to multiple submissions, auto-calculate late penalty per submission). Create `backend/tests/test_grades.py` with all grading edge cases (US-T3)
- [ ] D.6 **文件清理** — Create `backend/app/services/file_cleanup.py`: delete files in `/uploads/tmp/` older than 24 hours with no corresponding submission_files record. Create `backend/tests/test_files.py` with upload/download/cleanup edge cases

## Phase E — 完整前端功能 (Full Frontend Features)

> 管理员页面、教师增强、学生增强。

- [ ] E.1 Create admin user management page (US-A1, US-A3): Element Plus table with pagination, role filter dropdown, name/username search input, create/edit user dialog, deactivate button with confirmation dialog
- [ ] E.2 Create admin class management page (US-A2): table with semester filter, create/edit class dialog, assign teacher dropdown, delete with confirmation, view roster link
- [ ] E.3 Create admin class roster page: enrolled students table, enroll student input (search + add), transfer student from another class confirmation
- [ ] E.4 Enhance teacher task list: add edit task button (opens pre-filled form), archive button with confirmation, delete button (disabled if submissions exist, tooltip explains why)
- [ ] E.5 Enhance teacher grading: bulk grade button opens multi-select + score input, show penalty_applied and effective score in submission review table
- [ ] E.6 Enhance student submission: show resubmit confirmation with "this replaces your previous submission (version N)" message, show version history in submission detail

## Phase F — 部署上线 (Deployment)

> 生产环境配置、自动化部署。

- [ ] F.1 Create Nginx config: reverse proxy `/api` to uvicorn (port 8000), serve Vue static files from `/dist`, `location /uploads/` with `internal` directive and `X-Accel-Redirect` support, gzip compression, Content-Security-Policy headers
- [ ] F.2 Create systemd service file for backend: `ExecStart=/path/to/uvicorn app.main:app --host 0.0.0.0 --port 8000`, restart on failure
- [ ] F.3 Create deployment script: install Python deps, run Alembic migrations, build Vue frontend (`npm run build`), copy dist to Nginx serve path, restart services
- [ ] F.4 Add cron job for orphan file cleanup: daily run of file_cleanup service function, only targets /uploads/tmp/ files older than 24 hours
