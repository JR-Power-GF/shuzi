## Why

Phase 1 delivered a fully manual training platform. Phase 2 adds AI capabilities (task description generation, student Q&A, training summary generation), but none of these can ship safely without a governance layer that logs every AI call, enforces per-user rate limits, collects feedback, and provides cost visibility. Simultaneously, course management was explicitly deferred from V1 and is a prerequisite for organizing AI context around course-level boundaries. This sprint builds the rails before the train.

## What Changes

- Add `courses` module: CRUD API for course management, teacher can create/organize courses, tasks belong to courses, students view course-task hierarchy
- Add `ai_usage_logs` table: every LLM call logged with user, endpoint, model, tokens, estimated cost, latency, and status
- Add AI service layer: provider-abstracted LLM client (start with one provider, interface supports swapping), configuration for model selection and parameters
- Add per-user per-role daily token budget enforcement: API returns 429 when budget exceeded, configurable per role (admin/teacher/student)
- Add AI feedback endpoint: users can rate AI outputs (thumbs up/down + optional comment), feedback stored and queryable by admin
- Add admin AI usage dashboard endpoint: aggregated stats by user, endpoint, date range
- Migration: add `course_id` (nullable FK) to `tasks` table for backward compatibility with existing data

## Capabilities

### New Capabilities
- `ai-governance`: AI call logging, rate limiting, cost tracking, feedback collection, and admin visibility. The governance layer that all AI features depend on.
- `course-management`: Course CRUD, teacher-course assignment, course-task hierarchy, student course enrollment and browsing.

### Modified Capabilities
- `task-management`: Tasks gain an optional `course_id` foreign key. Existing endpoints continue to work without a course. New filter: list tasks by course.

## Impact

- **Database**: 2 new tables (`courses`, `ai_usage_logs`), 1 migration on `tasks` (add nullable `course_id`)
- **Backend**: New routers (`courses.py`, `ai.py`), new service layer (`services/ai.py`), new models (`course.py`, `ai_usage_log.py`)
- **Frontend**: New views for course management (admin/teacher list, create, detail), AI usage admin view
- **Dependencies**: One LLM provider SDK added to backend (e.g. `openai` or `anthropic` package)
- **Config**: New env vars for LLM API key, model name, daily token budgets per role
- **API**: 2 new route groups (`/api/courses`, `/api/ai`), 1 modified route group (`/api/tasks` with optional course filter)
