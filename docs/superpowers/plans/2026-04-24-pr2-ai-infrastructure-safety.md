# PR2: AI Infrastructure & Safety Boundaries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship AIService with provider abstraction, daily token budgets, usage logging, cost tracking, feedback collection, admin config/test endpoints, and prompt template management. No user-facing AI features yet.

**Architecture:** AIService wraps LLM calls with budget checking, usage logging, and error handling. Provider is abstracted behind a Protocol. Config is read from `ai_config` DB table per call (no caching). AIService receives db session from router as parameter — never uses Depends directly. Error logs are flushed before raising, and routers use JSONResponse (not raise) for error paths so get_db() commits the log.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, MySQL 8, Alembic, Pydantic v2, openai SDK (AsyncOpenAI), pytest-asyncio

---

## File Structure

### Backend — Create
- `backend/app/services/__init__.py` — empty package init
- `backend/app/services/ai.py` — AIResponse, AIProvider Protocol, MockProvider, OpenAIProvider, AIServiceError, BudgetExceededError, AIService
- `backend/app/services/prompts.py` — PromptService
- `backend/app/models/ai_usage_log.py`
- `backend/app/models/ai_feedback.py`
- `backend/app/models/ai_config.py`
- `backend/app/models/prompt_template.py`
- `backend/app/schemas/ai.py`
- `backend/app/schemas/prompt.py`
- `backend/app/routers/ai.py`
- `backend/app/routers/prompts.py`
- `backend/alembic/versions/XXXX_add_ai_tables.py`
- `backend/tests/test_ai_service.py`
- `backend/tests/test_ai_feedback.py`
- `backend/tests/test_ai_stats.py`
- `backend/tests/test_ai_endpoints.py`
- `backend/tests/test_prompts.py`

### Backend — Modify
- `backend/app/models/__init__.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- `backend/scripts/seed_demo.py`

### Frontend — Create
- `frontend/src/views/admin/AIConfig.vue`
- `frontend/src/views/admin/AIUsage.vue`
- `frontend/src/views/admin/AIFeedback.vue`
- `frontend/src/views/admin/PromptTemplates.vue`

### Frontend — Modify
- `frontend/src/router/index.js`
- `frontend/src/layouts/MainLayout.vue`

---

## Task 1: AI Models — ai_config, ai_usage_log, ai_feedback, prompt_template

**Files:**
- Create: `backend/app/models/ai_config.py`
- Create: `backend/app/models/ai_usage_log.py`
- Create: `backend/app/models/ai_feedback.py`
- Create: `backend/app/models/prompt_template.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create ai_config model**

Create `backend/app/models/ai_config.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIConfig(Base):
    __tablename__ = "ai_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 2: Create ai_usage_log model**

Create `backend/app/models/ai_usage_log.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"
    __table_args__ = (
        CheckConstraint("status IN ('success', 'error')", name="chk_ai_usage_status"),
        Index("ix_ai_usage_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_microdollars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
```

- [ ] **Step 3: Create ai_feedback model**

Create `backend/app/models/ai_feedback.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, SmallInteger, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIFeedback(Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (
        UniqueConstraint("ai_usage_log_id", "user_id", name="uq_feedback_log_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ai_usage_log_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_usage_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
```

- [ ] **Step 4: Create prompt_template model**

Create `backend/app/models/prompt_template.py`:

```python
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[str] = mapped_column(Text, nullable=False, comment="JSON array of variable names")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 5: Register all 4 models in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.ai_config import AIConfig
from app.models.ai_usage_log import AIUsageLog
from app.models.ai_feedback import AIFeedback
from app.models.prompt_template import PromptTemplate
```

Add to `__all__`: `"AIConfig"`, `"AIUsageLog"`, `"AIFeedback"`, `"PromptTemplate"`

- [ ] **Step 6: Verify models load**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/python -c "from app.models import AIConfig, AIUsageLog, AIFeedback, PromptTemplate; print('OK')"`

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/ && git commit -m "feat: add AI models (config, usage_log, feedback, prompt_template)"
```

---

## Task 2: AI Tables Migration

**Files:**
- Create: `backend/alembic/versions/XXXX_add_ai_tables.py`

- [ ] **Step 1: Create migration file**

Create `backend/alembic/versions/b5e8d2f3017a_add_ai_tables.py`:

```python
"""add ai tables

Revision ID: b5e8d2f3017a
Revises: a3f7c9e2015b
Create Date: 2026-04-24 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5e8d2f3017a'
down_revision: Union[str, Sequence[str], None] = 'a3f7c9e2015b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    )

    op.create_table('ai_usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_microdollars', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('success', 'error')", name='chk_ai_usage_status'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_ai_usage_logs_user_id', 'ai_usage_logs', ['user_id'])
    op.create_index('ix_ai_usage_user_created', 'ai_usage_logs', ['user_id', 'created_at'])

    op.create_table('ai_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ai_usage_log_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.SmallInteger(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ai_usage_log_id', 'user_id', name='uq_feedback_log_user'),
        sa.ForeignKeyConstraint(['ai_usage_log_id'], ['ai_usage_logs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_ai_feedback_ai_usage_log_id', 'ai_feedback', ['ai_usage_log_id'])

    op.create_table('prompt_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_text', sa.Text(), nullable=False),
        sa.Column('variables', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    )


def downgrade() -> None:
    op.drop_table('prompt_templates')
    op.drop_table('ai_feedback')
    op.drop_index('ix_ai_usage_user_created', table_name='ai_usage_logs')
    op.drop_index('ix_ai_usage_logs_user_id', table_name='ai_usage_logs')
    op.drop_table('ai_usage_logs')
    op.drop_table('ai_config')
```

- [ ] **Step 2: Run migration**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/alembic upgrade head`

- [ ] **Step 3: Verify existing tests still pass**

Run: `.venv/bin/python -m pytest tests/ -q`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/ && git commit -m "feat: add AI tables migration (config, usage_logs, feedback, prompt_templates)"
```

---

## Task 3: Config + Requirements Update

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add AI config vars**

In `backend/app/config.py`, add these fields to the `Settings` class (before `model_config`):

```python
    AI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    AI_BASE_URL: str = ""
```

- [ ] **Step 2: Add openai to requirements**

Append to `backend/requirements.txt`:

```
openai>=1.0.0
```

- [ ] **Step 3: Verify config loads**

Run: `.venv/bin/python -c "from app.config import settings; print(settings.AI_MODEL)"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/requirements.txt && git commit -m "feat: add AI config vars and openai dependency"
```

---

## Task 4: AI Service — Provider Protocol + MockProvider

**Files:**
- Create: `backend/app/services/__init__.py` (empty)
- Create: `backend/app/services/ai.py` (AIResponse, AIProvider, MockProvider, errors)

- [ ] **Step 1: Create services package**

Create `backend/app/services/__init__.py` as an empty file.

- [ ] **Step 2: Create ai.py with protocol, mock provider, and error types**

Create `backend/app/services/ai.py`:

```python
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class AIResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
class AIProvider(Protocol):
    async def generate(self, prompt: str, model: str) -> AIResponse:
        ...


class MockProvider:
    """Returns fixed responses for testing."""

    def __init__(self, response_text: str = "AI 生成的测试回复"):
        self.response_text = response_text

    async def generate(self, prompt: str, model: str) -> AIResponse:
        return AIResponse(
            text=self.response_text,
            prompt_tokens=len(prompt) // 4,
            completion_tokens=len(self.response_text) // 4,
        )


class AIServiceError(Exception):
    pass


class BudgetExceededError(Exception):
    pass
```

- [ ] **Step 3: Verify module loads**

Run: `.venv/bin/python -c "from app.services.ai import MockProvider, AIResponse; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ && git commit -m "feat: add AI provider protocol, MockProvider, error types"
```

---

## Task 5: AIService — Config Reading from DB

**Files:**
- Modify: `backend/app/services/ai.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_ai_service.py`:

```python
import pytest
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.services.ai import AIService, MockProvider


@pytest.mark.asyncio(loop_scope="session")
async def test_get_config_reads_from_db(db_session: AsyncSession):
    db_session.add(AIConfig(key="model", value="gpt-4o"))
    db_session.add(AIConfig(key="budget_student", value="50000"))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)

    assert config["model"] == "gpt-4o"
    assert config["budget_student"] == 50000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ai_service.py::test_get_config_reads_from_db -v`

- [ ] **Step 3: Implement AIService with _get_config**

Append to `backend/app/services/ai.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_config import AIConfig
from app.config import settings


class AIService:
    def __init__(self, provider: AIProvider = None):
        if provider is None:
            provider = MockProvider()
        self.provider = provider

    async def _get_config(self, db: AsyncSession) -> dict:
        result = await db.execute(select(AIConfig))
        rows = result.scalars().all()
        config = {
            "model": settings.AI_MODEL,
            "budget_admin": 500000,
            "budget_teacher": 200000,
            "budget_student": 50000,
            "price_input": 0.15,
            "price_output": 0.60,
        }
        for row in rows:
            if row.key in ("budget_admin", "budget_teacher", "budget_student",
                           "price_input", "price_output"):
                config[row.key] = float(row.value)
            else:
                config[row.key] = row.value
        return config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_ai_service.py::test_get_config_reads_from_db -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai.py backend/tests/test_ai_service.py && git commit -m "feat: add AIService with DB config reading"
```

---

## Task 6: AIService — Budget Check

**Files:**
- Modify: `backend/app/services/ai.py`
- Modify: `backend/tests/test_ai_service.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_ai_service.py`:

```python
import datetime


@pytest.mark.asyncio(loop_scope="session")
async def test_budget_within_limit(db_session: AsyncSession):
    user_id = 1
    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)
    remaining = await service.check_budget(db_session, user_id, "student", config)
    assert remaining == 50000


@pytest.mark.asyncio(loop_scope="session")
async def test_budget_exceeded(db_session: AsyncSession):
    from app.models.ai_usage_log import AIUsageLog

    user_id = 1
    db_session.add(AIUsageLog(
        user_id=user_id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=50000, completion_tokens=0, cost_microdollars=0,
        latency_ms=100, status="success",
    ))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)
    with pytest.raises(BudgetExceededError):
        await service.check_budget(db_session, user_id, "student", config)


@pytest.mark.asyncio(loop_scope="session")
async def test_budget_first_call_of_day(db_session: AsyncSession):
    service = AIService(provider=MockProvider())
    config = await service._get_config(db_session)
    remaining = await service.check_budget(db_session, 999, "teacher", config)
    assert remaining == 200000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ai_service.py -k "budget" -v`

- [ ] **Step 3: Implement check_budget**

Append to `AIService` class in `backend/app/services/ai.py`:

```python
    async def check_budget(self, db: AsyncSession, user_id: int, role: str, config: dict) -> int:
        from app.models.ai_usage_log import AIUsageLog
        from sqlalchemy import func

        budget_key = f"budget_{role}"
        budget = config.get(budget_key, 50000)

        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.coalesce(func.sum(
                AIUsageLog.prompt_tokens + AIUsageLog.completion_tokens
            ), 0)).where(
                AIUsageLog.user_id == user_id,
                AIUsageLog.created_at >= today_start,
            )
        )
        used = result.scalar()
        remaining = int(budget - used)
        if remaining <= 0:
            raise BudgetExceededError("今日 AI 调用额度已用完，请明天再试")
        return remaining
```

Add `import datetime` at the top of the file if not already there.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_ai_service.py -k "budget" -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai.py backend/tests/test_ai_service.py && git commit -m "feat: add AIService budget check with COALESCE"
```

---

## Task 7: AIService — Usage Logging

**Files:**
- Modify: `backend/app/services/ai.py`
- Modify: `backend/tests/test_ai_service.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_ai_service.py`:

```python
from sqlalchemy import select
from app.models.ai_usage_log import AIUsageLog


@pytest.mark.asyncio(loop_scope="session")
async def test_log_usage_success(db_session: AsyncSession):
    service = AIService(provider=MockProvider())
    log_id = await service._log_usage(
        db_session, user_id=1, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, cost_microdollars=45,
        latency_ms=200, status="success",
    )
    assert log_id is not None

    result = await db_session.execute(select(AIUsageLog).where(AIUsageLog.id == log_id))
    log = result.scalar_one()
    assert log.status == "success"
    assert log.cost_microdollars == 45
    assert log.prompt_tokens == 100


@pytest.mark.asyncio(loop_scope="session")
async def test_log_usage_error(db_session: AsyncSession):
    service = AIService(provider=MockProvider())
    log_id = await service._log_usage(
        db_session, user_id=1, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=0, completion_tokens=0, cost_microdollars=0,
        latency_ms=500, status="error",
    )
    result = await db_session.execute(select(AIUsageLog).where(AIUsageLog.id == log_id))
    log = result.scalar_one()
    assert log.status == "error"
    assert log.prompt_tokens == 0
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement _log_usage**

Append to `AIService` class:

```python
    async def _log_usage(
        self, db: AsyncSession, *, user_id: int, endpoint: str, model: str,
        prompt_tokens: int, completion_tokens: int, cost_microdollars: int,
        latency_ms: int, status: str,
    ) -> int:
        from app.models.ai_usage_log import AIUsageLog

        log = AIUsageLog(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_microdollars=cost_microdollars,
            latency_ms=latency_ms,
            status=status,
        )
        db.add(log)
        await db.flush()
        return log.id
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_ai_service.py -k "log_usage" -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai.py backend/tests/test_ai_service.py && git commit -m "feat: add AIService usage logging to DB"
```

---

## Task 8: AIService — generate() Full Lifecycle

**Files:**
- Modify: `backend/app/services/ai.py`
- Modify: `backend/tests/test_ai_service.py`

- [ ] **Step 1: Write failing test for success path**

Append to `backend/tests/test_ai_service.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_generate_success(db_session: AsyncSession):
    service = AIService(provider=MockProvider(response_text="这是生成的文本"))
    result = await service.generate(
        db=db_session,
        prompt="生成一个任务描述",
        user_id=1,
        role="teacher",
        endpoint="test_endpoint",
    )
    assert result["text"] == "这是生成的文本"
    assert result["usage_log_id"] is not None
    assert result["prompt_tokens"] > 0

    result2 = await db_session.execute(
        select(AIUsageLog).where(AIUsageLog.id == result["usage_log_id"])
    )
    log = result2.scalar_one()
    assert log.endpoint == "test_endpoint"
    assert log.status == "success"


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_provider_error(db_session: AsyncSession):
    class FailingProvider:
        async def generate(self, prompt: str, model: str) -> AIResponse:
            raise RuntimeError("provider timeout")

    service = AIService(provider=FailingProvider())
    with pytest.raises(AIServiceError):
        await service.generate(
            db=db_session, prompt="test", user_id=1, role="teacher", endpoint="test",
        )

    result = await db_session.execute(
        select(AIUsageLog).where(AIUsageLog.status == "error")
    )
    error_log = result.scalar_one_or_none()
    assert error_log is not None
    assert error_log.prompt_tokens == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_budget_exceeded(db_session: AsyncSession):
    from app.models.ai_usage_log import AIUsageLog

    db_session.add(AIUsageLog(
        user_id=1, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=50000, completion_tokens=0, cost_microdollars=0,
        latency_ms=100, status="success",
    ))
    await db_session.flush()

    service = AIService(provider=MockProvider())
    with pytest.raises(BudgetExceededError):
        await service.generate(
            db=db_session, prompt="test", user_id=1, role="student", endpoint="test",
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_cost_calculation(db_session: AsyncSession):
    class FixedTokenProvider:
        async def generate(self, prompt: str, model: str) -> AIResponse:
            return AIResponse(text="response", prompt_tokens=500, completion_tokens=200)

    db_session.add(AIConfig(key="price_input", value="0.15"))
    db_session.add(AIConfig(key="price_output", value="0.60"))
    await db_session.flush()

    service = AIService(provider=FixedTokenProvider())
    result = await service.generate(
        db=db_session, prompt="test", user_id=1, role="admin", endpoint="cost_test",
    )

    log_result = await db_session.execute(
        select(AIUsageLog).where(AIUsageLog.id == result["usage_log_id"])
    )
    log = log_result.scalar_one()
    assert log.cost_microdollars == 500 * 0.15 + 200 * 0.60
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement generate()**

Append to `AIService` class in `backend/app/services/ai.py`:

```python
    async def generate(
        self, *, db: AsyncSession, prompt: str, user_id: int,
        role: str, endpoint: str = "",
    ) -> dict:
        config = await self._get_config(db)
        await self.check_budget(db, user_id, role, config)

        model = config["model"]
        start = time.time()
        try:
            response = await self.provider.generate(prompt, model)
            latency_ms = int((time.time() - start) * 1000)
            cost = int(
                response.prompt_tokens * config.get("price_input", 0.15)
                + response.completion_tokens * config.get("price_output", 0.60)
            )
            log_id = await self._log_usage(
                db, user_id=user_id, endpoint=endpoint, model=model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cost_microdollars=cost, latency_ms=latency_ms, status="success",
            )
            return {
                "text": response.text,
                "usage_log_id": log_id,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "cost_microdollars": cost,
            }
        except (BudgetExceededError, AIServiceError):
            raise
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            await self._log_usage(
                db, user_id=user_id, endpoint=endpoint, model=model,
                prompt_tokens=0, completion_tokens=0, cost_microdollars=0,
                latency_ms=latency_ms, status="error",
            )
            raise AIServiceError("AI 服务暂时不可用") from e
```

- [ ] **Step 4: Run all AI service tests**

Run: `.venv/bin/python -m pytest tests/test_ai_service.py -v`

- [ ] **Step 5: Run full regression**

Run: `.venv/bin/python -m pytest tests/ -q`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai.py backend/tests/test_ai_service.py && git commit -m "feat: add AIService.generate() with budget, logging, error handling"
```

---

## Task 9: OpenAIProvider

**Files:**
- Modify: `backend/app/services/ai.py`

- [ ] **Step 1: Write test for OpenAIProvider**

Append to `backend/tests/test_ai_service.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_openai_provider_creates_client():
    from app.services.ai import OpenAIProvider
    provider = OpenAIProvider(api_key="test-key", base_url="https://api.example.com/v1")
    assert provider.api_key == "test-key"
    assert provider.base_url == "https://api.example.com/v1"
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement OpenAIProvider**

Append to `backend/app/services/ai.py`:

```python
class OpenAIProvider:
    """Real OpenAI API provider using AsyncOpenAI."""

    def __init__(self, api_key: str, base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url

    async def generate(self, prompt: str, model: str) -> AIResponse:
        from openai import AsyncOpenAI

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        client = AsyncOpenAI(**kwargs)
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        choice = response.choices[0]
        usage = response.usage
        return AIResponse(
            text=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
```

- [ ] **Step 4: Run test**

Run: `.venv/bin/python -m pytest tests/test_ai_service.py::test_openai_provider_creates_client -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai.py backend/tests/test_ai_service.py && git commit -m "feat: add OpenAIProvider with AsyncOpenAI"
```

---

## Task 10: PromptService

**Files:**
- Create: `backend/app/services/prompts.py`
- Create: `backend/tests/test_prompts.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_prompts.py`:

```python
import pytest
import json
from app.models.prompt_template import PromptTemplate
from app.services.prompts import PromptService


@pytest.mark.asyncio(loop_scope="session")
async def test_get_template(db_session):
    db_session.add(PromptTemplate(
        name="task_description",
        description="Generate task description",
        template_text="请为{course_name}课程生成关于{topic}的任务描述",
        variables=json.dumps(["course_name", "topic"]),
    ))
    await db_session.flush()

    service = PromptService()
    template = await service.get_template(db_session, "task_description")
    assert template["name"] == "task_description"
    assert "course_name" in template["variables"]


@pytest.mark.asyncio(loop_scope="session")
async def test_fill_template(db_session):
    db_session.add(PromptTemplate(
        name="test_tpl",
        description="test",
        template_text="你好 {name}，欢迎来到{course}",
        variables=json.dumps(["name", "course"]),
    ))
    await db_session.flush()

    service = PromptService()
    result = await service.fill_template(db_session, "test_tpl", {"name": "张三", "course": "Python"})
    assert result == "你好 张三，欢迎来到Python"


@pytest.mark.asyncio(loop_scope="session")
async def test_fill_template_missing_variable(db_session):
    db_session.add(PromptTemplate(
        name="test_missing",
        description="test",
        template_text="{a} and {b}",
        variables=json.dumps(["a", "b"]),
    ))
    await db_session.flush()

    service = PromptService()
    with pytest.raises(ValueError, match="Missing.*variable"):
        await service.fill_template(db_session, "test_missing", {"a": "x"})


@pytest.mark.asyncio(loop_scope="session")
async def test_fill_template_not_found(db_session):
    service = PromptService()
    with pytest.raises(ValueError, match="not found"):
        await service.fill_template(db_session, "nonexistent", {})
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement PromptService**

Create `backend/app/services/prompts.py`:

```python
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate


class PromptService:
    async def get_template(self, db: AsyncSession, name: str) -> dict:
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.name == name)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Template '{name}' not found")
        return {
            "name": template.name,
            "description": template.description,
            "template_text": template.template_text,
            "variables": json.loads(template.variables),
        }

    async def fill_template(self, db: AsyncSession, name: str, context: dict) -> str:
        template = await self.get_template(db, name)
        required_vars = set(template["variables"])
        provided_vars = set(context.keys())
        missing = required_vars - provided_vars
        if missing:
            raise ValueError(f"Missing template variables: {', '.join(sorted(missing))}")
        return template["template_text"].format(**context)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/prompts.py backend/tests/test_prompts.py && git commit -m "feat: add PromptService with template fill and validation"
```

---

## Task 11: AI Schemas

**Files:**
- Create: `backend/app/schemas/ai.py`
- Create: `backend/app/schemas/prompt.py`

- [ ] **Step 1: Create AI schemas**

Create `backend/app/schemas/ai.py`:

```python
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class AIFeedbackIn(BaseModel):
    ai_usage_log_id: int
    rating: int
    comment: Optional[str] = None


class AIFeedbackOut(BaseModel):
    id: int
    ai_usage_log_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class AIUsageOut(BaseModel):
    id: int
    user_id: int
    endpoint: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_microdollars: int
    latency_ms: int
    status: str
    created_at: datetime


class AIUsageWithBudget(BaseModel):
    items: List[AIUsageOut]
    total: int
    budget_limit: int
    budget_used: int
    budget_remaining: int


class AIStatsOut(BaseModel):
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_microdollars: int
    success_rate: float
    avg_latency_ms: float


class AIStatsByUser(BaseModel):
    user_id: int
    username: str
    total_calls: int
    total_tokens: int
    total_cost_microdollars: int


class AIFeedbackSummary(BaseModel):
    positive_count: int
    negative_count: int
    recent_negative: List[dict]


class AIConfigOut(BaseModel):
    model: str
    budget_admin: int
    budget_teacher: int
    budget_student: int
    is_configured: bool


class AIConfigUpdate(BaseModel):
    model: Optional[str] = None
    budget_admin: Optional[int] = None
    budget_teacher: Optional[int] = None
    budget_student: Optional[int] = None


class AITestOut(BaseModel):
    text: str
    usage_log_id: int
    prompt_tokens: int
    completion_tokens: int
```

- [ ] **Step 2: Create prompt schemas**

Create `backend/app/schemas/prompt.py`:

```python
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class PromptTemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    template_text: str
    variables: List[str]
    updated_at: datetime
    updated_by: Optional[int] = None


class PromptTemplateUpdate(BaseModel):
    template_text: str
```

- [ ] **Step 3: Verify imports**

Run: `.venv/bin/python -c "from app.schemas.ai import AIFeedbackIn, AIConfigOut; from app.schemas.prompt import PromptTemplateOut; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/ai.py backend/app/schemas/prompt.py && git commit -m "feat: add AI and prompt schemas"
```

---

## Task 12: AI Router — Feedback Endpoint

**Files:**
- Create: `backend/app/routers/ai.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ai_feedback.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_ai_feedback.py`:

```python
import pytest
from tests.helpers import create_test_user, login_user, auth_headers
from app.models.ai_usage_log import AIUsageLog


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_positive_feedback(client, db_session):
    user = await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": 1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["rating"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_negative_feedback_with_comment(client, db_session):
    user = await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": -1, "comment": "回答不准确"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["comment"] == "回答不准确"
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement feedback endpoint + register router**

Create `backend/app/routers/ai.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status, JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.ai_usage_log import AIUsageLog
from app.models.ai_feedback import AIFeedback
from app.models.ai_config import AIConfig
from app.models.user import User
from app.schemas.ai import (
    AIFeedbackIn, AIFeedbackOut, AIUsageOut, AIUsageWithBudget,
    AIStatsOut, AIStatsByUser, AIFeedbackSummary,
    AIConfigOut, AIConfigUpdate, AITestOut,
)
from app.services.ai import AIService, AIServiceError, BudgetExceededError, MockProvider
from app.config import settings

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_ai_service() -> AIService:
    if settings.AI_API_KEY:
        from app.services.ai import OpenAIProvider
        provider = OpenAIProvider(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)
        return AIService(provider=provider)
    return AIService(provider=MockProvider())


@router.post("/feedback", response_model=AIFeedbackOut)
async def submit_feedback(
    data: AIFeedbackIn,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    log_result = await db.execute(
        select(AIUsageLog).where(AIUsageLog.id == data.ai_usage_log_id)
    )
    log = log_result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="AI 调用记录不存在")
    if log.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="只能评价自己的 AI 调用")

    existing = await db.execute(
        select(AIFeedback).where(
            AIFeedback.ai_usage_log_id == data.ai_usage_log_id,
            AIFeedback.user_id == current_user["id"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="已经评价过")

    feedback = AIFeedback(
        ai_usage_log_id=data.ai_usage_log_id,
        user_id=current_user["id"],
        rating=data.rating,
        comment=data.comment,
    )
    db.add(feedback)
    await db.flush()

    return AIFeedbackOut(
        id=feedback.id,
        ai_usage_log_id=feedback.ai_usage_log_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )
```

Register in `backend/app/main.py`:

```python
from app.routers import ai as ai_router
# ...
app.include_router(ai_router.router)
```

- [ ] **Step 4: Run feedback tests**

Run: `.venv/bin/python -m pytest tests/test_ai_feedback.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai.py backend/app/main.py backend/tests/test_ai_feedback.py && git commit -m "feat: add AI feedback endpoint with ownership and duplicate checks"
```

---

## Task 13: AI Router — Feedback Edge Cases

**Files:**
- Modify: `backend/tests/test_ai_feedback.py`

- [ ] **Step 1: Write edge case tests**

Append to `backend/tests/test_ai_feedback.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_cross_user_forbidden(client, db_session):
    teacher = await create_test_user(db_session, username="teacher1", role="teacher")
    await create_test_user(db_session, username="teacher2", role="teacher")
    token2 = await login_user(client, "teacher2")

    log = AIUsageLog(
        user_id=teacher.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": 1},
        headers=auth_headers(token2),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_duplicate_rejected(client, db_session):
    user = await create_test_user(db_session, username="teacher1", role="teacher")
    token = await login_user(client, "teacher1")

    log = AIUsageLog(
        user_id=user.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": 1},
        headers=auth_headers(token),
    )

    resp = await client.post(
        "/api/ai/feedback",
        json={"ai_usage_log_id": log.id, "rating": -1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_ai_feedback.py -v`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_ai_feedback.py && git commit -m "test: add feedback edge case tests (cross-user 403, duplicate 409)"
```

---

## Task 14: AI Router — Usage Query Endpoint

**Files:**
- Modify: `backend/app/routers/ai.py`
- Create: `backend/tests/test_ai_stats.py`

- [ ] **Step 1: Write failing test for usage query**

Create `backend/tests/test_ai_stats.py`:

```python
import pytest
from tests.helpers import create_test_user, login_user, auth_headers
from app.models.ai_usage_log import AIUsageLog


@pytest.mark.asyncio(loop_scope="session")
async def test_usage_query_admin(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    student = await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "admin1")

    db_session.add(AIUsageLog(
        user_id=student.id, endpoint="student_qa", model="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, cost_microdollars=45,
        latency_ms=200, status="success",
    ))
    await db_session.flush()

    resp = await client.get("/api/ai/usage", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["endpoint"] == "student_qa"


@pytest.mark.asyncio(loop_scope="session")
async def test_usage_query_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.get("/api/ai/usage", headers=auth_headers(token))
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement usage query endpoint**

Add to `backend/app/routers/ai.py`:

```python
@router.get("/usage", response_model=AIUsageWithBudget)
async def query_usage(
    user_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AIUsageLog)
    if user_id:
        query = query.where(AIUsageLog.user_id == user_id)
    if start_date:
        from datetime import datetime as dt
        query = query.where(AIUsageLog.created_at >= dt.fromisoformat(start_date))
    if end_date:
        from datetime import datetime as dt
        query = query.where(AIUsageLog.created_at <= dt.fromisoformat(end_date))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    result = await db.execute(query.order_by(AIUsageLog.id.desc()).limit(100))
    logs = result.scalars().all()

    items = [
        AIUsageOut(
            id=l.id, user_id=l.user_id, endpoint=l.endpoint, model=l.model,
            prompt_tokens=l.prompt_tokens, completion_tokens=l.completion_tokens,
            cost_microdollars=l.cost_microdollars, latency_ms=l.latency_ms,
            status=l.status, created_at=l.created_at,
        ) for l in logs
    ]

    target_user_id = user_id or current_user["id"]
    user_result = await db.execute(select(User.role).where(User.id == target_user_id))
    role = user_result.scalar_one_or_none() or "student"

    config_result = await db.execute(select(AIConfig))
    configs = {c.key: c.value for c in config_result.scalars().all()}
    budget_limit = int(configs.get(f"budget_{role}", "50000"))

    from datetime import datetime as dt
    today_start = dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    used_result = await db.execute(
        select(func.coalesce(func.sum(
            AIUsageLog.prompt_tokens + AIUsageLog.completion_tokens
        ), 0)).where(
            AIUsageLog.user_id == target_user_id,
            AIUsageLog.created_at >= today_start,
        )
    )
    budget_used = int(used_result.scalar())

    return AIUsageWithBudget(
        items=items, total=total,
        budget_limit=budget_limit, budget_used=budget_used,
        budget_remaining=max(0, budget_limit - budget_used),
    )
```

Add `from typing import Optional` to the router imports.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_ai_stats.py -k "usage" -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai.py backend/tests/test_ai_stats.py && git commit -m "feat: add admin AI usage query endpoint with budget status"
```

---

## Task 15: AI Router — Stats Endpoints

**Files:**
- Modify: `backend/app/routers/ai.py`
- Modify: `backend/tests/test_ai_stats.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_ai_stats.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_stats_aggregate(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    student = await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "admin1")

    db_session.add(AIUsageLog(
        user_id=student.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=100, completion_tokens=50, cost_microdollars=45,
        latency_ms=200, status="success",
    ))
    db_session.add(AIUsageLog(
        user_id=student.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=80, completion_tokens=40, cost_microdollars=36,
        latency_ms=150, status="error",
    ))
    await db_session.flush()

    resp = await client.get("/api/ai/stats", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_calls"] == 2
    assert data["total_prompt_tokens"] == 180
    assert data["success_rate"] == 0.5


@pytest.mark.asyncio(loop_scope="session")
async def test_stats_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.get("/api/ai/stats", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_feedback_summary(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    student = await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "admin1")

    from app.models.ai_feedback import AIFeedback
    log = AIUsageLog(
        user_id=student.id, endpoint="test", model="gpt-4o-mini",
        prompt_tokens=10, completion_tokens=10, cost_microdollars=5,
        latency_ms=100, status="success",
    )
    db_session.add(log)
    await db_session.flush()

    db_session.add(AIFeedback(ai_usage_log_id=log.id, user_id=student.id, rating=1))
    db_session.add(AIFeedback(ai_usage_log_id=log.id, user_id=student.id, rating=-1, comment="不好"))
    await db_session.flush()

    resp = await client.get("/api/ai/stats/feedback", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["positive_count"] == 1
    assert data["negative_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement stats endpoints**

Add to `backend/app/routers/ai.py`:

```python
@router.get("/stats", response_model=AIStatsOut)
async def get_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AIUsageLog)
    from datetime import datetime as dt
    if start_date:
        query = query.where(AIUsageLog.created_at >= dt.fromisoformat(start_date))
    if end_date:
        query = query.where(AIUsageLog.created_at <= dt.fromisoformat(end_date))

    agg = await db.execute(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(AIUsageLog.prompt_tokens), 0).label("pt"),
            func.coalesce(func.sum(AIUsageLog.completion_tokens), 0).label("ct"),
            func.coalesce(func.sum(AIUsageLog.cost_microdollars), 0).label("cost"),
            func.coalesce(func.avg(AIUsageLog.latency_ms), 0).label("avg_lat"),
        ).select_from(query.subquery())
    )
    row = agg.one()
    success_count = await db.execute(
        select(func.count()).select_from(
            query.where(AIUsageLog.status == "success").subquery()
        )
    )
    total = row.total or 0
    success_rate = (success_count.scalar() / total) if total > 0 else 0.0

    return AIStatsOut(
        total_calls=total,
        total_prompt_tokens=int(row.pt),
        total_completion_tokens=int(row.ct),
        total_cost_microdollars=int(row.cost),
        success_rate=round(success_rate, 2),
        avg_latency_ms=round(float(row.avg_lat), 1),
    )


@router.get("/stats/feedback", response_model=AIFeedbackSummary)
async def get_feedback_summary(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    pos_result = await db.execute(
        select(func.count()).select_from(AIFeedback).where(AIFeedback.rating > 0)
    )
    neg_result = await db.execute(
        select(func.count()).select_from(AIFeedback).where(AIFeedback.rating < 0)
    )
    recent_neg = await db.execute(
        select(AIFeedback).where(AIFeedback.rating < 0).order_by(AIFeedback.created_at.desc()).limit(10)
    )
    recent = [
        {"id": f.id, "comment": f.comment, "created_at": f.created_at.isoformat()}
        for f in recent_neg.scalars().all()
    ]
    return AIFeedbackSummary(
        positive_count=pos_result.scalar(),
        negative_count=neg_result.scalar(),
        recent_negative=recent,
    )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_ai_stats.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai.py backend/tests/test_ai_stats.py && git commit -m "feat: add AI stats and feedback summary endpoints"
```

---

## Task 16: AI Router — Test + Config Endpoints

**Files:**
- Modify: `backend/app/routers/ai.py`
- Create: `backend/tests/test_ai_endpoints.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_ai_endpoints.py`:

```python
import pytest
from tests.helpers import create_test_user, login_user, auth_headers
from app.models.ai_config import AIConfig


@pytest.mark.asyncio(loop_scope="session")
async def test_ai_test_call(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    token = await login_user(client, "admin1")

    resp = await client.post("/api/ai/test", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    assert "usage_log_id" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_read_config(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    token = await login_user(client, "admin1")

    resp = await client.get("/api/ai/config", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "model" in data
    assert "is_configured" in data
    assert "budget_admin" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_update_config_model(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    token = await login_user(client, "admin1")

    resp = await client.put(
        "/api/ai/config",
        json={"model": "gpt-4o"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["model"] == "gpt-4o"

    resp2 = await client.get("/api/ai/config", headers=auth_headers(token))
    assert resp2.json()["model"] == "gpt-4o"


@pytest.mark.asyncio(loop_scope="session")
async def test_config_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.get("/api/ai/config", headers=auth_headers(token))
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_test_call_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.post("/api/ai/test", headers=auth_headers(token))
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement test + config endpoints**

Add to `backend/app/routers/ai.py`:

```python
@router.post("/test", response_model=AITestOut)
async def test_ai_call(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = _get_ai_service()
    try:
        result = await service.generate(
            db=db, prompt="你好，请回复'测试成功'", user_id=current_user["id"],
            role=current_user["role"], endpoint="test",
        )
    except BudgetExceededError:
        raise HTTPException(status_code=429, detail="今日 AI 调用额度已用完")
    except AIServiceError:
        return JSONResponse(status_code=502, content={"detail": "AI 服务暂时不可用"})

    return AITestOut(
        text=result["text"],
        usage_log_id=result["usage_log_id"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
    )


@router.get("/config", response_model=AIConfigOut)
async def read_config(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AIConfig))
    configs = {c.key: c.value for c in result.scalars().all()}

    return AIConfigOut(
        model=configs.get("model", settings.AI_MODEL),
        budget_admin=int(configs.get("budget_admin", "500000")),
        budget_teacher=int(configs.get("budget_teacher", "200000")),
        budget_student=int(configs.get("budget_student", "50000")),
        is_configured=bool(settings.AI_API_KEY),
    )


@router.put("/config", response_model=AIConfigOut)
async def update_config(
    data: AIConfigUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        result = await db.execute(select(AIConfig).where(AIConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            config.value = str(value)
            config.updated_by = current_user["id"]
        else:
            db.add(AIConfig(key=key, value=str(value), updated_by=current_user["id"]))
    await db.flush()

    return await read_config(current_user=current_user, db=db)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_ai_endpoints.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai.py backend/tests/test_ai_endpoints.py && git commit -m "feat: add AI test call, config read/update endpoints"
```

---

## Task 17: Prompt Router Endpoints

**Files:**
- Create: `backend/app/routers/prompts.py`
- Modify: `backend/tests/test_prompts.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_prompts.py`:

```python
import json
from tests.helpers import create_test_user, login_user, auth_headers
from app.models.prompt_template import PromptTemplate


@pytest.mark.asyncio(loop_scope="session")
async def test_list_templates(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    token = await login_user(client, "admin1")

    db_session.add(PromptTemplate(
        name="task_description", description="test",
        template_text="生成任务描述", variables=json.dumps(["course_name"]),
    ))
    await db_session.flush()

    resp = await client.get("/api/prompts", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "task_description"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_template(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    token = await login_user(client, "admin1")

    db_session.add(PromptTemplate(
        name="test_tpl", description="test",
        template_text="旧内容 {name}", variables=json.dumps(["name"]),
    ))
    await db_session.flush()

    resp = await client.put(
        "/api/prompts/test_tpl",
        json={"template_text": "新内容 {name}"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["template_text"] == "新内容 {name}"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_template_invalid_variable(client, db_session):
    await create_test_user(db_session, username="admin1", role="admin")
    token = await login_user(client, "admin1")

    db_session.add(PromptTemplate(
        name="test_invalid", description="test",
        template_text="{a}", variables=json.dumps(["a"]),
    ))
    await db_session.flush()

    resp = await client.put(
        "/api/prompts/test_invalid",
        json={"template_text": "{a} and {b}"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_prompts_non_admin_forbidden(client, db_session):
    await create_test_user(db_session, username="stu1", role="student")
    token = await login_user(client, "stu1")

    resp = await client.get("/api/prompts", headers=auth_headers(token))
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Create prompts router**

Create `backend/app/routers/prompts.py`:

```python
import json
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt import PromptTemplateOut, PromptTemplateUpdate

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptTemplateOut])
async def list_templates(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).order_by(PromptTemplate.name))
    templates = result.scalars().all()
    return [
        PromptTemplateOut(
            id=t.id, name=t.name, description=t.description,
            template_text=t.template_text, variables=json.loads(t.variables),
            updated_at=t.updated_at, updated_by=t.updated_by,
        ) for t in templates
    ]


@router.put("/{name}", response_model=PromptTemplateOut)
async def update_template(
    name: str,
    data: PromptTemplateUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.name == name))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    allowed_vars = set(json.loads(template.variables))
    used_vars = set(re.findall(r'\{(\w+)\}', data.template_text))
    invalid = used_vars - allowed_vars
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid variables: {', '.join(sorted(invalid))}",
        )

    template.template_text = data.template_text
    template.updated_by = current_user["id"]
    await db.flush()

    return PromptTemplateOut(
        id=template.id, name=template.name, description=template.description,
        template_text=template.template_text, variables=json.loads(template.variables),
        updated_at=template.updated_at, updated_by=template.updated_by,
    )
```

Register in `backend/app/main.py`:

```python
from app.routers import prompts as prompts_router
# ...
app.include_router(prompts_router.router)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/prompts.py backend/app/main.py backend/tests/test_prompts.py && git commit -m "feat: add prompt template list/update endpoints with variable validation"
```

---

## Task 18: Frontend — AI Admin Views

**Files:**
- Create: `frontend/src/views/admin/AIConfig.vue`
- Create: `frontend/src/views/admin/AIUsage.vue`
- Create: `frontend/src/views/admin/AIFeedback.vue`
- Create: `frontend/src/views/admin/PromptTemplates.vue`

- [ ] **Step 1: Create AIConfig.vue**

Create `frontend/src/views/admin/AIConfig.vue`:

```vue
<template>
  <div>
    <h3 style="margin-bottom: 16px">AI 配置</h3>
    <el-card v-loading="loading">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="当前模型">{{ config.model }}</el-descriptions-item>
        <el-descriptions-item label="API 密钥">
          <el-tag :type="config.is_configured ? 'success' : 'danger'" size="small">
            {{ config.is_configured ? '已配置' : '未配置' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="管理员预算">{{ config.budget_admin?.toLocaleString() }} tokens</el-descriptions-item>
        <el-descriptions-item label="教师预算">{{ config.budget_teacher?.toLocaleString() }} tokens</el-descriptions-item>
        <el-descriptions-item label="学生预算">{{ config.budget_student?.toLocaleString() }} tokens</el-descriptions-item>
      </el-descriptions>
      <el-divider />
      <el-form :model="form" label-width="100px" style="max-width: 400px">
        <el-form-item label="模型">
          <el-input v-model="form.model" />
        </el-form-item>
        <el-form-item label="管理员预算">
          <el-input-number v-model="form.budget_admin" :min="0" :step="10000" />
        </el-form-item>
        <el-form-item label="教师预算">
          <el-input-number v-model="form.budget_teacher" :min="0" :step="10000" />
        </el-form-item>
        <el-form-item label="学生预算">
          <el-input-number v-model="form.budget_student" :min="0" :step="10000" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
          <el-button @click="handleTest" :loading="testing" type="success">测试调用</el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="testResult" type="success" :title="'测试成功'" :description="testResult" show-icon style="margin-top: 16px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const config = ref({})
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref('')

const form = reactive({ model: '', budget_admin: 500000, budget_teacher: 200000, budget_student: 50000 })

async function fetchConfig() {
  loading.value = true
  try {
    const resp = await api.get('/ai/config')
    config.value = resp.data
    Object.assign(form, resp.data)
  } catch { ElMessage.error('获取配置失败') }
  finally { loading.value = false }
}

async function handleSave() {
  saving.value = true
  try {
    await api.put('/ai/config', form)
    ElMessage.success('配置已保存')
    await fetchConfig()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}

async function handleTest() {
  testing.value = true
  testResult.value = ''
  try {
    const resp = await api.post('/ai/test')
    testResult.value = `回复: ${resp.data.text} (tokens: ${resp.data.prompt_tokens}/${resp.data.completion_tokens})`
  } catch (err) { ElMessage.error(err.response?.data?.detail || '测试失败') }
  finally { testing.value = false }
}

onMounted(fetchConfig)
</script>
```

- [ ] **Step 2: Create AIUsage.vue**

Create `frontend/src/views/admin/AIUsage.vue`:

```vue
<template>
  <div>
    <h3 style="margin-bottom: 16px">AI 使用记录</h3>
    <el-table :data="usage.items" v-loading="loading" stripe>
      <el-table-column prop="user_id" label="用户ID" width="80" />
      <el-table-column prop="endpoint" label="功能" width="130" />
      <el-table-column prop="model" label="模型" width="120" />
      <el-table-column prop="prompt_tokens" label="输入 tokens" width="100" />
      <el-table-column prop="completion_tokens" label="输出 tokens" width="100" />
      <el-table-column prop="cost_microdollars" label="费用(μ$)" width="90" />
      <el-table-column prop="latency_ms" label="延迟(ms)" width="90" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" min-width="150">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const usage = reactive({ items: [], total: 0, budget_used: 0, budget_remaining: 0 })
const loading = ref(false)

async function fetchUsage() {
  loading.value = true
  try {
    const resp = await api.get('/ai/usage')
    Object.assign(usage, resp.data)
  } catch { ElMessage.error('获取使用记录失败') }
  finally { loading.value = false }
}

onMounted(fetchUsage)
</script>
```

- [ ] **Step 3: Create AIFeedback.vue**

Create `frontend/src/views/admin/AIFeedback.vue`:

```vue
<template>
  <div>
    <h3 style="margin-bottom: 16px">AI 反馈</h3>
    <el-descriptions :column="2" border style="margin-bottom: 16px">
      <el-descriptions-item label="正面评价">{{ summary.positive_count }}</el-descriptions-item>
      <el-descriptions-item label="负面评价">{{ summary.negative_count }}</el-descriptions-item>
    </el-descriptions>
    <h4>近期负面反馈</h4>
    <el-table :data="summary.recent_negative" v-loading="loading" stripe>
      <el-table-column prop="comment" label="评论" min-width="200" />
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const summary = reactive({ positive_count: 0, negative_count: 0, recent_negative: [] })
const loading = ref(false)

async function fetchSummary() {
  loading.value = true
  try {
    const resp = await api.get('/ai/stats/feedback')
    Object.assign(summary, resp.data)
  } catch { ElMessage.error('获取反馈失败') }
  finally { loading.value = false }
}

onMounted(fetchSummary)
</script>
```

- [ ] **Step 4: Create PromptTemplates.vue**

Create `frontend/src/views/admin/PromptTemplates.vue`:

```vue
<template>
  <div>
    <h3 style="margin-bottom: 16px">Prompt 模板管理</h3>
    <el-table :data="templates" v-loading="loading" stripe>
      <el-table-column prop="name" label="模板名称" width="180" />
      <el-table-column prop="description" label="描述" min-width="150" />
      <el-table-column prop="variables" label="变量" width="200">
        <template #default="{ row }">{{ row.variables?.join(', ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" :title="'编辑: ' + editingName" width="600px">
      <el-input v-model="editText" type="textarea" :rows="10" />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const templates = ref([])
const loading = ref(false)
const editVisible = ref(false)
const editingName = ref('')
const editText = ref('')
const saving = ref(false)

async function fetchTemplates() {
  loading.value = true
  try {
    const resp = await api.get('/prompts')
    templates.value = resp.data
  } catch { ElMessage.error('获取模板列表失败') }
  finally { loading.value = false }
}

function openEdit(template) {
  editingName.value = template.name
  editText.value = template.template_text
  editVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    await api.put(`/prompts/${editingName.value}`, { template_text: editText.value })
    ElMessage.success('模板已更新')
    editVisible.value = false
    await fetchTemplates()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '更新失败') }
  finally { saving.value = false }
}

onMounted(fetchTemplates)
</script>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/ && git commit -m "feat: add AI admin views (config, usage, feedback, prompts)"
```

---

## Task 19: Frontend — Routes + Sidebar

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Add AI admin routes**

In `frontend/src/router/index.js`, add inside the `children` array:

```javascript
      {
        path: 'admin/ai/config',
        name: 'AdminAIConfig',
        component: () => import('../views/admin/AIConfig.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/ai/usage',
        name: 'AdminAIUsage',
        component: () => import('../views/admin/AIUsage.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/ai/feedback',
        name: 'AdminAIFeedback',
        component: () => import('../views/admin/AIFeedback.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/ai/prompts',
        name: 'AdminPromptTemplates',
        component: () => import('../views/admin/PromptTemplates.vue'),
        meta: { roles: ['admin'] },
      },
```

- [ ] **Step 2: Add AI sidebar entries**

In `frontend/src/layouts/MainLayout.vue`, in the admin template section, add after "课程管理":

```html
          <el-menu-item index="/admin/ai/config">
            <span>AI 配置</span>
          </el-menu-item>
          <el-menu-item index="/admin/ai/usage">
            <span>AI 使用记录</span>
          </el-menu-item>
          <el-menu-item index="/admin/ai/feedback">
            <span>AI 反馈</span>
          </el-menu-item>
          <el-menu-item index="/admin/ai/prompts">
            <span>Prompt 模板</span>
          </el-menu-item>
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.js frontend/src/layouts/MainLayout.vue && git commit -m "feat: add AI admin routes and sidebar entries"
```

---

## Task 20: Seed Data + Full Verification

**Files:**
- Modify: `backend/scripts/seed_demo.py`

- [ ] **Step 1: Add AI seed data**

Append to `backend/scripts/seed_demo.py` (add after existing seed data):

```python
import json

# AI Config defaults
ai_configs = [
    AIConfig(key="model", value="gpt-4o-mini"),
    AIConfig(key="budget_admin", value="500000"),
    AIConfig(key="budget_teacher", value="200000"),
    AIConfig(key="budget_student", value="50000"),
    AIConfig(key="price_input", value="0.15"),
    AIConfig(key="price_output", value="0.60"),
]
for c in ai_configs:
    session.add(c)

# Default prompt templates
templates = [
    PromptTemplate(
        name="task_description",
        description="生成任务描述",
        template_text="请为 {course_name} 课程生成一个关于 {topic} 的任务描述，包括目标、步骤和评分标准。语言：{language}",
        variables=json.dumps(["course_name", "topic", "language"]),
    ),
    PromptTemplate(
        name="student_qa",
        description="学生任务问答",
        template_text="根据以下任务信息回答学生的问题。只使用提供的上下文，不要编造信息。\n\n任务：{task_title}\n描述：{task_description}\n要求：{task_requirements}\n课程：{course_name}\n\n学生问题：{question}",
        variables=json.dumps(["task_title", "task_description", "task_requirements", "course_name", "question"]),
    ),
    PromptTemplate(
        name="training_summary",
        description="生成实训总结",
        template_text="请根据学生的提交记录生成一份实训总结。\n\n课程：{course_name}\n课程描述：{course_description}\n提交次数：{submission_count}\n提交内容摘要：\n{submission_summaries}\n\n请包含：学习概述、主要收获、不足与改进",
        variables=json.dumps(["course_name", "course_description", "submission_count", "submission_summaries"]),
    ),
]
for t in templates:
    session.add(t)

await session.flush()
```

Adjust the import block at the top to include:
```python
from app.models.ai_config import AIConfig
from app.models.prompt_template import PromptTemplate
```

- [ ] **Step 2: Run full backend test suite**

Run: `cd /Users/gaofang/Desktop/new_project/backend && .venv/bin/python -m pytest tests/ -v`

Expected: All tests pass (existing + new AI tests).

- [ ] **Step 3: Run frontend build**

Run: `cd /Users/gaofang/Desktop/new_project/frontend && npx vite build`

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/seed_demo.py && git commit -m "feat: add AI seed data (config defaults, prompt templates)"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task(s) |
|---|---|
| AI service layer with provider abstraction | Tasks 4, 5, 8, 9 |
| AI usage logging (all fields) | Tasks 1, 7, 8 |
| Cost calculation (microdollars) | Task 8 (test_generate_cost_calculation) |
| Per-user daily token budget (COALESCE) | Task 6 |
| Budget exceeded returns 429 | Task 8, 16 |
| Provider error → 502 with error log | Task 8 |
| Config read from DB per call | Task 5 |
| AI feedback collection | Tasks 12, 13 |
| Feedback cross-user → 403 | Task 13 |
| Feedback duplicate → 409 | Task 13 |
| Admin usage dashboard | Task 14 |
| Admin stats (aggregate, feedback) | Task 15 |
| Admin test endpoint | Task 16 |
| Admin config read/update | Task 16 |
| API key status indicator | Task 16 (is_configured) |
| Prompt template list/update | Task 17 |
| Prompt variable validation → 400 | Task 17 |
| Non-admin forbidden on all admin endpoints | Tasks 14, 16, 17 |
| Frontend views | Task 18 |
| Routes + sidebar | Task 19 |
| Seed data | Task 20 |

### Placeholder Scan

No TBD, TODO, "implement later", "similar to Task N", or "add appropriate error handling" found.

### Type Consistency

- `AIResponse(text, prompt_tokens, completion_tokens)` — used consistently in MockProvider, OpenAIProvider, FailingProvider, FixedTokenProvider
- `AIService.generate()` returns `dict` with keys `text`, `usage_log_id`, `prompt_tokens`, `completion_tokens`, `cost_microdollars` — matched in router response building
- `AIServiceError` and `BudgetExceededError` — raised in service, caught in router
- `AIConfigOut` has `model`, `budget_admin/teacher/student`, `is_configured` — matched in router read/update
- All schemas use consistent field names matching model attributes
