## Context

Phase 1 delivered a manual training platform (FastAPI + Vue 3 + MySQL 8) with 7 capabilities: auth, user management, class management, task management, submissions, grading, and file storage. 106 tests pass. The platform runs on a single server (systemd + Nginx).

Phase 2 adds two categories of work: (A) completing two missing foundation capabilities (course management, basic statistics), and (B) introducing AI-powered assistance for teachers and students with proper governance infrastructure. The AI features are introduced incrementally across three sprints, but this change captures the full scope.

**Current constraints:**
- Python 3.11+, FastAPI async, SQLAlchemy 2.0 async, MySQL 8
- Vue 3 + Element Plus + Vite frontend
- Single-server deployment (systemd + Nginx)
- No LLM provider SDK or API key exists in the codebase yet
- Existing `services/` directory with `file_cleanup.py` establishes the service layer pattern
- `dependencies/auth.py` provides `get_current_user` and `require_role` for all RBAC

## Goals / Non-Goals

**Goals:**
- Ship course management that organizes tasks under courses with semester context
- Ship a minimal statistics dashboard scoped by role (admin sees all, teacher sees own)
- Ship an AI provider-abstracted service layer that all AI features call into
- Every LLM call is logged, costed, and rate-limited before it reaches the provider
- Teachers can generate task descriptions with AI assistance scoped to course context
- Students can ask questions about their assigned tasks (context bounded to their courses)
- Students can generate draft training summaries from their submission history
- Prompt templates are runtime-editable via admin API
- Admin has visibility into AI usage, costs, and quality feedback
- Users can rate AI outputs (thumbs up/down + optional comment)

**Non-Goals:**
- Automatic grading or AI-powered scoring (future consideration)
- Teacher evaluation or decision-making automation
- Complex agent orchestration, multi-step chains, or conversation memory
- Cross-course or cross-class global knowledge base
- Voice, image, or video multimodal AI
- Model training, fine-tuning platform, or on-premise model hosting
- University-wide AI middleware/platform
- Unauthorized cross-role data access
- Recommendation systems or adaptive learning paths
- Complex academic management (scheduling, credits, attendance, course selection)
- Complex BI reporting, custom analytics, drill-down, or advanced export
- Vector database or embedding infrastructure (revisit if/when semantic search is needed)

## Decisions

### D1: LLM provider: OpenAI SDK behind AIProvider protocol

**Choice:** Use `openai` Python SDK as the initial provider. Wrap it behind a `Protocol` class (`AIProvider`) with a single `generate()` method.

**Why:** OpenAI API is the most widely supported baseline. The protocol abstraction costs nothing in complexity (one class with `generate()` returning a typed response) and avoids lock-in. Do not use LangChain; the indirection is not justified for calling one API with structured prompts.

**Alternative considered:** Anthropic SDK first. Either works. The interface makes it swappable. OpenAI has broader community familiarity for a Chinese education platform context.

### D2: Rate limiting: in-database counter, not Redis

**Choice:** Track daily token usage in `ai_usage_logs` table with aggregation query. Check budget at the start of each AI call. No Redis dependency.

**Why:** Single-server deployment, low concurrency (10-50 AI calls/day). A `SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0) FROM ai_usage_logs WHERE user_id = ? AND created_at >= CURDATE()` query is fast enough. Adding Redis for rate limiting alone is over-engineering.

**Alternative considered:** Redis with sliding window. Better for high concurrency, but adds a new infra dependency. Revisit if/when the platform scales beyond single-server.

**TOCTOU note:** Under concurrent requests from the same user, the daily budget may be exceeded by up to N-1 calls where N is the number of simultaneous in-flight requests. Acceptable for low concurrency.

### D3: Course model: flat table with semester, teacher ownership, no org hierarchy

**Choice:** `Course` table with `id, name, description, semester, teacher_id, status(active/archived), created_at, updated_at`. Tasks get nullable `course_id` FK. No org hierarchy (college/major/class) in this phase.

**Why:** Matches the existing `Class` model pattern. Teacher creates course, assigns tasks to it. Nullable FK preserves backward compatibility. Student course visibility derived through task-class join (no enrollment table needed). Org hierarchy explicitly deferred.

**Archive-only lifecycle:** Courses are never deleted, only archived. Archived courses and their tasks are hidden from students but visible to teachers and admins. This matches how academic semesters actually work.

### D4: AIService as module-level singleton, reads config from DB on every call

**Choice:** `backend/app/services/ai.py` contains the `AIService` class. Module-level singleton instantiated on import. Each `generate()` call reads model and budget config from `ai_config` table (not cached). Provider client initialized once, model name read per-call.

**Why:** Single responsibility. Router validates input, service handles LLM lifecycle. Config reads from DB so admin changes take effect instantly without restart. Per-call DB read is negligible overhead (~1ms) for 10-50 calls/day.

### D5: AI feedback linked to usage log, not to feature-specific entities

**Choice:** `ai_feedback` table with `id, ai_usage_log_id, user_id, rating(1/-1), comment, created_at`. Unique constraint on `(ai_usage_log_id, user_id)`.

**Why:** Feedback must be traceable to the specific model, prompt, and context that produced the output. Linking to the usage log gives full context for quality analysis across all AI features (task generation, Q&A, summaries) without feature-specific feedback tables.

### D6: Statistics dashboard: pre-computed aggregation queries, no materialized views

**Choice:** Statistics endpoints run real-time aggregation queries against existing tables. No materialized views, no cron jobs, no separate analytics database. Queries are simple COUNT/GROUP BY on tables with proper indexes.

**Why:** The data volume is small (hundreds of tasks, thousands of submissions). MySQL handles these aggregations in milliseconds. Adding materialized views or a separate analytics pipeline is BI territory, which is a non-goal.

**Statistical scope:**
- Admin: all data across the platform
- Teacher: data where teacher_id matches own ID (own classes, own tasks, submissions to own tasks)
- Student: no dashboard access (their view is the course card home page with progress)

### D7: Context assembly: relational data joins, no vector database

**Choice:** AI context is assembled by querying related entities via foreign keys. For task description generation: Course + Task requirements. For Q&A: Course + Task + Submission + past Q&A. For summary: Course + all student submissions for that course.

**Why:** Every AI feature is scoped to a single course/task context. The context window is small (~1000-2000 tokens). Direct FK joins are sufficient. No semantic search needed because we always know exactly which entities to include (the course, the task, the student's own submissions).

**Alternative considered:** Vector DB for "find similar" features. Deferred. If future features need semantic search across uploaded materials, add Qdrant/Weaviate then. The `AIProvider.generate(prompt, user_id, context)` signature supports this via the `context` dict.

### D8: Prompt templates stored in database, editable via admin API

**Choice:** `prompt_templates` table with `id, name(unique), template_text, variables(JSON), description, updated_at, updated_by`. Admin can view and edit templates. AIService reads templates from DB when composing prompts.

**Why:** Prompt tuning is the primary lever for AI output quality. Making templates runtime-editable means teachers and admins can iterate on prompt quality without code deploys. Variables are declared as JSON array for validation.

### D9: Student Q&A context boundary: course + task + authorized materials only

**Choice:** Student Q&A context includes: current task requirements, task description, student's own submissions for that task, and any materials the teacher explicitly attached to the task. It does NOT include other students' submissions, other tasks, or any data outside the student's enrolled courses.

**Why:** Privacy and academic integrity. Students should not see other students' work through AI responses. The context boundary is enforced by the context assembly function, which queries with `student_id = current_user.id` and `class_id IN (student's enrolled classes)`.

### D10: Hallucination mitigation: structured prompts + source attribution

**Choice:** AI responses include a "sources" section listing which entities informed the answer. System prompts instruct the model to say "根据任务要求，我没有找到相关信息" when context doesn't contain the answer, rather than inventing information.

**Why:** In an educational context, hallucinated information is actively harmful. A student who receives wrong technical information from the AI has a worse outcome than a student who receives "I don't know." Source attribution makes hallucinations detectable.

## Risks / Trade-offs

**[In-database rate limiting under concurrent load]** → For single-server MySQL this is fine. If the platform scales, migrate to Redis-based rate limiting. The `AIService.check_budget()` method is the single point to change. TOCTOU race accepted for low concurrency.

**[LLM provider downtime]** → `AIService.generate()` catches provider exceptions, logs them to `ai_usage_logs` with status=error, and returns HTTP 502 with generic message "AI 服务暂时不可用". Callers never see raw provider errors. Future: add retry with exponential backoff.

**[API key security]** → LLM API key stored in environment variable (`AI_API_KEY`), never in code or config files. Logged tokens in `ai_usage_logs` are metadata (counts), never prompt content. Prompt content is NOT logged to avoid data retention concerns.

**[Nullable course_id migration]** → All existing tasks have `course_id = NULL`. Task list endpoints continue to work. New tasks can optionally set course_id. Backward compatible, no data migration needed.

**[Cost estimation accuracy]** → Token counting from provider response metadata, not estimated locally. Cost calculated from token counts * model-specific per-token rates in `ai_config`. Rates need manual updating when provider pricing changes.

**[Prompt template injection]** → Admin-only template editing. Templates use `str.format()` with a whitelist of variable names defined in the `variables` JSON column. User-submitted content is wrapped in XML tags (`<user_content>...</user_content>`) to separate data from instructions.

**[Statistics query performance at scale]** → All aggregation queries hit indexed columns. If data grows beyond ~100K submissions, add query-level caching with 5-minute TTL. Not needed now.

## Migration Plan

1. Deploy schema migration: `courses` table, `ai_usage_logs` table, `ai_feedback` table, `ai_config` table, `prompt_templates` table, add `course_id` to `tasks` with index
2. Seed `ai_config` with default values (model=gpt-4o-mini, budgets by role, pricing rates)
3. Seed `prompt_templates` with default templates (task_description, student_qa, training_summary)
4. Deploy backend with new routers and services (no behavior change for existing endpoints)
5. Deploy frontend with course management, statistics, and AI views
6. Set `AI_API_KEY` environment variable on server
7. Verify with a single test AI call from admin dashboard
8. No rollback risk for existing features; new tables and nullable FK are additive only

## Open Questions

- **Which LLM model to default to?** Recommendation: `gpt-4o-mini` for cost efficiency. Can be changed via `ai_config`.
- **Daily token budgets per role?** Recommendation: admin 500K, teacher 200K, student 50K. Configurable via `ai_config`.
- **Should prompt content be logged for debugging?** Recommendation: no, for data privacy. Only metadata (token counts, model, status, latency). If debugging is needed, add an opt-in `log_prompts` config flag.
- **Q&A conversation memory?** Recommendation: no conversation memory in this phase. Each question is independent. If multi-turn is needed later, add a `ai_conversations` table with message history, scoped to a task.
