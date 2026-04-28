# PR5: Student Training Summary AI Generation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable students to generate AI-powered training summaries based on their course submissions, edit the draft, and save/submit the final version.

**Architecture:** New `POST /api/courses/{course_id}/generate-summary` endpoint gathers the student's submissions for that course, builds context for the `training_summary` prompt template, and calls AI. A `TrainingSummary` model persists the user-edited final version. Frontend adds a new `CourseSummary.vue` view with generate/edit/save flow.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic, Alembic, PromptService, AIService (DeepSeek), Vue 3 + Element Plus

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/models/training_summary.py` | Create | TrainingSummary ORM model |
| `backend/alembic/versions/xxx_add_training_summaries_table.py` | Create | Alembic migration |
| `backend/app/schemas/training_summary.py` | Create | Request/response schemas |
| `backend/app/routers/courses.py` | Modify | Add generate/save/get summary endpoints |
| `backend/scripts/seed_demo.py` | Modify | Enhance training_summary prompt template |
| `backend/tests/test_training_summary.py` | Create | All tests |
| `frontend/src/views/student/CourseSummary.vue` | Create | Summary generation/edit/save view |
| `frontend/src/router/index.js` | Modify | Add route |

---

### Task 1: Create TrainingSummary model + migration

**Files:**
- Create: `backend/app/models/training_summary.py`
- Create: `backend/alembic/versions/xxx_add_training_summaries_table.py`

- [ ] **Step 1: Create the model file**

Create `backend/app/models/training_summary.py`:

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class TrainingSummary(Base):
    __tablename__ = "training_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="draft")
    ai_usage_log_id = Column(Integer, ForeignKey("ai_usage_logs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uq_student_course_summary"),)
```

- [ ] **Step 2: Generate the Alembic migration**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/alembic -c backend/alembic.ini revision --autogenerate -m "add_training_summaries_table"`

- [ ] **Step 3: Verify migration looks correct**

Open the generated migration file and verify it has `create_table('training_summaries', ...)` with the correct columns and unique constraint.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/training_summary.py backend/alembic/versions/
git commit -m "feat(pr5): add TrainingSummary model and migration"
```

---

### Task 2: Create request/response schemas

**Files:**
- Create: `backend/app/schemas/training_summary.py`

- [ ] **Step 1: Create the schemas file**

Create `backend/app/schemas/training_summary.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SummaryGenerateResponse(BaseModel):
    content: str
    usage_log_id: int
    prompt_tokens: int
    completion_tokens: int


class SummarySaveRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    status: str = Field("draft", pattern=r"^(draft|submitted)$")


class SummaryResponse(BaseModel):
    id: int
    course_id: int
    content: str
    status: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -c "from backend.app.schemas.training_summary import SummaryGenerateResponse, SummarySaveRequest, SummaryResponse; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/training_summary.py
git commit -m "feat(pr5): add training summary request/response schemas"
```

---

### Task 3: Write failing test for generate-summary

**Files:**
- Create: `backend/tests/test_training_summary.py`

- [ ] **Step 1: Write the test file with fixture + success test + permission tests**

Create `backend/tests/test_training_summary.py`:

```python
import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.class_ import Class
from app.models.course import Course
from app.models.prompt_template import PromptTemplate
from app.models.submission import Submission
from app.models.task import Task
from app.services.ai import AIServiceError, BudgetExceededError
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_summary_env(db_session):
    teacher = await create_test_user(db_session, username="teacher_summary", role="teacher")
    student = await create_test_user(db_session, username="student_summary", role="student")
    other_student = await create_test_user(db_session, username="student_other_summary", role="student")

    cls = Class(name="总结测试班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()

    student.primary_class_id = cls.id
    await db_session.flush()

    course = Course(
        name="Python程序设计", semester="2025-2026-2",
        teacher_id=teacher.id, description="Python基础与Web开发",
    )
    db_session.add(course)
    await db_session.flush()

    task1 = Task(
        title="Flask Web开发实践",
        description="使用Flask框架开发一个简单的Web应用",
        requirements="提交完整的源代码和实验报告",
        class_id=cls.id, course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip", ".pdf"]),
    )
    task2 = Task(
        title="数据库设计",
        description="设计并实现一个关系型数据库",
        requirements="提交ER图和SQL脚本",
        class_id=cls.id, course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip", ".pdf"]),
    )
    db_session.add_all([task1, task2])
    await db_session.flush()

    sub1 = Submission(task_id=task1.id, student_id=student.id, version=1)
    sub2 = Submission(task_id=task2.id, student_id=student.id, version=1)
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    template = PromptTemplate(
        name="training_summary",
        description="生成实训总结",
        template_text=(
            "请根据学生的提交记录生成一份实训总结。\n\n"
            "课程：{course_name}\n课程描述：{course_description}\n"
            "提交次数：{submission_count}\n提交内容摘要：\n{submission_summaries}\n\n"
            "请包含：学习概述、主要收获、不足与改进"
        ),
        variables=json.dumps(["course_name", "course_description", "submission_count", "submission_summaries"]),
    )
    db_session.add(template)
    await db_session.flush()

    return {
        "teacher": teacher, "student": student, "other_student": other_student,
        "cls": cls, "course": course, "tasks": [task1, task2], "submissions": [sub1, sub2],
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_success(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert len(data["content"]) > 0
    assert "usage_log_id" in data
    assert isinstance(data["usage_log_id"], int)


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_teacher_forbidden(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "teacher_summary")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_other_class_forbidden(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "student_other_summary")

    resp = await client.post(
        f"/api/courses/{env['course'].id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_course_not_found(client, db_session, setup_summary_env):
    token = await login_user(client, "student_summary")

    resp = await client.post(
        "/api/courses/99999/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run the test — expect FAIL (405, route does not exist)**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_training_summary.py::test_generate_summary_success -v`

Expected: FAIL — endpoint does not exist yet.

Do NOT commit — this is the TDD red artifact.

---

### Task 4: Implement generate-summary endpoint

**Files:**
- Modify: `backend/app/routers/courses.py`

This endpoint:
1. Verifies the student is enrolled (primary_class_id matches a class that has tasks for this course)
2. Queries all submissions for the student within tasks belonging to the course
3. Builds context for `training_summary` prompt template
4. Calls PromptService.fill_template then AIService.generate
5. Returns the AI-generated summary draft

- [ ] **Step 1: Add imports and endpoint to courses.py**

In `backend/app/routers/courses.py`, add imports at the top:

```python
from app.schemas.training_summary import SummaryGenerateResponse, SummarySaveRequest, SummaryResponse
from app.services.ai import AIServiceError, BudgetExceededError, get_ai_service
from app.services.prompts import PromptService
from app.models.training_summary import TrainingSummary
```

Add `from fastapi.responses import JSONResponse` to the existing imports.

Add the generate-summary endpoint BEFORE the `/{course_id}` GET route (around line 267, before `get_course_detail`):

```python
@router.post("/{course_id}/generate-summary", response_model=SummaryGenerateResponse)
async def generate_training_summary(
    course_id: int,
    current_user: dict = Depends(require_role(["student"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    user_result = await db.execute(
        select(User.primary_class_id).where(User.id == current_user["id"])
    )
    class_id = user_result.scalar_one_or_none()
    if class_id is None:
        raise HTTPException(status_code=403, detail="未分配班级")

    course_task_count = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.course_id == course_id, Task.class_id == class_id,
        )
    )
    if course_task_count.scalar() == 0:
        raise HTTPException(status_code=403, detail="无权访问该课程")

    submissions_result = await db.execute(
        select(Submission, Task.title, Task.description)
        .join(Task, Task.id == Submission.task_id)
        .where(
            Submission.student_id == current_user["id"],
            Task.course_id == course_id,
            Task.class_id == class_id,
        )
        .order_by(Submission.submitted_at)
    )
    rows = submissions_result.all()

    if not rows:
        raise HTTPException(status_code=400, detail="暂无提交记录，无法生成总结")

    submission_summaries = []
    for i, (sub, task_title, task_desc) in enumerate(rows, 1):
        late_tag = "（迟交）" if sub.is_late else ""
        submission_summaries.append(
            f"{i}. 任务「{task_title}」- 已提交(版本{sub.version}){late_tag}，提交时间：{sub.submitted_at.strftime('%Y-%m-%d')}"
        )

    prompt_service = PromptService()
    try:
        prompt_text = await prompt_service.fill_template(
            db, "training_summary",
            {
                "course_name": course.name or "",
                "course_description": course.description or "",
                "submission_count": str(len(rows)),
                "submission_summaries": "\n".join(submission_summaries),
            },
        )
    except ValueError:
        raise HTTPException(status_code=500, detail="总结模板未配置")

    service = get_ai_service()
    try:
        ai_result = await service.generate(
            db=db, prompt=prompt_text, user_id=current_user["id"],
            role=current_user["role"], endpoint="training_summary",
        )
    except BudgetExceededError:
        raise HTTPException(status_code=429, detail="今日 AI 调用额度已用完")
    except AIServiceError:
        return JSONResponse(status_code=502, content={"detail": "AI 服务暂时不可用"})

    return SummaryGenerateResponse(
        content=ai_result["text"],
        usage_log_id=ai_result["usage_log_id"],
        prompt_tokens=ai_result["prompt_tokens"],
        completion_tokens=ai_result["completion_tokens"],
    )
```

- [ ] **Step 2: Run the failing test from Task 3 — expect PASS**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_training_summary.py -v`

Expected: 4 tests pass (success, teacher 403, other-class 403, not-found 404)

- [ ] **Step 3: Run full test suite — no regressions**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/ -x -q`

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_training_summary.py backend/app/routers/courses.py backend/app/schemas/training_summary.py
git commit -m "feat(pr5): add generate-training-summary endpoint with TDD tests"
```

---

### Task 5: Add error boundary tests for generate-summary

**Files:**
- Modify: `backend/tests/test_training_summary.py`

- [ ] **Step 1: Add 429, 502, no-submissions, and template-missing tests**

Append to `backend/tests/test_training_summary.py`:

```python

@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_budget_exceeded(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "student_summary")
    mock_service = AsyncMock()
    mock_service.generate.side_effect = BudgetExceededError("额度用完")

    with patch("app.routers.courses.get_ai_service", return_value=mock_service):
        resp = await client.post(
            f"/api/courses/{env['course'].id}/generate-summary",
            headers=auth_headers(token),
        )
    assert resp.status_code == 429


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_ai_error(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "student_summary")
    mock_service = AsyncMock()
    mock_service.generate.side_effect = AIServiceError("不可用")

    with patch("app.routers.courses.get_ai_service", return_value=mock_service):
        resp = await client.post(
            f"/api/courses/{env['course'].id}/generate-summary",
            headers=auth_headers(token),
        )
    assert resp.status_code == 502


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_no_submissions(client, db_session):
    teacher = await create_test_user(db_session, username="teacher_nosub", role="teacher")
    student = await create_test_user(db_session, username="student_nosub", role="student")
    cls = Class(name="无提交班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()
    student.primary_class_id = cls.id
    await db_session.flush()
    course = Course(name="空课程", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(course)
    await db_session.flush()
    task = Task(
        title="测试任务", class_id=cls.id, course_id=course.id,
        created_by=teacher.id, deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".pdf"]),
    )
    db_session.add(task)
    template = PromptTemplate(
        name="training_summary", description="总结",
        template_text="总结 {course_name} {course_description} {submission_count} {submission_summaries}",
        variables=json.dumps(["course_name", "course_description", "submission_count", "submission_summaries"]),
    )
    db_session.add(template)
    await db_session.flush()

    token = await login_user(client, "student_nosub")
    resp = await client.post(
        f"/api/courses/{course.id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "提交" in resp.json()["detail"]


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_summary_template_missing(client, db_session):
    teacher = await create_test_user(db_session, username="teacher_notpl_sum", role="teacher")
    student = await create_test_user(db_session, username="student_notpl_sum", role="student")
    cls = Class(name="无模板班2", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()
    student.primary_class_id = cls.id
    await db_session.flush()
    course = Course(name="无模板课程", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(course)
    await db_session.flush()
    task = Task(
        title="测试任务", class_id=cls.id, course_id=course.id,
        created_by=teacher.id, deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".pdf"]),
    )
    db_session.add(task)
    sub = Submission(task_id=task.id, student_id=student.id, version=1)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "student_notpl_sum")
    resp = await client.post(
        f"/api/courses/{course.id}/generate-summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 500
    assert "模板" in resp.json()["detail"]
```

- [ ] **Step 2: Run all tests in the file**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_training_summary.py -v`

Expected: All 8 tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_training_summary.py
git commit -m "test(pr5): add error boundary tests for generate-summary endpoint"
```

---

### Task 6: Implement save/get summary endpoints

**Files:**
- Modify: `backend/app/routers/courses.py`

These endpoints let the student save their edited summary and retrieve it later.

- [ ] **Step 1: Add save and get endpoints to courses.py**

Add after the `generate_training_summary` endpoint, still BEFORE the `/{course_id}` GET route:

```python
@router.get("/{course_id}/summary", response_model=SummaryResponse)
async def get_training_summary(
    course_id: int,
    current_user: dict = Depends(require_role(["student"])),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(
        select(User.primary_class_id).where(User.id == current_user["id"])
    )
    class_id = user_result.scalar_one_or_none()
    if class_id is None:
        raise HTTPException(status_code=403, detail="未分配班级")

    course_task_count = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.course_id == course_id, Task.class_id == class_id,
        )
    )
    if course_task_count.scalar() == 0:
        raise HTTPException(status_code=403, detail="无权访问该课程")

    result = await db.execute(
        select(TrainingSummary).where(
            TrainingSummary.student_id == current_user["id"],
            TrainingSummary.course_id == course_id,
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="暂未保存总结")

    return SummaryResponse(
        id=summary.id,
        course_id=summary.course_id,
        content=summary.content,
        status=summary.status,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


@router.put("/{course_id}/summary", response_model=SummaryResponse)
async def save_training_summary(
    course_id: int,
    data: SummarySaveRequest,
    current_user: dict = Depends(require_role(["student"])),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(
        select(User.primary_class_id).where(User.id == current_user["id"])
    )
    class_id = user_result.scalar_one_or_none()
    if class_id is None:
        raise HTTPException(status_code=403, detail="未分配班级")

    course_task_count = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.course_id == course_id, Task.class_id == class_id,
        )
    )
    if course_task_count.scalar() == 0:
        raise HTTPException(status_code=403, detail="无权访问该课程")

    result = await db.execute(
        select(TrainingSummary).where(
            TrainingSummary.student_id == current_user["id"],
            TrainingSummary.course_id == course_id,
        )
    )
    summary = result.scalar_one_or_none()
    if summary:
        summary.content = data.content
        summary.status = data.status
    else:
        summary = TrainingSummary(
            student_id=current_user["id"],
            course_id=course_id,
            content=data.content,
            status=data.status,
        )
        db.add(summary)
    await db.flush()

    return SummaryResponse(
        id=summary.id,
        course_id=summary.course_id,
        content=summary.content,
        status=summary.status,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )
```

- [ ] **Step 2: Add save/get tests to test file**

Append to `backend/tests/test_training_summary.py`:

```python

@pytest.mark.asyncio(loop_scope="session")
async def test_save_and_get_summary(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    save_resp = await client.put(
        f"/api/courses/{env['course'].id}/summary",
        json={"content": "我的实训总结内容", "status": "draft"},
        headers=auth_headers(token),
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["content"] == "我的实训总结内容"
    assert save_resp.json()["status"] == "draft"
    summary_id = save_resp.json()["id"]

    get_resp = await client.get(
        f"/api/courses/{env['course'].id}/summary",
        headers=auth_headers(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == summary_id
    assert get_resp.json()["content"] == "我的实训总结内容"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_summary(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    await client.put(
        f"/api/courses/{env['course'].id}/summary",
        json={"content": "初稿", "status": "draft"},
        headers=auth_headers(token),
    )

    update_resp = await client.put(
        f"/api/courses/{env['course'].id}/summary",
        json={"content": "修改后的总结", "status": "submitted"},
        headers=auth_headers(token),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["content"] == "修改后的总结"
    assert update_resp.json()["status"] == "submitted"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_summary_not_found(client, db_session, setup_summary_env):
    env = setup_summary_env
    token = await login_user(client, "student_summary")

    resp = await client.get(
        f"/api/courses/{env['course'].id}/summary",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
```

- [ ] **Step 3: Run all tests**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_training_summary.py -v`

Expected: All 11 tests pass.

- [ ] **Step 4: Run full suite**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/ -x -q`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_training_summary.py
git commit -m "feat(pr5): add save/get training summary endpoints with tests"
```

---

### Task 7: Enhance training_summary prompt template

**Files:**
- Modify: `backend/scripts/seed_demo.py` (the training_summary PromptTemplate)

- [ ] **Step 1: Replace the training_summary template in seed_demo.py**

Find the existing `training_summary` PromptTemplate block (around lines 112-117) and replace:

```python
            PromptTemplate(
                name="training_summary",
                description="生成实训总结",
                template_text=(
                    "你是教学助教，请根据学生的提交记录生成一份实训总结。\n\n"
                    "## 学生信息\n"
                    "课程：{course_name}\n"
                    "课程描述：{course_description}\n"
                    "提交次数：{submission_count}\n\n"
                    "## 提交记录\n"
                    "{submission_summaries}\n\n"
                    "## 严格规则\n"
                    "1. 只根据上方提供的提交记录生成总结，不要编造不存在的任务或成果\n"
                    "2. 总结结构：学习概述、主要收获、不足与改进建议、下一步学习计划\n"
                    "3. 如果提交记录很少或为空，明确指出数据不足，建议学生补充\n"
                    "4. 用简洁清晰的中文撰写，长度 300-800 字\n"
                    "5. 这是初稿，学生可能会修改，不要加标题或格式标记\n"
                ),
                variables=json.dumps(["course_name", "course_description", "submission_count", "submission_summaries"]),
            ),
```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -c "from backend.app.models.prompt_template import PromptTemplate; print('OK')"`

- [ ] **Step 3: Run tests**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/ -x -q`

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/seed_demo.py
git commit -m "feat(pr5): enhance training_summary prompt with structured grounding rules"
```

---

### Task 8: Frontend — CourseSummary.vue + route

**Files:**
- Create: `frontend/src/views/student/CourseSummary.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/student/CourseList.vue` (add "生成总结" button)

- [ ] **Step 1: Create CourseSummary.vue**

Create `frontend/src/views/student/CourseSummary.vue`:

```vue
<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" :content="courseName || '实训总结'" />
    <div style="margin-top: 20px">
      <div v-if="!generated && !savedSummary" style="text-align: center; padding: 60px">
        <p style="color: #909399; margin-bottom: 20px">
          点击下方按钮，AI 将根据你的课程提交记录生成实训总结初稿
        </p>
        <el-button type="primary" size="large" @click="generateSummary" :loading="generating">
          生成实训总结
        </el-button>
      </div>

      <div v-else>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
          <span style="font-size: 14px; color: #909399">
            {{ generated ? 'AI 生成的初稿，你可以自由修改后保存' : '已保存的总结' }}
          </span>
          <el-button v-if="savedSummary" size="small" @click="regenerate" :loading="generating">
            重新生成
          </el-button>
        </div>
        <el-input
          v-model="summaryContent"
          type="textarea"
          :rows="15"
          placeholder="总结内容..."
        />
        <div style="margin-top: 16px; display: flex; gap: 12px">
          <el-button @click="saveSummary('draft')" :loading="saving">保存草稿</el-button>
          <el-button type="primary" @click="saveSummary('submitted')" :loading="saving">提交总结</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const route = useRoute()
const courseId = route.params.id

const courseName = ref('')
const loading = ref(false)
const generating = ref(false)
const saving = ref(false)
const generated = ref(false)
const savedSummary = ref(null)
const summaryContent = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/courses/${courseId}/summary`)
    savedSummary.value = resp.data
    summaryContent.value = resp.data.content
  } catch (err) {
    if (err.response?.status !== 404) {
      ElMessage.error('获取总结失败')
    }
  } finally {
    loading.value = false
  }

  try {
    const resp = await api.get('/courses')
    const course = resp.data.find(c => c.id === Number(courseId))
    if (course) courseName.value = course.name
  } catch {}
})

async function generateSummary() {
  generating.value = true
  try {
    const resp = await api.post(`/courses/${courseId}/generate-summary`)
    summaryContent.value = resp.data.content
    generated.value = true
  } catch (err) {
    if (err.response?.status === 429) {
      ElMessage.error('今日 AI 调用额度已用完，请明天再试')
    } else if (err.response?.status === 502) {
      ElMessage.error('AI 服务暂时不可用，请稍后再试')
    } else {
      ElMessage.error(err.response?.data?.detail || '生成失败')
    }
  } finally {
    generating.value = false
  }
}

async function regenerate() {
  generated.value = false
  savedSummary.value = null
  await generateSummary()
}

async function saveSummary(status) {
  if (!summaryContent.value.trim()) {
    ElMessage.warning('总结内容不能为空')
    return
  }
  saving.value = true
  try {
    const resp = await api.put(`/courses/${courseId}/summary`, {
      content: summaryContent.value,
      status,
    })
    savedSummary.value = resp.data
    generated.value = false
    ElMessage.success(status === 'submitted' ? '总结已提交' : '草稿已保存')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
```

- [ ] **Step 2: Add route to router/index.js**

In `frontend/src/router/index.js`, after the `student/courses` route (around line 108), add:

```javascript
      {
        path: 'student/courses/:id/summary',
        name: 'StudentCourseSummary',
        component: () => import('../views/student/CourseSummary.vue'),
        meta: { roles: ['student'] },
      },
```

- [ ] **Step 3: Add "生成总结" button to CourseList.vue**

In `frontend/src/views/student/CourseList.vue`, after the progress bar (after line 20), add a button:

```html
        <div style="margin-top: 12px">
          <el-button size="small" type="primary" @click="$router.push(`/student/courses/${course.id}/summary`)">
            实训总结
          </el-button>
        </div>
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -5`

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/student/CourseSummary.vue frontend/src/router/index.js frontend/src/views/student/CourseList.vue
git commit -m "feat(pr5): add CourseSummary.vue with generate/edit/save flow and route"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] 学生实训总结辅助生成 → Task 4 (generate endpoint) + Task 8 (frontend)
- [x] 基于当前任务与本人提交内容生成总结初稿 → Task 4 (queries submissions joined with tasks for the course)
- [x] 用户修改后再保存/提交 → Task 6 (save/get endpoints) + Task 8 (textarea + save buttons)
- [x] AI 反馈、错误处理 → Task 5 (429, 502, no-submissions, template-missing tests)
- [x] 最终 targeted regression → Task 6 Step 4 (full test suite run)

**Permission boundaries:**
- [x] Only students can generate/save summaries (require_role(["student"]))
- [x] Student must be in a class that has tasks for the course (verified via class_id join)
- [x] Teacher and other-class students get 403 (tested in Task 3)

**Placeholder scan:** No TBD, TODO, "implement later", or vague steps found.

**Type consistency:**
- `SummaryGenerateResponse` matches what AIService.generate() returns
- `SummarySaveRequest` matches what the frontend PUT sends
- `SummaryResponse` matches the TrainingSummary model fields
- Frontend API calls use correct field names matching schemas
