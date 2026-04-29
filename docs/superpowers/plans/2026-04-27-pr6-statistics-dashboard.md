# PR6: Statistics Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build minimum viable statistics dashboard for admin (global overview) and teacher (own courses/tasks/submissions/grades).

**Architecture:** New `/api/dashboard` router with two GET endpoints: admin overview and teacher overview. Each returns pre-computed aggregate metrics. Frontend adds two new Dashboard.vue pages with el-statistic cards + a simple daily submission chart. No complex BI, drill-down, or export.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic, Vue 3 + Element Plus + ECharts (via CDN)

---

## Statistical Definitions (统计口径)

All metrics are computed at query time from live data. No pre-aggregation tables.

| Metric | Definition | Formula |
|--------|-----------|---------|
| total_users | All users in the system | `COUNT(*) FROM users` |
| users_by_role | User count per role | `COUNT(*) GROUP BY role` |
| total_active_courses | Courses with status='active' | `COUNT(*) FROM courses WHERE status='active'` |
| total_active_tasks | Tasks with status='active' | `COUNT(*) FROM tasks WHERE status='active'` |
| total_submissions | All submission records | `COUNT(*) FROM submissions` |
| late_submissions | Submissions where is_late=True | `COUNT(*) FROM submissions WHERE is_late=1` |
| pending_grades | Submissions without a Grade record | `COUNT of submissions LEFT JOIN grades WHERE grades.id IS NULL` |
| avg_score | Average of all Grade.score values | `AVG(score) FROM grades` |
| daily_submissions_last_7d | Submissions per day, last 7 calendar days | `COUNT(*) GROUP BY DATE(submitted_at) WHERE submitted_at >= 7_days_ago` |

**Teacher scope:** All above metrics scoped to tasks where `created_by = teacher_id`.

**Permission boundary:**
- `GET /api/dashboard/admin` → `require_role(["admin"])`
- `GET /api/dashboard/teacher` → `require_role(["teacher"])`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/schemas/dashboard.py` | Create | Response schemas for dashboard data |
| `backend/app/routers/dashboard.py` | Create | Admin + teacher dashboard endpoints |
| `backend/app/main.py` | Modify | Register dashboard router |
| `backend/tests/test_dashboard.py` | Create | All dashboard tests |
| `frontend/src/views/admin/Dashboard.vue` | Create | Admin dashboard with metric cards + chart |
| `frontend/src/views/teacher/Dashboard.vue` | Create | Teacher dashboard with metric cards + chart |
| `frontend/src/router/index.js` | Modify | Add dashboard routes |
| `frontend/src/layouts/MainLayout.vue` | Modify | Add dashboard nav items |

---

### Task 1: Schemas + failing tests (lock metrics + permissions FIRST)

**Files:**
- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/tests/test_dashboard.py`

- [ ] **Step 1: Create dashboard schemas**

Create `backend/app/schemas/dashboard.py`:

```python
from datetime import datetime
from pydantic import BaseModel


class DailyCount(BaseModel):
    date: str
    count: int


class AdminDashboardResponse(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    total_active_courses: int
    total_active_tasks: int
    total_submissions: int
    late_submissions: int
    pending_grades: int
    avg_score: float | None
    daily_submissions_last_7d: list[DailyCount]


class TeacherDashboardResponse(BaseModel):
    my_active_courses: int
    my_active_tasks: int
    my_total_submissions: int
    my_late_submissions: int
    my_pending_grades: int
    my_avg_score: float | None
    my_daily_submissions_last_7d: list[DailyCount]
```

- [ ] **Step 2: Verify schema imports**

Run: `cd /Users/gaofang/Desktop/new_project/backend && ../backend/.venv/bin/python -c "from app.schemas.dashboard import AdminDashboardResponse, TeacherDashboardResponse, DailyCount; print('OK')"`

- [ ] **Step 3: Write all failing tests**

Create `backend/tests/test_dashboard.py`:

```python
import json
import datetime

import pytest
import pytest_asyncio

from app.models.class_ import Class
from app.models.course import Course
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from tests.helpers import create_test_user, login_user, auth_headers


@pytest_asyncio.fixture(loop_scope="session")
async def setup_dashboard_env(db_session):
    admin = await create_test_user(db_session, username="admin_dash", role="admin", real_name="管理员")
    teacher = await create_test_user(db_session, username="teacher_dash", role="teacher", real_name="教师")
    other_teacher = await create_test_user(db_session, username="teacher_other_dash", role="teacher", real_name="其他教师")
    student1 = await create_test_user(db_session, username="student_dash1", role="student", real_name="学生1")
    student2 = await create_test_user(db_session, username="student_dash2", role="student", real_name="学生2")

    cls = Class(name="统计测试班", semester="2025-2026-2", teacher_id=teacher.id)
    db_session.add(cls)
    await db_session.flush()

    student1.primary_class_id = cls.id
    student2.primary_class_id = cls.id
    await db_session.flush()

    course = Course(
        name="统计测试课程", semester="2025-2026-2",
        teacher_id=teacher.id, description="用于统计测试",
    )
    db_session.add(course)
    await db_session.flush()

    task1 = Task(
        title="统计任务1", class_id=cls.id, course_id=course.id,
        created_by=teacher.id, deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".pdf"]),
    )
    task2 = Task(
        title="统计任务2", class_id=cls.id, course_id=course.id,
        created_by=teacher.id, deadline="2026-12-31 23:59:59",
        allowed_file_types=json.dumps([".pdf"]),
    )
    db_session.add_all([task1, task2])
    await db_session.flush()

    # task1: student1 submitted on time, graded
    sub1 = Submission(task_id=task1.id, student_id=student1.id, version=1, is_late=False)
    db_session.add(sub1)
    await db_session.flush()
    grade1 = Grade(submission_id=sub1.id, score=85.0, graded_by=teacher.id)
    db_session.add(grade1)

    # task1: student2 submitted late, not graded
    sub2 = Submission(task_id=task1.id, student_id=student2.id, version=1, is_late=True)
    db_session.add(sub2)

    # task2: student1 submitted on time, graded
    sub3 = Submission(task_id=task2.id, student_id=student1.id, version=1, is_late=False)
    db_session.add(sub3)
    await db_session.flush()
    grade2 = Grade(submission_id=sub3.id, score=90.0, graded_by=teacher.id)
    db_session.add(grade2)

    # task2: student2 has NOT submitted → this is a "missing" submission (not counted)

    await db_session.flush()

    return {
        "admin": admin, "teacher": teacher, "other_teacher": other_teacher,
        "student1": student1, "student2": student2,
        "cls": cls, "course": course, "tasks": [task1, task2],
    }


# --- Permission tests FIRST ---


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_dashboard_requires_admin(client, db_session, setup_dashboard_env):
    """Teacher and student cannot access admin dashboard."""
    env = setup_dashboard_env

    teacher_token = await login_user(client, "teacher_dash")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(teacher_token))
    assert resp.status_code == 403

    student_token = await login_user(client, "student_dash1")
    resp = await client.get("/api/dashboard/admin", headers=auth_headers(student_token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_requires_teacher(client, db_session, setup_dashboard_env):
    """Admin and student cannot access teacher dashboard."""
    env = setup_dashboard_env

    admin_token = await login_user(client, "admin_dash")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(admin_token))
    assert resp.status_code == 403

    student_token = await login_user(client, "student_dash1")
    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(student_token))
    assert resp.status_code == 403


# --- Admin dashboard data tests ---


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_dashboard_metrics(client, db_session, setup_dashboard_env):
    env = setup_dashboard_env
    token = await login_user(client, "admin_dash")

    resp = await client.get("/api/dashboard/admin", headers=auth_headers(token))
    assert resp.status_code == 200

    data = resp.json()
    # Total users: admin + teacher + other_teacher + student1 + student2 = 5
    assert data["total_users"] >= 5
    assert "admin" in data["users_by_role"]
    assert "teacher" in data["users_by_role"]
    assert "student" in data["users_by_role"]

    # At least 1 active course, 2 active tasks
    assert data["total_active_courses"] >= 1
    assert data["total_active_tasks"] >= 2

    # 3 submissions total (sub1, sub2, sub3)
    assert data["total_submissions"] >= 3
    # 1 late (sub2)
    assert data["late_submissions"] >= 1
    # 1 pending grade (sub2 has no Grade)
    assert data["pending_grades"] >= 1
    # Average of 85 and 90 = 87.5
    assert data["avg_score"] is not None
    assert abs(data["avg_score"] - 87.5) < 0.1

    # daily_submissions_last_7d is a list of {date, count}
    assert isinstance(data["daily_submissions_last_7d"], list)


# --- Teacher dashboard data tests ---


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_metrics(client, db_session, setup_dashboard_env):
    env = setup_dashboard_env
    token = await login_user(client, "teacher_dash")

    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(token))
    assert resp.status_code == 200

    data = resp.json()
    # Teacher owns 1 active course
    assert data["my_active_courses"] >= 1
    # Teacher created 2 active tasks
    assert data["my_active_tasks"] >= 2
    # 3 submissions to teacher's tasks
    assert data["my_total_submissions"] >= 3
    # 1 late
    assert data["my_late_submissions"] >= 1
    # 1 pending grade
    assert data["my_pending_grades"] >= 1
    # avg of 85 and 90
    assert data["my_avg_score"] is not None
    assert abs(data["my_avg_score"] - 87.5) < 0.1

    assert isinstance(data["my_daily_submissions_last_7d"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_teacher_dashboard_isolation(client, db_session, setup_dashboard_env):
    """Other teacher sees zero metrics — their data is isolated."""
    env = setup_dashboard_env
    token = await login_user(client, "teacher_other_dash")

    resp = await client.get("/api/dashboard/teacher", headers=auth_headers(token))
    assert resp.status_code == 200

    data = resp.json()
    assert data["my_active_courses"] == 0
    assert data["my_active_tasks"] == 0
    assert data["my_total_submissions"] == 0
    assert data["my_pending_grades"] == 0


# --- Empty dashboard test ---


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_dashboard_empty_system(client, db_session):
    """Admin dashboard works with no data (fresh system)."""
    admin = await create_test_user(db_session, username="admin_empty_dash", role="admin")
    token = await login_user(client, "admin_empty_dash")

    resp = await client.get("/api/dashboard/admin", headers=auth_headers(token))
    assert resp.status_code == 200

    data = resp.json()
    assert data["total_users"] >= 1  # at least the admin
    assert data["total_submissions"] == 0
    assert data["pending_grades"] == 0
    assert data["avg_score"] is None
```

- [ ] **Step 4: Run tests — expect FAIL (404/405, route does not exist)**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_dashboard.py -v`

Expected: All 6 tests fail (route does not exist).

Do NOT commit — this is the TDD red artifact.

---

### Task 2: Implement admin dashboard endpoint

**Files:**
- Create: `backend/app/routers/dashboard.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create dashboard router**

Create `backend/app/routers/dashboard.py`:

```python
import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.class_ import Class
from app.models.course import Course
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from app.schemas.dashboard import AdminDashboardResponse, DailyCount, TeacherDashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/admin", response_model=AdminDashboardResponse)
async def admin_dashboard(
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    # Users by role
    role_result = await db.execute(
        select(User.role, func.count()).group_by(User.role)
    )
    users_by_role = {role: count for role, count in role_result.all()}
    total_users = sum(users_by_role.values())

    # Active courses
    active_courses = await db.execute(
        select(func.count()).select_from(Course).where(Course.status == "active")
    )
    total_active_courses = active_courses.scalar()

    # Active tasks
    active_tasks = await db.execute(
        select(func.count()).select_from(Task).where(Task.status == "active")
    )
    total_active_tasks = active_tasks.scalar()

    # Submissions
    total_sub_result = await db.execute(
        select(func.count()).select_from(Submission)
    )
    total_submissions = total_sub_result.scalar()

    late_sub_result = await db.execute(
        select(func.count()).select_from(Submission).where(Submission.is_late == True)  # noqa: E712
    )
    late_submissions = late_sub_result.scalar()

    # Pending grades: submissions with no Grade record
    pending_result = await db.execute(
        select(func.count()).select_from(Submission)
        .outerjoin(Grade, Grade.submission_id == Submission.id)
        .where(Grade.id.is_(None))
    )
    pending_grades = pending_result.scalar()

    # Average score
    avg_result = await db.execute(select(func.avg(Grade.score)))
    avg_score = avg_result.scalar()

    # Daily submissions last 7 days
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    daily_result = await db.execute(
        select(
            func.date(Submission.submitted_at).label("date"),
            func.count().label("count"),
        )
        .where(Submission.submitted_at >= seven_days_ago)
        .group_by(func.date(Submission.submitted_at))
        .order_by(func.date(Submission.submitted_at))
    )
    daily_submissions_last_7d = [
        DailyCount(date=str(row.date), count=row.count)
        for row in daily_result.all()
    ]

    return AdminDashboardResponse(
        total_users=total_users,
        users_by_role=users_by_role,
        total_active_courses=total_active_courses,
        total_active_tasks=total_active_tasks,
        total_submissions=total_submissions,
        late_submissions=late_submissions,
        pending_grades=pending_grades,
        avg_score=round(avg_score, 2) if avg_score is not None else None,
        daily_submissions_last_7d=daily_submissions_last_7d,
    )


@router.get("/teacher", response_model=TeacherDashboardResponse)
async def teacher_dashboard(
    current_user: dict = Depends(require_role(["teacher"])),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = current_user["id"]

    # Teacher's active courses
    my_courses = await db.execute(
        select(func.count()).select_from(Course).where(
            Course.teacher_id == teacher_id, Course.status == "active",
        )
    )
    my_active_courses = my_courses.scalar()

    # Teacher's active tasks
    my_tasks = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.created_by == teacher_id, Task.status == "active",
        )
    )
    my_active_tasks = my_tasks.scalar()

    # Submissions to teacher's tasks
    my_task_ids = select(Task.id).where(Task.created_by == teacher_id)

    total_sub = await db.execute(
        select(func.count()).select_from(Submission).where(
            Submission.task_id.in_(my_task_ids)
        )
    )
    my_total_submissions = total_sub.scalar()

    late_sub = await db.execute(
        select(func.count()).select_from(Submission).where(
            Submission.task_id.in_(my_task_ids), Submission.is_late == True,  # noqa: E712
        )
    )
    my_late_submissions = late_sub.scalar()

    # Pending grades for teacher's tasks
    pending = await db.execute(
        select(func.count()).select_from(Submission)
        .outerjoin(Grade, Grade.submission_id == Submission.id)
        .where(
            Submission.task_id.in_(my_task_ids), Grade.id.is_(None),
        )
    )
    my_pending_grades = pending.scalar()

    # Average score for teacher's tasks
    avg_result = await db.execute(
        select(func.avg(Grade.score))
        .join(Submission, Submission.id == Grade.submission_id)
        .where(Submission.task_id.in_(my_task_ids))
    )
    my_avg_score = avg_result.scalar()

    # Daily submissions last 7 days for teacher's tasks
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    daily_result = await db.execute(
        select(
            func.date(Submission.submitted_at).label("date"),
            func.count().label("count"),
        )
        .where(
            Submission.task_id.in_(my_task_ids),
            Submission.submitted_at >= seven_days_ago,
        )
        .group_by(func.date(Submission.submitted_at))
        .order_by(func.date(Submission.submitted_at))
    )
    my_daily_submissions_last_7d = [
        DailyCount(date=str(row.date), count=row.count)
        for row in daily_result.all()
    ]

    return TeacherDashboardResponse(
        my_active_courses=my_active_courses,
        my_active_tasks=my_active_tasks,
        my_total_submissions=my_total_submissions,
        my_late_submissions=my_late_submissions,
        my_pending_grades=my_pending_grades,
        my_avg_score=round(my_avg_score, 2) if my_avg_score is not None else None,
        my_daily_submissions_last_7d=my_daily_submissions_last_7d,
    )
```

- [ ] **Step 2: Register router in main.py**

Add to `backend/app/main.py` imports (around line 17):

```python
from app.routers import dashboard as dashboard_router
```

Add to router registrations (around line 57):

```python
app.include_router(dashboard_router.router)
```

- [ ] **Step 3: Run dashboard tests — expect PASS**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/test_dashboard.py -v`

Expected: All 6 tests pass.

- [ ] **Step 4: Run full suite — no regressions**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/ -x -q`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add backend/app/schemas/dashboard.py backend/app/routers/dashboard.py backend/app/main.py backend/tests/test_dashboard.py && git commit -m "feat(pr6): add admin and teacher dashboard endpoints with permission tests"
```

---

### Task 3: Admin Dashboard frontend

**Files:**
- Create: `frontend/src/views/admin/Dashboard.vue`

- [ ] **Step 1: Create admin dashboard page**

Create `frontend/src/views/admin/Dashboard.vue`:

```vue
<template>
  <div v-loading="loading">
    <h3 style="margin-bottom: 16px">系统概览</h3>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="用户总数" :value="data.total_users" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="活跃课程" :value="data.total_active_courses" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="活跃任务" :value="data.total_active_tasks" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总提交数" :value="data.total_submissions" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="迟交数" :value="data.late_submissions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="待评分" :value="data.pending_grades" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic
            title="平均分"
            :value="data.avg_score ?? '-'"
            :precision="1"
          />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="margin-bottom: 8px; color: #909399; font-size: 13px">用户分布</div>
          <div v-for="(count, role) in data.users_by_role" :key="role" style="font-size: 14px; margin-bottom: 4px">
            {{ roleLabel(role) }}：{{ count }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover">
      <template #header><span>近 7 天提交趋势</span></template>
      <div ref="chartRef" style="height: 300px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const loading = ref(false)
const chartRef = ref(null)
const data = ref({
  total_users: 0, users_by_role: {}, total_active_courses: 0,
  total_active_tasks: 0, total_submissions: 0, late_submissions: 0,
  pending_grades: 0, avg_score: null, daily_submissions_last_7d: [],
})

function roleLabel(role) {
  const map = { admin: '管理员', teacher: '教师', student: '学生' }
  return map[role] || role
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/dashboard/admin')
    data.value = resp.data
    await nextTick()
    renderChart(data.value.daily_submissions_last_7d)
  } catch {
    ElMessage.error('获取统计数据失败')
  } finally {
    loading.value = false
  }
})

function renderChart(dailyData) {
  if (!chartRef.value || !window.echarts) return
  const chart = window.echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dailyData.map(d => d.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: dailyData.map(d => d.count), itemStyle: { color: '#409eff' } }],
  })
  window.addEventListener('resize', () => chart.resize())
}
</script>
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -5`

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/admin/Dashboard.vue && git commit -m "feat(pr6): add admin Dashboard.vue with metric cards and daily chart"
```

---

### Task 4: Teacher Dashboard frontend

**Files:**
- Create: `frontend/src/views/teacher/Dashboard.vue`

- [ ] **Step 1: Create teacher dashboard page**

Create `frontend/src/views/teacher/Dashboard.vue`:

```vue
<template>
  <div v-loading="loading">
    <h3 style="margin-bottom: 16px">教学概览</h3>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="我的课程" :value="data.my_active_courses" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="我的任务" :value="data.my_active_tasks" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总提交数" :value="data.my_total_submissions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="待评分" :value="data.my_pending_grades">
            <template #suffix>
              <el-tag v-if="data.my_pending_grades > 0" type="warning" size="small" style="margin-left: 8px">需处理</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="迟交数" :value="data.my_late_submissions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic
            title="平均分"
            :value="data.my_avg_score ?? '-'"
            :precision="1"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover">
      <template #header><span>近 7 天提交趋势</span></template>
      <div ref="chartRef" style="height: 300px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const loading = ref(false)
const chartRef = ref(null)
const data = ref({
  my_active_courses: 0, my_active_tasks: 0, my_total_submissions: 0,
  my_late_submissions: 0, my_pending_grades: 0, my_avg_score: null,
  my_daily_submissions_last_7d: [],
})

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/dashboard/teacher')
    data.value = resp.data
    await nextTick()
    renderChart(data.value.my_daily_submissions_last_7d)
  } catch {
    ElMessage.error('获取统计数据失败')
  } finally {
    loading.value = false
  }
})

function renderChart(dailyData) {
  if (!chartRef.value || !window.echarts) return
  const chart = window.echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dailyData.map(d => d.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: dailyData.map(d => d.count), itemStyle: { color: '#67c23a' } }],
  })
  window.addEventListener('resize', () => chart.resize())
}
</script>
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -5`

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/teacher/Dashboard.vue && git commit -m "feat(pr6): add teacher Dashboard.vue with metric cards and daily chart"
```

---

### Task 5: Routes + navigation

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/index.html` (add ECharts CDN)

- [ ] **Step 1: Add dashboard routes to router**

In `frontend/src/router/index.js`, add BEFORE the existing admin/teacher routes:

For admin, before the `admin/users` route (around line 95):
```javascript
      {
        path: 'admin/dashboard',
        name: 'AdminDashboard',
        component: () => import('../views/admin/Dashboard.vue'),
        meta: { roles: ['admin'] },
      },
```

For teacher, before the `teacher/courses` route (around line 83):
```javascript
      {
        path: 'teacher/dashboard',
        name: 'TeacherDashboard',
        component: () => import('../views/teacher/Dashboard.vue'),
        meta: { roles: ['teacher'] },
      },
```

- [ ] **Step 2: Add sidebar nav items**

In `frontend/src/layouts/MainLayout.vue`, add dashboard menu items as the FIRST item in each role's template:

In the teacher template (before line 15 `<el-menu-item index="/teacher/courses">`):
```html
          <el-menu-item index="/teacher/dashboard">
            <span>教学概览</span>
          </el-menu-item>
```

In the admin template (before line 34 `<el-menu-item index="/admin/users">`):
```html
          <el-menu-item index="/admin/dashboard">
            <span>系统概览</span>
          </el-menu-item>
```

- [ ] **Step 3: Add ECharts CDN to index.html**

In `frontend/index.html`, add before `</head>`:
```html
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -5`

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/router/index.js frontend/src/layouts/MainLayout.vue frontend/index.html && git commit -m "feat(pr6): add dashboard routes, nav items, and ECharts CDN"
```

---

### Task 6: Regression + polish

**Files:**
- Modify: `frontend/src/router/index.js` (update default routes)

- [ ] **Step 1: Update default redirect routes**

In `frontend/src/router/index.js`, find the teacher and admin redirect/home routes. Update the teacher's default page from tasks to dashboard, and admin's from users to dashboard. Look for route guards or initial redirect logic and update the teacher to point to `/teacher/dashboard` and admin to `/admin/dashboard`.

If there's a `router.beforeEach` guard that redirects to a default route, update:
- admin default: `/admin/dashboard`
- teacher default: `/teacher/dashboard`

- [ ] **Step 2: Run full backend test suite**

Run: `cd /Users/gaofang/Desktop/new_project && backend/.venv/bin/python -m pytest backend/tests/ -v --tb=short 2>&1 | tail -20`

Expected: All tests pass (baseline 199+ = 193 existing + 6 new dashboard tests).

- [ ] **Step 3: Run full frontend build**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build 2>&1 | tail -5`

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/router/index.js && git commit -m "feat(pr6): set dashboard as default landing page for admin and teacher"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] 基础统计看板最小版 → Tasks 2-4 (backend + frontend)
- [x] admin 查看全局概览 → Task 2 (admin endpoint) + Task 3 (admin page)
- [x] teacher 查看本人相关概览 → Task 2 (teacher endpoint) + Task 4 (teacher page)
- [x] 最小指标卡 + 简单趋势 → el-statistic cards + ECharts bar chart (daily submissions)
- [x] 明确统计口径 → Defined in table above, implemented in queries
- [x] 权限隔离 → Task 1 tests (admin-only, teacher-only, data isolation)
- [x] 回归测试 + polish → Task 6

**Placeholder scan:** No TBD, TODO, "implement later", or vague steps found.

**Type consistency:**
- `AdminDashboardResponse` fields match endpoint return values
- `TeacherDashboardResponse` fields match endpoint return values
- `DailyCount` used consistently in both endpoints and schemas
- Frontend field names match backend response keys
