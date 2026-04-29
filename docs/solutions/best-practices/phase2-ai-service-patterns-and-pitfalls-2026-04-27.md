---
title: "PR3-PR6 Phase 2 Development Patterns and Pitfalls"
date: "2026-04-27"
category: best-practices
module: digital-training-platform
problem_type: best_practice
component: development_workflow
severity: medium
applies_when:
  - building AI-integrated features with service singletons
  - writing tests that interact with global module-level state
  - implementing statistics or aggregation endpoints with ORM queries
  - calculating token-based costs for AI API usage
  - designing dashboard APIs that must match frontend spec exactly
  - hardening Pydantic schemas for public-facing endpoints
  - integrating chart libraries in Vue without npm dependencies
  - running compound-engineering review cycles with multiple personas
tags:
  - ai-service
  - singleton-pattern
  - testing
  - query-optimization
  - cost-calculation
  - schema-validation
  - ce-review
  - echarts
  - fastapi
  - sqlalchemy
  - vue3
---

# PR3-PR6 Phase 2 Development Patterns and Pitfalls

## Context

This document captures development learnings from PR3-PR6 of a Digital Training Platform built with FastAPI + SQLAlchemy 2.0 async + Vue 3 + Element Plus. These PRs implemented Phase 2 features spanning 109 commits, 116 files, and 203 tests. The learnings emerged from real bugs found during implementation, CE review findings, spec compliance verification, and cross-review between parallel PRs.

The Phase 2 work covered: AI task description generation (PR3), student Q&A assistant (PR4), AI-generated training summaries (PR5), and statistics dashboards (PR6), plus AI infrastructure (config, usage tracking, feedback, prompt templates, budget enforcement).

This is a companion to the PR1 MVP learnings doc (`full-mvp-development-cycle-patterns-and-learnings-2026-04-23.md`). Together they form a chronological series covering the full platform development lifecycle.

## Guidance

### Topic 1: Module-Level Singleton Services

Use a module-level variable with a factory function for service singletons that need configuration-dependent initialization.

```python
# app/services/ai.py
_ai_service = None

def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        if settings.AI_API_KEY:
            provider = OpenAIProvider(api_key=settings.AI_API_KEY, model=settings.AI_MODEL)
        else:
            provider = MockProvider()
        _ai_service = AIService(provider=provider, db_session_factory=get_session)
    return _ai_service
```

Rules:
- Every singleton must have a reset mechanism for testing.
- The factory function must read config at call time, not at import time.
- Tests that assert on provider type must both reset the singleton AND patch the config value.

Pitfall: If `.env` contains a real API key, any test that runs after an unrelated import can initialize the singleton with the real provider. The fix is not just resetting the variable but also patching the config:

```python
def test_get_ai_service_returns_mock_by_default():
    import app.services.ai as ai_module
    ai_module._ai_service = None
    with patch.object(ai_module.settings, "AI_API_KEY", ""):
        service = ai_module.get_ai_service()
        assert isinstance(service.provider, MockProvider)
```

### Topic 2: Async SQLAlchemy Session Scoping for Side Effects

When you need to log a side effect (e.g., AI usage cost) that should persist even if the primary operation fails, use a separate session with an eager commit.

```python
# WRONG: logging in the same session as the AI call
async with get_session() as session:
    result = await ai_provider.call(prompt)
    usage_log = AIUsageLog(cost=cost, tokens=result.tokens)
    session.add(usage_log)
    # If an error occurs after this line, session rollback drops the log
    await session.commit()

# CORRECT: separate session for audit trail
async with get_session() as audit_session:
    usage_log = AIUsageLog(cost=cost, tokens=estimated_tokens)
    audit_session.add(usage_log)
    await audit_session.commit()

# Now make the AI call (if it fails, the usage log is still recorded)
result = await ai_provider.call(prompt)
```

Audit trails, cost logs, and irreversible side effects must not share a session with the operation they monitor.

### Topic 3: Preventing N+1 Queries in Async SQLAlchemy

Four endpoints in this project had queries inside loops. The root cause is that async SQLAlchemy makes correlated subqueries less ergonomic than sync, so developers default to loop-and-query.

Detection checklist:
1. Any `for ... in results:` followed by `await session.execute(...)` is an N+1.
2. Any endpoint that returns a list and does per-item DB lookups is an N+1.

Fix patterns, ranked by preference:

**Pattern A -- Batch with IN clause:**

```python
# Before: N+1
for course in courses:
    task_count = await session.execute(
        select(func.count(Task.id)).where(Task.course_id == course.id)
    )

# After: batch
course_ids = [c.id for c in courses]
counts = await session.execute(
    select(Task.course_id, func.count(Task.id))
    .where(Task.course_id.in_(course_ids))
    .group_by(Task.course_id)
)
count_map = dict(counts.all())
```

**Pattern B -- JOIN + GROUP BY in the main query:**

```python
stmt = (
    select(Course, func.count(Task.id).label("task_count"))
    .outerjoin(Task, Task.course_id == Course.id)
    .group_by(Course.id)
)
results = await session.execute(stmt)
```

**Pattern C -- selectinload for related objects:**

```python
stmt = select(Course).options(selectinload(Course.tasks))
courses = await session.execute(stmt)
```

When reviewing any list endpoint, explicitly verify the query count. If a single HTTP request produces more than 3 DB queries for a list of items, it is likely an N+1.

### Topic 4: Unit Pricing Arithmetic for External APIs

Always verify the unit denomination of pricing against the actual API billing unit.

```python
# OpenAI pricing is per-1K tokens.
# If input_price = 0.03 (dollars per 1K input tokens):

# WRONG: treats price as per-token
cost = input_tokens * input_price + output_tokens * output_price

# CORRECT: convert from per-1K to per-token
cost = (input_tokens * input_price + output_tokens * output_price) / 1000
```

Write a test that calculates cost for a known input and asserts the expected dollar amount:

```python
def test_cost_calculation_accuracy():
    cost = calculate_cost(input_tokens=1000, output_tokens=0,
                          input_price=0.03, output_price=0.06)
    assert cost == pytest.approx(0.03, abs=0.001)
```

### Topic 5: Spec-Driven Dashboard Field Alignment

When implementing an endpoint from a spec, create a field checklist before coding and validate after.

Common mistakes found:
- Missing fields for inactive/archived counts (`total_archived_courses`, `total_archived_tasks`)
- Missing role-specific fields (admin `nearby_deadline` vs teacher `my_nearby_deadline`)
- Wrong rounding precision (`round(avg_score, 2)` vs spec's `round(avg_score, 1)`)
- Missing filters (`is_active=True` on user count queries)

Prevention pattern:

```python
# In the test, assert every field:
def test_dashboard_response_shape(client, admin_token):
    resp = client.get("/api/dashboard/admin", headers=auth_headers(admin_token))
    data = resp.json()
    expected_fields = {
        "total_users", "users_by_role", "total_classes",
        "total_active_courses", "total_archived_courses",
        "total_active_tasks", "total_archived_tasks",
        "total_submissions", "pending_grades", "graded",
        "late_submissions", "avg_score", "nearby_deadline",
        "daily_submissions_last_7d",
    }
    assert expected_fields <= set(data.keys())
```

### Topic 6: SQLAlchemy Async Result Reuse

In SQLAlchemy async, you cannot call `scalar()` (or any fetch method) twice on the same result object.

```python
# WRONG: ResourceClosedError on the second scalar()
result = await session.execute(query)
count = result.scalar()       # consumes the result
total = result.scalar()       # ERROR: result is closed

# CORRECT: use the appropriate method once
row = (await session.execute(query)).one()
count = row[0]
```

Every async result object is single-use. If you need two values, use `result.one()` or `result.all()` and extract from the row, or execute separate queries.

### Topic 7: Pydantic Schema Hardening

Apply these constraints consistently across all schemas:

```python
# Reject unknown fields in update schemas
class CourseUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = None
    description: str | None = None

# Validate enum-like strings with regex
class UserUpdate(BaseModel):
    role: str | None = Field(None, pattern=r'^(admin|teacher|student)$')

# Constrain numeric ranges
class GradeCreate(BaseModel):
    score: float = Field(..., ge=0, le=100)

# Replace untyped List[dict] with typed models
class AIFeedbackNegativeItem(BaseModel):
    reason: str
    detail: str = ""

class AIFeedback(BaseModel):
    negatives: list[AIFeedbackNegativeItem] = []
```

Every schema that accepts external input should have at minimum: `extra = "forbid"` on update schemas, range constraints on numerics, and typed sub-models instead of raw dicts.

### Topic 8: Frontend Chart and Lifecycle Patterns

**ECharts via CDN** -- loaded in `index.html`, available as `window.echarts`:

```javascript
const chartRef = ref(null)
let chartInstance = null

onMounted(() => {
  if (window.echarts && chartRef.value) {
    chartInstance = window.echarts.init(chartRef.value)
    chartInstance.setOption({ /* ... */ })
  }
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
})
```

**Resize listeners** -- register at setup() scope, NOT inside onMounted:

```javascript
const handleResize = () => chartInstance?.resize()
window.addEventListener('resize', handleResize)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
```

**Nullable statistics** -- el-statistic crashes on null/undefined:

```html
<el-statistic v-if="avgScore !== null" :value="avgScore" />
<span v-else>N/A</span>
```

### Topic 9: CE Review Fix Classification

The compound-engineering review system classifies findings into three action levels:

- **safe_auto**: Deterministic fixes with no risk of regression (typos, missing validation, wrong defaults). Applied immediately. 9 of these were applied in PR4.
- **gated_auto**: Fix is known but touches sensitive boundaries (cost calculations, N+1 query rewrites, auth logic). Applied with explicit sign-off and targeted test coverage.
- **manual**: Requires human judgment, multi-file coordination, or product decision. Documented as a follow-up.

Process safe_auto findings first, then gated_auto, then present manual items. Never skip gated_auto items -- they are the ones most likely to cause silent data or money bugs.

## Why This Matters

**Singleton without test isolation:** A single `.env` file can cause every test in a suite to use the production AI provider instead of the mock. This leads to real API calls during testing, flaky tests, and cost exposure. The fix is two lines per test but the bug is invisible until someone runs tests with a real API key.

**Shared-session audit logs:** If AI usage is logged in the same session as the AI call, any exception rolls back the usage record. The system silently underreports costs -- a billing discrepancy that is extremely difficult to trace because the code "looks correct."

**N+1 queries:** The dashboard endpoint `GET /api/dashboard/courses` with 20 courses executed over 100 queries. At production scale with 100+ courses, this becomes latency and connection pool exhaustion.

**1000x cost underreporting:** A single arithmetic error in unit conversion caused all AI usage to be reported at 1/1000th of actual cost. This passes all tests unless you have a test with a known expected dollar amount.

**Missing spec fields:** Dashboard endpoints that omit spec-required fields cause frontend errors in production because the frontend expects those fields. The missing `is_active=True` filter caused the admin dashboard to show deleted users in the count.

**Schema without validation:** Without `extra = "forbid"`, a client can send arbitrary fields. Without range constraints, a grade of -50 or 9999 is accepted. These become data integrity issues painful to clean up retrospectively.

## When to Apply

| Condition | Apply These Patterns |
|---|---|
| Building services that depend on external config (API keys, feature flags) | Singleton with test isolation (Topic 1) |
| Logging side effects of external calls (cost, usage, audit) | Separate session for audit trail (Topic 2) |
| Building any list endpoint that returns aggregated data | N+1 query prevention (Topic 3) |
| Integrating usage-based external APIs (OpenAI, AWS, Stripe) | Unit pricing test with known amounts (Topic 4) |
| Implementing endpoints defined by a spec document | Field checklist before/after coding (Topic 5) |
| Using SQLAlchemy async with aggregate queries | Single-use result handling (Topic 6) |
| Defining any Pydantic schema for external input | Schema hardening constraints (Topic 7) |
| Adding charts, resize listeners, or statistic displays to Vue components | Lifecycle cleanup and null guards (Topic 8) |
| Running compound-engineering review on a PR | Fix classification workflow (Topic 9) |
| Any new module that does async database operations | Topics 2, 3, 6 |

## Examples

### Example 1: Singleton Test Isolation

Before -- fails when .env has real API key:

```python
def test_get_ai_service_returns_mock_by_default():
    service = get_ai_service()
    assert isinstance(service.provider, MockProvider)
    # FAILS: _ai_service was already initialized with OpenAIProvider
```

After -- passes regardless of .env:

```python
def test_get_ai_service_returns_mock_by_default():
    import app.services.ai as ai_module
    ai_module._ai_service = None
    with patch.object(ai_module.settings, "AI_API_KEY", ""):
        service = ai_module.get_ai_service()
        assert isinstance(service.provider, MockProvider)
```

### Example 2: N+1 Dashboard Query

Before -- 5N queries for N courses:

```python
for course in courses:
    task_count = (await session.execute(
        select(func.count(Task.id)).where(Task.course_id == course.id)
    )).scalar()
    submission_count = (await session.execute(
        select(func.count(Submission.id)).where(Submission.task_id.in_(
            select(Task.id).where(Task.course_id == course.id)
        ))
    )).scalar()
```

After -- 2 queries total:

```python
course_ids = [c.id for c in courses]
task_counts = dict(
    (await session.execute(
        select(Task.course_id, func.count(Task.id))
        .where(Task.course_id.in_(course_ids))
        .group_by(Task.course_id)
    )).all()
)
submission_counts = dict(
    (await session.execute(
        select(Task.course_id, func.count(Submission.id))
        .join(Task, Task.id == Submission.task_id)
        .where(Task.course_id.in_(course_ids))
        .group_by(Task.course_id)
    )).all()
)
```

### Example 3: Cost Calculation

Before -- 1000x underreporting:

```python
cost_microdollars = (input_tokens * input_price + output_tokens * output_price)
```

After -- correct per-1K token pricing:

```python
cost_microdollars = (input_tokens * input_price + output_tokens * output_price) / 1000
```

Test that catches it:

```python
def test_gpt4_cost_for_1000_tokens():
    cost = calculate_cost(input_tokens=1000, output_tokens=0,
                          input_price=0.03, output_price=0.06)
    assert cost == pytest.approx(0.03, abs=0.001)  # $0.03, not $30.00
```

### Example 4: Schema Hardening

Before -- accepts anything:

```python
class CourseUpdate(BaseModel):
    title: str | None = None

class GradeCreate(BaseModel):
    score: float
    feedback: list[dict] = []
```

After -- strict validation:

```python
class CourseUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = None

class GradeCreate(BaseModel):
    score: float = Field(..., ge=0, le=100)
    feedback: list[FeedbackItem] = []
```

### Example 5: COALESCE for Zero-Usage Aggregation

Before -- returns None when no rows exist:

```python
total = (await session.execute(
    select(func.sum(AIUsageLog.cost)).where(AIUsageLog.user_id == user_id)
)).scalar()
# total is None if user has no usage logs, causing TypeError in arithmetic
```

After -- returns 0 for empty sets:

```python
total = (await session.execute(
    select(func.coalesce(func.sum(AIUsageLog.cost), 0))
    .where(AIUsageLog.user_id == user_id)
)).scalar()
```

## Related

- `docs/solutions/developer-experience/full-mvp-development-cycle-patterns-and-learnings-2026-04-23.md` -- PR1 MVP learnings (companion doc)
- `docs/superpowers/plans/2026-04-24-pr2-ai-infrastructure-safety.md` -- AI infrastructure plan
- `docs/superpowers/plans/2026-04-27-pr6-statistics-dashboard.md` -- Dashboard plan
- `openspec/changes/add-digital-training-platform-phase2-foundation-and-ai-assist/` -- Phase 2 specs
- PR #2: https://github.com/JR-Power-GF/shuzi/pull/2
