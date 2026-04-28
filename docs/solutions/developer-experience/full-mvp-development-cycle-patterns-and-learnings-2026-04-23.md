---
title: "Full MVP Development Cycle: Patterns, Anti-Patterns, and Learnings"
date: "2026-04-23"
category: developer-experience
module: training-platform-mvp
problem_type: developer_experience
component: development_workflow
severity: medium
applies_when:
  - Starting a greenfield MVP with FastAPI + Vue 3 stack
  - Planning a multi-phase feature rollout with TDD discipline
  - Setting up auth, CRUD, state machines, and deployment in one cycle
  - Running structured QA and security review rounds before release
tags:
  - fastapi
  - vue3
  - jwt-auth
  - tdd
  - spec-verification
  - permission-matrix
  - state-machine
  - mvp
---

# Full MVP Development Cycle: Patterns, Anti-Patterns, and Learnings

## Context

A Digital Training Teaching Management Platform MVP was built from scratch using FastAPI + SQLAlchemy 2.0 async (backend) and Vue 3 + Element Plus (frontend). The project went through a full lifecycle: OpenSpec requirements capture, spec/design/task breakdown, TDD-driven implementation, three rounds of fix cycles (P0 security, QA release blockers, spec compliance verification), and deployment configuration.

**38 commits, 55 files changed, +5482/-45 lines, 106 tests passing.**

The most instructive part of this MVP was not the initial implementation but the three fix rounds that followed. The initial code passed basic smoke tests but failed on security hardening, spec compliance edge cases, and state machine enforcement. The patterns that emerged from those fix rounds are the core learnings here.

## Guidance

### 1. JWT Auth: Token Rotation and Account Lockout

**Token rotation** must reject old refresh tokens atomically. Store the refresh token value server-side, and on every rotation, replace it. If the presented token does not match the stored value, reject it.

```python
# Refresh endpoint: rotate and invalidate old token
user = result.scalar_one()

if user.refresh_token != provided_refresh_token:
    raise HTTPException(status_code=401, detail="Refresh token已失效")

new_access = create_access_token(user.id)
new_refresh = create_refresh_token(user.id)
user.refresh_token = new_refresh
await session.commit()
```

**Account lockout** requires careful session lifecycle handling. The FAIL-002 bug: `failed_login_attempts` was incremented and `flush()` called, but the handler then raised `HTTPException`, which triggered `get_db()`'s rollback path, losing the counter. The fix: return a `JSONResponse` instead of raising, so `get_db()` follows its commit-on-success path.

```python
# WRONG: raising HTTPException triggers get_db() rollback, losing the counter
user.failed_login_attempts += 1
if user.failed_login_attempts >= settings.LOCKOUT_THRESHOLD:
    user.locked_until = now + timedelta(minutes=30)
await db.flush()
raise HTTPException(401, "用户名或密码错误")  # Counter lost!

# CORRECT: return JSONResponse so get_db() commits on normal return
user.failed_login_attempts += 1
if user.failed_login_attempts >= settings.LOCKOUT_THRESHOLD:
    user.locked_until = now + timedelta(minutes=30)
await db.flush()
from fastapi.responses import JSONResponse
return JSONResponse(status_code=401, content={"detail": "用户名或密码错误"})
```

Key lesson: when using a `get_db()` generator that commits on success and rolls back on exception, you must understand which path each response takes. Raising exceptions triggers rollback; returning responses triggers commit. For state that must persist (counters, lockout timestamps), use the return path.

### 2. Permission Enforcement via Dependency Injection

Use FastAPI's `Depends()` to enforce role-based access at the router level, not inside handler bodies.

```python
def require_role(allowed_roles):
    """Accept a single role string or a list of role strings."""
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return role_checker
```

Critical subtlety (C-1): deactivated users must return **403**, not 401. The login endpoint correctly splits this into two checks (401 for not found, 403 for deactivated). However, note that `get_current_user` itself still returns 401 for inactive users on authenticated endpoints -- this is a known residual gap. A deactivated user who already has a valid JWT can still hit protected endpoints and gets "Unauthorized" instead of "Forbidden" from the dependency layer. Fixing this requires adding an `is_active` check to `get_current_user` returning 403.

### 3. State Machine: Grade Publish/Unpublish

Grades follow Draft -> Published -> Unpublished. Rules:
- Cannot modify grades while published (C-14, C-15)
- Cannot publish with zero grades (C-16)
- Unpublishing returns to an editable state

Every state change endpoint must validate current state before transitioning. Do not rely on the frontend to enforce this.

```python
if task.grades_published:
    raise HTTPException(status_code=400, detail="请先撤回已发布的成绩")
```

### 4. TDD with Spec Verification

The most effective pattern: write spec compliance tests BEFORE implementing fixes.

1. Identify the spec requirement (e.g., "duplicate username returns 409")
2. Write a failing test asserting exact spec behavior
3. Implement the minimal fix
4. Run the test to confirm

This produced 9 critical spec compliance fixes in one pass, each backed by a test. The spec verification pass caught issues that manual testing missed because the tests were exhaustive, checking exact status codes and error messages.

### 5. Common Spec Compliance Pitfalls

From the 9 critical fixes, these patterns recurred:

- **Wrong HTTP status codes**: Using generic 400/401 when the spec requires 403, 409. Always check the spec's status code table, not intuition.
- **Missing edge case guards**: Self-deactivation (C-6) was not guarded because "who would deactivate themselves?" is an assumption, not a spec requirement. Code against the spec, not assumptions.
- **Schema drift**: `UserUpdate` was missing the `role` field (C-7), so admins could never change a user's role. Schemas must be validated against the full spec, not just the happy path.
- **Post-condition enforcement**: Tasks with submissions had insufficient edit restrictions (C-8, C-9). The fix required checking "does a submission exist that would be invalidated by this change?" (e.g., reducing a deadline below an existing submission timestamp).

## Why This Matters

Without these patterns, the MVP would have shipped with:
- Replay-vulnerable refresh tokens (security)
- Bypassable account lockout (security)
- Wrong HTTP status codes on every error path (broken API contract)
- Missing permission checks on critical endpoints (authorization holes)
- Grade modification while published (data integrity)
- Self-deactivation allowing users to lock themselves out (operational pain)

The three fix rounds consumed roughly as much effort as the initial implementation. This is a normal and healthy ratio for a first MVP. Skipping any of the three rounds would have shipped production bugs.

## When to Apply

- Building a new API with authentication and role-based access control
- The system has domain state machines (grades, tasks, submissions with lifecycle rules)
- A written spec defines exact status codes, error messages, and state transitions
- Using FastAPI with async SQLAlchemy (or similar async ORM patterns)
- Multiple user roles with different permission sets

The TDD-with-spec-verification pattern applies to any project with a testable requirements spec. Most valuable when the spec is detailed enough to assert specific status codes, messages, and state guards.

## Related

- `openspec/changes/add-digital-training-platform-mvp/` -- Full spec, design, and task breakdown
- `docs/superpowers/plans/2026-04-22-pr4-full-features-deployment.md` -- PR4 implementation plan
- `.gstack/qa-reports/qa-report-training-platform-2026-04-23.md` -- QA report that drove fix rounds
- PR #2: https://github.com/JR-Power-GF/shuzi/pull/2

## Known Residual Issues

- `get_current_user` (auth.py:42) returns 401 for inactive users on authenticated endpoints. The login endpoint correctly returns 403, but the dependency layer does not. A deactivated user with a valid JWT still gets "Unauthorized" from protected endpoints instead of "Forbidden." Fix: add `is_active` check to `get_current_user` returning 403.
- `datetime.utcnow()` is deprecated since Python 3.12. Used in auth.py, grades.py, and submissions.py. Should migrate to `datetime.now(timezone.utc)`.
