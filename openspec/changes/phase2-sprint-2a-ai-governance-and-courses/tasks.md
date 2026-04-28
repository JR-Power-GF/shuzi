## 1. Database Schema

- [ ] 1.1 Create `courses` table migration (id, name, description, semester, teacher_id FK, status enum active/archived, created_at, updated_at)
- [ ] 1.2 Create `ai_usage_logs` table migration (id, user_id FK, endpoint varchar, model varchar, prompt_tokens int, completion_tokens int, cost_microdollars int, latency_ms int, status enum success/error, created_at). Add composite index on (user_id, created_at) for budget check performance.
- [ ] 1.3 Create `ai_feedback` table migration (id, ai_usage_log_id FK, user_id FK, rating smallint, comment text nullable, created_at, unique constraint on ai_usage_log_id + user_id)
- [ ] 1.4 Create `ai_config` table migration (id, key varchar unique, value text, updated_at) for runtime-editable AI settings (model, budgets)
- [ ] 1.5 Create migration to add nullable `course_id` FK to `tasks` table

## 2. Course Management Backend

- [ ] 2.1 Create `backend/app/models/course.py` with Course SQLAlchemy model
- [ ] 2.2 Register Course model in `backend/app/models/__init__.py`
- [ ] 2.3 Create `backend/app/schemas/course.py` with CourseCreate, CourseUpdate, CourseOut, CourseListOut schemas
- [ ] 2.4 Create `backend/app/routers/courses.py` with CRUD endpoints (POST create, PUT update, GET list, GET detail, POST archive)
- [ ] 2.5 Add course_id parameter to task creation and update in `backend/app/routers/tasks.py`
- [ ] 2.6 Add course_id filter to task list endpoint in `backend/app/routers/tasks.py`
- [ ] 2.7 Modify student task listing (GET /api/tasks/my) to exclude tasks belonging to archived courses
- [ ] 2.8 Write tests for course CRUD (create, edit, archive, permission checks, duplicate name)
- [ ] 2.9 Write tests for task-course linking (create with course, filter by course, permission on course ownership)
- [ ] 2.10 Write test for archived course hiding tasks from student task list

## 3. AI Service Layer

- [ ] 3.1 Add `openai` dependency to `backend/requirements.txt`
- [ ] 3.2 Add AI config to `backend/app/config.py` (AI_API_KEY, AI_MODEL, AI_BASE_URL env vars as defaults) and create `ai_config` table accessor for runtime overrides
- [ ] 3.3 Create `backend/app/services/__init__.py`
- [ ] 3.4 Create `backend/app/services/ai.py` with AIProvider protocol, OpenAIProvider implementation, and module-level AIService singleton
- [ ] 3.5 Implement `AIService.generate()`: budget check (with COALESCE), provider call, usage logging (cost in microdollars), error handling
- [ ] 3.6 Implement `AIService.check_budget()`: query daily token usage with COALESCE(SUM, 0), compare against role budget from config
- [ ] 3.7 Create `backend/app/models/ai_usage_log.py`, `backend/app/models/ai_feedback.py`, `backend/app/models/ai_config.py`
- [ ] 3.8 Register new models in `backend/app/models/__init__.py`

## 4. AI Governance Endpoints

- [ ] 4.1 Create `backend/app/schemas/ai.py` with AIFeedbackIn, AIUsageOut, AIStatsOut, AIConfigOut, AIConfigUpdate schemas
- [ ] 4.2 Create `backend/app/routers/ai.py` with feedback endpoint (POST /api/ai/feedback)
- [ ] 4.3 Add admin usage query endpoint (GET /api/ai/usage with user_id, date filters)
- [ ] 4.4 Add admin stats endpoint (GET /api/ai/stats with date range, group_by, feedback summary)
- [ ] 4.5 Add admin test endpoint (POST /api/ai/test) for triggering a single AI call to verify the full stack (budget check, provider call, logging, error handling)
- [ ] 4.6 Add admin config endpoints (GET /api/ai/config, PUT /api/ai/config) for reading and updating AI model, budgets, and API key status
- [ ] 4.7 Write tests for rate limiting (budget exceeded returns 429, within budget passes, first-call-of-day with zero rows)
- [ ] 4.8 Write tests for AI usage logging (successful call logged, failed call logged, cost calculation in microdollars)
- [ ] 4.9 Write tests for feedback (submit positive/negative, duplicate rejection, cross-user rejection)
- [ ] 4.10 Write tests for admin stats endpoints (aggregate, by-user, feedback summary, non-admin forbidden)
- [ ] 4.11 Write test for admin test endpoint (trigger AI call end-to-end, verify log created)

## 5. Frontend: Course Management

- [ ] 5.1 Create `frontend/src/views/teacher/CourseList.vue` (teacher's courses, create button, archive)
- [ ] 5.2 Create `frontend/src/views/teacher/CourseDetail.vue` (course info + task list under course)
- [ ] 5.3 Create `frontend/src/views/teacher/CourseCreate.vue` (form: name, description, semester)
- [ ] 5.4 Create `frontend/src/views/admin/CourseList.vue` (all courses with filters)
- [ ] 5.5 Create `frontend/src/views/student/CourseList.vue` (card-based home page with progress bars and deadline badges per course)
- [ ] 5.6 Add course_id selector to TaskCreate.vue and TaskEdit.vue
- [ ] 5.7 Add course routes to router (teacher, admin, student sections)
- [ ] 5.8 Add backend endpoint for student course progress data (GET /api/courses/my with task completion counts per course)

## 6. Frontend: AI Admin

- [ ] 6.1 Create `frontend/src/views/admin/AIUsage.vue` (usage stats dashboard with filters)
- [ ] 6.2 Create `frontend/src/views/admin/AIFeedback.vue` (feedback list with ratings and comments)
- [ ] 6.3 Create `frontend/src/views/admin/AIConfig.vue` (model selector, budget inputs per role, API key status indicator)
- [ ] 6.4 Add AI admin routes to router

## 7. Integration & Verification

- [ ] 7.1 Run full test suite and verify all existing tests still pass
- [ ] 7.2 Extend seed_demo.py: create 2 courses linked to existing tasks, insert sample ai_usage_logs (47 rows with realistic dates, costs, statuses), insert sample ai_feedback (92% positive)
- [ ] 7.3 Manual verification: create course, create task with course, view course detail, archive course, verify tasks hidden from student
- [ ] 7.4 Manual verification: trigger test AI call from admin, verify usage log appears, submit feedback, verify in admin dashboard
- [ ] 7.5 Manual verification: change AI model via admin config page, verify next call uses new model
- [ ] 7.6 Run `openspec verify` against this change
