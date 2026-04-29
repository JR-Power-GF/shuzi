# PR4: Student Task Q&A Assistant

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable students to ask questions about their assigned tasks, with AI answers strictly grounded in the task's context (title, description, requirements, course name). When the AI cannot answer from context alone, it must clearly say so.

**Architecture:** New `POST /api/tasks/{task_id}/qa` endpoint. The endpoint first verifies the student is assigned to the task's class, then builds a context dict from the task + course, fills the existing `student_qa` prompt template via `PromptService.fill_template()`, and calls `AIService.generate()`. The frontend adds a collapsible Q&A panel inside `TaskDetail.vue` with a chat-like input, message history, and thumbs-up/down feedback.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic, PromptService, AIService (DeepSeek), Vue 3 + Element Plus

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/schemas/task.py` | Modify | Add `TaskQARequest`, `TaskQAResponse` |
| `backend/app/routers/tasks.py` | Modify | Add `POST /{task_id}/qa` endpoint |
| `backend/tests/test_task_qa.py` | Create | Tests for the new endpoint |
| `backend/scripts/seed_demo.py` | Modify | Enhance `student_qa` template with stronger grounding instructions |
| `frontend/src/views/student/TaskDetail.vue` | Modify | Add Q&A chat panel with feedback buttons |

---

### Task 1: Add request/response schemas

**Files:**
- Modify: `backend/app/schemas/task.py` (append after line 63)

- [ ] **Step 1: Add the two new schemas**

Append after line 63 (after `TaskDescriptionGenerateResponse`):

```python


class TaskQARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class TaskQAResponse(BaseModel):
    answer: str
    usage_log_id: int
    prompt_tokens: int
    completion_tokens: int
```

Note: `Field` is already imported from pydantic on line 5.

- [ ] **Step 2: Verify no syntax errors**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -c "from backend.app.schemas.task import TaskQARequest, TaskQAResponse; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/task.py
git commit -m "feat(pr4): add student Q&A request/response schemas"
```

---

### Task 2: Write failing test for Q&A endpoint

**Files:**
- Create: `backend/tests/test_task_qa.py`

- [ ] **Step 1: Write the test file**

Create `backend/tests/test_task_qa.py`:

```python
import json

import pytest
import pytest_asyncio

from app.models.class_ import Class
from app.models.course import Course
from app.models.prompt_template import PromptTemplate
from app.models.task import Task
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_qa_env(db_session):
    teacher = await create_test_user(db_session, username="teacher_qa", role="teacher")
    student = await create_test_user(db_session, username="student_qa", role="student")
    other_student = await create_test_user(db_session, username="student_other_qa", role="student")

    cls = Class(name="Q&A测试班", semester="2025-2026-2", teacher_id=teacher.id)
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

    task = Task(
        title="Flask Web开发实践",
        description="使用Flask框架开发一个简单的Web应用",
        requirements="提交完整的源代码和实验报告",
        class_id=cls.id, course_id=course.id,
        created_by=teacher.id,
        deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".zip", ".pdf"]),
    )
    db_session.add(task)
    await db_session.flush()

    template = PromptTemplate(
        name="student_qa",
        description="学生任务问答",
        template_text="根据以下任务信息回答学生的问题。只使用提供的上下文，不要编造信息。\n\n任务：{task_title}\n描述：{task_description}\n要求：{task_requirements}\n课程：{course_name}\n\n学生问题：{question}",
        variables=json.dumps(["task_title", "task_description", "task_requirements", "course_name", "question"]),
    )
    db_session.add(template)
    await db_session.flush()

    return {
        "teacher": teacher, "student": student, "other_student": other_student,
        "cls": cls, "course": course, "task": task,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_success(client, db_session, setup_qa_env):
    env = setup_qa_env
    token = await login_user(client, "student_qa")

    resp = await client.post(
        f"/api/tasks/{env['task'].id}/qa",
        json={"question": "需要提交什么格式？"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert len(data["answer"]) > 0
    assert "usage_log_id" in data
    assert isinstance(data["usage_log_id"], int)
    assert "prompt_tokens" in data
    assert "completion_tokens" in data
```

- [ ] **Step 2: Run the test — expect it to FAIL (405, route does not exist)**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_task_qa.py::test_qa_success -v`

Expected: FAIL — the endpoint `/api/tasks/{task_id}/qa` does not exist yet.

Do NOT commit — this is the TDD red artifact.

---

### Task 3: Implement the Q&A endpoint

**Files:**
- Modify: `backend/app/routers/tasks.py` (add imports and endpoint)

- [ ] **Step 1: Add new schema imports**

In `backend/app/routers/tasks.py`, update the import block on lines 17-20. Change:

```python
from app.schemas.task import (
    TaskCreate, TaskDescriptionGenerateRequest, TaskDescriptionGenerateResponse,
    TaskResponse, TaskUpdate,
)
```

to:

```python
from app.schemas.task import (
    TaskCreate, TaskDescriptionGenerateRequest, TaskDescriptionGenerateResponse,
    TaskQARequest, TaskQAResponse, TaskResponse, TaskUpdate,
)
```

- [ ] **Step 2: Add the Q&A endpoint**

Insert after the `generate_task_description` endpoint (which ends around line 80), before the `create_task` endpoint. This must be placed BEFORE the `GET /{task_id}` route to avoid path parameter shadowing:

```python
@router.post("/{task_id}/qa", response_model=TaskQAResponse)
async def ask_task_question(
    task_id: int,
    data: TaskQARequest,
    current_user: dict = Depends(require_role(["student"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    user_result = await db.execute(
        select(User.primary_class_id).where(User.id == current_user["id"])
    )
    class_id = user_result.scalar_one_or_none()
    if not class_id or class_id != task.class_id:
        raise HTTPException(status_code=403, detail="无权访问该任务")

    course_name = ""
    if task.course_id:
        course_result = await db.execute(select(Course.name).where(Course.id == task.course_id))
        course_name = course_result.scalar_one_or_none() or ""

    prompt_service = PromptService()
    try:
        prompt_text = await prompt_service.fill_template(
            db, "student_qa",
            {
                "task_title": task.title or "",
                "task_description": task.description or "",
                "task_requirements": task.requirements or "",
                "course_name": course_name,
                "question": data.question,
            },
        )
    except ValueError:
        raise HTTPException(status_code=500, detail="问答模板未配置")

    service = get_ai_service()
    try:
        ai_result = await service.generate(
            db=db, prompt=prompt_text, user_id=current_user["id"],
            role=current_user["role"], endpoint="student_qa",
        )
    except BudgetExceededError:
        raise HTTPException(status_code=429, detail="今日 AI 调用额度已用完")
    except AIServiceError:
        return JSONResponse(status_code=502, content={"detail": "AI 服务暂时不可用"})

    return TaskQAResponse(
        answer=ai_result["text"],
        usage_log_id=ai_result["usage_log_id"],
        prompt_tokens=ai_result["prompt_tokens"],
        completion_tokens=ai_result["completion_tokens"],
    )


```

- [ ] **Step 3: Run the failing test from Task 2 — expect PASS**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_task_qa.py::test_qa_success -v`

Expected: PASS

- [ ] **Step 4: Run full test suite — no regressions**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/ -x -q`

Expected: All tests pass (173 tests — 172 existing + 1 new)

- [ ] **Step 5: Commit both test and endpoint**

```bash
git add backend/tests/test_task_qa.py backend/app/routers/tasks.py
git commit -m "feat(pr4): add POST /api/tasks/{task_id}/qa endpoint with TDD test"
```

---

### Task 4: Add error case tests

**Files:**
- Modify: `backend/tests/test_task_qa.py`

- [ ] **Step 1: Add four error case tests**

Append to `backend/tests/test_task_qa.py`:

```python

@pytest.mark.asyncio(loop_scope="session")
async def test_qa_teacher_forbidden(client, db_session, setup_qa_env):
    env = setup_qa_env
    token = await login_user(client, "teacher_qa")

    resp = await client.post(
        f"/api/tasks/{env['task'].id}/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_other_class_student_forbidden(client, db_session, setup_qa_env):
    env = setup_qa_env
    token = await login_user(client, "student_other_qa")

    resp = await client.post(
        f"/api/tasks/{env['task'].id}/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_task_not_found(client, db_session, setup_qa_env):
    token = await login_user(client, "student_qa")

    resp = await client.post(
        "/api/tasks/99999/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_qa_template_missing(client, db_session):
    student = await create_test_user(db_session, username="student_notpl", role="student")
    teacher = await create_test_user(db_session, username="teacher_notpl_qa", role="teacher")
    cls = Class(name="无模板班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()
    student.primary_class_id = cls.id
    await db_session.flush()
    task = Task(
        title="测试任务", class_id=cls.id, created_by=teacher.id,
        deadline="2026-12-31 23:59:59", allowed_file_types=json.dumps([".pdf"]),
    )
    db_session.add(task)
    await db_session.flush()

    token = await login_user(client, "student_notpl")
    resp = await client.post(
        f"/api/tasks/{task.id}/qa",
        json={"question": "测试问题"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "问答模板未配置"
```

- [ ] **Step 2: Run all tests in the file**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_task_qa.py -v`

Expected: All 5 tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_task_qa.py
git commit -m "test(pr4): add error case tests for student Q&A endpoint"
```

---

### Task 5: Enhance student_qa prompt template

**Files:**
- Modify: `backend/scripts/seed_demo.py` (lines 93-98)

- [ ] **Step 1: Replace the `student_qa` template**

In `backend/scripts/seed_demo.py`, replace lines 93-98:

```python
            PromptTemplate(
                name="student_qa",
                description="学生任务问答",
                template_text="根据以下任务信息回答学生的问题。只使用提供的上下文，不要编造信息。\n\n任务：{task_title}\n描述：{task_description}\n要求：{task_requirements}\n课程：{course_name}\n\n学生问题：{question}",
                variables=json.dumps(["task_title", "task_description", "task_requirements", "course_name", "question"]),
            ),
```

with:

```python
            PromptTemplate(
                name="student_qa",
                description="学生任务问答",
                template_text=(
                    "你是课程助教，根据以下任务信息回答学生的问题。\n\n"
                    "## 可用上下文\n"
                    "课程：{course_name}\n"
                    "任务：{task_title}\n"
                    "描述：{task_description}\n"
                    "要求：{task_requirements}\n\n"
                    "## 严格规则\n"
                    "1. 只使用上方提供的上下文信息回答问题，不要使用外部知识\n"
                    "2. 如果上下文信息不足以回答问题，明确回复「根据当前任务信息无法回答这个问题，建议咨询任课教师。」\n"
                    "3. 不要编造、推测或补充任何上下文中未提及的内容\n"
                    "4. 用简洁清晰的中文回答\n\n"
                    "学生问题：{question}"
                ),
                variables=json.dumps(["task_title", "task_description", "task_requirements", "course_name", "question"]),
            ),
```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -c "import backend.scripts.seed_demo; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_demo.py
git commit -m "feat(pr4): enhance student_qa prompt with strict grounding rules"
```

---

### Task 6: Frontend — Q&A chat panel in TaskDetail.vue

**Files:**
- Modify: `frontend/src/views/student/TaskDetail.vue`

This adds a collapsible Q&A panel below the submission section. Students type a question, see the AI answer in a chat-like display, and can give thumbs-up/down feedback.

- [ ] **Step 1: Add state variables**

After `const uploadRef = ref(null)` (line 51), add:

```javascript
const showQAPanel = ref(false)
const qaQuestion = ref('')
const qaLoading = ref(false)
const qaMessages = ref([])
const qaUsageLogId = ref(null)
const qaFeedback = ref(0)
```

- [ ] **Step 2: Add the Q&A panel to the template**

After the submit button block (after line 31, before `</div>` that closes the `v-if="task"` block), add:

```html

      <el-divider />

      <div style="display: flex; align-items: center; justify-content: space-between">
        <h4>任务问答助手</h4>
        <el-button size="small" @click="showQAPanel = !showQAPanel">
          {{ showQAPanel ? '收起' : '展开' }}
        </el-button>
      </div>

      <div v-if="showQAPanel" style="margin-top: 12px">
        <div
          v-for="(msg, idx) in qaMessages"
          :key="idx"
          :style="{
            display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '12px',
          }"
        >
          <div
            :style="{
              maxWidth: '80%', padding: '10px 14px', borderRadius: '8px',
              backgroundColor: msg.role === 'user' ? '#409eff' : '#f4f4f5',
              color: msg.role === 'user' ? '#fff' : '#303133',
            }"
          >
            <div style="white-space: pre-wrap">{{ msg.content }}</div>
            <div v-if="msg.role === 'assistant' && msg.usageLogId" style="margin-top: 8px; text-align: right">
              <el-button-group>
                <el-button
                  size="small"
                  :type="msg.feedback === 1 ? 'primary' : 'default'"
                  @click="submitQAFeedback(idx, 1)"
                >
                  有用
                </el-button>
                <el-button
                  size="small"
                  :type="msg.feedback === -1 ? 'danger' : 'default'"
                  @click="submitQAFeedback(idx, -1)"
                >
                  待改进
                </el-button>
              </el-button-group>
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 8px; margin-top: 8px">
          <el-input
            v-model="qaQuestion"
            placeholder="输入你关于这个任务的问题..."
            @keyup.enter="askQuestion"
            :disabled="qaLoading"
          />
          <el-button type="primary" @click="askQuestion" :loading="qaLoading" :disabled="!qaQuestion.trim()">
            提问
          </el-button>
        </div>
      </div>
```

- [ ] **Step 3: Add the methods**

After `handleSubmit` (after line 93, before `</script>`), add:

```javascript

async function askQuestion() {
  const question = qaQuestion.value.trim()
  if (!question) return

  qaMessages.value.push({ role: 'user', content: question })
  qaQuestion.value = ''
  qaLoading.value = true

  try {
    const resp = await api.post(`/tasks/${taskId}/qa`, { question })
    qaMessages.value.push({
      role: 'assistant',
      content: resp.data.answer,
      usageLogId: resp.data.usage_log_id,
      feedback: 0,
    })
  } catch (err) {
    if (err.response?.status === 429) {
      qaMessages.value.push({ role: 'assistant', content: '今日 AI 调用额度已用完，请明天再试。', usageLogId: null, feedback: 0 })
    } else if (err.response?.status === 502) {
      qaMessages.value.push({ role: 'assistant', content: 'AI 服务暂时不可用，请稍后再试。', usageLogId: null, feedback: 0 })
    } else {
      qaMessages.value.push({ role: 'assistant', content: err.response?.data?.detail || '问答失败，请重试。', usageLogId: null, feedback: 0 })
    }
  } finally {
    qaLoading.value = false
  }
}

async function submitQAFeedback(messageIndex, rating) {
  const msg = qaMessages.value[messageIndex]
  if (!msg?.usageLogId) return
  try {
    await api.post('/ai/feedback', { ai_usage_log_id: msg.usageLogId, rating })
    msg.feedback = rating
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
git add frontend/src/views/student/TaskDetail.vue
git commit -m "feat(pr4): add student Q&A chat panel with feedback in TaskDetail"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] 学生任务问答助手 → Task 3 (endpoint) + Task 6 (frontend chat panel)
- [x] 只能使用当前课程/项目/任务及授权材料作为上下文 → Task 3 (builds context from task+course only) + Task 5 (template enforces context-only answers)
- [x] 无依据时要明确拒答或提示信息不足 → Task 5 (template rule #2: explicit refusal message)
- [x] 记录 AI 调用日志 → Automatic via `AIService.generate()` which calls `_log_usage()`
- [x] 记录用户反馈 → Task 6 (thumbs up/down calls `/api/ai/feedback`)

**Permission boundaries:**
- [x] Only students can call Q&A endpoint (`require_role(["student"])`)
- [x] Student must belong to the task's class (verified by `primary_class_id` match)
- [x] Teacher and other-class students get 403 (tested in Task 4)

**Placeholder scan:** No TBD, TODO, "implement later", or vague steps found.

**Type consistency:**
- `TaskQARequest` field `question` matches the `question` variable in the `student_qa` template
- `TaskQAResponse` fields match what `AIService.generate()` returns (`text` → `answer`, `usage_log_id`, `prompt_tokens`, `completion_tokens`)
- Frontend API call sends `{ question }` matching `TaskQARequest`
- Frontend response uses `resp.data.answer`, `resp.data.usage_log_id` matching `TaskQAResponse`
