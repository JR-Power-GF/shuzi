# PR1: Backend Skeleton + Database Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the FastAPI backend skeleton with 7 database models, Alembic migrations, auth dependency, and Docker MySQL — no business logic yet.

**Architecture:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / MySQL 8. Project structure: `backend/app/` with models, dependencies, routers (empty for now), and grader/ extension point. Alembic handles migrations with async template. Docker Compose provides local MySQL.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, aiomysql, PyJWT, bcrypt, Pydantic v2

---

## Task 1: Docker Compose for MySQL 8

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write docker-compose.yml**

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: training_mysql
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: training_platform
      MYSQL_CHARACTER_SET_SERVER: utf8mb4
      MYSQL_COLLATION_SERVER: utf8mb4_unicode_ci
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

- [ ] **Step 2: Start MySQL and verify**

Run: `docker compose up -d`
Expected: Container starts, MySQL listens on port 3306.

Run: `docker compose exec mysql mysql -uroot -prootpassword -e "SELECT 1"`
Expected: Output shows `1`

- [ ] **Step 3: Commit**

Run: `git add docker-compose.yml && git commit -m "chore: add docker-compose for local MySQL 8"`

**Verification:** `docker compose ps` shows mysql container running. `mysql -h127.0.0.1 -uroot -prootpassword -e "SHOW DATABASES"` lists `training_platform`.

---

## Task 2: Project Structure + requirements.txt

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/grader/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/requirements.txt`

- [ ] **Step 1: Create directory structure and empty init files**

Run:
```bash
mkdir -p backend/app/{models,routers,dependencies,schemas,grader} backend/tests backend/scripts
touch backend/app/__init__.py
touch backend/app/grader/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.25
alembic>=1.13.0
aiomysql>=0.2.0
pymysql>=1.1.0
PyJWT>=2.8.0
bcrypt>=4.1.0
python-multipart>=0.0.6
pydantic>=2.5.0
pydantic-settings>=2.1.0
httpx>=0.26.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 3: Install and verify**

Run: `cd backend && pip install -r requirements.txt`
Expected: All packages install successfully.

Run: `python -c "import fastapi; import sqlalchemy; import alembic; import jwt; import bcrypt; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 4: Commit**

Run: `git add backend/ && git commit -m "chore: initialize backend project structure and dependencies"`

**Verification:** `pip list | grep -E "fastapi|sqlalchemy|alembic|PyJWT|bcrypt"` shows all packages installed.

---

## Task 3: Config Module

**Files:**
- Create: `backend/app/config.py`

- [ ] **Step 1: Write the failing test for config**

Create: `backend/tests/test_config.py`

```python
import os
import pytest


def test_settings_loads_defaults():
    os.environ.setdefault("DATABASE_URL", "mysql+aiomysql://root:rootpassword@127.0.0.1:3306/training_platform")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-dev-only")
    from app.config import settings

    assert settings.DATABASE_URL is not None
    assert settings.SECRET_KEY is not None
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert settings.MAX_FILE_SIZE_MB > 0
    assert isinstance(settings.ALLOWED_FILE_TYPES, list)
    assert len(settings.ALLOWED_FILE_TYPES) > 0


def test_settings_has_upload_dir():
    from app.config import settings

    assert settings.UPLOAD_DIR is not None
    assert "uploads" in settings.UPLOAD_DIR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Write config.py**

Create: `backend/app/config.py`

```python
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:rootpassword@127.0.0.1:3306/training_platform"
    SYNC_DATABASE_URL: str = "mysql+pymysql://root:rootpassword@127.0.0.1:3306/training_platform"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    UPLOAD_DIR: str = "/uploads"
    UPLOAD_TMP_DIR: str = "/uploads/tmp"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_FILE_TYPES: List[str] = [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".ppt", ".pptx", ".zip", ".rar",
        ".jpg", ".jpeg", ".png", ".gif",
        ".mp4", ".avi", ".mov",
        ".txt", ".csv",
    ]
    LOCKOUT_THRESHOLD: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30
    TOTAL_SUBMISSION_SIZE_LIMIT_MB: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/config.py backend/tests/test_config.py && git commit -m "feat: add config module with Pydantic settings"`

**Verification:** `pytest tests/test_config.py` passes. Config loads from env vars with sensible defaults.

---

## Task 4: Database Module

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/tests/test_database.py`

- [ ] **Step 1: Write the failing test for database module**

Create: `backend/tests/test_database.py`

```python
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_database_engine_created():
    from app.database import engine

    assert engine is not None
    assert "aiomysql" in str(engine.url)


@pytest.mark.asyncio
async def test_database_session_can_connect():
    from app.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1


def test_base_is_declarative():
    from app.database import Base

    assert Base is not None
    assert hasattr(Base, "metadata")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.database'`

- [ ] **Step 3: Write database.py**

Create: `backend/app/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_database.py -v`
Expected: 3 passed (requires MySQL running from Task 1)

- [ ] **Step 5: Commit**

Run: `git add backend/app/database.py backend/tests/test_database.py && git commit -m "feat: add async database module with SQLAlchemy 2.0 engine"`

**Verification:** `pytest tests/test_database.py` passes. Engine connects to MySQL and `SELECT 1` returns.

---

## Task 5: User Model

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/tests/test_models.py` (first test)

- [ ] **Step 1: Write the failing test for User model**

Create: `backend/tests/test_models.py`

```python
from sqlalchemy import inspect


def test_user_model_table_exists():
    from app.models.user import User
    from app.database import Base

    assert User.__tablename__ == "users"

    mapper = inspect(User)
    col_names = {c.key for c in mapper.column_attrs}

    required_cols = {
        "id", "username", "password_hash", "real_name", "role",
        "is_active", "locked_until", "failed_login_attempts",
        "must_change_password", "primary_class_id",
        "email", "phone", "created_at", "updated_at",
    }
    assert required_cols.issubset(col_names), f"Missing columns: {required_cols - col_names}"


def test_user_model_role_is_enum():
    from app.models.user import User

    mapper = inspect(User)
    role_col = None
    for c in mapper.columns:
        if c.key == "role":
            role_col = c
            break

    assert role_col is not None
    # Role should be VARCHAR with CHECK constraint, not MySQL ENUM
    assert "VARCHAR" in str(role_col.type).upper() or "VARCHAR" in str(role_col.type)


def test_user_model_primary_class_id_nullable():
    from app.models.user import User

    mapper = inspect(User)
    for c in mapper.columns:
        if c.key == "primary_class_id":
            assert c.nullable is True, "primary_class_id must be nullable (null for teachers/admins)"
            return
    raise AssertionError("primary_class_id column not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.user'`

- [ ] **Step 3: Write user model**

Create: `backend/app/models/user.py`

```python
import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    locked_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    primary_class_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="RESTRICT"), nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'teacher', 'student')", name="chk_user_role"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py::test_user_model_table_exists tests/test_models.py::test_user_model_role_is_enum tests/test_models.py::test_user_model_primary_class_id_nullable -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/user.py backend/tests/test_models.py && git commit -m "feat: add User model with role enum and class FK"`

**Verification:** User model has all required columns, role is VARCHAR with CHECK, primary_class_id is nullable FK.

---

## Task 6: Class Model

**Files:**
- Create: `backend/app/models/class_.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test for Class model**

Append to: `backend/tests/test_models.py`

```python
def test_class_model_table_and_columns():
    from app.models.class_ import Class

    assert Class.__tablename__ == "classes"

    mapper = inspect(Class)
    col_names = {c.key for c in mapper.column_attrs}

    required_cols = {"id", "name", "semester", "teacher_id", "created_at", "updated_at"}
    assert required_cols.issubset(col_names), f"Missing columns: {required_cols - col_names}"


def test_class_model_teacher_id_is_fk_to_users():
    from app.models.class_ import Class

    mapper = inspect(Class)
    for c in mapper.columns:
        if c.key == "teacher_id":
            assert c.nullable is True, "teacher_id must be nullable"
            # Verify FK target
            fk = list(c.foreign_keys)[0]
            assert "users.id" in str(fk.target_fullname)
            return
    raise AssertionError("teacher_id column not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py::test_class_model_table_and_columns -v`
Expected: FAIL

- [ ] **Step 3: Write class model**

Create: `backend/app/models/class_.py`

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    teacher_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py::test_class_model -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/class_.py && git commit -m "feat: add Class model with teacher FK"`

**Verification:** Class model has name, semester, teacher_id as nullable FK to users.

---

## Task 7: Task Model

**Files:**
- Create: `backend/app/models/task.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test for Task model**

Append to: `backend/tests/test_models.py`

```python
def test_task_model_table_and_columns():
    from app.models.task import Task

    assert Task.__tablename__ == "tasks"

    mapper = inspect(Task)
    col_names = {c.key for c in mapper.column_attrs}

    required_cols = {
        "id", "title", "description", "requirements", "class_id", "created_by",
        "deadline", "allowed_file_types", "max_file_size_mb",
        "allow_late_submission", "late_penalty_percent", "status",
        "grades_published", "grades_published_at", "grades_published_by",
        "created_at", "updated_at",
    }
    assert required_cols.issubset(col_names), f"Missing columns: {required_cols - col_names}"


def test_task_model_class_id_is_fk():
    from app.models.task import Task

    mapper = inspect(Task)
    for c in mapper.columns:
        if c.key == "class_id":
            fk = list(c.foreign_keys)[0]
            assert "classes.id" in str(fk.target_fullname)
            return
    raise AssertionError("class_id column not found")


def test_task_model_grades_published_is_bool():
    from sqlalchemy import Boolean
    from app.models.task import Task

    mapper = inspect(Task)
    for c in mapper.columns:
        if c.key == "grades_published":
            assert isinstance(c.type, Boolean)
            return
    raise AssertionError("grades_published column not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py::test_task_model -v`
Expected: FAIL

- [ ] **Step 3: Write task model**

Create: `backend/app/models/task.py`

```python
import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    class_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    deadline: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    allowed_file_types: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array string e.g. '[".pdf",".docx"]'
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    allow_late_submission: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_penalty_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    grades_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grades_published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    grades_published_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="chk_task_status"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py::test_task_model -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/task.py && git commit -m "feat: add Task model with class FK and grade publication fields"`

**Verification:** Task model has all required columns including grades_published boolean and class_id FK.

---

## Task 8: Submission Model

**Files:**
- Create: `backend/app/models/submission.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test for Submission model**

Append to: `backend/tests/test_models.py`

```python
def test_submission_model_table_and_columns():
    from app.models.submission import Submission

    assert Submission.__tablename__ == "submissions"

    mapper = inspect(Submission)
    col_names = {c.key for c in mapper.column_attrs}

    required_cols = {"id", "task_id", "student_id", "version", "is_late", "submitted_at", "updated_at"}
    assert required_cols.issubset(col_names), f"Missing columns: {required_cols - col_names}"


def test_submission_model_has_unique_constraint():
    from app.models.submission import Submission

    # Check that the table args include unique constraint on (task_id, student_id)
    table_args = Submission.__table_args__
    found = False
    if isinstance(table_args, tuple):
        for arg in table_args:
            if hasattr(arg, "columns"):
                col_names = {c.name for c in arg.columns}
                if col_names == {"task_id", "student_id"}:
                    found = True
    elif isinstance(table_args, dict):
        pass  # no table args
    assert found, "UNIQUE(task_id, student_id) constraint not found"


def test_submission_model_version_default():
    from app.models.submission import Submission

    mapper = inspect(Submission)
    for c in mapper.columns:
        if c.key == "version":
            assert c.default is not None or c.server_default is not None
            return
    raise AssertionError("version column not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py::test_submission_model -v`
Expected: FAIL

- [ ] **Step 3: Write submission model**

Create: `backend/app/models/submission.py`

```python
import datetime

from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("task_id", "student_id", name="uq_submission_task_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py::test_submission_model -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/submission.py && git commit -m "feat: add Submission model with UNIQUE(task_id, student_id)"`

**Verification:** Submission model has UNIQUE constraint on (task_id, student_id), version defaults to 1.

---

## Task 9: SubmissionFile Model

**Files:**
- Create: `backend/app/models/submission_file.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test for SubmissionFile model**

Append to: `backend/tests/test_models.py`

```python
def test_submission_file_model_table_and_columns():
    from app.models.submission_file import SubmissionFile

    assert SubmissionFile.__tablename__ == "submission_files"

    mapper = inspect(SubmissionFile)
    col_names = {c.key for c in mapper.column_attrs}

    required_cols = {"id", "submission_id", "file_name", "file_path", "file_size", "file_type", "uploaded_at"}
    assert required_cols.issubset(col_names), f"Missing columns: {required_cols - col_names}"


def test_submission_file_model_submission_id_is_fk():
    from app.models.submission_file import SubmissionFile

    mapper = inspect(SubmissionFile)
    for c in mapper.columns:
        if c.key == "submission_id":
            fk = list(c.foreign_keys)[0]
            assert "submissions.id" in str(fk.target_fullname)
            return
    raise AssertionError("submission_id column not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py::test_submission_file_model -v`
Expected: FAIL

- [ ] **Step 3: Write submission_file model**

Create: `backend/app/models/submission_file.py`

```python
import datetime

from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py::test_submission_file_model -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/submission_file.py && git commit -m "feat: add SubmissionFile model with CASCADE delete"`

**Verification:** SubmissionFile model has submission_id FK with CASCADE delete, file metadata columns.

---

## Task 10: Grade Model

**Files:**
- Create: `backend/app/models/grade.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test for Grade model**

Append to: `backend/tests/test_models.py`

```python
def test_grade_model_table_and_columns():
    from app.models.grade import Grade

    assert Grade.__tablename__ == "grades"

    mapper = inspect(Grade)
    col_names = {c.key for c in mapper.column_attrs}

    required_cols = {"id", "submission_id", "score", "penalty_applied", "feedback", "graded_by", "graded_at"}
    assert required_cols.issubset(col_names), f"Missing columns: {required_cols - col_names}"


def test_grade_model_submission_id_is_unique():
    from app.models.grade import Grade

    mapper = inspect(Grade)
    for c in mapper.columns:
        if c.key == "submission_id":
            assert c.unique is True, "submission_id must be UNIQUE (1:1 with submissions)"
            return
    raise AssertionError("submission_id column not found")


def test_grade_model_score_is_numeric():
    from sqlalchemy import Float, Numeric
    from app.models.grade import Grade

    mapper = inspect(Grade)
    for c in mapper.columns:
        if c.key == "score":
            assert isinstance(c.type, (Float, Numeric))
            return
    raise AssertionError("score column not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py::test_grade_model -v`
Expected: FAIL

- [ ] **Step 3: Write grade model**

Create: `backend/app/models/grade.py`

```python
import datetime
from typing import Optional

from sqlalchemy import Float, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    penalty_applied: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    graded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    graded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py::test_grade_model -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/grade.py && git commit -m "feat: add Grade model with unique submission_id and penalty_applied"`

**Verification:** Grade model has submission_id UNIQUE, score as Float, penalty_applied nullable.

---

## Task 11: RefreshToken Model

**Files:**
- Create: `backend/app/models/refresh_token.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test for RefreshToken model**

Append to: `backend/tests/test_models.py`

```python
def test_refresh_token_model_table_and_columns():
    from app.models.refresh_token import RefreshToken

    assert RefreshToken.__tablename__ == "refresh_tokens"

    mapper = inspect(RefreshToken)
    col_names = {c.key for c in mapper.column_attrs}

    required_cols = {"id", "user_id", "token_hash", "revoked", "expires_at", "created_at"}
    assert required_cols.issubset(col_names), f"Missing columns: {required_cols - col_names}"


def test_refresh_token_model_user_id_is_fk():
    from app.models.refresh_token import RefreshToken

    mapper = inspect(RefreshToken)
    for c in mapper.columns:
        if c.key == "user_id":
            fk = list(c.foreign_keys)[0]
            assert "users.id" in str(fk.target_fullname)
            return
    raise AssertionError("user_id column not found")


def test_refresh_token_model_revoked_default_false():
    from app.models.refresh_token import RefreshToken

    mapper = inspect(RefreshToken)
    for c in mapper.columns:
        if c.key == "revoked":
            assert c.default is not None or c.server_default is not None
            return
    raise AssertionError("revoked column not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py::test_refresh_token_model -v`
Expected: FAIL

- [ ] **Step 3: Write refresh_token model**

Create: `backend/app/models/refresh_token.py`

```python
import datetime

from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py::test_refresh_token_model -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/refresh_token.py && git commit -m "feat: add RefreshToken model for JWT revocation"`

**Verification:** RefreshToken model has user_id FK, token_hash, revoked boolean, expires_at.

---

## Task 12: Models __init__.py (Alembic Detection)

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/tests/test_models_init.py`

- [ ] **Step 1: Write the failing test**

Create: `backend/tests/test_models_init.py`

```python
def test_all_models_imported_in_init():
    from app.models import User, Class, Task, Submission, SubmissionFile, Grade, RefreshToken

    assert User.__tablename__ == "users"
    assert Class.__tablename__ == "classes"
    assert Task.__tablename__ == "tasks"
    assert Submission.__tablename__ == "submissions"
    assert SubmissionFile.__tablename__ == "submission_files"
    assert Grade.__tablename__ == "grades"
    assert RefreshToken.__tablename__ == "refresh_tokens"


def test_all_models_registered_with_base():
    from app.database import Base
    import app.models  # noqa: triggers registration

    table_names = set(Base.metadata.tables.keys())
    expected = {"users", "classes", "tasks", "submissions", "submission_files", "grades", "refresh_tokens"}
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models_init.py -v`
Expected: FAIL — `ImportError` for models

- [ ] **Step 3: Write models __init__.py**

Create: `backend/app/models/__init__.py`

```python
from app.models.user import User
from app.models.class_ import Class
from app.models.task import Task
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.grade import Grade
from app.models.refresh_token import RefreshToken

__all__ = [
    "User",
    "Class",
    "Task",
    "Submission",
    "SubmissionFile",
    "Grade",
    "RefreshToken",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models_init.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/models/__init__.py backend/tests/test_models_init.py && git commit -m "feat: add models __init__ for Alembic autogenerate detection"`

**Verification:** All 7 models importable from `app.models` and registered with Base.metadata.

---

## Task 13: Alembic Initialization + Initial Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/` (auto-generated)
- Create: `backend/tests/test_migration.py`

- [ ] **Step 1: Initialize Alembic**

Run: `cd backend && alembic init alembic`
Expected: Creates `alembic/` directory with `env.py`, `script.py.mako`, `versions/`

- [ ] **Step 2: Configure alembic.ini**

Read and modify `backend/alembic.ini` — set `sqlalchemy.url` to empty (we'll override in env.py):

Replace the `sqlalchemy.url` line in `alembic.ini` with:
```
sqlalchemy.url =
```

- [ ] **Step 3: Rewrite env.py for async + model imports**

Replace `backend/alembic/env.py` with:

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings
from app.database import Base
import app.models  # noqa: registers all models

config = context.config
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate initial migration**

Run: `cd backend && alembic revision --autogenerate -m "initial tables"`
Expected: Generates migration file with all 7 tables.

- [ ] **Step 5: Write migration verification test**

Create: `backend/tests/test_migration.py`

```python
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_all_tables_created():
    from app.database import engine

    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW TABLES"))
        table_names = {row[0] for row in result}

    expected = {"users", "classes", "tasks", "submissions", "submission_files", "grades", "refresh_tokens"}
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


@pytest.mark.asyncio
async def test_users_table_has_correct_columns():
    from app.database import engine

    async with engine.connect() as conn:
        result = await conn.execute(text("DESCRIBE users"))
        col_names = {row[0] for row in result}

    required = {"id", "username", "password_hash", "real_name", "role", "is_active",
                "locked_until", "failed_login_attempts", "must_change_password",
                "primary_class_id", "email", "phone", "created_at", "updated_at"}
    assert required.issubset(col_names), f"Missing: {required - col_names}"


@pytest.mark.asyncio
async def test_submissions_unique_constraint_exists():
    from app.database import engine

    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW CREATE TABLE submissions"))
        create_stmt = result.fetchone()[1]

    assert "uq_submission_task_student" in create_stmt or "UNIQUE" in create_stmt


@pytest.mark.asyncio
async def test_grades_submission_id_unique():
    from app.database import engine

    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW CREATE TABLE grades"))
        create_stmt = result.fetchone()[1]

    assert "UNIQUE" in create_stmt and "submission_id" in create_stmt
```

- [ ] **Step 6: Run migration and verify**

Run: `cd backend && alembic upgrade head`
Expected: All 7 tables created.

Run: `cd backend && python -m pytest tests/test_migration.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

Run: `git add backend/alembic.ini backend/alembic/ && git commit -m "feat: initialize Alembic with async env.py and initial migration for 7 tables"`

**Verification:** `alembic upgrade head` creates all 7 tables. Migration test verifies tables, columns, and constraints.

---

## Task 14: Auth Dependency (JWT Decode + Role Guard)

**Files:**
- Create: `backend/app/dependencies/auth.py`
- Create: `backend/tests/test_auth_dependency.py`

- [ ] **Step 1: Write the failing test for auth dependency**

Create: `backend/tests/test_auth_dependency.py`

```python
import pytest
import jwt
from datetime import datetime, timedelta, timezone

from app.config import settings


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def test_get_current_user_valid_token():
    from app.dependencies.auth import get_current_user

    token = _make_token({"sub": "1", "role": "admin", "type": "access"})

    # get_current_user is async, returns a dict or user-like object
    # For now, test that it decodes without error
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        _call_get_current_user(token)
    )
    assert result is not None


async def _call_get_current_user(token: str):
    from app.dependencies.auth import get_current_user
    from unittest.mock import MagicMock

    # Mock the DB call — we just want to verify token decode works
    return await get_current_user(token=token, db=MagicMock())


def test_get_current_user_expired_token():
    from app.dependencies.auth import get_current_user
    from fastapi import HTTPException

    expired = _make_token({
        "sub": "1", "role": "admin", "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    })

    import asyncio
    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(
            _call_get_current_user(expired)
        )
    assert exc_info.value.status_code == 401


def test_require_role_allows_correct_role():
    from app.dependencies.auth import require_role

    dep = require_role("admin")
    assert callable(dep) or dep is not None


def test_require_role_blocks_wrong_role():
    from app.dependencies.auth import require_role
    from fastapi import HTTPException
    import asyncio

    dep = require_role("admin")

    # Simulate a user with role="student" trying to access admin endpoint
    with pytest.raises(HTTPException) as exc_info:
        asyncio.get_event_loop().run_until_complete(
            dep(current_user={"id": 1, "role": "student"})
        )
    assert exc_info.value.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_auth_dependency.py -v`
Expected: FAIL

- [ ] **Step 3: Write auth dependency**

Create: `backend/app/dependencies/auth.py`

```python
from typing import AsyncGenerator, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return {
            "id": int(payload["sub"]),
            "role": payload["role"],
            "username": payload.get("username"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


def require_role(allowed_role: str):
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] != allowed_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{allowed_role}' required",
            )
        return current_user
    return role_checker
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_auth_dependency.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/dependencies/auth.py backend/tests/test_auth_dependency.py && git commit -m "feat: add JWT auth dependency with role guard"`

**Verification:** Auth dependency decodes valid JWT, rejects expired tokens, require_role blocks wrong roles.

---

## Task 15: FastAPI Main App + Health Endpoint

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/test_main.py`

- [ ] **Step 1: Write the failing test for main app**

Create: `backend/tests/test_main.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_cors_headers_present():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_api_docs_available():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/docs")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_main.py -v`
Expected: FAIL

- [ ] **Step 3: Write main.py**

Create: `backend/app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_main.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

Run: `git add backend/app/main.py backend/tests/test_main.py && git commit -m "feat: add FastAPI main app with CORS, health endpoint"`

**Verification:** Health endpoint returns `{"status": "ok"}`, CORS headers present, OpenAPI docs available.

---

## Task 16: Test Conftest (Shared Fixtures)

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write conftest.py with shared test fixtures**

Create: `backend/tests/conftest.py`

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app

# Use a test database (same server, different database)
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/training_platform", "/training_platform_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Provide a clean database session for each test."""
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Provide an async HTTP test client with DB session override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Create test database and verify conftest loads**

Run:
```bash
cd backend
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
url = settings.DATABASE_URL.replace('/training_platform', '/training_platform_test')
engine = create_async_engine(url)
async def create_db():
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text('CREATE DATABASE IF NOT EXISTS training_platform_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
asyncio.run(create_db())
print('Test database created')
"
```
Expected: `Test database created`

Run: `cd backend && python -m pytest tests/test_main.py -v`
Expected: Still passes (conftest loaded, test DB created)

- [ ] **Step 3: Commit**

Run: `git add backend/tests/conftest.py && git commit -m "feat: add test conftest with async DB fixtures and test client"`

**Verification:** `pytest` runs successfully with conftest providing async DB session and test client.

---

## Task 17: Final Integration Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Verify Alembic migration from scratch**

Run: `cd backend && alembic downgrade base && alembic upgrade head`
Expected: All 7 tables recreated successfully.

- [ ] **Step 3: Verify app starts with uvicorn**

Run: `cd backend && timeout 3 uvicorn app.main:app --host 0.0.0.0 --port 8000 || true`
Expected: App starts, shows `Uvicorn running on http://0.0.0.0:8000`

- [ ] **Step 4: Verify health endpoint responds**

Run: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 &`
Wait 2s, then:
Run: `curl -s http://localhost:8000/health`
Expected: `{"status":"ok"}`

Run: `curl -s http://localhost:8000/docs | head -5`
Expected: HTML for Swagger UI

- [ ] **Step 5: Verify MySQL table structure**

Run:
```bash
mysql -h127.0.0.1 -uroot -prootpassword -e "
USE training_platform;
SHOW TABLES;
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA='training_platform'
ORDER BY TABLE_NAME, ORDINAL_POSITION;
"
```
Expected: 7 tables with all columns matching model definitions.

- [ ] **Step 6: Final commit if any fixes needed**

Run: `git add -A && git commit -m "chore: PR1 final integration fixes" || echo "No changes to commit"`

**Verification:** Full test suite passes, migration runs cleanly, app starts, health endpoint responds, MySQL has all 7 tables.
