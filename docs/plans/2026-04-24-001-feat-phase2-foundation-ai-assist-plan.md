---
title: Phase 2 Execution Plan: Foundation + AI Assist
type: feat
status: active
date: 2026-04-24
origin: openspec/changes/add-digital-training-platform-phase2-foundation-and-ai-assist/
---

# Phase 2 Execution Plan: Foundation + AI Assist

## Overview

Phase 2 completes two missing foundation capabilities (course management, statistics dashboard) and introduces AI-powered assistance for teachers and students with governance infrastructure. Split into 6 reviewable, mergeable PRs in dependency order.

## Problem Frame

Phase 1 shipped 7 capabilities with 106 tests. Two gaps remain: course management (no way to organize tasks under courses) and statistics (no visibility into platform health). Meanwhile, teachers and students do all work manually. AI assistance can reduce task design time, improve student understanding, and accelerate summary writing. But AI features need governance: budget controls, usage logging, error handling, and permission boundaries.

## Requirements Trace

- R1. Course CRUD with semester, teacher ownership, archive lifecycle, student visibility via task-class join
- R2. Tasks can be optionally linked to courses (backward compatible)
- R3. AI service layer with provider abstraction, per-user daily budget, usage logging, cost tracking
- R4. AI feedback collection (thumbs up/down + comment) linked to usage logs
- R5. Admin AI config management (model, budgets, API key status, prompt templates)
- R6. Teacher can generate task descriptions with AI, scoped to course context
- R7. Student Q&A assistant bounded to enrolled course/task context only
- R8. Student training summary generation from submission history
- R9. Role-scoped statistics dashboard (admin: all, teacher: own classes)
- R10. Student course card home view with progress data
- R11. Prompt templates runtime-editable via admin API
- R12. No cross-role data leaks in AI responses

## Scope Boundaries

- No automatic grading
- No complex agent orchestration, multi-step chains, or conversation memory
- No vector database or embedding infrastructure
- No cross-course global knowledge base
- No voice/image/video multimodal
- No complex BI, custom analytics, drill-down, or advanced export
- No academic management (scheduling, credits, attendance, course selection)
- No model training or fine-tuning

## PR Dependency Graph

```
PR1: Course Management ──┐
                         ├──> PR3: Teacher Task Description ──┐
PR2: AI Infrastructure ──┘                                     │
                         ├──> PR4: Student Q&A ────────────────┤
                         │                                      ├──> PR6: Statistics & Acceptance
                         └──> PR5: Student Summary ────────────┘
```

PR1 and PR2 are independent and could run in parallel, but sequential is safer. PR3, PR4, PR5 depend on both PR1 and PR2. PR4 and PR5 are independent of each other. PR6 is independent of AI but most useful after all features exist, and serves as the final acceptance gate.

---

## PR1: Course Management

**Goal:** Ship course CRUD, task-course linking, student course cards. Foundation for AI context boundaries.

**Requirements:** R1, R2, R10

**Dependencies:** None. Builds on existing task/class/user models.

### Modules / Files

**Backend:**
- Create: `backend/app/models/course.py`
- Create: `backend/app/schemas/course.py`
- Create: `backend/app/routers/courses.py`
- Create: `backend/alembic/versions/XXXX_add_courses_and_task_course_id.py`
- Modify: `backend/app/models/__init__.py` (register Course)
- Modify: `backend/app/models/task.py` (add nullable course_id column)
- Modify: `backend/app/routers/tasks.py` (add course_id to create/update, add course filter, exclude archived course tasks from student list)
- Modify: `backend/app/main.py` (include courses router)
- Create: `backend/tests/test_courses.py`
- Create: `backend/tests/test_courses_extended.py`

**Frontend:**
- Create: `frontend/src/views/teacher/CourseList.vue`
- Create: `frontend/src/views/teacher/CourseDetail.vue`
- Create: `frontend/src/views/teacher/CourseCreate.vue`
- Create: `frontend/src/views/admin/CourseList.vue`
- Create: `frontend/src/views/student/CourseList.vue`
- Modify: `frontend/src/views/teacher/TaskCreate.vue` (add course selector)
- Modify: `frontend/src/views/teacher/TaskEdit.vue` (add course selector)
- Modify: `frontend/src/router/index.js` (add course routes)
- Modify: `frontend/src/layouts/MainLayout.vue` (add sidebar entries)

### Risk Points

| Risk | Mitigation |
|------|------------|
| Nullable course_id FK migration on large tasks table | MySQL ALTER TABLE on nullable FK is non-blocking. Existing rows get NULL. |
| Student course visibility via task-class join may be slow | Add index on `tasks.course_id`. Join is bounded by student's single class. |
| Archived course task filtering adds JOIN to student task list | LEFT JOIN with WHERE filter. Covered by course_id index. |
| Duplicate course name in same semester | Unique constraint on (name, semester, teacher_id). Tested. |

### Test Strategy

Follow existing test patterns: `conftest.py` fixtures, `helpers.py` utilities, `@pytest.mark.asyncio(loop_scope="session")`.

**Backend tests (`test_courses.py` + `test_courses_extended.py`):**
- Happy path: create course with all fields, edit own course, archive course, list as teacher/student/admin, view detail with tasks
- Permission: student creates course -> 403, teacher edits other's course -> 403, create task with unowned course -> 403
- Edge cases: duplicate name in same semester -> 409, no delete endpoint -> 405, archived course tasks hidden from student list, student with no courses gets empty list
- Task-course linking: create task with course_id, filter tasks by course, task without course still works, course_id selector only shows own courses

**Frontend:** Manual verification.

### Demo / Verification

1. Login as teacher, create a course "Python程序设计" with semester "2026-2027-1"
2. Create a task under that course, verify course appears in task detail
3. Login as student, verify course card shows on home page with task count and deadline
4. Archive the course, verify student can no longer see it or its tasks
5. Login as admin, verify course list shows all courses with filters
6. Run `cd backend && python -m pytest tests/ -v` -- all tests pass including new ones

### Rollback

Revert PR. The `course_id` column on tasks is nullable; existing functionality is unaffected. Courses table can be dropped without data loss (no data existed before).

---

## PR2: AI Infrastructure & Safety Boundaries

**Goal:** Ship AIService with provider abstraction, daily token budgets, usage logging, cost tracking, feedback collection, admin config/test endpoints, and prompt template management. No user-facing AI features yet.

**Requirements:** R3, R4, R5, R11

**Dependencies:** None (independent of PR1). Can run in parallel if desired.

### Modules / Files

**Backend:**
- Create: `backend/app/services/ai.py` (AIResponse, AIProvider protocol, OpenAIProvider, AIService singleton)
- Create: `backend/app/services/prompts.py` (PromptService: get_template, fill_template, validate_variables)
- Create: `backend/app/models/ai_usage_log.py`
- Create: `backend/app/models/ai_feedback.py`
- Create: `backend/app/models/ai_config.py`
- Create: `backend/app/models/prompt_template.py`
- Create: `backend/app/schemas/ai.py`
- Create: `backend/app/schemas/prompt.py`
- Create: `backend/app/routers/ai.py` (feedback, usage, stats, test, config endpoints)
- Create: `backend/app/routers/prompts.py` (list, update template endpoints)
- Create: `backend/alembic/versions/XXXX_add_ai_tables.py`
- Create: `backend/alembic/versions/XXXX_add_prompt_templates.py`
- Modify: `backend/app/models/__init__.py` (register 4 new models)
- Modify: `backend/app/config.py` (add AI_API_KEY, AI_MODEL, AI_BASE_URL env vars)
- Modify: `backend/app/main.py` (include ai, prompts routers)
- Modify: `backend/requirements.txt` (add `openai`)
- Create: `backend/tests/test_ai_service.py`
- Create: `backend/tests/test_ai_endpoints.py`
- Create: `backend/tests/test_ai_feedback.py`
- Create: `backend/tests/test_ai_stats.py`
- Create: `backend/tests/test_prompts.py`
- Modify: `backend/scripts/seed_demo.py` (add ai_config, prompt_template seed data, sample usage logs)

**Frontend:**
- Create: `frontend/src/views/admin/AIConfig.vue`
- Create: `frontend/src/views/admin/AIUsage.vue`
- Create: `frontend/src/views/admin/AIFeedback.vue`
- Create: `frontend/src/views/admin/PromptTemplates.vue`
- Modify: `frontend/src/router/index.js` (add AI admin routes)
- Modify: `frontend/src/layouts/MainLayout.vue` (add AI management sidebar)

### Risk Points

| Risk | Mitigation |
|------|------------|
| OpenAI SDK version compatibility | Pin `openai>=1.0.0` in requirements.txt. AsyncOpenAI available since 1.0. |
| TOCTOU race in budget check | Accepted for single-server low concurrency. Documented in design. |
| AI_API_KEY not set in development | Env var has no default. Admin config shows is_configured=false. Test endpoint returns 503. |
| get_db() commit/rollback path mismatch | AIService receives db session from router (via parameter, not Depends). Router handles commit/rollback. Service only does queries and flushes. (See institutional learning: FAIL-002 root cause) |
| Prompt template injection | Admin-only editing. Variables validated against declared list. User content wrapped in XML tags. |
| Cost calculation accuracy | Token counts from provider response metadata. Per-token rates from ai_config. Stored as integer microdollars. |

### Test Strategy

Use MockProvider that returns fixed responses. No real API key needed for test suite.

**AIService unit tests (`test_ai_service.py`):**
- Budget check: within budget passes, over budget returns 429, first call of day (COALESCE) returns 0 and passes
- Usage logging: successful call logged with all fields, failed call logged with status=error and zero tokens, cost_microdollars calculation correct
- Config read: reads from ai_config table on each call, not cached
- Error handling: provider exception caught, logged as error, raises 502

**AI endpoint tests (`test_ai_endpoints.py`, `test_ai_feedback.py`, `test_ai_stats.py`):**
- Feedback: submit positive, submit negative with comment, duplicate -> 409, cross-user -> 403
- Usage query: admin sees all, date filters work, user budget status returned
- Stats: aggregate counts, group_by=user, feedback summary, non-admin -> 403
- Test endpoint: triggers AI call, verifies log created, unconfigured returns 503
- Config: read current config, update model, next test call uses new model, API key status

**Prompt tests (`test_prompts.py`):**
- List templates, update template text, invalid variables -> 400, immutable name -> 400, non-admin -> 403

### Demo / Verification

1. Set `AI_API_KEY` in `.env` (or skip for non-AI demo)
2. Login as admin, navigate to AI Config page
3. Verify model, budgets, API key status displayed
4. Click "测试调用" button, verify response and usage log appears in AI Usage page
5. Submit feedback on the test call, verify in AI Feedback page
6. Navigate to Prompt Templates, edit the "task_description" template
7. Run `cd backend && python -m pytest tests/ -v` -- all tests pass

### Rollback

Revert PR. New tables (ai_usage_logs, ai_feedback, ai_config, prompt_templates) can be dropped. No existing functionality affected. AIService is only called from new endpoints.

---

## PR3: Teacher AI Task Description Generation

**Goal:** Teachers can generate task description drafts with AI assistance, scoped to course context. Supports regeneration. Human must confirm before saving. All calls logged with feedback collection.

**Requirements:** R6

**Dependencies:** PR1 (course context for AI), PR2 (AIService + prompt templates)

### Modules / Files

**Backend:**
- Create: `backend/app/schemas/ai_teacher.py`
- Create: `backend/app/routers/ai_teacher.py` (POST /api/ai/teacher/task-description)
- Create: `backend/tests/test_ai_teacher.py`
- Modify: `backend/app/main.py` (include ai_teacher router)

**Frontend:**
- Modify: `frontend/src/views/teacher/TaskCreate.vue` (add "AI 生成" button, preview dialog, "重新生成" button, "应用到描述" confirmation button)
- Modify: `frontend/src/views/teacher/TaskEdit.vue` (add same AI generation capability for existing tasks)

### Risk Points

| Risk | Mitigation |
|------|------------|
| AI generates low-quality descriptions | Default prompt template tuned for Chinese education context. Admin can edit template. Teacher can regenerate. |
| Teacher uses AI for courses they don't own | Permission check: course.teacher_id == current_user.id. Returns 403. |
| AI call slow (2-5 seconds) | Show loading spinner. No streaming in this phase. |
| Budget exceeded during generation | AIService returns 429 before calling provider. Frontend shows warning. |
| Teacher accidentally saves raw AI output | "应用到描述" button requires explicit click. Teacher sees full preview before confirming. Description field is editable after application. |
| Regeneration costs accumulate | Each regeneration is logged as a separate ai_usage_logs entry. Teacher sees token usage in the dialog. Budget check runs before each call. |

### Test Strategy

**Backend tests (`test_ai_teacher.py`):**
- Happy path: generate description for own course with topic, verify usage logged with endpoint="task_description"
- Regeneration: same endpoint called multiple times with same params, each logged separately
- Permission: unowned course -> 403, student role -> 403
- Budget: exceeded -> 429
- Edge: non-existent course -> 404, empty topic -> 422 validation
- Context assembly: verify course_name and topic are in the prompt sent to MockProvider
- No auto-save: verify endpoint only returns generated text, does not modify any task record

**Frontend:** Manual verification.

### Demo / Verification

1. Login as teacher, navigate to task creation page
2. Select a course, enter topic "网络协议分析"
3. Click "AI 生成" button, verify loading spinner appears
4. Verify generated text appears in preview dialog with structured sections (目标, 步骤, 评分标准)
5. Click "重新生成", verify new text generated (different from first)
6. Click "应用到描述", verify description field populated but NOT auto-saved
7. Edit the description, then save the task normally
8. Navigate to task edit page for an existing task, verify AI generation works there too
9. Run `cd backend && python -m pytest tests/ -v`

### Rollback

Revert PR. The "AI 生成" button disappears from task creation/edit. Tasks can still be created and edited manually.

---

## PR4: Student Q&A Assistant

**Goal:** Students can ask questions about their assigned tasks with AI assistance. Context is strictly bounded to enrolled course + assigned task data. AI refuses when context is insufficient. No cross-role data leaks.

**Requirements:** R7, R12

**Dependencies:** PR1 (course context), PR2 (AIService + prompt templates)

### Modules / Files

**Backend:**
- Create: `backend/app/schemas/ai_student.py` (StudentQAIn, StudentQAOut)
- Create: `backend/app/routers/ai_student.py` (POST /api/ai/student/qa)
- Create: `backend/tests/test_ai_student_qa.py`
- Modify: `backend/app/main.py` (include ai_student router)

**Frontend:**
- Create: `frontend/src/views/student/TaskQA.vue` (chat-like interface for asking questions about a task)
- Modify: `frontend/src/views/student/TaskDetail.vue` (add "AI 问答" button)
- Modify: `frontend/src/router/index.js` (add /student/tasks/:id/qa route)
- Modify: `frontend/src/layouts/MainLayout.vue` (add "AI 问答" sidebar entry for student)

### Risk Points

| Risk | Mitigation |
|------|------------|
| AI leaks other students' data | Context assembly enforces student_id = current_user.id. System prompt instructs model to refuse questions about other students' work. |
| AI hallucinates information | System prompt instructs model to say "根据任务要求，我没有找到相关信息" when context is insufficient. |
| Q&A used for cheating | Context only includes task requirements, not answer keys or grading details. Teacher can review Q&A logs in admin dashboard. |
| Student accesses unassigned task | Permission check: task.class_id matches student's primary_class_id. Returns 403. |
| Context boundary not enforced | Test explicitly verifies MockProvider receives ONLY task title, description, requirements, and course name — no other students' data, no other courses. |

### Test Strategy

**Backend tests (`test_ai_student_qa.py`):**
- Happy path: ask question about assigned task, verify context includes task + course info, usage logged with endpoint="student_qa"
- Permission: unassigned task -> 403, teacher role -> 403
- Budget: exceeded -> 429 with message "今日 AI 调用额度已用完，请明天再试"
- Context boundary: verify MockProvider receives only student's own context (task title, description, requirements, course name), not other students' submissions or data from other courses
- Refuse behavior: system prompt includes instruction to say "根据任务要求，我没有找到相关信息" when context insufficient
- Edge: non-existent task -> 404, empty question -> 422 validation

**Frontend:** Manual verification.

### Demo / Verification

1. Login as student, navigate to a task detail page
2. Click "AI 问答" button, type "评分标准是什么？"
3. Verify AI response references task requirements from context
4. Ask "其他同学怎么做的？", verify AI refuses to discuss other students
5. Ask an irrelevant question, verify AI says it cannot find relevant information
6. Login as admin, verify Q&A calls appear in AI Usage dashboard with endpoint="student_qa"
7. Run `cd backend && python -m pytest tests/ -v`

### Rollback

Revert PR. Q&A page and button disappear. Students can still view tasks and submissions normally.

---

## PR5: Student Training Summary Generation

**Goal:** Students can generate training summary drafts based on their own submission history for a specific course. Supports multiple generations. Student can edit before saving/submitting.

**Requirements:** R8

**Dependencies:** PR1 (course + submission history), PR2 (AIService + prompt templates). PR4 must be merged first for shared ai_student router context.

### Modules / Files

**Backend:**
- Modify: `backend/app/schemas/ai_student.py` (add SummaryIn, SummaryOut)
- Modify: `backend/app/routers/ai_student.py` (add POST /api/ai/student/summary)
- Create: `backend/tests/test_ai_student_summary.py`

**Frontend:**
- Create: `frontend/src/views/student/SummaryGenerator.vue` (course selector, generate button, preview textarea with edit capability)
- Modify: `frontend/src/router/index.js` (add /student/summary route)
- Modify: `frontend/src/layouts/MainLayout.vue` (add "生成实训总结" sidebar entry)

### Risk Points

| Risk | Mitigation |
|------|------------|
| Student generates summary with no submissions | Returns 400 "该课程暂无提交记录，无法生成总结" |
| Student generates summary for unenrolled course | Permission check via task-class join. Returns 403. |
| Multiple generations accumulate costs | Each generation is logged separately. Budget check runs before each call. Student sees token usage in UI. |
| Summary quality varies by submission count | Prompt template handles edge cases (1 submission vs many). Student can edit output. |
| Long submission histories exceed token limit | Truncate individual submission summaries. Include submission_count and condensed summaries in context. |

### Test Strategy

**Backend tests (`test_ai_student_summary.py`):**
- Happy path: generate summary for enrolled course with submissions, verify usage logged with endpoint="training_summary"
- Multiple generations: call endpoint twice, both logged separately, both return valid summaries
- Edge: no submissions -> 400, unenrolled course -> 403
- Context: verify submission history (titles, truncated descriptions) included in prompt, course info included
- Budget: exceeded -> 429
- Output structure: verify default prompt template produces sections (学习概述, 主要收获, 不足与改进)
- Targeted regression: PR4 Q&A endpoint still works after adding summary endpoint (shared router)

**Frontend:** Manual verification.

### Demo / Verification

1. Login as student, navigate to "生成实训总结"
2. Select a course with submissions, click "生成总结"
3. Verify structured output (学习概述, 主要收获, 不足与改进)
4. Edit the generated text in the textarea
5. Click "重新生成", verify new text generated (different from first)
6. Select a course with no submissions, verify error message "该课程暂无提交记录"
7. Login as admin, verify summary calls appear in AI Usage dashboard
8. Verify PR4 Q&A feature still works (targeted regression)
9. Run `cd backend && python -m pytest tests/ -v`

### Rollback

Revert PR. Summary generator page disappears. Q&A feature (PR4) unaffected. Students can still view submissions normally.

---

## PR6: Statistics Dashboard & Final Acceptance

**Goal:** Ship role-scoped statistics dashboard with simple trend/distribution display. Extend seed data for full demo. Run regression testing across all Phase 2 features. Final polish and acceptance.

**Requirements:** R9

**Dependencies:** PR1 (course counts needed for meaningful statistics). Most useful after PR3-PR5 merge so dashboard reflects AI usage data too.

### Modules / Files

**Backend:**
- Create: `backend/app/schemas/stats.py`
- Create: `backend/app/routers/stats.py` (GET /api/stats/dashboard, GET /api/stats/courses)
- Create: `backend/tests/test_stats.py`
- Modify: `backend/app/main.py` (include stats router)
- Modify: `backend/scripts/seed_demo.py` (ensure all entities have realistic counts, include AI usage data)

**Frontend:**
- Create: `frontend/src/views/admin/Dashboard.vue`
- Create: `frontend/src/views/teacher/Dashboard.vue`
- Create: `frontend/src/views/admin/CourseStats.vue`
- Modify: `frontend/src/router/index.js` (add stats routes, set dashboard as default landing)
- Modify: `frontend/src/layouts/MainLayout.vue` (add dashboard sidebar entries)
- Modify: `frontend/src/stores/auth.js` (update getHomeRoute to point to dashboard)

### Statistical Scope Definitions

- **users by role**: COUNT from users WHERE is_active=true, GROUP BY role
- **classes**: COUNT from classes
- **courses active/archived**: COUNT from courses GROUP BY status
- **tasks active/archived**: COUNT from tasks GROUP BY status
- **submissions total**: COUNT from submissions
- **pending_grade**: submissions without a grade record
- **graded**: submissions with a grade record
- **average_score**: AVG(grade.score) rounded to 1 decimal. NULL if no grades.
- **ai_usage_summary**: total calls, total tokens, total cost (microdollars), calls by endpoint (from ai_usage_logs)
- **Teacher scope**: all counts filtered WHERE teacher_id = current_user.id (for classes, tasks) or WHERE task.created_by = current_user.id (for submissions, grades)

### Simple Trend / Distribution Display

- **Admin dashboard**: recent 7-day AI usage trend (daily call count bar chart using ECharts or simple CSS bars)
- **Course stats**: submission count distribution across courses (simple table + percentage bars)
- No complex BI, no drill-down, no export. Just enough for operational awareness.

### Risk Points

| Risk | Mitigation |
|------|------------|
| Statistics queries slow on large data | All queries use indexed columns (teacher_id, status, created_by). No full table scans. |
| Teacher sees other teachers' data | WHERE clause enforces teacher_id = current_user.id on all queries. |
| Average score NULL when no grades | Frontend displays "--" for null. Backend returns null explicitly. |
| Dashboard becomes default landing, breaks existing navigation | getHomeRoute updated: admin -> /admin/dashboard, teacher -> /teacher/dashboard, student -> /student/courses |

### Test Strategy

**Backend tests (`test_stats.py`):**
- Admin dashboard: returns all counts (users by role, classes, courses, tasks, submissions, pending/graded, average_score)
- Teacher dashboard: returns counts scoped to own classes/tasks only
- Empty platform: all counts 0, average_score null
- Non-admin forbidden: student GET /api/stats/dashboard -> 403
- Course breakdown: per-course stats with correct counts, teacher sees own courses only
- Statistical accuracy: create known entities, verify counts match

**Regression testing:**
- Full Phase 1 regression: all 106 existing tests still pass
- Phase 2 cross-feature: course CRUD + task linking, AI teacher + student Q&A + summary, admin config + prompt editing all work together
- Seed data integrity: seed_demo.py produces consistent, realistic data

**Frontend:** Manual verification.

### Demo / Verification

1. Run `python backend/scripts/seed_demo.py` to populate realistic data
2. Login as admin, verify dashboard shows: user counts, class/course/task/submission counts, pending grades, average score, AI usage trend
3. Navigate to course stats, verify per-course breakdown with submission distribution
4. Login as teacher, verify dashboard shows only own data
5. Login as student, verify course cards show on home page (not dashboard)
6. Run `cd backend && python -m pytest tests/ -v` -- all tests pass (including Phase 1 regression)
7. Run `cd frontend && npx vite build` -- build succeeds
8. Full smoke test: create course -> create task with course -> archive course -> generate AI description -> ask student Q&A -> generate summary -> view stats -> verify counts
9. Verify all roles land on correct default pages after login

### Rollback

Revert PR. Dashboard pages disappear. Landing pages revert to previous routes. No data changes.

---

## Task-to-PR Mapping

Maps `openspec/changes/.../tasks.md` groups to PRs for execution tracking.

| tasks.md Group | PR | Notes |
|---|---|---|
| 1. Database Schema Migrations | PR1 (1.1-1.2), PR2 (1.3-1.6), PR6 (1.7 final verify) | Split by domain |
| 2. Course Management Backend | PR1 | All course CRUD + task linking |
| 3. AI Service Layer | PR2 | AIService, models, config |
| 4. AI Governance Endpoints | PR2 | Admin AI endpoints |
| 5. Prompt Management Endpoints | PR2 | Template CRUD |
| 6. Teacher AI Endpoints | PR3 | Task description generation |
| 7. Student AI Endpoints (Q&A only) | PR4 | Tasks 7.1-7.3, 7.6 |
| 7. Student AI Endpoints (Summary) | PR5 | Tasks 7.4-7.5, 7.7 |
| 8. Statistics Backend | PR6 | Dashboard + course stats |
| 9. Frontend: Course Management | PR1 | Course views + routes |
| 10. Frontend: Statistics Dashboard | PR6 | Dashboard views |
| 11. Frontend: AI Admin | PR2 | Config, usage, feedback, prompts pages |
| 12. Frontend: Teacher AI | PR3 | AI generate button + dialog |
| 13. Frontend: Student AI (Q&A) | PR4 | TaskQA.vue + route |
| 13. Frontend: Student AI (Summary) | PR5 | SummaryGenerator.vue + route |
| 14. Seed Data and Integration | PR1 (14.1 courses), PR2 (14.1 AI seed), PR6 (14.2-14.8 final) | Incremental |

---

## System-Wide Impact

- **Interaction graph:** New routers (courses, ai, ai_teacher, ai_student, prompts, stats) across PR1-PR6 all follow existing pattern: `Depends(get_db)`, `Depends(require_role)`, inline business logic. No middleware, no callbacks, no observers.
- **Error propagation:** AIService errors return 502 to users (generic message). Budget errors return 429. Permission errors return 403. All errors are logged to ai_usage_logs (AI calls) or returned as HTTPException (non-AI).
- **State lifecycle risks:** Courses use archive-only lifecycle (never deleted). Tasks with archived courses are hidden from students but not deleted. AI config changes take effect on next call (no restart). Prompt template changes take effect on next call.
- **API surface parity:** All new endpoints follow existing patterns: `/api/{resource}`, JWT Bearer auth, role-based access, Chinese error messages, paginated list responses.
- **Integration coverage:** AI call lifecycle (budget check -> provider call -> usage logging -> response) tested end-to-end via MockProvider in PR2-PR5. Context boundary enforcement tested by verifying MockProvider input in PR4 and PR5 separately.
- **Unchanged invariants:** Existing auth, user management, class management, task CRUD, submissions, grading, and file storage are not modified. Task model gains nullable FK (additive only). No existing API contracts change.

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OpenAI API key unavailable in dev/test | High | Low | MockProvider for tests. Admin config shows is_configured=false. Non-AI features work without key. |
| get_db() rollback loses AI usage log | Medium | Medium | AIService._log_usage() uses db.flush() within the router's session. If the router raises HTTPException, the session rolls back and the log is lost. For error cases, the router should catch the AIService error and return JSONResponse (not raise) if logging the error matters. (See institutional learning.) |
| TOCTOU budget race under concurrency | Low | Low | Accepted for single-server. Max overage = N-1 concurrent calls. |
| Statistics queries degrade at scale | Low | Low | All indexed. Revisit if > 100K submissions. |
| Prompt template breaks after admin edit | Medium | Medium | Template validation checks variables match declared list. Admin can revert via PUT. |

## Open Questions

### Resolved During Planning

- **PR ordering:** Expert's 6-PR split adopted. Q&A (PR4) and Summary (PR5) are separate because: (1) different context boundaries (task-level vs course-level), (2) each is a self-contained reviewable increment, (3) summary depends on Q&A's shared router infrastructure. Statistics (PR6) serves as final acceptance gate with regression testing.
- **Statistics PR position:** Put last (PR6). Most useful after all data exists. Includes simple trend/distribution display and full regression testing across Phase 2.
- **PR1 and PR2 parallelism:** They're independent. If the team has capacity, they could run in parallel. Plan assumes sequential for safety.
- **Human confirmation pattern:** PR3 requires explicit "应用到描述" click. PR5 allows editing before save. No AI output is auto-saved without human review.

### Deferred to Implementation

- **Exact prompt template text:** Default templates will be tuned during implementation. The schema and management endpoints are fixed.
- **Token pricing updates:** ai_config stores per-token rates. These need manual updating when OpenAI changes pricing. Not automatable in this phase.
- **Streaming responses:** Not in scope. AI responses appear after full generation completes. Streaming requires SSE or WebSocket infrastructure, deferred.

## Sources & References

- **Origin document:** [openspec/changes/add-digital-training-platform-phase2-foundation-and-ai-assist/](openspec/changes/add-digital-training-platform-phase2-foundation-and-ai-assist/proposal.md)
- Existing patterns: `backend/app/routers/tasks.py` (router template), `backend/app/models/task.py` (model template), `backend/tests/test_tasks.py` (test template)
- Institutional learning: `docs/solutions/developer-experience/full-mvp-development-cycle-patterns-and-learnings-2026-04-23.md`
- Related plans: `docs/superpowers/plans/2026-04-22-pr2-core-api-loop.md`, `docs/superpowers/plans/2026-04-22-pr4-full-features-deployment.md`
