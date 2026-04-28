## Context

Phase 1 delivered a manual training platform (FastAPI + Vue 3 + MySQL 8) with 7 capabilities: auth, user management, class management, task management, submissions, grading, and file storage. The `grades` table has no `grading_type` column yet.

Phase 2 adds AI features across 3 sprints. This sprint (2A) builds the governance infrastructure and course management that all subsequent AI features depend on. No AI user-facing features ship in this sprint.

**Current constraints:**
- Python 3.11+, FastAPI async, SQLAlchemy 2.0 async, MySQL 8
- Vue 3 + Element Plus + Vite frontend
- Single-server deployment (systemd + Nginx)
- No LLM provider SDK or API key exists in the codebase

## Goals / Non-Goals

**Goals:**
- Ship a provider-abstracted AI service layer that future AI features call into
- Every LLM call is logged, costed, and rate-limited before it reaches the provider
- Course management CRUD that organizes tasks under courses
- Admin visibility into AI usage (who called what, how much it cost, success rates)
- Feedback loop: users can rate AI outputs, data is queryable

**Non-Goals:**
- AI grading, AI task description generation, student Q&A, or training summary generation (Sprint 2B/2C)
- Vector database or embeddings infrastructure
- Multi-model orchestration or prompt chaining
- Conversation memory or stateful chat
- Real-time streaming of LLM responses
- AI-powered admin automation

## Decisions

### D1: LLM provider: start with OpenAI, abstract behind interface

**Choice:** Use `openai` Python SDK as the initial provider. Wrap it behind a protocol class (`AIProvider`) so other providers (Anthropic, local models) can be added without changing callers.

**Why:** OpenAI API is the most widely supported baseline. The protocol abstraction costs nothing in complexity (one class with `generate()` and `count_tokens()` methods) and avoids lock-in. Do not use LangChain; the indirection is not justified for calling one API with structured prompts.

**Alternative considered:** Anthropic SDK first. Perfectly valid, but OpenAI has broader community familiarity for a Chinese education platform context where the team may vary. Either works, the interface makes it swappable.

### D2: Rate limiting: in-database counter, not Redis

**Choice:** Track daily token usage in `ai_usage_logs` table with aggregation query. Check budget at the start of each AI call. No Redis dependency.

**Why:** Single-server deployment, low concurrency. A `SELECT SUM(prompt_tokens + completion_tokens) FROM ai_usage_logs WHERE user_id = ? AND created_at >= TODAY()` query is fast enough. Adding Redis for rate limiting alone is over-engineering for the current deployment.

**Alternative considered:** Redis with sliding window. Better for high concurrency, but adds a new infra dependency. Revisit if/when the platform scales beyond single-server.

### D3: Course model: flat list with semester, teacher owns courses

**Choice:** `Course` table with `id, name, description, semester, teacher_id, status, created_at, updated_at`. Tasks get nullable `course_id` FK. No org hierarchy (college/major/class) in this sprint.

**Why:** Matches the existing `Class` model pattern. Teacher creates course, assigns tasks to it. Nullable FK preserves backward compatibility. Org hierarchy was explicitly deferred.

### D4: AI service as a standalone module, not mixed into routers

**Choice:** `backend/app/services/ai.py` contains the `AIService` class. Routers call `ai_service.generate()` which handles logging, rate limiting, provider call, and error handling in one place.

**Why:** Single responsibility. The router validates input and returns response. The service handles the LLM interaction lifecycle. This pattern matches how the existing auth service works. `AIService` is a module-level singleton instantiated on import, with the provider client initialized once.

### D5: AI feedback: separate table linked to usage log

**Choice:** `ai_feedback` table with `id, ai_usage_log_id, user_id, rating (1/-1), comment, created_at`. Linked to the specific AI call that generated the output.

**Why:** Feedback must be traceable to the specific model, prompt, and context that produced the output. Linking to the usage log gives full context for quality analysis.

## Risks / Trade-offs

**[In-database rate limiting under concurrent load]** → For single-server MySQL this is fine. If the platform scales, migrate to Redis-based rate limiting. The `AIService.check_budget()` method is the single point to change. Note: under concurrent requests from the same user, the daily budget may be exceeded by up to N-1 calls where N is the number of simultaneous in-flight requests (TOCTOU race between SELECT SUM and INSERT). Acceptable for Sprint 2A given low concurrency.

**[LLM provider downtime]** → `AIService.generate()` catches provider exceptions, logs them to `ai_usage_logs` with status=error, and returns a structured error to the caller. Callers never see raw provider errors. Future: add retry with exponential backoff.

**[API key security]** → LLM API key stored in environment variable (`AI_API_KEY`), never in code or config files. Logged tokens in `ai_usage_logs` are metadata (counts), never prompt content. Prompt content is NOT logged to avoid data retention concerns.

**[Nullable course_id migration]** → All existing tasks have `course_id = NULL`. Task list endpoints continue to work. New tasks can optionally set course_id. Backward compatible, no data migration needed.

**[Cost estimation accuracy]** → Token counting is done by the provider response metadata, not estimated locally. Cost is calculated from token counts × model-specific per-token rates configured in `ai_config`. Rates need manual updating when provider pricing changes.

## Migration Plan

1. Deploy schema migration: `courses` table, `ai_usage_logs` table, `ai_feedback` table, add `course_id` to `tasks`
2. Deploy backend with new routers and services (no behavior change for existing endpoints)
3. Deploy frontend with course management views
4. Set `AI_API_KEY` environment variable on server
5. Verify with a single test AI call from admin dashboard
6. No rollback risk for existing features; new tables and nullable FK are additive only

## Open Questions

- **Which LLM model to default to?** Recommendation: `gpt-4o-mini` for cost efficiency. Can be changed in config.
- **Daily token budgets per role?** Recommendation: admin 500K, teacher 200K, student 50K. Configurable via `ai_config`.
- **Should prompt content be logged for debugging?** Recommendation: no, for data privacy. Only metadata (token counts, model, status, latency). If debugging is needed, add an opt-in `log_prompts` config flag.
