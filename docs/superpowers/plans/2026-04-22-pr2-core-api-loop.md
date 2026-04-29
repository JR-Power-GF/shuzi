# PR2: Core API Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all REST API endpoints for the minimum closed loop: login → teacher creates task → student uploads and submits → teacher grades and publishes → student sees grade.

**Architecture:** FastAPI routers with Pydantic v2 request/response schemas. JWT Bearer authentication via existing `get_current_user` / `require_role` dependencies. SQLAlchemy 2.0 async queries against MySQL 8. File upload via multipart form with UUID-prefix atomic rename. Grade publication via single boolean toggle on `tasks.grades_published`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), PyJWT, bcrypt, httpx (tests), pytest-asyncio

---

## File Structure

### New files to create

| File | Purpose |
|------|---------|
| `backend/app/utils/__init__.py` | Package init (empty) |
| `backend/app/utils/security.py` | Password hashing + JWT token creation |
| `backend/app/schemas/__init__.py` | Package init (empty) |
| `backend/app/schemas/auth.py` | Login request/response schemas |
| `backend/app/schemas/class_.py` | Class create/response schemas |
| `backend/app/schemas/task.py` | Task create/response schemas |
| `backend/app/schemas/file.py` | File upload response schema |
| `backend/app/schemas/submission.py` | Submission create/response schemas |
| `backend/app/schemas/grade.py` | Grade create/response schemas |
| `backend/app/routers/__init__.py` | Package init (empty) |
| `backend/app/routers/auth.py` | POST /api/auth/login |
| `backend/app/routers/classes.py` | POST, GET /my, GET /:id/students |
| `backend/app/routers/tasks.py` | POST, GET /my, GET /:id |
| `backend/app/routers/files.py` | POST upload, GET download |
| `backend/app/routers/submissions.py` | POST submit, GET /:id, GET /tasks/:id/submissions |
| `backend/app/routers/grades.py` | POST grade, POST publish, POST unpublish |
| `backend/app/services/__init__.py` | Package init (empty) |
| `backend/app/services/file_cleanup.py` | Orphan file cleanup |
| `backend/scripts/seed_demo.py` | Demo data seeding script |
| `backend/tests/helpers.py` | Shared test utility functions |

### New test files

| File | Tests |
|------|-------|
| `backend/tests/test_auth.py` | Login success, invalid credentials, lockout |
| `backend/tests/test_classes.py` | Create class, list my classes, list students |
| `backend/tests/test_tasks.py` | Create task, list my tasks, get task detail |
| `backend/tests/test_files.py` | Upload file, download file |
| `backend/tests/test_submissions.py` | Submit, resubmit, view own, teacher list |
| `backend/tests/test_grades.py` | Grade, publish, unpublish |
| `backend/tests/test_min_loop.py` | Full end-to-end closed loop |

### Files to modify

| File | Change |
|------|--------|
| `backend/app/main.py` | Include all routers |
| `backend/tests/conftest.py` | Add `upload_dir` fixture |

---

## PR1 Prerequisites (already complete)

The following are already in the codebase and will NOT be created by this plan:

- `backend/app/models/` — all 7 ORM models (User, Class, Task, Submission, SubmissionFile, Grade, RefreshToken)
- `backend/app/dependencies/auth.py` — `get_current_user` returns `{"id": int, "role": str, "username": str}`, `require_role(role: str)` raises 403 on mismatch
- `backend/app/config.py` — `settings` with DATABASE_URL, SECRET_KEY, UPLOAD_DIR, UPLOAD_TMP_DIR, MAX_FILE_SIZE_MB, ALLOWED_FILE_TYPES, LOCKOUT_THRESHOLD, LOCKOUT_DURATION_MINUTES
- `backend/app/database.py` — `get_db` async generator, `Base` declarative base
- `backend/tests/conftest.py` — `db_session` (clean session per test, rolled back), `client` (httpx AsyncClient with DB override)
- `backend/alembic/` — initial migration for all 7 tables

---

## Task 1: Package inits + Security Utility + Auth Schemas

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/security.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/services/__init__.py`

- [ ] **Step 1: Create all empty `__init__.py` files**

```bash
touch backend/app/utils/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/routers/__init__.py
touch backend/app/services/__init__.py
```

- [ ] **Step 2: Create `backend/app/utils/security.py`**

```python
import bcrypt
import hashlib
import datetime

import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(user_id: int, role: str, username: str) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "username": username,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

- [ ] **Step 3: Create `backend/app/schemas/auth.py`**

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserBrief(BaseModel):
    id: int
    username: str
    real_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool
    user: UserBrief
```

- [ ] **Step 4: Verify imports work**

Run: `cd backend && python -c "from app.utils.security import hash_password, verify_password, create_access_token; from app.schemas.auth import LoginRequest, LoginResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/ backend/app/schemas/ backend/app/routers/ backend/app/services/
git commit -m "feat: add package inits, security utility, and auth schemas"
```

---

## Task 2: Auth Login Endpoint — Success Path

**Files:**
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py` — include auth router
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing test for login success**

Create `backend/tests/test_auth.py`:

```python
import pytest
from tests.helpers import create_test_user, login_user


@pytest.mark.asyncio
async def test_login_success(client, db_session):
    user = await create_test_user(
        db_session, username="teacher1", password="teacher123", role="teacher", real_name="王老师"
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": "teacher1", "password": "teacher123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["must_change_password"] is True
    assert data["user"]["id"] == user.id
    assert data["user"]["username"] == "teacher1"
    assert data["user"]["real_name"] == "王老师"
    assert data["user"]["role"] == "teacher"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_auth.py::test_login_success -v`
Expected: FAIL (404 or connection error — router not registered yet)

- [ ] **Step 3: Implement auth login endpoint**

Create `backend/app/routers/auth.py`:

```python
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserBrief
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    now = datetime.datetime.utcnow()
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=403, detail="账号已被锁定，请稍后重试")

    if not verify_password(data.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOCKOUT_THRESHOLD:
            user.locked_until = now + datetime.timedelta(
                minutes=settings.LOCKOUT_DURATION_MINUTES
            )
        await db.flush()
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.failed_login_attempts = 0
    user.locked_until = None

    access_token = create_access_token(user.id, user.role, user.username)
    refresh_token_str = create_refresh_token(user.id)

    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token_str),
        expires_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    await db.flush()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        must_change_password=user.must_change_password,
        user=UserBrief(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            role=user.role,
        ),
    )
```

- [ ] **Step 4: Register auth router in main.py**

In `backend/app/main.py`, add after the CORS middleware block:

```python
from app.routers import auth as auth_router

app.include_router(auth_router.router)
```

The full `main.py` should become:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth as auth_router

app = FastAPI(
    title="数字实训教学管理平台",
    description="Digital Training Teaching Management Platform API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_auth.py::test_login_success -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/auth.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: add auth login endpoint with success path"
```

---

## Task 3: Auth Login — Failure Cases

**Files:**
- Modify: `backend/tests/test_auth.py`
- Modify: `backend/app/routers/auth.py` (already handles failures, just add tests)

- [ ] **Step 1: Write failing tests for login failures**

Append to `backend/tests/test_auth.py`:

```python
@pytest.mark.asyncio
async def test_login_wrong_password(client, db_session):
    await create_test_user(db_session, username="teacher1", password="teacher123", role="teacher")
    resp = await client.post(
        "/api/auth/login",
        json={"username": "teacher1", "password": "wrongpass"},
    )
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client, db_session):
    resp = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "whatever"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client, db_session):
    await create_test_user(
        db_session, username="disabled", password="pass123", role="student", is_active=False
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": "disabled", "password": "pass123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_locked_account(client, db_session):
    import datetime
    from app.models.user import User

    user = await create_test_user(
        db_session, username="locked_user", password="pass123", role="student"
    )
    user.locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    await db_session.flush()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "locked_user", "password": "pass123"},
    )
    assert resp.status_code == 403
    assert "锁定" in resp.json()["detail"]
```

- [ ] **Step 2: Run all auth tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_auth.py
git commit -m "test: add auth login failure case tests"
```

---

## Task 4: Test Helpers + Conftest Upload Fixture

**Files:**
- Create: `backend/tests/helpers.py`
- Modify: `backend/tests/conftest.py` — add `upload_dir` fixture

- [ ] **Step 1: Create `backend/tests/helpers.py`**

```python
import json
import datetime

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import Class
from app.models.task import Task
from app.models.user import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


async def create_test_user(
    db: AsyncSession,
    *,
    username: str,
    password: str = "testpass123",
    role: str = "student",
    real_name: str = "测试用户",
    is_active: bool = True,
    primary_class_id: int = None,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        real_name=real_name,
        role=role,
        is_active=is_active,
        primary_class_id=primary_class_id,
    )
    db.add(user)
    await db.flush()
    return user


async def create_test_class(
    db: AsyncSession,
    *,
    name: str = "测试班级",
    semester: str = "2025-2026-2",
    teacher_id: int = None,
) -> Class:
    cls = Class(name=name, semester=semester, teacher_id=teacher_id)
    db.add(cls)
    await db.flush()
    return cls


async def create_test_task(
    db: AsyncSession,
    *,
    title: str = "测试任务",
    class_id: int,
    created_by: int,
    deadline: datetime.datetime = None,
    allowed_file_types: list = None,
    **kwargs,
) -> Task:
    task = Task(
        title=title,
        class_id=class_id,
        created_by=created_by,
        deadline=deadline or datetime.datetime(2026, 12, 31),
        allowed_file_types=json.dumps(allowed_file_types or [".pdf", ".doc", ".docx"]),
        **kwargs,
    )
    db.add(task)
    await db.flush()
    return task


async def login_user(client, username: str, password: str = "testpass123") -> str:
    response = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: Add `upload_dir` fixture to conftest.py**

Append to `backend/tests/conftest.py`:

```python
import pytest
import pytest_asyncio


@pytest.fixture
def upload_dir(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "tmp").mkdir()

    original_upload_dir = settings.UPLOAD_DIR
    original_tmp_dir = settings.UPLOAD_TMP_DIR

    settings.UPLOAD_DIR = str(uploads)
    settings.UPLOAD_TMP_DIR = str(uploads / "tmp")

    yield str(uploads)

    settings.UPLOAD_DIR = original_upload_dir
    settings.UPLOAD_TMP_DIR = original_tmp_dir
```

Note: add `import pytest` at top of conftest.py if not present (it already has `import pytest_asyncio`).

The `import pytest` line should be added at line 1. The fixture function should be added after the existing `client` fixture (after line 74).

- [ ] **Step 3: Verify helpers import works**

Run: `cd backend && python -c "from tests.helpers import create_test_user, login_user, auth_headers; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/tests/helpers.py backend/tests/conftest.py
git commit -m "feat: add test helpers and upload_dir fixture"
```

---

## Task 5: Seed Demo Script

**Files:**
- Create: `backend/scripts/seed_demo.py`

- [ ] **Step 1: Create seed script**

Create `backend/scripts/seed_demo.py`:

```python
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.class_ import Class
from app.models.user import User
from app.utils.security import hash_password


async def seed():
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Demo data already exists, skipping.")
            return

        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            real_name="系统管理员",
            role="admin",
            must_change_password=True,
        )
        db.add(admin)
        await db.flush()

        teacher = User(
            username="teacher1",
            password_hash=hash_password("teacher123"),
            real_name="王老师",
            role="teacher",
            must_change_password=True,
        )
        db.add(teacher)
        await db.flush()

        cls = Class(
            name="计算机网络1班",
            semester="2025-2026-2",
            teacher_id=teacher.id,
        )
        db.add(cls)
        await db.flush()

        student = User(
            username="student1",
            password_hash=hash_password("student123"),
            real_name="张三",
            role="student",
            primary_class_id=cls.id,
            must_change_password=True,
        )
        db.add(student)
        await db.flush()

        await db.commit()
        print(f"Created: admin({admin.id}), teacher1({teacher.id}), class({cls.id}), student1({student.id})")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 2: Verify script syntax**

Run: `cd backend && python -c "import ast; ast.parse(open('scripts/seed_demo.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_demo.py
git commit -m "feat: add demo data seeding script"
```

---

## Task 6: Class Schemas + POST /api/classes

**Files:**
- Create: `backend/app/schemas/class_.py`
- Create: `backend/app/routers/classes.py`
- Create: `backend/tests/test_classes.py`
- Modify: `backend/app/main.py` — include class router

- [ ] **Step 1: Create class schemas**

Create `backend/app/schemas/class_.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClassCreate(BaseModel):
    name: str
    semester: str
    teacher_id: Optional[int] = None


class ClassResponse(BaseModel):
    id: int
    name: str
    semester: str
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    student_count: int = 0
    created_at: datetime
```

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_classes.py`:

```python
import pytest
from tests.helpers import create_test_user, create_test_class, login_user, auth_headers


@pytest.mark.asyncio
async def test_create_class_success(client, db_session):
    admin = await create_test_user(db_session, username="admin1", role="admin", real_name="管理员")
    teacher = await create_test_user(db_session, username="teacher1", role="teacher", real_name="王老师")
    token = await login_user(client, "admin1")

    resp = await client.post(
        "/api/classes",
        json={"name": "计算机网络1班", "semester": "2025-2026-2", "teacher_id": teacher.id},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "计算机网络1班"
    assert data["semester"] == "2025-2026-2"
    assert data["teacher_id"] == teacher.id
    assert data["teacher_name"] == "王老师"
    assert data["student_count"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_create_class_forbidden_for_teacher(client, db_session):
    await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/classes",
        json={"name": "班级", "semester": "2025-2026-2"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_classes.py -v`
Expected: FAIL (404 — router not registered)

- [ ] **Step 4: Implement POST /api/classes**

Create `backend/app/routers/classes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.user import User
from app.schemas.class_ import ClassCreate, ClassResponse

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    data: ClassCreate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    cls = Class(name=data.name, semester=data.semester, teacher_id=data.teacher_id)
    db.add(cls)
    await db.flush()

    teacher_name = None
    if cls.teacher_id:
        result = await db.execute(select(User.real_name).where(User.id == cls.teacher_id))
        teacher_name = result.scalar_one_or_none()

    count_result = await db.execute(
        select(func.count()).select_from(User).where(User.primary_class_id == cls.id)
    )
    student_count = count_result.scalar() or 0

    return ClassResponse(
        id=cls.id,
        name=cls.name,
        semester=cls.semester,
        teacher_id=cls.teacher_id,
        teacher_name=teacher_name,
        student_count=student_count,
        created_at=cls.created_at,
    )
```

- [ ] **Step 5: Register class router in main.py**

Add to `backend/app/main.py` imports and include:

```python
from app.routers import auth as auth_router
from app.routers import classes as classes_router

app.include_router(auth_router.router)
app.include_router(classes_router.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_classes.py -v`
Expected: 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/class_.py backend/app/routers/classes.py backend/tests/test_classes.py backend/app/main.py
git commit -m "feat: add class schemas and POST /api/classes endpoint"
```

---

## Task 7: GET /api/classes/my

**Files:**
- Modify: `backend/app/routers/classes.py`
- Modify: `backend/tests/test_classes.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_classes.py`:

```python
@pytest.mark.asyncio
async def test_get_my_classes(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, name="计算机网络1班", teacher_id=teacher.id)
    await create_test_class(db_session, name="其他班级")

    token = await login_user(client, "teacher1")
    resp = await client.get("/api/classes/my", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "计算机网络1班"
    assert data[0]["teacher_id"] == teacher.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_classes.py::test_get_my_classes -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement GET /api/classes/my**

Add to `backend/app/routers/classes.py` (after `create_class`):

```python
@router.get("/my", response_model=list[ClassResponse])
async def get_my_classes(
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Class).where(Class.teacher_id == current_user["id"])
    )
    classes = result.scalars().all()

    response = []
    for cls in classes:
        teacher_name = None
        if cls.teacher_id:
            t_result = await db.execute(select(User.real_name).where(User.id == cls.teacher_id))
            teacher_name = t_result.scalar_one_or_none()

        count_result = await db.execute(
            select(func.count()).select_from(User).where(User.primary_class_id == cls.id)
        )
        student_count = count_result.scalar() or 0

        response.append(ClassResponse(
            id=cls.id,
            name=cls.name,
            semester=cls.semester,
            teacher_id=cls.teacher_id,
            teacher_name=teacher_name,
            student_count=student_count,
            created_at=cls.created_at,
        ))
    return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_classes.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/classes.py backend/tests/test_classes.py
git commit -m "feat: add GET /api/classes/my endpoint"
```

---

## Task 8: GET /api/classes/:id/students

**Files:**
- Modify: `backend/app/routers/classes.py`
- Modify: `backend/tests/test_classes.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_classes.py`:

```python
@pytest.mark.asyncio
async def test_get_class_students(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    s1 = await create_test_user(db_session, username="stu1", role="student", real_name="张三", primary_class_id=cls.id)
    s2 = await create_user(db_session, username="stu2", role="student", real_name="李四", primary_class_id=cls.id)

    token = await login_user(client, "teacher1")
    resp = await client.get(f"/api/classes/{cls.id}/students", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {s["real_name"] for s in data}
    assert names == {"张三", "李四"}
```

Note: there's a typo in the test — `create_user` should be `create_test_user`. Corrected version:

```python
@pytest.mark.asyncio
async def test_get_class_students(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", real_name="张三", primary_class_id=cls.id)
    await create_test_user(db_session, username="stu2", role="student", real_name="李四", primary_class_id=cls.id)

    token = await login_user(client, "teacher1")
    resp = await client.get(f"/api/classes/{cls.id}/students", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {s["real_name"] for s in data}
    assert names == {"张三", "李四"}


@pytest.mark.asyncio
async def test_get_class_students_forbidden_for_other_teacher(client, db_session):
    teacher1 = await create_test_user(db_session, username="teacher1", role="teacher")
    teacher2 = await create_test_user(db_session, username="teacher2", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher1.id)

    token = await login_user(client, "teacher2")
    resp = await client.get(f"/api/classes/{cls.id}/students", headers=auth_headers(token))
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_classes.py::test_get_class_students -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement GET /api/classes/:id/students**

Add to `backend/app/schemas/class_.py`:

```python
class StudentBrief(BaseModel):
    id: int
    username: str
    real_name: str
```

Add to `backend/app/routers/classes.py`:

```python
from app.schemas.class_ import ClassCreate, ClassResponse, StudentBrief


@router.get("/{class_id}/students", response_model=list[StudentBrief])
async def get_class_students(
    class_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    if current_user["role"] not in ("admin",):
        if current_user["role"] == "teacher" and cls.teacher_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该班级学生")
        if current_user["role"] == "student":
            raise HTTPException(status_code=403, detail="无权查看班级学生列表")

    result = await db.execute(
        select(User.id, User.username, User.real_name)
        .where(User.primary_class_id == class_id)
        .order_by(User.id)
    )
    rows = result.all()
    return [StudentBrief(id=r[0], username=r[1], real_name=r[2]) for r in rows]
```

- [ ] **Step 4: Run all class tests**

Run: `cd backend && python -m pytest tests/test_classes.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/classes.py backend/app/schemas/class_.py backend/tests/test_classes.py
git commit -m "feat: add GET /api/classes/:id/students endpoint"
```

---

## Task 9: Task Schemas + POST /api/tasks

**Files:**
- Create: `backend/app/schemas/task.py`
- Create: `backend/app/routers/tasks.py`
- Create: `backend/tests/test_tasks.py`
- Modify: `backend/app/main.py` — include task router

- [ ] **Step 1: Create task schemas**

Create `backend/app/schemas/task.py`:

```python
import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    class_id: int
    deadline: datetime
    allowed_file_types: List[str]
    max_file_size_mb: int = 50
    allow_late_submission: bool = False
    late_penalty_percent: Optional[float] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    class_id: int
    class_name: str
    created_by: int
    deadline: datetime
    allowed_file_types: List[str]
    max_file_size_mb: int
    allow_late_submission: bool
    late_penalty_percent: Optional[float] = None
    status: str
    grades_published: bool
    created_at: datetime
```

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_tasks.py`:

```python
import datetime
import pytest
from tests.helpers import create_test_user, create_test_class, login_user, auth_headers


@pytest.mark.asyncio
async def test_create_task_success(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    token = await login_user(client, "teacher1")

    resp = await client.post(
        "/api/tasks",
        json={
            "title": "网络协议实验报告",
            "description": "完成Wireshark抓包分析",
            "class_id": cls.id,
            "deadline": "2026-06-01T23:59:59",
            "allowed_file_types": [".pdf", ".docx"],
            "max_file_size_mb": 20,
            "allow_late_submission": True,
            "late_penalty_percent": 10.0,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "网络协议实验报告"
    assert data["class_id"] == cls.id
    assert data["created_by"] == teacher.id
    assert data["status"] == "active"
    assert data["grades_published"] is False
    assert data["allowed_file_types"] == [".pdf", ".docx"]
    assert data["allow_late_submission"] is True
    assert data["late_penalty_percent"] == 10.0


@pytest.mark.asyncio
async def test_create_task_not_own_class(client, db_session):
    teacher1 = await create_test_user(db_session, username="teacher1", role="teacher")
    teacher2 = await create_test_user(db_session, username="teacher2", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher1.id)

    token = await login_user(client, "teacher2")
    resp = await client.post(
        "/api/tasks",
        json={
            "title": "任务",
            "class_id": cls.id,
            "deadline": "2026-06-01T23:59:59",
            "allowed_file_types": [".pdf"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tasks.py -v`
Expected: FAIL (404)

- [ ] **Step 4: Implement POST /api/tasks**

Create `backend/app/routers/tasks.py`:

```python
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_to_response(task: Task, class_name: str) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        requirements=task.requirements,
        class_id=task.class_id,
        class_name=class_name,
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


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Class).where(Class.id == data.class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    if cls.teacher_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能为自己的班级创建任务")

    task = Task(
        title=data.title,
        description=data.description,
        requirements=data.requirements,
        class_id=data.class_id,
        created_by=current_user["id"],
        deadline=data.deadline,
        allowed_file_types=json.dumps(data.allowed_file_types),
        max_file_size_mb=data.max_file_size_mb,
        allow_late_submission=data.allow_late_submission,
        late_penalty_percent=data.late_penalty_percent,
    )
    db.add(task)
    await db.flush()

    return _task_to_response(task, cls.name)
```

- [ ] **Step 5: Register task router in main.py**

Add to `backend/app/main.py` imports and include:

```python
from app.routers import tasks as tasks_router

app.include_router(tasks_router.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_tasks.py -v`
Expected: 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/task.py backend/app/routers/tasks.py backend/tests/test_tasks.py backend/app/main.py
git commit -m "feat: add task schemas and POST /api/tasks endpoint"
```

---

## Task 10: GET /api/tasks/my

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_tasks.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_tasks.py`:

```python
@pytest.mark.asyncio
async def test_get_my_tasks_student(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(
        db_session, username="stu1", role="student", primary_class_id=cls.id
    )
    await create_test_task(db_session, title="任务1", class_id=cls.id, created_by=teacher.id)
    await create_test_task(db_session, title="任务2", class_id=cls.id, created_by=teacher.id)

    token = await login_user(client, "stu1")
    resp = await client.get("/api/tasks/my", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = {t["title"] for t in data}
    assert titles == {"任务1", "任务2"}


@pytest.mark.asyncio
async def test_get_my_tasks_teacher(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_task(db_session, title="我的任务", class_id=cls.id, created_by=teacher.id)

    token = await login_user(client, "teacher1")
    resp = await client.get("/api/tasks/my", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "我的任务"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tasks.py::test_get_my_tasks_student -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement GET /api/tasks/my**

Add to `backend/app/routers/tasks.py`:

```python
@router.get("/my", response_model=list[TaskResponse])
async def get_my_tasks(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "student":
        result = await db.execute(
            select(Task)
            .where(Task.class_id == select(User.primary_class_id).where(User.id == current_user["id"]))
            .where(Task.status == "active")
            .order_by(Task.deadline)
        )
    elif current_user["role"] == "teacher":
        result = await db.execute(
            select(Task)
            .where(Task.created_by == current_user["id"])
            .order_by(Task.created_at.desc())
        )
    else:
        result = await db.execute(select(Task).order_by(Task.created_at.desc()))

    tasks = result.scalars().all()
    response = []
    for task in tasks:
        cls_result = await db.execute(select(Class.name).where(Class.id == task.class_id))
        class_name = cls_result.scalar_one()
        response.append(_task_to_response(task, class_name))
    return response
```

Wait — the subquery approach for student is wrong. The student's `primary_class_id` is already in the token's user dict? No, `get_current_user` only returns `id`, `role`, `username`. We need to query the User model to get `primary_class_id`.

Corrected implementation:

```python
@router.get("/my", response_model=list[TaskResponse])
async def get_my_tasks(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] == "student":
        user_result = await db.execute(select(User.primary_class_id).where(User.id == current_user["id"]))
        class_id = user_result.scalar_one_or_none()
        if not class_id:
            return []
        result = await db.execute(
            select(Task)
            .where(Task.class_id == class_id)
            .where(Task.status == "active")
            .order_by(Task.deadline)
        )
    elif current_user["role"] == "teacher":
        result = await db.execute(
            select(Task)
            .where(Task.created_by == current_user["id"])
            .order_by(Task.created_at.desc())
        )
    else:
        return []

    tasks = result.scalars().all()
    response = []
    for task in tasks:
        cls_result = await db.execute(select(Class.name).where(Class.id == task.class_id))
        class_name = cls_result.scalar_one()
        response.append(_task_to_response(task, class_name))
    return response
```

Also add `from app.models.user import User` to the imports in tasks.py.

- [ ] **Step 4: Run all task tests**

Run: `cd backend && python -m pytest tests/test_tasks.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/tasks.py backend/tests/test_tasks.py
git commit -m "feat: add GET /api/tasks/my endpoint for students and teachers"
```

---

## Task 11: GET /api/tasks/:id

**Files:**
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/tests/test_tasks.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_tasks.py`:

```python
@pytest.mark.asyncio
async def test_get_task_detail_student_in_class(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, title="网络实验", class_id=cls.id, created_by=teacher.id)

    token = await login_user(client, "stu1")
    resp = await client.get(f"/api/tasks/{task.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "网络实验"


@pytest.mark.asyncio
async def test_get_task_detail_forbidden_other_student(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    cls2 = await create_test_class(db_session, name="其他班")
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    await create_test_user(db_session, username="outsider", role="student", primary_class_id=cls2.id)

    token = await login_user(client, "outsider")
    resp = await client.get(f"/api/tasks/{task.id}", headers=auth_headers(token))
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tasks.py::test_get_task_detail_student_in_class -v`
Expected: FAIL (404 or 405)

- [ ] **Step 3: Implement GET /api/tasks/:id**

Add to `backend/app/routers/tasks.py`:

```python
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_detail(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if current_user["role"] == "admin":
        pass
    elif current_user["role"] == "teacher":
        if task.created_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该任务")
    elif current_user["role"] == "student":
        user_result = await db.execute(
            select(User.primary_class_id).where(User.id == current_user["id"])
        )
        if user_result.scalar_one() != task.class_id:
            raise HTTPException(status_code=403, detail="无权查看该任务")
    else:
        raise HTTPException(status_code=403)

    cls_result = await db.execute(select(Class.name).where(Class.id == task.class_id))
    class_name = cls_result.scalar_one()
    return _task_to_response(task, class_name)
```

- [ ] **Step 4: Run all task tests**

Run: `cd backend && python -m pytest tests/test_tasks.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/tasks.py backend/tests/test_tasks.py
git commit -m "feat: add GET /api/tasks/:id endpoint with role-based access control"
```

---

## Task 12: File Upload Endpoint

**Files:**
- Create: `backend/app/schemas/file.py`
- Create: `backend/app/routers/files.py`
- Create: `backend/tests/test_files.py`
- Modify: `backend/app/main.py` — include file router

- [ ] **Step 1: Create file schema**

Create `backend/app/schemas/file.py`:

```python
from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    file_token: str
    file_name: str
    file_size: int
    file_type: str
```

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_files.py`:

```python
import io
import pytest
from tests.helpers import create_test_user, login_user, auth_headers


@pytest.mark.asyncio
async def test_upload_file_success(client, db_session, upload_dir):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    file_content = b"Test PDF content for upload"
    resp = await client.post(
        "/api/files/upload",
        files={"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_token"]
    assert data["file_name"] == "report.pdf"
    assert data["file_size"] == len(file_content)
    assert data["file_type"] == ".pdf"


@pytest.mark.asyncio
async def test_upload_file_rejected_type(client, db_session, upload_dir):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.post(
        "/api/files/upload",
        files={"file": ("malware.exe", io.BytesIO(b"bad"), "application/octet-stream")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_files.py -v`
Expected: FAIL (404)

- [ ] **Step 4: Implement POST /api/files/upload**

Create `backend/app/routers/files.py`:

```python
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.file import FileUploadResponse

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    filename = file.filename or "unnamed"
    file_ext = os.path.splitext(filename)[1].lower()

    if file_ext not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的文件类型: {file_ext}",
        )

    contents = await file.read()
    if len(contents) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail=f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)",
        )

    file_token = str(uuid.uuid4())
    final_name = f"{file_token}_{filename}"
    final_path = os.path.join(settings.UPLOAD_DIR, final_name)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(final_path, "wb") as f:
        f.write(contents)

    return FileUploadResponse(
        file_token=file_token,
        file_name=filename,
        file_size=len(contents),
        file_type=file_ext,
    )
```

- [ ] **Step 5: Register file router in main.py**

Add to `backend/app/main.py` imports and include:

```python
from app.routers import files as files_router

app.include_router(files_router.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_files.py -v`
Expected: 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/file.py backend/app/routers/files.py backend/tests/test_files.py backend/app/main.py
git commit -m "feat: add file upload endpoint with type/size validation"
```

---

## Task 13: File Download Endpoint

**Files:**
- Modify: `backend/app/routers/files.py`
- Modify: `backend/tests/test_files.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_files.py`:

```python
import io
import os
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile


@pytest.mark.asyncio
async def test_download_file_success(client, db_session, upload_dir):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    student = await create_test_user(db_session, username="stu1", role="student")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student.primary_class_id = cls.id
    await db_session.flush()

    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    file_path = os.path.join(upload_dir, "test_report.pdf")
    with open(file_path, "wb") as f:
        f.write(b"PDF content here")

    sf = SubmissionFile(
        submission_id=sub.id,
        file_name="report.pdf",
        file_path=file_path,
        file_size=14,
        file_type=".pdf",
    )
    db_session.add(sf)
    await db_session.flush()

    token = await login_user(client, "stu1")
    resp = await client.get(f"/api/files/{sf.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.content == b"PDF content here"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_files.py::test_download_file_success -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement GET /api/files/:id**

Add to `backend/app/routers/files.py`:

```python
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.task import Task
from app.models.user import User


@router.get("/{file_id}")
async def download_file(
    file_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SubmissionFile).where(SubmissionFile.id == file_id))
    sf = result.scalar_one_or_none()
    if not sf:
        raise HTTPException(status_code=404, detail="文件不存在")

    sub_result = await db.execute(select(Submission).where(Submission.id == sf.submission_id))
    submission = sub_result.scalar_one()

    task_result = await db.execute(select(Task).where(Task.id == submission.task_id))
    task = task_result.scalar_one()

    if current_user["role"] == "admin":
        pass
    elif current_user["role"] == "teacher":
        if task.created_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权下载该文件")
    elif current_user["role"] == "student":
        if submission.student_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权下载该文件")
    else:
        raise HTTPException(status_code=403)

    if not os.path.exists(sf.file_path):
        raise HTTPException(status_code=404, detail="文件已被删除")

    return FileResponse(
        path=sf.file_path,
        filename=sf.file_name,
        media_type="application/octet-stream",
    )
```

Also ensure `import os` is at the top (it is, from the upload endpoint).

- [ ] **Step 4: Run all file tests**

Run: `cd backend && python -m pytest tests/test_files.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/files.py backend/tests/test_files.py
git commit -m "feat: add file download endpoint with ownership validation"
```

---

## Task 14: Submission Schemas + POST /api/tasks/:id/submissions

**Files:**
- Create: `backend/app/schemas/submission.py`
- Create: `backend/app/routers/submissions.py`
- Create: `backend/tests/test_submissions.py`
- Modify: `backend/app/main.py` — include submission router

- [ ] **Step 1: Create submission schemas**

Create `backend/app/schemas/submission.py`:

```python
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    file_tokens: List[str]


class SubmissionFileBrief(BaseModel):
    id: int
    file_name: str
    file_size: int
    file_type: str


class GradeBrief(BaseModel):
    score: float
    penalty_applied: Optional[float] = None
    feedback: Optional[str] = None
    graded_at: datetime


class SubmissionResponse(BaseModel):
    id: int
    task_id: int
    student_id: int
    student_name: Optional[str] = None
    version: int
    is_late: bool
    submitted_at: datetime
    updated_at: datetime
    files: List[SubmissionFileBrief] = []
    grade: Optional[GradeBrief] = None
```

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_submissions.py`:

```python
import io
import os
import datetime
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)


@pytest.mark.asyncio
async def test_submit_success(client, db_session, upload_dir):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(
        db_session, username="stu1", role="student", primary_class_id=cls.id
    )
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    stu_token = await login_user(client, "stu1")
    upload_resp = await client.post(
        "/api/files/upload",
        files={"file": ("report.pdf", io.BytesIO(b"PDF content"), "application/pdf")},
        headers=auth_headers(stu_token),
    )
    file_token = upload_resp.json()["file_token"]

    resp = await client.post(
        f"/api/tasks/{task.id}/submissions",
        json={"file_tokens": [file_token]},
        headers=auth_headers(stu_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_id"] == task.id
    assert data["student_id"] == student.id
    assert data["version"] == 1
    assert data["is_late"] is False
    assert len(data["files"]) == 1
    assert data["files"][0]["file_name"] == "report.pdf"


@pytest.mark.asyncio
async def test_submit_deadline_passed_reject(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(
        db_session,
        class_id=cls.id,
        created_by=teacher.id,
        deadline=datetime.datetime(2020, 1, 1),
    )

    token = await login_user(client, "stu1")
    resp = await client.post(
        f"/api/tasks/{task.id}/submissions",
        json={"file_tokens": ["fake-token"]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "截止" in resp.json()["detail"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_submissions.py -v`
Expected: FAIL (404)

- [ ] **Step 4: Implement POST /api/tasks/:id/submissions**

Create `backend/app/routers/submissions.py`:

```python
import glob
import os
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.class_ import Class
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.task import Task
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionResponse, SubmissionFileBrief

router = APIRouter(prefix="/api", tags=["submissions"])


@router.post("/tasks/{task_id}/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    task_id: int,
    data: SubmissionCreate,
    current_user: dict = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    user_result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = user_result.scalar_one()

    if user.primary_class_id != task.class_id:
        raise HTTPException(status_code=403, detail="你不属于该任务的班级")

    now = datetime.datetime.utcnow()
    is_late = now > task.deadline.replace(tzinfo=None) if task.deadline.tzinfo else now > task.deadline

    if is_late and not task.allow_late_submission:
        raise HTTPException(status_code=400, detail="已过截止日期，不允许迟交")

    file_infos = []
    for token in data.file_tokens:
        matches = glob.glob(os.path.join(settings.UPLOAD_DIR, f"{token}_*"))
        if not matches:
            raise HTTPException(status_code=400, detail=f"文件 {token} 不存在，请重新上传")
        file_infos.append((token, matches[0]))

    existing_result = await db.execute(
        select(Submission).where(
            Submission.task_id == task_id,
            Submission.student_id == current_user["id"],
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.version += 1
        existing.is_late = is_late
        existing.submitted_at = now
        existing.updated_at = now
        await db.flush()

        old_files_result = await db.execute(
            select(SubmissionFile).where(SubmissionFile.submission_id == existing.id)
        )
        for old_f in old_files_result.scalars().all():
            await db.delete(old_f)
        await db.flush()

        submission = existing
    else:
        submission = Submission(
            task_id=task_id,
            student_id=current_user["id"],
            is_late=is_late,
        )
        db.add(submission)
        await db.flush()

    for token, file_path in file_infos:
        original_name = os.path.basename(file_path).split("_", 1)[1]
        sf = SubmissionFile(
            submission_id=submission.id,
            file_name=original_name,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            file_type=os.path.splitext(original_name)[1],
        )
        db.add(sf)
    await db.flush()

    files_result = await db.execute(
        select(SubmissionFile).where(SubmissionFile.submission_id == submission.id)
    )
    files = [
        SubmissionFileBrief(id=f.id, file_name=f.file_name, file_size=f.file_size, file_type=f.file_type)
        for f in files_result.scalars().all()
    ]

    return SubmissionResponse(
        id=submission.id,
        task_id=submission.task_id,
        student_id=submission.student_id,
        version=submission.version,
        is_late=submission.is_late,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        files=files,
    )
```

- [ ] **Step 5: Register submission router in main.py**

Add to `backend/app/main.py` imports and include:

```python
from app.routers import submissions as submissions_router

app.include_router(submissions_router.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_submissions.py -v`
Expected: 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/submission.py backend/app/routers/submissions.py backend/tests/test_submissions.py backend/app/main.py
git commit -m "feat: add submission schemas and POST submit endpoint"
```

---

## Task 15: GET /api/submissions/:id

**Files:**
- Modify: `backend/app/routers/submissions.py`
- Modify: `backend/tests/test_submissions.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_submissions.py`:

```python
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.grade import Grade


@pytest.mark.asyncio
async def test_get_submission_own(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "stu1")
    resp = await client.get(f"/api/submissions/{sub.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == sub.id


@pytest.mark.asyncio
async def test_get_submission_grade_visible_only_when_published(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    grade = Grade(submission_id=sub.id, score=85.0, feedback="Good", graded_by=teacher.id)
    db_session.add(grade)
    await db_session.flush()

    token = await login_user(client, "stu1")

    resp = await client.get(f"/api/submissions/{sub.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["grade"] is None

    task.grades_published = True
    await db_session.flush()

    resp = await client.get(f"/api/submissions/{sub.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["grade"]["score"] == 85.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_submissions.py::test_get_submission_own -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement GET /api/submissions/:id**

Add to `backend/app/routers/submissions.py` (add imports and endpoint):

Add to imports:
```python
from app.schemas.submission import GradeBrief
```

Add endpoint:
```python
@router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")

    task_result = await db.execute(select(Task).where(Task.id == submission.task_id))
    task = task_result.scalar_one()

    if current_user["role"] == "admin":
        pass
    elif current_user["role"] == "teacher":
        if task.created_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该提交")
    elif current_user["role"] == "student":
        if submission.student_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="无权查看该提交")
    else:
        raise HTTPException(status_code=403)

    user_result = await db.execute(select(User.real_name).where(User.id == submission.student_id))
    student_name = user_result.scalar_one_or_none()

    files_result = await db.execute(
        select(SubmissionFile).where(SubmissionFile.submission_id == submission.id)
    )
    files = [
        SubmissionFileBrief(id=f.id, file_name=f.file_name, file_size=f.file_size, file_type=f.file_type)
        for f in files_result.scalars().all()
    ]

    grade_data = None
    grade_result = await db.execute(select(Grade).where(Grade.submission_id == submission.id))
    grade = grade_result.scalar_one_or_none()

    if grade:
        show_grade = False
        if current_user["role"] in ("admin", "teacher"):
            show_grade = True
        elif current_user["role"] == "student" and task.grades_published:
            show_grade = True

        if show_grade:
            grade_data = GradeBrief(
                score=grade.score,
                penalty_applied=grade.penalty_applied,
                feedback=grade.feedback,
                graded_at=grade.graded_at,
            )

    return SubmissionResponse(
        id=submission.id,
        task_id=submission.task_id,
        student_id=submission.student_id,
        student_name=student_name,
        version=submission.version,
        is_late=submission.is_late,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        files=files,
        grade=grade_data,
    )
```

Add `from app.models.grade import Grade` to the imports.

- [ ] **Step 4: Run all submission tests**

Run: `cd backend && python -m pytest tests/test_submissions.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/submissions.py backend/tests/test_submissions.py
git commit -m "feat: add GET /api/submissions/:id with grade visibility control"
```

---

## Task 16: GET /api/tasks/:id/submissions (Teacher List)

**Files:**
- Modify: `backend/app/routers/submissions.py`
- Modify: `backend/tests/test_submissions.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_submissions.py`:

```python
@pytest.mark.asyncio
async def test_teacher_list_submissions(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    s1 = await create_test_user(db_session, username="stu1", role="student", real_name="张三", primary_class_id=cls.id)
    s2 = await create_test_user(db_session, username="stu2", role="student", real_name="李四", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub1 = Submission(task_id=task.id, student_id=s1.id)
    sub2 = Submission(task_id=task.id, student_id=s2.id)
    db_session.add_all([sub1, sub2])
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.get(f"/api/tasks/{task.id}/submissions", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {s["student_name"] for s in data}
    assert names == {"张三", "李四"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_submissions.py::test_teacher_list_submissions -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement GET /api/tasks/:id/submissions**

Add to `backend/app/routers/submissions.py`:

```python
@router.get("/tasks/{task_id}/submissions", response_model=list[SubmissionResponse])
async def list_task_submissions(
    task_id: int,
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能查看自己任务的提交")

    result = await db.execute(
        select(Submission).where(Submission.task_id == task_id)
    )
    submissions = result.scalars().all()

    response = []
    for sub in submissions:
        user_result = await db.execute(select(User.real_name).where(User.id == sub.student_id))
        student_name = user_result.scalar_one_or_none()

        files_result = await db.execute(
            select(SubmissionFile).where(SubmissionFile.submission_id == sub.id)
        )
        files = [
            SubmissionFileBrief(id=f.id, file_name=f.file_name, file_size=f.file_size, file_type=f.file_type)
            for f in files_result.scalars().all()
        ]

        grade_result = await db.execute(select(Grade).where(Grade.submission_id == sub.id))
        grade = grade_result.scalar_one_or_none()
        grade_data = None
        if grade:
            grade_data = GradeBrief(
                score=grade.score,
                penalty_applied=grade.penalty_applied,
                feedback=grade.feedback,
                graded_at=grade.graded_at,
            )

        response.append(SubmissionResponse(
            id=sub.id,
            task_id=sub.task_id,
            student_id=sub.student_id,
            student_name=student_name,
            version=sub.version,
            is_late=sub.is_late,
            submitted_at=sub.submitted_at,
            updated_at=sub.updated_at,
            files=files,
            grade=grade_data,
        ))
    return response
```

- [ ] **Step 4: Run all submission tests**

Run: `cd backend && python -m pytest tests/test_submissions.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/submissions.py backend/tests/test_submissions.py
git commit -m "feat: add GET /api/tasks/:id/submissions teacher list endpoint"
```

---

## Task 17: Grade Schemas + POST /api/tasks/:id/grades

**Files:**
- Create: `backend/app/schemas/grade.py`
- Create: `backend/app/routers/grades.py`
- Create: `backend/tests/test_grades.py`
- Modify: `backend/app/main.py` — include grade router

- [ ] **Step 1: Create grade schemas**

Create `backend/app/schemas/grade.py`:

```python
from typing import Optional

from pydantic import BaseModel


class GradeCreate(BaseModel):
    submission_id: int
    score: float
    feedback: Optional[str] = None


class GradeResponse(BaseModel):
    id: int
    submission_id: int
    score: float
    penalty_applied: Optional[float] = None
    feedback: Optional[str] = None
    graded_by: int
```

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_grades.py`:

```python
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)
from app.models.submission import Submission


@pytest.mark.asyncio
async def test_grade_submission(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades",
        json={"submission_id": sub.id, "score": 85.0, "feedback": "Good work"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 85.0
    assert data["feedback"] == "Good work"
    assert data["submission_id"] == sub.id
    assert data["penalty_applied"] is None


@pytest.mark.asyncio
async def test_grade_late_submission_auto_penalty(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(
        db_session, class_id=cls.id, created_by=teacher.id,
        allow_late_submission=True, late_penalty_percent=20.0,
    )

    sub = Submission(task_id=task.id, student_id=student.id, is_late=True)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades",
        json={"submission_id": sub.id, "score": 80.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 80.0
    assert data["penalty_applied"] == 16.0  # 80 * 20%


@pytest.mark.asyncio
async def test_grade_invalid_score(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades",
        json={"submission_id": sub.id, "score": 150.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_grades.py -v`
Expected: FAIL (404)

- [ ] **Step 4: Implement POST /api/tasks/:id/grades**

Create `backend/app/routers/grades.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.grade import Grade
from app.models.submission import Submission
from app.models.task import Task
from app.schemas.grade import GradeCreate, GradeResponse

router = APIRouter(prefix="/api", tags=["grades"])


@router.post("/tasks/{task_id}/grades", response_model=GradeResponse)
async def grade_submission(
    task_id: int,
    data: GradeCreate,
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能评自己创建的任务")

    if data.score < 0 or data.score > 100:
        raise HTTPException(status_code=422, detail="分数必须在 0-100 之间")

    sub_result = await db.execute(select(Submission).where(Submission.id == data.submission_id))
    submission = sub_result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")

    if submission.task_id != task_id:
        raise HTTPException(status_code=400, detail="提交不属于该任务")

    penalty_applied = None
    if submission.is_late and task.late_penalty_percent:
        penalty_applied = round(data.score * task.late_penalty_percent / 100, 2)

    existing = await db.execute(
        select(Grade).where(Grade.submission_id == data.submission_id)
    )
    existing_grade = existing.scalar_one_or_none()

    if existing_grade:
        existing_grade.score = data.score
        existing_grade.feedback = data.feedback
        existing_grade.penalty_applied = penalty_applied
        existing_grade.graded_by = current_user["id"]
        await db.flush()
        grade = existing_grade
    else:
        grade = Grade(
            submission_id=data.submission_id,
            score=data.score,
            feedback=data.feedback,
            penalty_applied=penalty_applied,
            graded_by=current_user["id"],
        )
        db.add(grade)
        await db.flush()

    return GradeResponse(
        id=grade.id,
        submission_id=grade.submission_id,
        score=grade.score,
        penalty_applied=grade.penalty_applied,
        feedback=grade.feedback,
        graded_by=grade.graded_by,
    )
```

- [ ] **Step 5: Register grade router in main.py**

Add to `backend/app/main.py` imports and include:

```python
from app.routers import grades as grades_router

app.include_router(grades_router.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_grades.py -v`
Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/grade.py backend/app/routers/grades.py backend/tests/test_grades.py backend/app/main.py
git commit -m "feat: add grade schemas and POST /api/tasks/:id/grades endpoint"
```

---

## Task 18: POST grades/publish + POST grades/unpublish

**Files:**
- Modify: `backend/app/routers/grades.py`
- Modify: `backend/tests/test_grades.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_grades.py`:

```python
@pytest.mark.asyncio
async def test_publish_grades(client, db_session):
    import datetime
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)

    sub = Submission(task_id=task.id, student_id=student.id)
    db_session.add(sub)
    await db_session.flush()

    grade = Grade(submission_id=sub.id, score=90.0, graded_by=teacher.id)
    db_session.add(grade)
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/publish",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["grades_published"] is True

    await db_session.flush()
    result = await db_session.execute(select(Task).where(Task.id == task.id))
    refreshed = result.scalar_one()
    assert refreshed.grades_published is True


@pytest.mark.asyncio
async def test_unpublish_grades(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    cls = await create_test_class(db_session, teacher_id=teacher.id)
    student = await create_test_user(db_session, username="stu1", role="student", primary_class_id=cls.id)
    task = await create_test_task(db_session, class_id=cls.id, created_by=teacher.id)
    task.grades_published = True
    await db_session.flush()

    token = await login_user(client, "teacher1")
    resp = await client.post(
        f"/api/tasks/{task.id}/grades/unpublish",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["grades_published"] is False
```

Note: the test needs these additional imports at the top of `test_grades.py`:

```python
from app.models.grade import Grade
from sqlalchemy import select
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_grades.py::test_publish_grades -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement publish and unpublish endpoints**

Add to `backend/app/routers/grades.py`:

```python
import datetime

from app.models.task import Task
from app.schemas.grade import GradeCreate, GradeResponse


@router.post("/tasks/{task_id}/grades/publish")
async def publish_grades(
    task_id: int,
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能发布自己任务的成绩")

    task.grades_published = True
    task.grades_published_at = datetime.datetime.utcnow()
    task.grades_published_by = current_user["id"]
    await db.flush()

    return {"grades_published": True, "task_id": task_id}


@router.post("/tasks/{task_id}/grades/unpublish")
async def unpublish_grades(
    task_id: int,
    current_user: dict = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.created_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能取消发布自己任务的成绩")

    task.grades_published = False
    task.grades_published_at = None
    task.grades_published_by = None
    await db.flush()

    return {"grades_published": False, "task_id": task_id}
```

Remove the duplicate import of `Task` if it already exists at the top of the file.

- [ ] **Step 4: Run all grade tests**

Run: `cd backend && python -m pytest tests/test_grades.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/grades.py backend/tests/test_grades.py
git commit -m "feat: add grade publish/unpublish endpoints"
```

---

## Task 19: File Cleanup Service

**Files:**
- Create: `backend/app/services/file_cleanup.py`

- [ ] **Step 1: Create the cleanup service**

Create `backend/app/services/file_cleanup.py`:

```python
import glob
import os
import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.submission_file import SubmissionFile


async def cleanup_orphan_files(db: AsyncSession) -> int:
    """Delete uploaded files older than 24h that have no SubmissionFile record."""
    upload_dir = settings.UPLOAD_DIR
    if not os.path.isdir(upload_dir):
        return 0

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    deleted = 0

    result = await db.execute(select(SubmissionFile.file_path))
    tracked_paths = set(result.scalars().all())

    for filepath in glob.glob(os.path.join(upload_dir, "*")):
        if os.path.isdir(filepath):
            continue

        if filepath in tracked_paths:
            continue

        try:
            mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                os.remove(filepath)
                deleted += 1
        except OSError:
            continue

    return deleted
```

- [ ] **Step 2: Verify syntax and imports**

Run: `cd backend && python -c "from app.services.file_cleanup import cleanup_orphan_files; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/file_cleanup.py
git commit -m "feat: add orphan file cleanup service"
```

---

## Task 20: E2E Minimum Loop Test

**Files:**
- Create: `backend/tests/test_min_loop.py`

- [ ] **Step 1: Write the end-to-end closed loop test**

Create `backend/tests/test_min_loop.py`:

```python
import io
import pytest
from tests.helpers import (
    create_test_user, create_test_class, create_test_task,
    login_user, auth_headers,
)


@pytest.mark.asyncio
async def test_minimum_closed_loop(client, db_session, upload_dir):
    # --- Setup: admin creates class, assigns teacher ---
    admin = await create_test_user(db_session, username="admin", password="admin123", role="admin", real_name="管理员")
    teacher = await create_test_user(db_session, username="teacher1", password="teacher123", role="teacher", real_name="王老师")
    student = await create_test_user(db_session, username="student1", password="student123", role="student", real_name="张三")

    admin_token = await login_user(client, "admin", "admin123")
    cls_resp = await client.post(
        "/api/classes",
        json={"name": "计算机网络1班", "semester": "2025-2026-2", "teacher_id": teacher.id},
        headers=auth_headers(admin_token),
    )
    assert cls_resp.status_code == 201
    class_id = cls_resp.json()["id"]

    student.primary_class_id = class_id
    await db_session.flush()

    # --- Step 1: Teacher creates a task ---
    teacher_token = await login_user(client, "teacher1", "teacher123")
    task_resp = await client.post(
        "/api/tasks",
        json={
            "title": "Wireshark抓包实验",
            "description": "完成三次握手抓包分析",
            "class_id": class_id,
            "deadline": "2026-12-31T23:59:59",
            "allowed_file_types": [".pdf", ".docx"],
            "max_file_size_mb": 20,
            "allow_late_submission": True,
            "late_penalty_percent": 10.0,
        },
        headers=auth_headers(teacher_token),
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]
    assert task_resp.json()["title"] == "Wireshark抓包实验"

    # --- Step 2: Student views available tasks ---
    student_token = await login_user(client, "student1", "student123")
    my_tasks_resp = await client.get("/api/tasks/my", headers=auth_headers(student_token))
    assert my_tasks_resp.status_code == 200
    assert len(my_tasks_resp.json()) == 1
    assert my_tasks_resp.json()[0]["id"] == task_id

    # --- Step 3: Student uploads a file ---
    upload_resp = await client.post(
        "/api/files/upload",
        files={"file": ("report.pdf", io.BytesIO(b"PDF report content"), "application/pdf")},
        headers=auth_headers(student_token),
    )
    assert upload_resp.status_code == 200
    file_token = upload_resp.json()["file_token"]
    assert file_token

    # --- Step 4: Student submits ---
    submit_resp = await client.post(
        f"/api/tasks/{task_id}/submissions",
        json={"file_tokens": [file_token]},
        headers=auth_headers(student_token),
    )
    assert submit_resp.status_code == 201
    submission_id = submit_resp.json()["id"]
    assert submit_resp.json()["version"] == 1
    assert submit_resp.json()["is_late"] is False
    assert len(submit_resp.json()["files"]) == 1

    # --- Step 5: Teacher views submissions ---
    subs_resp = await client.get(
        f"/api/tasks/{task_id}/submissions",
        headers=auth_headers(teacher_token),
    )
    assert subs_resp.status_code == 200
    assert len(subs_resp.json()) == 1
    assert subs_resp.json()[0]["student_name"] == "张三"
    assert subs_resp.json()[0]["grade"] is None

    # --- Step 6: Teacher grades ---
    grade_resp = await client.post(
        f"/api/tasks/{task_id}/grades",
        json={"submission_id": submission_id, "score": 92.0, "feedback": "分析很详细，继续保持"},
        headers=auth_headers(teacher_token),
    )
    assert grade_resp.status_code == 200
    assert grade_resp.json()["score"] == 92.0

    # --- Step 7: Student cannot see grade yet (not published) ---
    sub_detail_resp = await client.get(
        f"/api/submissions/{submission_id}",
        headers=auth_headers(student_token),
    )
    assert sub_detail_resp.status_code == 200
    assert sub_detail_resp.json()["grade"] is None

    # --- Step 8: Teacher publishes grades ---
    publish_resp = await client.post(
        f"/api/tasks/{task_id}/grades/publish",
        headers=auth_headers(teacher_token),
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["grades_published"] is True

    # --- Step 9: Student sees the grade ---
    final_resp = await client.get(
        f"/api/submissions/{submission_id}",
        headers=auth_headers(student_token),
    )
    assert final_resp.status_code == 200
    grade_data = final_resp.json()["grade"]
    assert grade_data is not None
    assert grade_data["score"] == 92.0
    assert grade_data["feedback"] == "分析很详细，继续保持"
```

- [ ] **Step 2: Run the E2E test**

Run: `cd backend && python -m pytest tests/test_min_loop.py -v`
Expected: 1 test PASS

- [ ] **Step 3: Run ALL tests to verify no regressions**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS (auth + classes + tasks + files + submissions + grades + min_loop)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_min_loop.py
git commit -m "test: add E2E minimum closed loop test"
```

---

## Self-Review Checklist

### Spec Coverage

| OpenSpec Task | Plan Task(s) |
|---|---|
| B.1 Login | Task 2, 3 |
| B.2 Seed demo | Task 5 |
| B.3 Class minimum (3 endpoints) | Task 6, 7, 8 |
| B.4 Task create+view (3 endpoints) | Task 9, 10, 11 |
| B.5 File upload (2 endpoints) | Task 12, 13 |
| B.6 Student submit (POST + GET /:id) | Task 14, 15 |
| B.7 Teacher view submissions | Task 16 |
| B.8 Grade + publish/unpublish | Task 17, 18 |
| B.9 E2E test | Task 20 |
| D.6 File cleanup service | Task 19 |

### Placeholder Scan

No TBD, TODO, "implement later", "add validation", "handle edge cases", or "similar to Task N" found. Every step contains exact code and exact commands.

### Type Consistency

- `SubmissionResponse` used in Tasks 14, 15, 16 — same schema file (`schemas/submission.py`)
- `ClassResponse` used in Tasks 6, 7, 8 — same schema file (`schemas/class_.py`)
- `TaskResponse` used in Tasks 9, 10, 11 — same schema file (`schemas/task.py`)
- `GradeResponse` used in Tasks 17, 18 — same schema file (`schemas/grade.py`)
- `auth_headers()` returns `{"Authorization": f"Bearer {token}"}` — consistent across all test files
- `require_role("admin")`, `require_role("teacher")`, `require_role("student")` — matches existing auth dependency signature
- `get_current_user` returns `{"id": int, "role": str, "username": str}` — used consistently for multi-role checks

---

## Summary

**20 tasks**, each 5-10 minutes. Total estimated implementation time: ~3 hours.

**Dependency chain:**
- Tasks 1-3: Foundation (security utility, auth endpoint) — must be first
- Task 4-5: Test helpers + seed — enables all subsequent tests
- Tasks 6-8: Classes — needed before tasks (tasks reference classes)
- Tasks 9-11: Tasks — needed before submissions (submissions reference tasks)
- Tasks 12-13: Files — needed before submissions (submissions link files)
- Tasks 14-16: Submissions — needed before grades (grades reference submissions)
- Tasks 17-18: Grades — final backend endpoints
- Task 19: File cleanup — independent service
- Task 20: E2E test — validates the entire loop
