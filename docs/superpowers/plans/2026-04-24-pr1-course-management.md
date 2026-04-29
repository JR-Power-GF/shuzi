# PR1: Course Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship course CRUD, task-course linking, student course cards. Foundation for AI context boundaries in later PRs.

**Architecture:** Course is a flat table with teacher ownership and archive-only lifecycle (no delete). Student course visibility is derived through the task-class join — no enrollment table. Task gains a nullable `course_id` FK (backward compatible).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, MySQL 8, Alembic, Pydantic v2, pytest-asyncio, Vue 3 + Element Plus

---

## File Structure

### Backend — Create
- `backend/app/models/course.py` — Course SQLAlchemy model
- `backend/app/schemas/course.py` — CourseCreate, CourseUpdate, CourseResponse, CourseDetailResponse, CourseProgressResponse
- `backend/app/routers/courses.py` — Course CRUD endpoints
- `backend/tests/test_courses.py` — All course endpoint tests
- `backend/tests/test_task_course_linking.py` — Task-course linking tests
- `backend/alembic/versions/XXXX_add_courses_table.py` — courses table migration
- `backend/alembic/versions/XXXX_add_course_id_to_tasks.py` — nullable FK on tasks

### Backend — Modify
- `backend/app/models/__init__.py` — Register Course model
- `backend/app/models/task.py` — Add nullable course_id column
- `backend/app/schemas/task.py` — Add course_id to TaskCreate, TaskUpdate, TaskResponse
- `backend/app/routers/tasks.py` — Add course_id to create/update, filter archived course tasks, add course filter
- `backend/app/main.py` — Include courses router
- `backend/scripts/seed_demo.py` — Add course seed data

### Frontend — Create
- `frontend/src/views/teacher/CourseList.vue` — Teacher's courses table
- `frontend/src/views/teacher/CourseCreate.vue` — Course creation form
- `frontend/src/views/teacher/CourseDetail.vue` — Course detail + task list
- `frontend/src/views/admin/CourseList.vue` — All courses with filters
- `frontend/src/views/student/CourseList.vue` — Card-based home page

### Frontend — Modify
- `frontend/src/views/teacher/TaskCreate.vue` — Add course selector
- `frontend/src/views/teacher/TaskEdit.vue` — Add course selector
- `frontend/src/router/index.js` — Add course routes
- `frontend/src/layouts/MainLayout.vue` — Add sidebar entries

---

## Task 1: Course Model

**Files:**
- Create: `backend/app/models/course.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create Course model**

Create `backend/app/models/course.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="chk_course_status"),
        UniqueConstraint("name", "semester", "teacher_id", name="uq_course_name_semester_teacher"),
    )
```

- [ ] **Step 2: Register in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.course import Course
```

And add `"Course"` to `__all__`.

- [ ] **Step 3: Verify model loads**

Run: `cd backend && python -c "from app.models import Course; print(Course.__tablename__)"`
Expected: `courses`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/course.py backend/app/models/__init__.py
git commit -m "feat: add Course model with archive lifecycle and unique constraint"
```

---

## Task 2: Courses Table Migration

**Files:**
- Create: `backend/alembic/versions/XXXX_add_courses_table.py`

- [ ] **Step 1: Generate migration**

Run: `cd backend && alembic revision -m "add_courses_table" --autogenerate`

If autogenerate picks it up, verify the generated file. Otherwise, write manually.

- [ ] **Step 2: Write or verify migration**

The migration should create the `courses` table matching the model:

```python
def upgrade() -> None:
    op.create_table('courses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('semester', sa.String(length=20), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('active', 'archived')", name='chk_course_status'),
        sa.UniqueConstraint('name', 'semester', 'teacher_id', name='uq_course_name_semester_teacher'),
    )
    op.create_index('ix_courses_teacher_id', 'courses', ['teacher_id'])


def downgrade() -> None:
    op.drop_index('ix_courses_teacher_id', table_name='courses')
    op.drop_table('courses')
```

Set `revision` to a unique hex string and `down_revision` to `'513402d511d6'` (the initial migration).

- [ ] **Step 3: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: No errors.

- [ ] **Step 4: Verify table exists**

Run: `cd backend && python -c "import asyncio; from sqlalchemy import text; from app.database import engine; async def check():
    async with engine.connect() as c:
        r = await c.execute(text('DESCRIBE courses'))
        for row in r: print(row)
asyncio.run(check())"`
Expected: Shows courses table columns.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: add courses table migration"
```

---

## Task 3: Course Schemas

**Files:**
- Create: `backend/app/schemas/course.py`

- [ ] **Step 1: Create schemas file**

Create `backend/app/schemas/course.py`:

```python
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class CourseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    semester: str


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    semester: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    semester: str
    teacher_id: int
    teacher_name: Optional[str] = None
    status: str
    task_count: int = 0
    created_at: datetime
    updated_at: datetime


class CourseDetailResponse(CourseResponse):
    tasks: List[dict] = []


class CourseProgressResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    semester: str
    teacher_name: Optional[str] = None
    task_count: int = 0
    submitted_count: int = 0
    graded_count: int = 0
    nearest_deadline: Optional[datetime] = None
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.schemas.course import CourseCreate; print(CourseCreate(name='test', semester='2026-2027-1'))"`
Expected: Prints the model instance.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/course.py
git commit -m "feat: add course schemas (create, update, response, progress)"
```

---

## Task 4: Course Router — Create Endpoint

**Files:**
- Create: `backend/app/routers/courses.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing test for create course success**

Create `backend/tests/test_courses.py`:

```python
import pytest
from tests.helpers import create_test_user, create_test_class, login_user, auth_headers


@pytest.mark.asyncio(loop_scope="session")
async def test_create_course_success(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/courses",
        json={
            "name": "Python程序设计",
            "description": "Python基础编程课程",
            "semester": "2026-2027-1",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Python程序设计"
    assert data["semester"] == "2026-2027-1"
    assert data["teacher_id"] == teacher.id
    assert data["status"] == "active"
    assert data["task_count"] == 0
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_courses.py::test_create_course_success -v`
Expected: FAIL (404 — router not registered)

- [ ] **Step 3: Implement create endpoint**

Create `backend/app/routers/courses.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.course import Course
from app.models.user import User
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, CourseDetailResponse, CourseProgressResponse

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _course_to_response(course: Course, teacher_name: str = "", task_count: int = 0) -> CourseResponse:
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        semester=course.semester,
        teacher_id=course.teacher_id,
        teacher_name=teacher_name,
        status=course.status,
        task_count=task_count,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    teacher_id = current_user["id"]

    existing = await db.execute(
        select(Course).where(
            Course.name == data.name,
            Course.semester == data.semester,
            Course.teacher_id == teacher_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="同一学期已存在同名课程")

    course = Course(
        name=data.name,
        description=data.description,
        semester=data.semester,
        teacher_id=teacher_id,
    )
    db.add(course)
    await db.flush()

    teacher_name_result = await db.execute(select(User.real_name).where(User.id == teacher_id))
    teacher_name = teacher_name_result.scalar_one()
    return _course_to_response(course, teacher_name)
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import courses as courses_router
```

And add:

```python
app.include_router(courses_router.router)
```

- [ ] **Step 5: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_courses.py::test_create_course_success -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/courses.py backend/app/main.py backend/tests/test_courses.py
git commit -m "feat: add course creation endpoint with duplicate check"
```

---

## Task 5: Course Create — Permission & Validation Tests

**Files:**
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing test for student 403**

Append to `backend/tests/test_courses.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_create_course_student_forbidden(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.post(
        "/api/courses",
        json={"name": "test", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_courses.py::test_create_course_student_forbidden -v`
Expected: PASS (require_role already enforces this)

- [ ] **Step 3: Write test for duplicate course name 409**

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_create_course_duplicate_name(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    resp1 = await client.post(
        "/api/courses",
        json={"name": "Python程序设计", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/courses",
        json={"name": "Python程序设计", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    assert resp2.status_code == 409
    assert "同一学期已存在同名课程" in resp2.json()["detail"]
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_courses.py::test_create_course_duplicate_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_courses.py
git commit -m "test: add course creation permission and duplicate name tests"
```

---

## Task 6: Course Update Endpoint

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing tests for update**

Append to `backend/tests/test_courses.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_update_course_own(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/courses/{course_id}",
        json={"name": "课程B", "description": "更新描述"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "课程B"
    assert resp.json()["description"] == "更新描述"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_course_other_teacher_forbidden(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    token1 = await login_user(client, "teacher1")
    token2 = await login_user(client, "teacher2")

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token1),
    )
    course_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/courses/{course_id}",
        json={"name": "hacked"},
        headers=auth_headers(token2),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_update_course_admin_can_edit(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    admin = await create_test_user(db_session, username="admin1", role="admin")
    token_t = await login_user(client, "teacher1")
    token_a = await login_user(client, "admin1")

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token_t),
    )
    course_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/courses/{course_id}",
        json={"name": "管理员修改"},
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "管理员修改"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_courses.py::test_update_course_own -v`
Expected: FAIL (405 — endpoint doesn't exist)

- [ ] **Step 3: Implement update endpoint**

Add to `backend/app/routers/courses.py`:

```python
@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    data: CourseUpdate,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    if current_user["role"] != "admin" and course.teacher_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能编辑自己的课程")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)
    await db.flush()

    teacher_name_result = await db.execute(select(User.real_name).where(User.id == course.teacher_id))
    teacher_name = teacher_name_result.scalar_one()
    return _course_to_response(course, teacher_name)
```

- [ ] **Step 4: Run all update tests**

Run: `cd backend && python -m pytest tests/test_courses.py -k "update" -v`
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_courses.py
git commit -m "feat: add course update endpoint with ownership check"
```

---

## Task 7: Course Archive Endpoint

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_courses.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_archive_course_own(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/courses/{course_id}/archive",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@pytest.mark.asyncio(loop_scope="session")
async def test_archive_course_other_teacher_forbidden(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    token1 = await login_user(client, "teacher1")
    token2 = await login_user(client, "teacher2")

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token1),
    )
    course_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/courses/{course_id}/archive",
        headers=auth_headers(token2),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_course_not_allowed(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/courses/{course_id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 405
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_courses.py -k "archive" -v`
Expected: FAIL

- [ ] **Step 3: Implement archive endpoint and 405 handler**

Add to `backend/app/routers/courses.py`:

```python
@router.post("/{course_id}/archive")
async def archive_course(
    course_id: int,
    current_user: dict = Depends(require_role(["teacher", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    if current_user["role"] != "admin" and course.teacher_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能归档自己的课程")

    course.status = "archived"
    await db.flush()
    return {"id": course.id, "status": "archived"}


@router.delete("/{course_id}", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)
async def delete_course():
    raise HTTPException(status_code=405, detail="课程不支持删除，请使用归档")
```

- [ ] **Step 4: Run archive and delete tests**

Run: `cd backend && python -m pytest tests/test_courses.py -k "archive or delete_course" -v`
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_courses.py
git commit -m "feat: add course archive endpoint, block delete with 405"
```

---

## Task 8: Course List — Teacher Own Courses

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_courses.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_list_courses_teacher_own(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    token1 = await login_user(client, "teacher1")
    token2 = await login_user(client, "teacher2")

    await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token1),
    )
    await client.post(
        "/api/courses",
        json={"name": "课程B", "semester": "2025-2026-2"},
        headers=auth_headers(token1),
    )
    await client.post(
        "/api/courses",
        json={"name": "课程C", "semester": "2026-2027-1"},
        headers=auth_headers(token2),
    )

    resp = await client.get("/api/courses", headers=auth_headers(token1))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {c["name"] for c in data}
    assert names == {"课程A", "课程B"}
    assert data[0]["teacher_name"] is not None
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_courses.py::test_list_courses_teacher_own -v`
Expected: FAIL

- [ ] **Step 3: Implement list endpoint**

Add to `backend/app/routers/courses.py` (add `from app.models.task import Task` to imports at top):

```python
@router.get("", response_model=list[CourseResponse])
async def list_courses(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "admin":
        result = await db.execute(
            select(Course).order_by(Course.semester.desc(), Course.name)
        )
    elif current_user["role"] == "teacher":
        result = await db.execute(
            select(Course)
            .where(Course.teacher_id == current_user["id"])
            .order_by(Course.semester.desc(), Course.name)
        )
    else:
        return []

    courses = result.scalars().all()
    response = []
    for course in courses:
        teacher_name_result = await db.execute(
            select(User.real_name).where(User.id == course.teacher_id)
        )
        teacher_name = teacher_name_result.scalar_one()
        task_count_result = await db.execute(
            select(func.count()).select_from(Task).where(Task.course_id == course.id)
        )
        task_count = task_count_result.scalar()
        response.append(_course_to_response(course, teacher_name, task_count))
    return response
```

Also add `from app.models.task import Task` to the router file imports.

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_courses.py::test_list_courses_teacher_own -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_courses.py
git commit -m "feat: add course list endpoint (teacher: own, admin: all)"
```

---

## Task 9: Course List — Admin with Filters

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing test for admin with filters**

Append to `backend/tests/test_courses.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_list_courses_admin_all(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="admin1", role="admin")
    token_t = await login_user(client, "teacher1")
    token_a = await login_user(client, "admin1")

    await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token_t),
    )
    await client.post(
        "/api/courses",
        json={"name": "课程B", "semester": "2025-2026-2"},
        headers=auth_headers(token_t),
    )

    resp = await client.get("/api/courses", headers=auth_headers(token_a))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_list_courses_admin_filter(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="admin1", role="admin")
    token_t = await login_user(client, "teacher1")
    token_a = await login_user(client, "admin1")

    await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token_t),
    )
    await client.post(
        "/api/courses",
        json={"name": "课程B", "semester": "2025-2026-2"},
        headers=auth_headers(token_t),
    )

    resp = await client.get(
        "/api/courses?semester=2026-2027-1",
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "课程A"
```

- [ ] **Step 2: Run tests, verify admin_all passes but admin_filter fails**

Run: `cd backend && python -m pytest tests/test_courses.py -k "admin" -v`
Expected: admin_all PASS, admin_filter FAIL (no semester filter)

- [ ] **Step 3: Add query parameters for filters**

Modify the `list_courses` endpoint signature and logic. Replace the entire `list_courses` function with:

```python
@router.get("", response_model=list[CourseResponse])
async def list_courses(
    semester: Optional[str] = Query(None),
    teacher_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "admin":
        query = select(Course)
    elif current_user["role"] == "teacher":
        query = select(Course).where(Course.teacher_id == current_user["id"])
    else:
        return []

    if semester:
        query = query.where(Course.semester == semester)
    if teacher_id:
        query = query.where(Course.teacher_id == teacher_id)
    if status_filter:
        query = query.where(Course.status == status_filter)

    query = query.order_by(Course.semester.desc(), Course.name)
    result = await db.execute(query)
    courses = result.scalars().all()

    response = []
    for course in courses:
        teacher_name_result = await db.execute(
            select(User.real_name).where(User.id == course.teacher_id)
        )
        teacher_name = teacher_name_result.scalar_one()
        task_count_result = await db.execute(
            select(func.count()).select_from(Task).where(Task.course_id == course.id)
        )
        task_count = task_count_result.scalar()
        response.append(_course_to_response(course, teacher_name, task_count))
    return response
```

Add `from typing import Optional` to the router file imports (it may already be there from other imports).

- [ ] **Step 4: Run all course list tests**

Run: `cd backend && python -m pytest tests/test_courses.py -k "list_courses" -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_courses.py
git commit -m "feat: add admin course list with semester/teacher/status filters"
```

---

## Task 10: Course Detail with Task List

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_courses.py`:

```python
import json
import datetime


@pytest.mark.asyncio(loop_scope="session")
async def test_course_detail_with_tasks(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    from tests.helpers import create_test_task

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = create_resp.json()["id"]

    task = await create_test_task(db_session, title="任务1", class_id=cls.id, created_by=teacher.id)

    resp = await client.get(f"/api/courses/{course_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "课程A"
    assert isinstance(data["tasks"], list)
```

Note: The task won't appear in the course detail yet because task.course_id isn't linked. That's fine — this test verifies the endpoint works. Task-course linking comes in Task 13.

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_courses.py::test_course_detail_with_tasks -v`
Expected: FAIL (endpoint doesn't exist)

- [ ] **Step 3: Implement detail endpoint**

Add to `backend/app/routers/courses.py`:

```python
@router.get("/{course_id}", response_model=CourseDetailResponse)
async def get_course_detail(
    course_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    if current_user["role"] == "teacher" and course.teacher_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权查看该课程")
    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="学生请使用课程卡片接口")

    teacher_name_result = await db.execute(
        select(User.real_name).where(User.id == course.teacher_id)
    )
    teacher_name = teacher_name_result.scalar_one()

    task_result = await db.execute(
        select(Task).where(Task.course_id == course_id).order_by(Task.deadline)
    )
    tasks = task_result.scalars().all()
    task_list = []
    for t in tasks:
        cls_result = await db.execute(select(Class.name).where(Class.id == t.class_id))
        class_name = cls_result.scalar_one_or_none() or ""
        task_list.append({
            "id": t.id,
            "title": t.title,
            "class_name": class_name,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "status": t.status,
        })

    return CourseDetailResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        semester=course.semester,
        teacher_id=course.teacher_id,
        teacher_name=teacher_name,
        status=course.status,
        task_count=len(task_list),
        created_at=course.created_at,
        updated_at=course.updated_at,
        tasks=task_list,
    )
```

Add `from app.models.class_ import Class` to the router imports.

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_courses.py::test_course_detail_with_tasks -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_courses.py
git commit -m "feat: add course detail endpoint with task list"
```

---

## Task 11: Student Course List (via Task-Class Join)

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_courses.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_list_courses_student(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_user(db_session, username="stu1", role="student")
    cls = await create_test_class(db_session, name="1班", teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    token_t = await login_user(client, "teacher1")
    token_s = await login_user(client, "stu1")

    from tests.helpers import create_test_task

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token_t),
    )
    course_id = create_resp.json()["id"]

    task = await create_test_task(db_session, title="任务1", class_id=cls.id, created_by=teacher.id)
    task.course_id = course_id
    await db_session.flush()

    resp = await client.get("/api/courses", headers=auth_headers(token_s))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "课程A"
    assert data[0]["status"] == "active"
```

Note: The student list needs a different path — tasks with course_id where the student's class matches. The existing `list_courses` handles this via the `else: return []` branch. We need to replace that.

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_courses.py::test_list_courses_student -v`
Expected: FAIL (student gets empty list from current code)

- [ ] **Step 3: Implement student course list logic**

Replace the `else: return []` in `list_courses` with:

```python
    else:
        user_result = await db.execute(
            select(User.primary_class_id).where(User.id == current_user["id"])
        )
        class_id = user_result.scalar_one_or_none()
        if not class_id:
            return []

        query = (
            select(Course)
            .join(Task, Task.course_id == Course.id)
            .where(Task.class_id == class_id)
            .where(Course.status == "active")
            .distinct()
        )
        query = query.order_by(Course.semester.desc(), Course.name)
        result = await db.execute(query)
        courses = result.scalars().all()

        response = []
        for course in courses:
            teacher_name_result = await db.execute(
                select(User.real_name).where(User.id == course.teacher_id)
            )
            teacher_name = teacher_name_result.scalar_one()
            task_count_result = await db.execute(
                select(func.count()).select_from(Task).where(Task.course_id == course.id)
            )
            task_count = task_count_result.scalar()
            response.append(_course_to_response(course, teacher_name, task_count))
        return response
```

Since this branch returns early, the shared response-building code at the bottom of the function still handles admin and teacher. We need to restructure. Replace the entire `list_courses` function:

```python
@router.get("", response_model=list[CourseResponse])
async def list_courses(
    semester: Optional[str] = Query(None),
    teacher_id_filter: Optional[int] = Query(None, alias="teacher_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "student":
        user_result = await db.execute(
            select(User.primary_class_id).where(User.id == current_user["id"])
        )
        class_id = user_result.scalar_one_or_none()
        if not class_id:
            return []
        query = (
            select(Course)
            .join(Task, Task.course_id == Course.id)
            .where(Task.class_id == class_id)
            .where(Course.status == "active")
            .distinct()
            .order_by(Course.semester.desc(), Course.name)
        )
    elif current_user["role"] == "teacher":
        query = select(Course).where(Course.teacher_id == current_user["id"])
        if status_filter:
            query = query.where(Course.status == status_filter)
        query = query.order_by(Course.semester.desc(), Course.name)
    else:
        query = select(Course)
        if semester:
            query = query.where(Course.semester == semester)
        if teacher_id_filter:
            query = query.where(Course.teacher_id == teacher_id_filter)
        if status_filter:
            query = query.where(Course.status == status_filter)
        query = query.order_by(Course.semester.desc(), Course.name)

    result = await db.execute(query)
    courses = result.scalars().all()

    response = []
    for course in courses:
        teacher_name_result = await db.execute(
            select(User.real_name).where(User.id == course.teacher_id)
        )
        teacher_name = teacher_name_result.scalar_one()
        task_count_result = await db.execute(
            select(func.count()).select_from(Task).where(Task.course_id == course.id)
        )
        task_count = task_count_result.scalar()
        response.append(_course_to_response(course, teacher_name, task_count))
    return response
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_courses.py::test_list_courses_student -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_courses.py
git commit -m "feat: student course list via task-class join, active courses only"
```

---

## Task 12: Student Course Cards with Progress

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `backend/tests/test_courses.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_courses.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_student_course_cards_with_progress(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, name="1班", teacher_id=teacher.id)
    stu = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    token_t = await login_user(client, "teacher1")
    token_s = await login_user(client, "stu1")

    from tests.helpers import create_test_task

    create_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token_t),
    )
    course_id = create_resp.json()["id"]

    task1 = await create_test_task(db_session, title="任务1", class_id=cls.id, created_by=teacher.id)
    task1.course_id = course_id
    task2 = await create_test_task(db_session, title="任务2", class_id=cls.id, created_by=teacher.id)
    task2.course_id = course_id
    await db_session.flush()

    resp = await client.get("/api/courses/my", headers=auth_headers(token_s))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "课程A"
    assert data[0]["task_count"] == 2
    assert data[0]["submitted_count"] == 0
    assert data[0]["graded_count"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_student_course_cards_empty(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.get("/api/courses/my", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd backend && python -m pytest tests/test_courses.py -k "course_cards" -v`
Expected: FAIL (endpoint doesn't exist)

- [ ] **Step 3: Implement student course cards endpoint**

Add to `backend/app/routers/courses.py` (add `from app.models.submission import Submission` to imports):

```python
@router.get("/my", response_model=list[CourseProgressResponse])
async def student_course_cards(
    current_user: dict = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(
        select(User.primary_class_id).where(User.id == current_user["id"])
    )
    class_id = user_result.scalar_one_or_none()
    if not class_id:
        return []

    courses_result = await db.execute(
        select(Course)
        .join(Task, Task.course_id == Course.id)
        .where(Task.class_id == class_id)
        .where(Course.status == "active")
        .distinct()
        .order_by(Course.semester.desc(), Course.name)
    )
    courses = courses_result.scalars().all()

    response = []
    for course in courses:
        task_count_result = await db.execute(
            select(func.count()).select_from(Task).where(
                Task.course_id == course.id,
                Task.class_id == class_id,
                Task.status == "active",
            )
        )
        task_count = task_count_result.scalar()

        submitted_result = await db.execute(
            select(func.count()).select_from(Submission).where(
                Submission.task_id.in_(
                    select(Task.id).where(
                        Task.course_id == course.id,
                        Task.class_id == class_id,
                    )
                ),
                Submission.student_id == current_user["id"],
            )
        )
        submitted_count = submitted_result.scalar()

        graded_result = await db.execute(
            select(func.count()).select_from(Submission).where(
                Submission.task_id.in_(
                    select(Task.id).where(
                        Task.course_id == course.id,
                        Task.class_id == class_id,
                    )
                ),
                Submission.student_id == current_user["id"],
                Submission.is_graded == True,
            )
        )
        graded_count = graded_result.scalar()

        deadline_result = await db.execute(
            select(func.min(Task.deadline)).where(
                Task.course_id == course.id,
                Task.class_id == class_id,
                Task.status == "active",
                Task.deadline > datetime.datetime.utcnow(),
            )
        )
        nearest_deadline = deadline_result.scalar_one_or_none()

        teacher_name_result = await db.execute(
            select(User.real_name).where(User.id == course.teacher_id)
        )
        teacher_name = teacher_name_result.scalar_one()

        response.append(CourseProgressResponse(
            id=course.id,
            name=course.name,
            description=course.description,
            semester=course.semester,
            teacher_name=teacher_name,
            task_count=task_count,
            submitted_count=submitted_count,
            graded_count=graded_count,
            nearest_deadline=nearest_deadline,
        ))
    return response
```

Also add `import datetime` and `from app.models.submission import Submission` to the router file imports.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_courses.py -k "course_cards" -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py backend/tests/test_courses.py
git commit -m "feat: add student course cards endpoint with progress data"
```

---

## Task 13: Add course_id FK to Tasks Table

**Files:**
- Create: `backend/alembic/versions/XXXX_add_course_id_to_tasks.py`
- Modify: `backend/app/models/task.py`
- Modify: `backend/app/schemas/task.py`

- [ ] **Step 1: Generate migration**

Run: `cd backend && alembic revision -m "add_course_id_to_tasks" --autogenerate`

If autogenerate doesn't pick it up, create manually.

- [ ] **Step 2: Write migration**

Create migration file with `down_revision` pointing to the courses table migration revision:

```python
def upgrade() -> None:
    op.add_column('tasks', sa.Column('course_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_tasks_course_id', 'tasks', 'courses', ['course_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_tasks_course_id', 'tasks', ['course_id'])


def downgrade() -> None:
    op.drop_index('ix_tasks_course_id', table_name='tasks')
    op.drop_constraint('fk_tasks_course_id', 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'course_id')
```

- [ ] **Step 3: Add course_id to Task model**

Add to `backend/app/models/task.py` after the `class_id` field:

```python
    course_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="RESTRICT"), nullable=True, index=True
    )
```

- [ ] **Step 4: Add course_id to task schemas**

In `backend/app/schemas/task.py`, add to `TaskCreate`:

```python
    course_id: Optional[int] = None
```

Add to `TaskUpdate`:

```python
    course_id: Optional[int] = None
```

Add to `TaskResponse`:

```python
    course_id: Optional[int] = None
```

- [ ] **Step 5: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: No errors.

- [ ] **Step 6: Verify existing tests still pass**

Run: `cd backend && python -m pytest tests/test_tasks.py -v`
Expected: All PASS (course_id is nullable, backward compatible)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/task.py backend/app/schemas/task.py backend/alembic/versions/
git commit -m "feat: add nullable course_id FK to tasks table (backward compatible)"
```

---

## Task 14: Task Create/Update with course_id

**Files:**
- Create: `backend/tests/test_task_course_linking.py`
- Modify: `backend/app/routers/tasks.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_task_course_linking.py`:

```python
import datetime
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_with_course(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = course_resp.json()["id"]

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "网络实验",
            "class_id": cls.id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf"],
            "course_id": course_id,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["course_id"] == course_id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_with_unowned_course(client, db_session):
    teacher1 = await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher1.id)
    token1 = await login_user(client, "teacher1")
    token2 = await login_user(client, "teacher2")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token1),
    )
    course_id = course_resp.json()["id"]

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "网络实验",
            "class_id": cls.id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf"],
            "course_id": course_id,
        },
        headers=auth_headers(token2),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_create_task_without_course(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "无课程任务",
            "class_id": cls.id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    assert resp.json()["course_id"] is None
```

- [ ] **Step 2: Run tests, verify create_with_course passes, unowned fails**

Run: `cd backend && python -m pytest tests/test_task_course_linking.py::test_create_task_with_course -v`
Expected: FAIL (router doesn't save course_id yet)

- [ ] **Step 3: Modify task create endpoint**

In `backend/app/routers/tasks.py`, modify the `create_task` function. After the class ownership check, add course ownership check:

```python
    course_id = data.course_id
    if course_id is not None:
        from app.models.course import Course
        course_result = await db.execute(select(Course).where(Course.id == course_id))
        course = course_result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail="课程不存在")
        if current_user["role"] != "admin" and course.teacher_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="只能关联自己的课程")
```

And add `course_id=course_id` to the Task constructor.

Update `_task_to_response` to include course_id:

```python
def _task_to_response(task: Task, class_name: str) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        requirements=task.requirements,
        class_id=task.class_id,
        class_name=class_name,
        course_id=task.course_id,
        created_by=task.created_by,
        deadline=task.deadline,
        allowed_file_types=json.loads(task.allowed_file_types),
        max_file_size_mb=task.max_file_size_mb,
        allow_late_submission=task.allow_late_submission,
        late_penalty_percent=task.late_penalty_percent,
        status=task.status,
        grades_published=task.grades_published,
        created_at=task.created_at,
    )
```

- [ ] **Step 4: Run all task-course linking tests**

Run: `cd backend && python -m pytest tests/test_task_course_linking.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Run existing task tests for regression**

Run: `cd backend && python -m pytest tests/test_tasks.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/tasks.py backend/tests/test_task_course_linking.py
git commit -m "feat: add course_id to task creation with ownership check"
```

---

## Task 15: Task Update with course_id

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_task_course_linking.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_task_course_linking.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_update_task_course(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token),
    )
    course_id = course_resp.json()["id"]

    task = await create_test_task(db_session, title="任务1", class_id=cls.id, created_by=teacher.id)

    resp = await client.put(
        f"/api/tasks/{task.id}",
        json={"course_id": course_id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["course_id"] == course_id
```

- [ ] **Step 2: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_task_course_linking.py::test_update_task_course -v`
Expected: May PASS if TaskUpdate's `course_id` is already applied via `model_dump(exclude_unset=True)` + `setattr` loop. If it doesn't pass, add course ownership check to update_task.

If the update endpoint needs a course ownership check (same as create), add it in the update_task function before the field loop:

```python
    if "course_id" in update_data and update_data["course_id"] is not None:
        from app.models.course import Course
        course_result = await db.execute(select(Course).where(Course.id == update_data["course_id"]))
        course = course_result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail="课程不存在")
        if current_user["role"] != "admin" and course.teacher_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="只能关联自己的课程")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/tasks.py backend/tests/test_task_course_linking.py
git commit -m "feat: add course_id to task update with ownership check"
```

---

## Task 16: Student Task List — Exclude Archived Course Tasks

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_task_course_linking.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_task_course_linking.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_student_tasks_exclude_archived_course(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, name="1班", teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    token_t = await login_user(client, "teacher1")
    token_s = await login_user(client, "stu1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "归档课程", "semester": "2025-2026-2"},
        headers=auth_headers(token_t),
    )
    archived_course_id = course_resp.json()["id"]

    task1 = await create_test_task(db_session, title="归档任务", class_id=cls.id, created_by=teacher.id)
    task1.course_id = archived_course_id
    task2 = await create_test_task(db_session, title="普通任务", class_id=cls.id, created_by=teacher.id)
    await db_session.flush()

    await client.post(
        f"/api/courses/{archived_course_id}/archive",
        headers=auth_headers(token_t),
    )

    resp = await client.get("/api/tasks/my", headers=auth_headers(token_s))
    assert resp.status_code == 200
    data = resp.json()
    titles = {t["title"] for t in data}
    assert "归档任务" not in titles
    assert "普通任务" in titles
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_task_course_linking.py::test_student_tasks_exclude_archived_course -v`
Expected: FAIL (both tasks appear, archived course task not filtered)

- [ ] **Step 3: Modify student task listing in get_my_tasks**

In `backend/app/routers/tasks.py`, modify the student branch of `get_my_tasks`. Add `from app.models.course import Course` to imports. Then replace the student query:

```python
    if current_user["role"] == "student":
        user_result = await db.execute(
            select(User.primary_class_id).where(User.id == current_user["id"])
        )
        class_id = user_result.scalar_one_or_none()
        if not class_id:
            return []
        result = await db.execute(
            select(Task)
            .outerjoin(Course, Course.id == Task.course_id)
            .where(Task.class_id == class_id)
            .where(Task.status == "active")
            .where((Course.status == "active") | (Course.id.is_(None)))
            .order_by(Task.deadline)
        )
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_task_course_linking.py::test_student_tasks_exclude_archived_course -v`
Expected: PASS

- [ ] **Step 5: Run existing student task tests for regression**

Run: `cd backend && python -m pytest tests/test_tasks.py -k "student" -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/tasks.py backend/tests/test_task_course_linking.py
git commit -m "feat: exclude archived course tasks from student task list"
```

---

## Task 17: Admin Task List — Course Filter

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_task_course_linking.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_task_course_linking.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_admin_tasks_filter_by_course(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    admin = await create_test_user(db_session, username="admin1", role="admin")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token_t = await login_user(client, "teacher1")
    token_a = await login_user(client, "admin1")

    course_resp = await client.post(
        "/api/courses",
        json={"name": "课程A", "semester": "2026-2027-1"},
        headers=auth_headers(token_t),
    )
    course_id = course_resp.json()["id"]

    task1 = await create_test_task(db_session, title="课程任务", class_id=cls.id, created_by=teacher.id)
    task1.course_id = course_id
    task2 = await create_test_task(db_session, title="无课程任务", class_id=cls.id, created_by=teacher.id)
    await db_session.flush()

    resp = await client.get(
        f"/api/tasks?course_id={course_id}",
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "课程任务"
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_task_course_linking.py::test_admin_tasks_filter_by_course -v`
Expected: FAIL (course_id filter not implemented)

- [ ] **Step 3: Add course_id filter to admin task list**

In `backend/app/routers/tasks.py`, modify `list_tasks_admin` to accept course_id query param:

```python
@router.get("", response_model=dict)
async def list_tasks_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    course_id: Optional[int] = Query(None),
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Task)
    if course_id is not None:
        query = query.where(Task.course_id == course_id)
    # ... rest unchanged
```

Also add `from typing import Optional` if not already imported.

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && python -m pytest tests/test_task_course_linking.py::test_admin_tasks_filter_by_course -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/tasks.py backend/tests/test_task_course_linking.py
git commit -m "feat: add course_id filter to admin task list"
```

---

## Task 18: Frontend — Teacher CourseList.vue

**Files:**
- Create: `frontend/src/views/teacher/CourseList.vue`

- [ ] **Step 1: Create CourseList component**

Create `frontend/src/views/teacher/CourseList.vue`:

```vue
<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">课程管理</h3>
      <el-button type="primary" @click="$router.push('/teacher/courses/create')">创建课程</el-button>
    </div>
    <el-table :data="courses" v-loading="loading" stripe>
      <el-table-column prop="name" label="课程名称" min-width="150" />
      <el-table-column prop="semester" label="学期" width="130" />
      <el-table-column prop="task_count" label="任务数" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/teacher/courses/${row.id}`)">查看</el-button>
          <el-button v-if="row.status === 'active'" size="small" type="warning" @click="handleArchive(row)">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const courses = ref([])
const loading = ref(false)

async function fetchCourses() {
  loading.value = true
  try {
    const resp = await api.get('/courses')
    courses.value = resp.data
  } catch { ElMessage.error('获取课程列表失败') }
  finally { loading.value = false }
}

async function handleArchive(course) {
  try {
    await ElMessageBox.confirm(`确认归档课程 "${course.name}"？归档后学生将看不到该课程及任务。`, '归档课程')
    await api.post(`/courses/${course.id}/archive`)
    ElMessage.success('已归档')
    await fetchCourses()
  } catch (err) { if (err !== 'cancel') ElMessage.error('归档失败') }
}

onMounted(fetchCourses)
</script>
```

- [ ] **Step 2: Verify file created, no syntax errors**

Run: `cd frontend && npx vue-tsc --noEmit 2>&1 | head -20` or just verify the file loads.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/teacher/CourseList.vue
git commit -m "feat: add teacher course list view"
```

---

## Task 19: Frontend — Teacher CourseCreate.vue

**Files:**
- Create: `frontend/src/views/teacher/CourseCreate.vue`

- [ ] **Step 1: Create CourseCreate component**

Create `frontend/src/views/teacher/CourseCreate.vue`:

```vue
<template>
  <div>
    <h3>创建课程</h3>
    <el-form :model="form" :rules="rules" ref="formRef" label-width="100px" style="max-width: 500px">
      <el-form-item label="课程名称" prop="name">
        <el-input v-model="form.name" placeholder="如：Python程序设计" />
      </el-form-item>
      <el-form-item label="课程描述">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="课程简介（可选）" />
      </el-form-item>
      <el-form-item label="学期" prop="semester">
        <el-select v-model="form.semester" placeholder="选择学期">
          <el-option label="2026-2027-1" value="2026-2027-1" />
          <el-option label="2026-2027-2" value="2026-2027-2" />
          <el-option label="2025-2026-1" value="2025-2026-1" />
          <el-option label="2025-2026-2" value="2025-2026-2" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSubmit" :loading="loading">创建课程</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ name: '', description: '', semester: '' })
const rules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  semester: [{ required: true, message: '请选择学期', trigger: 'change' }],
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await api.post('/courses', form)
    ElMessage.success('课程创建成功')
    router.push('/teacher/courses')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/teacher/CourseCreate.vue
git commit -m "feat: add teacher course creation form"
```

---

## Task 20: Frontend — Teacher CourseDetail.vue

**Files:**
- Create: `frontend/src/views/teacher/CourseDetail.vue`

- [ ] **Step 1: Create CourseDetail component**

Create `frontend/src/views/teacher/CourseDetail.vue`:

```vue
<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" :content="course?.name || '课程详情'" />
    <div v-if="course" style="margin-top: 20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="课程名称">{{ course.name }}</el-descriptions-item>
        <el-descriptions-item label="学期">{{ course.semester }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="course.status === 'active' ? 'success' : 'info'">
            {{ course.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="任务数">{{ course.task_count }}</el-descriptions-item>
        <el-descriptions-item label="课程描述" :span="2">{{ course.description || '无' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
        <h4 style="margin: 0">课程任务</h4>
        <el-button type="primary" size="small" @click="$router.push('/teacher/tasks/create')">添加任务</el-button>
      </div>
      <el-table :data="course.tasks" stripe>
        <el-table-column prop="title" label="任务标题" min-width="150" />
        <el-table-column prop="class_name" label="班级" width="120" />
        <el-table-column label="截止时间" width="170">
          <template #default="{ row }">{{ formatDate(row.deadline) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '进行中' : '已归档' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
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

const course = ref(null)
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/courses/${courseId}`)
    course.value = resp.data
  } catch {
    ElMessage.error('获取课程详情失败')
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/teacher/CourseDetail.vue
git commit -m "feat: add teacher course detail view with task list"
```

---

## Task 21: Frontend — Add Course Selector to TaskCreate/TaskEdit

**Files:**
- Modify: `frontend/src/views/teacher/TaskCreate.vue`
- Modify: `frontend/src/views/teacher/TaskEdit.vue`

- [ ] **Step 1: Add course selector to TaskCreate.vue**

In `frontend/src/views/teacher/TaskCreate.vue`, add a `courses` ref and fetch it on mount:

After the `classes` ref, add:

```javascript
const courses = ref([])
```

In the `onMounted`, after fetching classes, add:

```javascript
    const courseResp = await api.get('/courses')
    courses.value = courseResp.data.filter(c => c.status === 'active')
```

In the `form` reactive object, add:

```javascript
  course_id: null,
```

In the template, after the "选择班级" form-item, add:

```html
      <el-form-item label="关联课程">
        <el-select v-model="form.course_id" placeholder="选择课程（可选）" clearable>
          <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
```

- [ ] **Step 2: Add same course selector to TaskEdit.vue**

In `frontend/src/views/teacher/TaskEdit.vue`, add `courses` ref:

```javascript
const courses = ref([])
```

In `onMounted`, after loading task data, fetch courses:

```javascript
    const courseResp = await api.get('/courses')
    courses.value = courseResp.data.filter(c => c.status === 'active')
```

Add `course_id` to the `form` reactive and populate it from task data in Object.assign:

```javascript
      course_id: task.value.course_id || null,
```

In the template, after the "实验要求" form-item, add the same course selector:

```html
      <el-form-item label="关联课程">
        <el-select v-model="form.course_id" placeholder="选择课程（可选）" clearable>
          <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/teacher/TaskCreate.vue frontend/src/views/teacher/TaskEdit.vue
git commit -m "feat: add course selector to task create and edit forms"
```

---

## Task 22: Frontend — Admin CourseList.vue

**Files:**
- Create: `frontend/src/views/admin/CourseList.vue`

- [ ] **Step 1: Create AdminCourseList component**

Create `frontend/src/views/admin/CourseList.vue`:

```vue
<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">课程管理</h3>
    </div>
    <div style="margin-bottom: 16px; display: flex; gap: 12px">
      <el-select v-model="semesterFilter" placeholder="筛选学期" clearable style="width: 160px" @change="fetchCourses">
        <el-option label="2026-2027-1" value="2026-2027-1" />
        <el-option label="2026-2027-2" value="2026-2027-2" />
        <el-option label="2025-2026-1" value="2025-2026-1" />
        <el-option label="2025-2026-2" value="2025-2026-2" />
      </el-select>
      <el-select v-model="statusFilter" placeholder="筛选状态" clearable style="width: 120px" @change="fetchCourses">
        <el-option label="进行中" value="active" />
        <el-option label="已归档" value="archived" />
      </el-select>
    </div>
    <el-table :data="courses" v-loading="loading" stripe>
      <el-table-column prop="name" label="课程名称" min-width="150" />
      <el-table-column prop="semester" label="学期" width="130" />
      <el-table-column prop="teacher_name" label="教师" width="100" />
      <el-table-column prop="task_count" label="任务数" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const courses = ref([])
const loading = ref(false)
const semesterFilter = ref('')
const statusFilter = ref('')

async function fetchCourses() {
  loading.value = true
  try {
    const params = {}
    if (semesterFilter.value) params.semester = semesterFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    const resp = await api.get('/courses', { params })
    courses.value = resp.data
  } catch { ElMessage.error('获取课程列表失败') }
  finally { loading.value = false }
}

onMounted(fetchCourses)
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/admin/CourseList.vue
git commit -m "feat: add admin course list with filters"
```

---

## Task 23: Frontend — Student CourseList.vue (Cards)

**Files:**
- Create: `frontend/src/views/student/CourseList.vue`

- [ ] **Step 1: Create StudentCourseList component**

Create `frontend/src/views/student/CourseList.vue`:

```vue
<template>
  <div>
    <h3 style="margin-bottom: 16px">我的课程</h3>
    <div v-if="courses.length === 0 && !loading" style="text-align: center; padding: 40px; color: #909399">
      暂无课程，请等待教师创建课程并分配任务
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px">
      <el-card v-for="course in courses" :key="course.id" shadow="hover">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span style="font-size: 16px; font-weight: bold">{{ course.name }}</span>
            <el-tag size="small">{{ course.semester }}</el-tag>
          </div>
        </template>
        <p style="color: #606266; margin: 0 0 12px">{{ course.description || '暂无描述' }}</p>
        <p style="color: #909399; font-size: 13px; margin: 0 0 12px">教师：{{ course.teacher_name }}</p>
        <el-progress
          :percentage="course.task_count ? Math.round(course.submitted_count / course.task_count * 100) : 0"
          :format="() => `${course.submitted_count}/${course.task_count}`"
        />
        <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center">
          <span v-if="course.nearest_deadline" style="color: #e6a23c; font-size: 13px">
            最近截止：{{ formatDate(course.nearest_deadline) }}
          </span>
          <span v-else style="color: #909399; font-size: 13px">无待办任务</span>
          <el-tag v-if="course.graded_count > 0" type="success" size="small">
            已出分 {{ course.graded_count }}
          </el-tag>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const courses = ref([])
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/courses/my')
    courses.value = resp.data
  } catch {
    ElMessage.error('获取课程列表失败')
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/student/CourseList.vue
git commit -m "feat: add student course cards view with progress"
```

---

## Task 24: Frontend — Routes & Sidebar

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/src/stores/auth.js`

- [ ] **Step 1: Add course routes to router**

In `frontend/src/router/index.js`, add these routes inside the `children` array:

```javascript
      {
        path: 'teacher/courses',
        name: 'TeacherCourseList',
        component: () => import('../views/teacher/CourseList.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'teacher/courses/create',
        name: 'TeacherCourseCreate',
        component: () => import('../views/teacher/CourseCreate.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'teacher/courses/:id',
        name: 'TeacherCourseDetail',
        component: () => import('../views/teacher/CourseDetail.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'admin/courses',
        name: 'AdminCourseList',
        component: () => import('../views/admin/CourseList.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'student/courses',
        name: 'StudentCourseList',
        component: () => import('../views/student/CourseList.vue'),
        meta: { roles: ['student'] },
      },
```

- [ ] **Step 2: Add sidebar entries to MainLayout**

In `frontend/src/layouts/MainLayout.vue`, add menu items:

In the teacher template block, add before "我的任务":

```html
          <el-menu-item index="/teacher/courses">
            <span>课程管理</span>
          </el-menu-item>
```

In the student template block, add before "我的任务":

```html
          <el-menu-item index="/student/courses">
            <span>我的课程</span>
          </el-menu-item>
```

In the admin template block, add after "班级管理":

```html
          <el-menu-item index="/admin/courses">
            <span>课程管理</span>
          </el-menu-item>
```

- [ ] **Step 3: Update student home route in auth store**

In `frontend/src/stores/auth.js`, change the student case in `getHomeRoute`:

```javascript
      case 'student': return '/student/courses'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.js frontend/src/layouts/MainLayout.vue frontend/src/stores/auth.js
git commit -m "feat: add course routes, sidebar entries, student home to courses"
```

---

## Task 25: Full Integration Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS, including Phase 1 tests (no regressions).

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Manual smoke test — Backend**

Start backend: `cd backend && uvicorn app.main:app --reload`

Test these API calls (use curl or httpie):
1. `POST /api/auth/login` as teacher -> get token
2. `POST /api/courses` -> create course
3. `GET /api/courses` -> verify course appears
4. `GET /api/courses/:id` -> verify detail with task list
5. `POST /api/courses/:id/archive` -> verify archived
6. `GET /api/courses` as student -> verify only active courses via task-class join

- [ ] **Step 4: Manual smoke test — Frontend**

Start frontend: `cd frontend && npm run dev`

1. Login as teacher -> verify "课程管理" in sidebar
2. Click "课程管理" -> see course list
3. Click "创建课程" -> fill form, submit -> redirect to list
4. Click course name -> see detail page with tasks
5. Archive a course -> verify status changes
6. Go to "创建任务" -> verify course selector appears
7. Login as student -> verify "我的课程" in sidebar, lands on course cards
8. Login as admin -> verify "课程管理" in sidebar, see all courses with filters

- [ ] **Step 5: Final commit (if any fixes needed)**

If any issues found during verification, fix and commit with descriptive message.

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task(s) |
|---|---|
| Teacher can create courses | Task 4, 5 |
| Teacher can edit their own courses | Task 6 |
| Teacher can archive courses | Task 7 |
| No delete endpoint (405) | Task 7 |
| Teacher lists own courses | Task 8 |
| Admin lists all courses with filters | Task 9 |
| Student lists courses via task-class join | Task 11 |
| Course detail with task list | Task 10 |
| Student course cards with progress | Task 12 |
| Create task with course_id | Task 14 |
| Create task with unowned course -> 403 | Task 14 |
| Create task without course (backward compat) | Task 14 |
| Update task with course_id | Task 15 |
| Student tasks exclude archived course tasks | Task 16 |
| Admin tasks filter by course_id | Task 17 |
| Teacher CourseList frontend | Task 18 |
| Teacher CourseCreate frontend | Task 19 |
| Teacher CourseDetail frontend | Task 20 |
| Admin CourseList frontend | Task 22 |
| Student CourseList (cards) frontend | Task 23 |
| Task create/edit course selector | Task 21 |
| Routes + sidebar | Task 24 |

### Placeholder Scan

No TBD, TODO, "implement later", "add appropriate error handling", or "similar to Task N" patterns found.

### Type Consistency

- `CourseResponse` used consistently across all list/detail endpoints
- `CourseProgressResponse` used only for `/api/courses/my`
- `CourseDetailResponse` extends `CourseResponse` with `tasks: List[dict]`
- `course_id: Optional[int] = None` on TaskCreate, TaskUpdate, TaskResponse
- `_task_to_response` updated to include `course_id`
