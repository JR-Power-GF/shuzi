## 1. Database Schema Migrations

- [ ] 1.1 Create `courses` table migration (id, name, description, semester, teacher_id FK to users, status enum active/archived, created_at, updated_at). Add unique constraint on (name, semester, teacher_id).
- [ ] 1.2 Create migration to add nullable `course_id` FK to `tasks` table. Add index on `tasks.course_id` for archived course filtering performance.
- [ ] 1.3 Create `ai_usage_logs` table migration (id, user_id FK, endpoint varchar, model varchar, prompt_tokens int, completion_tokens int, cost_microdollars int, latency_ms int, status enum success/error, created_at). Add composite index on (user_id, created_at) for budget check performance.
- [ ] 1.4 Create `ai_feedback` table migration (id, ai_usage_log_id FK, user_id FK, rating smallint, comment text nullable, created_at, unique constraint on ai_usage_log_id + user_id)
- [ ] 1.5 Create `ai_config` table migration (id, key varchar unique, value text, updated_at, updated_by int FK nullable) for runtime-editable AI settings (model, budgets, pricing)
- [ ] 1.6 Create `prompt_templates` table migration (id, name varchar unique, description text, template_text text, variables JSON array, updated_at, updated_by int FK nullable)
- [ ] 1.7 Run all migrations and verify existing tests still pass

## 2. Course Management Backend

- [ ] 2.1 Create `backend/app/models/course.py` with Course SQLAlchemy model (matches schema from 1.1)
- [ ] 2.2 Register Course model in `backend/app/models/__init__.py`
- [ ] 2.3 Create `backend/app/schemas/course.py` with CourseCreate, CourseUpdate, CourseOut, CourseListOut, CourseProgressOut schemas
- [ ] 2.4 Create `backend/app/routers/courses.py` with CRUD endpoints (POST create, PUT update, GET list, GET detail, POST archive)
- [ ] 2.5 Add course_id parameter to task creation in `backend/app/routers/tasks.py` (validate course.teacher_id == current_user.id)
- [ ] 2.6 Add course_id parameter to task update in `backend/app/routers/tasks.py`
- [ ] 2.7 Add course_id filter to admin task list endpoint (GET /api/tasks?course_id=5)
- [ ] 2.8 Modify student task listing (GET /api/tasks/my) to exclude tasks belonging to archived courses (LEFT JOIN courses, filter WHERE course.status != 'archived' OR course_id IS NULL)
- [ ] 2.9 Add GET /api/courses/my endpoint for student course cards with progress data (task counts: total, submitted, graded per course)
- [ ] 2.10 Write tests for course CRUD (create, edit, archive, permission checks, duplicate name 409)
- [ ] 2.11 Write tests for task-course linking (create with course, filter by course, permission on course ownership 403)
- [ ] 2.12 Write test for archived course hiding tasks from student task list
- [ ] 2.13 Write test for student course progress endpoint (counts, deadline badge, empty case)

## 3. AI Service Layer

- [ ] 3.1 Add `openai` dependency to `backend/requirements.txt`
- [ ] 3.2 Add AI config to `backend/app/config.py` (AI_API_KEY, AI_BASE_URL env vars as defaults) and create ai_config table accessor for runtime overrides
- [ ] 3.3 Create `backend/app/services/ai.py` with AIResponse dataclass, AIProvider Protocol, and OpenAIProvider implementation using AsyncOpenAI
- [ ] 3.4 Implement `AIService` class: __init__ (create provider from env config), generate(prompt, user_id, context=None, endpoint=""), check_budget(), _log_usage(), _get_config()
- [ ] 3.5 Implement `AIService.check_budget()`: query daily token usage with COALESCE(SUM, 0), compare against role budget from ai_config table, return remaining tokens
- [ ] 3.6 Implement `AIService._log_usage()`: create ai_usage_logs row with all fields including cost_microdollars calculation
- [ ] 3.7 Implement `AIService.generate()`: read config from DB, check budget, call provider, log usage, handle errors (catch provider exceptions, log as error, raise 502)
- [ ] 3.8 Create `backend/app/models/ai_usage_log.py`, `backend/app/models/ai_feedback.py`, `backend/app/models/ai_config.py`, `backend/app/models/prompt_template.py`
- [ ] 3.9 Register new models in `backend/app/models/__init__.py`
- [ ] 3.10 Create `backend/app/services/prompts.py` with PromptService: get_template(name), fill_template(name, context_dict), validate_variables()
- [ ] 3.11 Write tests for AIService with MockProvider (budget check: within/over/first-call-of-day COALESCE, logging: success/error, cost calculation, config read from DB)

## 4. AI Governance Endpoints

- [ ] 4.1 Create `backend/app/schemas/ai.py` with AIFeedbackIn, AIUsageOut, AIStatsOut, AIConfigOut, AIConfigUpdate, AITestOut schemas
- [ ] 4.2 Create `backend/app/routers/ai.py` with feedback endpoint (POST /api/ai/feedback)
- [ ] 4.3 Add admin usage query endpoint (GET /api/ai/usage with user_id, date filters)
- [ ] 4.4 Add admin stats endpoint (GET /api/ai/stats with date range, group_by parameter)
- [ ] 4.5 Add admin feedback summary endpoint (GET /api/ai/stats/feedback)
- [ ] 4.6 Add admin test endpoint (POST /api/ai/test) for triggering a single AI call to verify full stack
- [ ] 4.7 Add admin config endpoints (GET /api/ai/config, PUT /api/ai/config) for reading and updating AI model, budgets, and API key status
- [ ] 4.8 Write tests for rate limiting (budget exceeded returns 429, within budget passes, first-call-of-day with zero rows)
- [ ] 4.9 Write tests for AI usage logging (successful call logged, failed call logged, cost calculation in microdollars)
- [ ] 4.10 Write tests for feedback (submit positive/negative, duplicate rejection 409, cross-user rejection 403)
- [ ] 4.11 Write tests for admin stats endpoints (aggregate, by-user, feedback summary, non-admin forbidden 403)
- [ ] 4.12 Write test for admin test endpoint (trigger AI call end-to-end, verify log created)
- [ ] 4.13 Write test for admin config (read config, update model, verify next call uses new model, API key status indicator)

## 5. Prompt Management Endpoints

- [ ] 5.1 Create `backend/app/schemas/prompt.py` with PromptTemplateOut, PromptTemplateUpdate schemas
- [ ] 5.2 Create `backend/app/routers/prompts.py` with list templates (GET /api/prompts) and update template (PUT /api/prompts/:name) endpoints
- [ ] 5.3 Write tests for prompt management (list templates, update template, invalid variables 400, immutable name 400, non-admin 403)

## 6. Teacher AI Endpoints

- [ ] 6.1 Create `backend/app/schemas/ai_teacher.py` with TaskDescriptionIn, TaskDescriptionOut schemas
- [ ] 6.2 Create `backend/app/routers/ai_teacher.py` with POST /api/ai/teacher/task-description endpoint (validate course ownership, assemble context, call AIService with endpoint="task_description")
- [ ] 6.3 Implement task description context assembly: query Course by course_id, fill prompt_template "task_description" with course_name, course_description, topic
- [ ] 6.4 Write tests for task description generation (success, unowned course 403, budget exceeded 429, missing course 404)

## 7. Student AI Endpoints

- [ ] 7.1 Create `backend/app/schemas/ai_student.py` with StudentQAIn, StudentQAOut, SummaryIn, SummaryOut schemas
- [ ] 7.2 Create `backend/app/routers/ai_student.py` with POST /api/ai/student/qa endpoint (validate task assignment, assemble bounded context, call AIService with endpoint="student_qa")
- [ ] 7.3 Implement student Q&A context assembly: query Task + Course, verify student's class matches task.class_id, fill template with task_title, task_description, task_requirements, course_name, question
- [ ] 7.4 Create POST /api/ai/student/summary endpoint (validate enrollment, assemble submission history, call AIService with endpoint="training_summary")
- [ ] 7.5 Implement training summary context assembly: query Course + all student's Submissions for tasks in that course, fill template with course_name, submission_count, submission_summaries
- [ ] 7.6 Write tests for student Q&A (success, unassigned task 403, budget exceeded 429, context boundary verification)
- [ ] 7.7 Write tests for training summary (success with submissions, no submissions 400, unenrolled course 403)

## 8. Statistics Backend

- [ ] 8.1 Create `backend/app/schemas/stats.py` with DashboardStatsOut, CourseStatsOut schemas
- [ ] 8.2 Create `backend/app/routers/stats.py` with GET /api/stats/dashboard endpoint (role-scoped: admin sees all, teacher sees own classes)
- [ ] 8.3 Add GET /api/stats/courses endpoint for per-course breakdown (admin: all courses, teacher: own courses)
- [ ] 8.4 Write tests for statistics (admin dashboard, teacher dashboard scoped, course breakdown, empty platform, non-admin forbidden 403)

## 9. Frontend: Course Management

- [ ] 9.1 Create `frontend/src/views/teacher/CourseList.vue` (teacher's courses table, create button, archive action)
- [ ] 9.2 Create `frontend/src/views/teacher/CourseDetail.vue` (course info card + task list under course)
- [ ] 9.3 Create `frontend/src/views/teacher/CourseCreate.vue` (form: name, description, semester selector)
- [ ] 9.4 Create `frontend/src/views/admin/CourseList.vue` (all courses with filters: semester, teacher, status)
- [ ] 9.5 Create `frontend/src/views/student/CourseList.vue` (card-based home page with progress bars and deadline badges per course)
- [ ] 9.6 Add course_id selector to TaskCreate.vue and TaskEdit.vue (dropdown of teacher's own courses)
- [ ] 9.7 Add course routes to router (teacher: /teacher/courses, /teacher/courses/create, /teacher/courses/:id; admin: /admin/courses; student: /student/courses)
- [ ] 9.8 Add sidebar menu entries for course management (teacher: "课程管理", admin: "课程管理", student: "我的课程")

## 10. Frontend: Statistics Dashboard

- [ ] 10.1 Create `frontend/src/views/admin/Dashboard.vue` (admin statistics: user counts, class/course/task/submission counts, pending grades, average score)
- [ ] 10.2 Create `frontend/src/views/teacher/Dashboard.vue` (teacher statistics: own class/task/submission counts, pending grades, average score)
- [ ] 10.3 Create `frontend/src/views/admin/CourseStats.vue` (per-course breakdown table)
- [ ] 10.4 Add statistics routes to router (admin: /admin/dashboard, /admin/stats/courses; teacher: /teacher/dashboard)
- [ ] 10.5 Add dashboard sidebar entries and set as default landing page (admin lands on /admin/dashboard, teacher lands on /teacher/dashboard)

## 11. Frontend: AI Admin

- [ ] 11.1 Create `frontend/src/views/admin/AIUsage.vue` (usage stats dashboard with date range and user filters)
- [ ] 11.2 Create `frontend/src/views/admin/AIFeedback.vue` (feedback list with ratings and comments)
- [ ] 11.3 Create `frontend/src/views/admin/AIConfig.vue` (model selector, budget inputs per role, API key status indicator, test call button)
- [ ] 11.4 Create `frontend/src/views/admin/PromptTemplates.vue` (template list with inline edit capability)
- [ ] 11.5 Add AI admin routes to router (/admin/ai/usage, /admin/ai/feedback, /admin/ai/config, /admin/ai/prompts)
- [ ] 11.6 Add AI management sidebar entry under admin section

## 12. Frontend: Teacher AI

- [ ] 12.1 Add "AI 生成" button to TaskCreate.vue that calls POST /api/ai/teacher/task-description, displays generated text in a preview dialog
- [ ] 12.2 Add "应用到描述" button in the preview dialog that populates the description field
- [ ] 12.3 Add course_id auto-fill: when course is selected, pass course context to the AI generation call
- [ ] 12.4 Handle AI errors in UI (429 budget exceeded → ElMessage.warning, 502 provider error → ElMessage.error)

## 13. Frontend: Student AI

- [ ] 13.1 Create `frontend/src/views/student/TaskQA.vue` (chat-like interface for asking questions about a task, displays AI responses)
- [ ] 13.2 Create `frontend/src/views/student/SummaryGenerator.vue` (course selector, generate button, preview textarea with edit capability)
- [ ] 13.3 Add student AI routes to router (/student/tasks/:id/qa, /student/summary)
- [ ] 13.4 Add "AI 问答" button on TaskDetail.vue that navigates to Q&A page
- [ ] 13.5 Add "生成实训总结" entry in student sidebar

## 14. Seed Data and Integration

- [ ] 14.1 Extend seed_demo.py: create 2 courses linked to existing tasks, insert sample ai_usage_logs (50 rows with realistic dates, costs, statuses, varied endpoints), insert sample ai_feedback (90% positive), insert default ai_config rows, insert default prompt_template rows
- [ ] 14.2 Verify seed data loads without errors and existing tests still pass
- [ ] 14.3 Manual verification: create course, create task with course, view course detail, archive course, verify tasks hidden from student
- [ ] 14.4 Manual verification: trigger test AI call from admin, verify usage log appears, submit feedback, verify in admin dashboard
- [ ] 14.5 Manual verification: change AI model via admin config page, verify next call uses new model
- [ ] 14.6 Manual verification: teacher generates task description with AI, student asks Q&A, student generates summary
- [ ] 14.7 Manual verification: view statistics dashboard as admin and teacher, verify counts match expected values
- [ ] 14.8 Run full test suite and verify all existing tests still pass
