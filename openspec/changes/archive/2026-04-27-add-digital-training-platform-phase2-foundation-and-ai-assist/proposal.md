## Why

Phase 1 delivered a manual training platform (auth, user/class management, tasks, submissions, grading, file storage) with 106 passing tests. Two gaps remain unfilled (course management, basic statistics), and the platform lacks AI assistance for teachers and students. Teachers spend significant time writing task descriptions and reviewing submissions. Students struggle to understand task requirements and write training summaries. Without a governance layer, AI features cannot be safely introduced. This change completes the foundation and adds AI-powered assistance with proper guardrails.

## What Changes

- **Course management**: New capability for teachers to organize tasks under courses with semester context, archive expired courses, and provide students a course-centric home view.
- **Basic statistics dashboard**: New capability showing aggregate metrics (course count, task count, submission count, pending/graded counts) scoped by role. Minimal, not a BI platform.
- **AI governance infrastructure**: New capability providing a provider-abstracted AI service layer with per-user daily token budgets, usage logging, cost tracking, feedback collection, and admin visibility.
- **Teacher AI task description generation**: New capability allowing teachers to generate task descriptions with AI assistance, scoped to course context.
- **Student AI Q&A assistant**: New capability allowing students to ask questions about their assigned tasks, with context bounded to their enrolled courses and assigned tasks.
- **Student AI training summary generation**: New capability allowing students to generate draft training summaries from their submission history.
- **AI prompt/context template management**: New capability for managing prompt templates and context assembly rules used by AI features. Runtime-configurable via admin API.
- **Task-course linking**: Modify task-management to support optional course_id association and course-based filtering.

## Capabilities

### New Capabilities
- `course-management`: Course CRUD, semester organization, archive lifecycle, student course visibility via task-class join, course progress data for student home view
- `statistics-dashboard`: Role-scoped aggregate metrics for admin/teacher dashboards (course, task, submission, grade counts). Defines clear statistical scope and permissions.
- `ai-governance`: AIProvider protocol, AIService singleton, daily token budget enforcement (COALESCE), usage logging with microdollar cost tracking, feedback collection, admin usage/stats/config endpoints, provider error handling
- `ai-teacher-assist`: Teacher-facing AI features: task description generation with course context, prompt templates for task design assistance
- `ai-student-assist`: Student-facing AI features: task Q&A (bounded to enrolled course/task context), training summary draft generation from submission history
- `ai-prompt-management`: Runtime-editable prompt templates and context assembly rules. Admin can view/edit templates. AIService reads templates from DB on each call.

### Modified Capabilities
- `task-management`: Add optional course_id FK to tasks, add course_id filter to task list endpoint, exclude tasks belonging to archived courses from student task listing

## Impact

- **Database**: 5 new tables (courses, ai_usage_logs, ai_feedback, ai_config, prompt_templates), 1 modified table (tasks: add nullable course_id FK with index)
- **Backend**: 4 new routers (courses, ai, statistics, prompts), 1 new service module (services/ai.py with AIService singleton + AIProvider protocol), 5 new models, 6 new schema files. New dependency: `openai` Python SDK.
- **Frontend**: ~8 new views (teacher course CRUD, admin statistics, admin AI dashboard, admin AI config, admin prompt management, student course home, student Q&A, student summary generator), 1 modified view (TaskCreate/TaskEdit add course selector). New routes and sidebar entries.
- **API**: 7 new course endpoints, 6 new AI endpoints, 2 new statistics endpoints, 2 new prompt management endpoints, 1 modified task endpoint
- **Dependencies**: `openai` Python SDK added to requirements.txt
- **Environment**: New env vars AI_API_KEY, AI_MODEL, AI_BASE_URL (defaults, overridable via ai_config table)
- **Deployment**: Requires AI_API_KEY set in environment before AI features work. Non-AI features (courses, statistics) work without it.
