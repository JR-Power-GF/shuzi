# PR3: AI-Assisted Task Description Generation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable teachers to AI-generate structured task descriptions (background, objectives, steps, submission requirements, grading criteria) with a confirm-before-save dialog and AI feedback collection.

**Architecture:** New `POST /api/tasks/generate-description` endpoint in the tasks router. It uses `PromptService.fill_template()` to hydrate the existing `task_description` prompt template, then calls `AIService.generate()` to produce a draft. The frontend shows the draft in an editable dialog — teacher reviews, optionally edits, then confirms to populate the form field. AI usage is automatically logged via `AIService.generate()`, and teachers can give thumbs-up/down feedback using the existing `/api/ai/feedback` endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic, PromptService, AIService (DeepSeek via OpenAIProvider), Vue 3 + Element Plus

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/schemas/task.py` | Modify | Add `TaskDescriptionGenerateRequest`, `TaskDescriptionGenerateResponse` |
| `backend/app/routers/tasks.py` | Modify | Add `POST /generate-description` endpoint |
| `backend/tests/test_task_ai_gen.py` | Create | Tests for the new endpoint (happy path, error cases) |
| `backend/scripts/seed_demo.py` | Modify | Update `task_description` template to include structured sections |
| `frontend/src/views/teacher/TaskCreate.vue` | Modify | Add AI generate button, preview dialog, confirm flow, feedback buttons |

---

### Task 1: Add request/response schemas

**Files:**
- Modify: `backend/app/schemas/task.py` (append after line 50)

- [ ] **Step 1: Add the two new schemas to `schemas/task.py`**

Append after line 50 (after `TaskResponse` class):

```python


class TaskDescriptionGenerateRequest(BaseModel):
    title: str
    course_name: str = "实训课程"
    language: str = "中文"


class TaskDescriptionGenerateResponse(BaseModel):
    description: str
    usage_log_id: int
    prompt_tokens: int
    completion_tokens: int
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -c "from backend.app.schemas.task import TaskDescriptionGenerateRequest, TaskDescriptionGenerateResponse; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/task.py
git commit -m "feat(pr3): add task description generation request/response schemas"
```

---

### Task 2: Write failing test for generate-description endpoint

**Files:**
- Create: `backend/tests/test_task_ai_gen.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/test_task_ai_gen.py`:

```python
import json

import pytest

from app.models.prompt_template import PromptTemplate
from tests.helpers import create_test_user, login_user, auth_headers


@pytest.fixture
async def setup_template(db_session):
    template = PromptTemplate(
        name="task_description",
        description="生成任务描述",
        template_text="请为 {course_name} 课程生成一个关于 {topic} 的任务描述。语言：{language}",
        variables=json.dumps(["course_name", "topic", "language"]),
    )
    db_session.add(template)
    await db_session.flush()


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_description_success(client, db_session, setup_template):
    teacher = await create_test_user(db_session, username="teacher_ai_gen", role="teacher")
    token = await login_user(client, "teacher_ai_gen")

    resp = await client.post(
        "/api/tasks/generate-description",
        json={"title": "Python Web 开发", "course_name": "Python 程序设计"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "description" in data
    assert len(data["description"]) > 0
    assert "usage_log_id" in data
    assert isinstance(data["usage_log_id"], int)
    assert "prompt_tokens" in data
    assert "completion_tokens" in data
```

- [ ] **Step 2: Run the test — expect it to FAIL (404, route does not exist)**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_task_ai_gen.py::test_generate_description_success -v`

Expected: FAIL — the endpoint `/api/tasks/generate-description` returns 404 because it has not been registered yet.

---

### Task 3: Implement the generate-description endpoint

**Files:**
- Modify: `backend/app/routers/tasks.py` (add imports at line 5-6, add endpoint before line 42)

- [ ] **Step 1: Add imports at the top of `tasks.py`**

Replace lines 5-6:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
```

with:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
```

Then add after line 16 (after `from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate`):

```python
from app.config import settings
from app.schemas.task import TaskDescriptionGenerateRequest, TaskDescriptionGenerateResponse
from app.services.ai import AIServiceError, BudgetExceededError, MockProvider, get_ai_service
from app.services.prompts import PromptService
```

Also update the existing import on line 16 to include the new schemas. The full import block (lines 1-17) becomes:

```python
import json

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.course import Course
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskCreate, TaskDescriptionGenerateRequest, TaskDescriptionGenerateResponse,
    TaskResponse, TaskUpdate,
)
from app.services.ai import AIServiceError, BudgetExceededError, MockProvider, get_ai_service
from app.services.prompts import PromptService
```

- [ ] **Step 2: Add the `generate-description` endpoint**

Insert after the `_task_to_response` helper (after line 39), before the `create_task` endpoint. **This must come BEFORE the `/{task_id}` routes** because FastAPI matches routes in order — a `/generate-description` route after `/{task_id}` would never be reached:

```python
@router.post("/generate-description", response_model=TaskDescriptionGenerateResponse)
async def generate_task_description(
    data: TaskDescriptionGenerateRequest,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    prompt_service = PromptService()
    try:
        prompt_text = await prompt_service.fill_template(
            db, "task_description",
            {"course_name": data.course_name, "topic": data.title, "language": data.language},
        )
    except ValueError:
        raise HTTPException(status_code=500, detail="任务描述模板未配置")

    service = get_ai_service()
    try:
        result = await service.generate(
            db=db, prompt=prompt_text, user_id=current_user["id"],
            role=current_user["role"], endpoint="generate_description",
        )
    except BudgetExceededError:
        raise HTTPException(status_code=429, detail="今日 AI 调用额度已用完")
    except AIServiceError:
        # JSONResponse (not HTTPException) so get_db() commits the error log
        return JSONResponse(status_code=502, content={"detail": "AI 服务暂时不可用"})

    return TaskDescriptionGenerateResponse(
        description=result["text"],
        usage_log_id=result["usage_log_id"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
    )


```

- [ ] **Step 3: Run the failing test from Task 2 — expect PASS**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_task_ai_gen.py::test_generate_description_success -v`

Expected: PASS

- [ ] **Step 4: Run full test suite to verify no regressions**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/ -x -q`

Expected: All tests pass (169 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/tasks.py
git commit -m "feat(pr3): add POST /api/tasks/generate-description endpoint"
```

---

### Task 4: Add error case tests

**Files:**
- Modify: `backend/tests/test_task_ai_gen.py`

- [ ] **Step 1: Add two error case tests**

Append to `backend/tests/test_task_ai_gen.py`:

```python

@pytest.mark.asyncio(loop_scope="session")
async def test_generate_description_student_forbidden(client, db_session, setup_template):
    await create_test_user(db_session, username="student_ai_gen", role="student")
    token = await login_user(client, "student_ai_gen")

    resp = await client.post(
        "/api/tasks/generate-description",
        json={"title": "Python Web 开发"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_description_template_missing(client, db_session):
    teacher = await create_test_user(db_session, username="teacher_notpl", role="teacher")
    token = await login_user(client, "teacher_notpl")

    resp = await client.post(
        "/api/tasks/generate-description",
        json={"title": "Python Web 开发"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "任务描述模板未配置"
```

- [ ] **Step 2: Run all tests in the file**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_task_ai_gen.py -v`

Expected: All 3 tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_task_ai_gen.py
git commit -m "test(pr3): add error case tests for generate-description endpoint"
```

---

### Task 5: Update prompt template in seed data

**Files:**
- Modify: `backend/scripts/seed_demo.py` (lines 79-84)

- [ ] **Step 1: Update the `task_description` template**

In `backend/scripts/seed_demo.py`, replace lines 79-84:

```python
            PromptTemplate(
                name="task_description",
                description="生成任务描述",
                template_text="请为 {course_name} 课程生成一个关于 {topic} 的任务描述，包括目标、步骤和评分标准。语言：{language}",
                variables=json.dumps(["course_name", "topic", "language"]),
            ),
```

with the enhanced version:

```python
            PromptTemplate(
                name="task_description",
                description="生成任务描述",
                template_text=(
                    "请为「{course_name}」课程生成一个关于「{topic}」的实训任务说明草稿，要求包含以下部分：\n\n"
                    "## 任务背景\n简要说明该任务的背景和实际意义。\n\n"
                    "## 任务目标\n列出 3-5 个具体、可衡量的学习目标。\n\n"
                    "## 实施步骤\n分步骤说明学生需要完成的工作，每一步包含具体操作指导。\n\n"
                    "## 提交要求\n说明需要提交的内容、格式和命名规范。\n\n"
                    "## 评分要点\n列出评分维度（如完成度、代码质量、文档规范性等）和权重建议。\n\n"
                    "请使用{language}撰写，确保内容清晰、可操作。只输出任务说明正文，不要输出额外解释。"
                ),
                variables=json.dumps(["course_name", "topic", "language"]),
            ),
```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -c "import backend.scripts.seed_demo; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_demo.py
git commit -m "feat(pr3): enhance task_description prompt template with structured sections"
```

---

### Task 6: Frontend — AI generate button, preview dialog, and confirm flow

**Files:**
- Modify: `frontend/src/views/teacher/TaskCreate.vue`

This is the largest task. It adds the AI generation button next to the description field, a preview dialog where the teacher can review/edit the generated draft, and a confirm button that populates `form.description`.

- [ ] **Step 1: Add state variables**

In the `<script setup>` section, after `const loading = ref(false)` (line 57), add:

```javascript
const generating = ref(false)
const showAIDialog = ref(false)
const generatedDescription = ref('')
const usageLogId = ref(null)
const aiFeedback = ref(0)
```

- [ ] **Step 2: Add the AI generate button and dialog to the template**

Replace lines 8-10 (the description form-item):

```html
      <el-form-item label="任务描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
```

with:

```html
      <el-form-item label="任务描述">
        <div style="width: 100%">
          <div style="margin-bottom: 8px">
            <el-button
              type="primary"
              plain
              size="small"
              @click="generateDescription"
              :loading="generating"
              :disabled="!form.title"
            >
              AI 生成描述
            </el-button>
            <span v-if="!form.title" style="color: #909399; font-size: 12px; margin-left: 8px">
              请先输入任务标题
            </span>
          </div>
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </div>
      </el-form-item>
```

Add the preview dialog before the closing `</div>` of the template root (after `</el-form>`, before line 46's `</div>`):

```html
    <el-dialog v-model="showAIDialog" title="AI 生成的任务描述" width="700px" :close-on-click-modal="false">
      <el-input
        v-model="generatedDescription"
        type="textarea"
        :rows="15"
        placeholder="AI 正在生成..."
      />
      <div style="margin-top: 16px; display: flex; align-items: center; justify-content: space-between">
        <div>
          <span style="color: #909399; font-size: 13px">对生成结果满意吗？</span>
          <el-button-group style="margin-left: 8px">
            <el-button
              size="small"
              :type="aiFeedback === 1 ? 'primary' : 'default'"
              @click="submitAIFeedback(1)"
            >
              有用
            </el-button>
            <el-button
              size="small"
              :type="aiFeedback === -1 ? 'danger' : 'default'"
              @click="submitAIFeedback(-1)"
            >
              待改进
            </el-button>
          </el-button-group>
        </div>
        <div>
          <el-button @click="showAIDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmAIDescription">确认使用</el-button>
        </div>
      </div>
    </el-dialog>
```

- [ ] **Step 3: Add the methods**

Add after `handleSubmit` (after line 111), still inside `<script setup>`:

```javascript

async function generateDescription() {
  generating.value = true
  try {
    const courseName = form.course_id
      ? courses.value.find(c => c.id === form.course_id)?.name || '实训课程'
      : '实训课程'

    const resp = await api.post('/tasks/generate-description', {
      title: form.title,
      course_name: courseName,
      language: '中文',
    })

    generatedDescription.value = resp.data.description
    usageLogId.value = resp.data.usage_log_id
    aiFeedback.value = 0
    showAIDialog.value = true
  } catch (err) {
    if (err.response?.status === 429) {
      ElMessage.error('今日 AI 调用额度已用完')
    } else if (err.response?.status === 502) {
      ElMessage.error('AI 服务暂时不可用，请稍后再试')
    } else {
      ElMessage.error(err.response?.data?.detail || 'AI 生成失败')
    }
  } finally {
    generating.value = false
  }
}

function confirmAIDescription() {
  form.description = generatedDescription.value
  showAIDialog.value = false
  ElMessage.success('已填入 AI 生成的描述，可继续编辑')
}

async function submitAIFeedback(rating) {
  if (!usageLogId.value) return
  try {
    await api.post('/ai/feedback', {
      ai_usage_log_id: usageLogId.value,
      rating: rating,
    })
    aiFeedback.value = rating
    ElMessage.success('感谢您的反馈')
  } catch {
    ElMessage.error('反馈提交失败')
  }
}
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -5`

Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/teacher/TaskCreate.vue
git commit -m "feat(pr3): add AI task description generation with preview dialog and feedback"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] 教师任务说明辅助生成 → Task 3 (endpoint) + Task 6 (frontend button)
- [x] 生成任务背景、目标、步骤、提交要求、评分要点草稿 → Task 5 (template) + Task 3 (generation)
- [x] 教师确认后才能保存 → Task 6 (dialog with confirm button populates form.description)
- [x] 记录 AI 调用日志 → Automatic via `AIService.generate()` which calls `_log_usage()`
- [x] 记录反馈 → Task 6 (thumbs up/down calls `/api/ai/feedback`)
- [x] 不要进入学生问答和总结生成 → Not in scope, `student_qa` and `training_summary` templates untouched

**Placeholder scan:** No TBD, TODO, "implement later", or vague steps found.

**Type consistency:**
- `TaskDescriptionGenerateRequest` fields (`title: str`, `course_name: str`, `language: str`) match template variables (`topic`, `course_name`, `language`)
- `TaskDescriptionGenerateResponse` fields match what `AIService.generate()` returns (`text` → `description`, `usage_log_id`, `prompt_tokens`, `completion_tokens`)
- Frontend API call sends fields matching `TaskDescriptionGenerateRequest`
- Frontend response usage matches `TaskDescriptionGenerateResponse`
