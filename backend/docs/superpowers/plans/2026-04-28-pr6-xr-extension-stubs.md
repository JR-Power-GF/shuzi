# PR6: XR 对接预留接口 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为未来 XR 厂商接入建立稳定扩展位——provider/adapter 抽象、预约-XR 会话绑定模型、回调事件记录、幂等处理、feature flag 隔离、失败追踪与基础重试。

**Architecture:** 以 Python Protocol 定义 XRProvider 接口，NullXRProvider 为默认实现（无外部调用）。XRSession 表绑定本地预约与外部 XR 会话，XREvent 表记录回调/事件日志（含 event_id 去重）。BookingService 零 XR 耦合——通过 FastAPI BackgroundTasks 在预约提交后异步触发 XR 操作，保证本地主流程不依赖外部调用成功。所有 XR 能力可通过 `XR_ENABLED=False` 一键关闭。

**Tech Stack:** FastAPI BackgroundTasks, SQLAlchemy 2.0 async, HMAC-SHA256 signature verification, Pydantic v2, MySQL 8

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Booking Router (bookings.py)                                │
│  ┌──────────────┐    BackgroundTasks.add_task()              │
│  │ BookingService│ ─────────────────────────────────┐        │
│  │ (zero XR deps)│                                  │        │
│  └──────────────┘                                  ▼        │
│                                         xr_service.py        │
│                                    (own DB session)           │
│                                         │                    │
│                                    ┌────┴────┐               │
│                                    │ XRProvider│              │
│                                    │ Protocol │              │
│                                    └────┬────┘               │
│                                  ┌──────┴──────┐             │
│                                  │NullXRProvider│ (default)   │
│                                  │[FutureVendor]│ (pluggable) │
│                                  └─────────────┘             │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  XR Callback Router (xr.py)                                  │
│  POST /api/v1/xr/callbacks                                   │
│    1. Verify HMAC signature (if secret configured)           │
│    2. Dedup by event_id                                      │
│    3. Create XREvent record                                  │
│    4. Process event → update XRSession status                │
│    5. Return 200/202                                         │
└──────────────────────────────────────────────────────────────┘
```

## Data Model

### xr_sessions — 预约 ↔ 外部 XR 会话绑定

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | INT PK autoincrement | NO | |
| booking_id | INT FK → bookings | NO | UNIQUE, one XR session per booking |
| provider | VARCHAR(20) | NO | default "null" |
| external_session_id | VARCHAR(200) | YES | returned by XR provider |
| status | VARCHAR(20) | NO | pending/active/completed/failed/cancelled |
| request_payload | TEXT | YES | JSON sent to provider |
| response_payload | TEXT | YES | JSON returned by provider |
| error_message | TEXT | YES | failure detail |
| retry_count | INT default 0 | NO | |
| last_retry_at | DATETIME | YES | |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |

Indexes: `ix_xr_sessions_booking_id` (unique), `ix_xr_sessions_status`, `ix_xr_sessions_provider`

### xr_events — 回调/事件日志

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | INT PK autoincrement | NO | |
| event_id | VARCHAR(200) UNIQUE | NO | external dedup key |
| booking_id | INT FK → bookings | YES | may not match known booking |
| xr_session_id | INT FK → xr_sessions | YES | |
| provider | VARCHAR(20) | NO | |
| event_type | VARCHAR(50) | NO | session.started, session.completed, etc. |
| payload | TEXT | YES | JSON body |
| idempotency_key | VARCHAR(200) UNIQUE | YES | processing dedup |
| signature_verified | BOOL default 0 | NO | |
| processed | BOOL default 0 | NO | |
| processing_error | TEXT | YES | |
| processed_at | DATETIME | YES | |
| created_at | DATETIME | NO | |

Indexes: `ix_xr_events_event_id` (unique), `ix_xr_events_idempotency_key` (unique), `ix_xr_events_booking_id`, `ix_xr_events_provider_type` (provider, event_type), `ix_xr_events_processed`

---

## File Structure

**New files:**
| File | Purpose |
|------|---------|
| `app/models/xr_session.py` | XRSession model |
| `app/models/xr_event.py` | XREvent model |
| `app/schemas/xr.py` | XR response schemas |
| `app/services/xr_provider.py` | XRResult dataclass, XRProvider Protocol, NullXRProvider, provider factory |
| `app/services/xr_service.py` | XRService orchestration, signature verification, background tasks |
| `app/routers/xr.py` | XR callback endpoint, session query/retry endpoints |
| `alembic/versions/<hash>_add_xr_tables.py` | Migration for xr_sessions + xr_events |
| `tests/test_xr_provider.py` | Protocol + NullXRProvider + factory tests |
| `tests/test_xr_service.py` | XRService + background task + retry tests |
| `tests/test_xr_callbacks.py` | Callback endpoint + signature + dedup tests |

**Modified files:**
| File | Change |
|------|--------|
| `app/config.py` | +XR_ENABLED, +XR_PROVIDER, +XR_CALLBACK_SECRET |
| `app/models/__init__.py` | +XRSession, +XREvent registration |
| `app/routers/bookings.py` | +BackgroundTasks for XR on create/cancel |
| `app/main.py` | +XR router registration |

---

## Tasks

### Task 1: XR Feature Flag + Provider Config

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xr_config.py
from app.config import Settings


def test_xr_settings_defaults():
    s = Settings()
    assert s.XR_ENABLED is False
    assert s.XR_PROVIDER == "null"
    assert s.XR_CALLBACK_SECRET == ""


def test_xr_settings_from_env(monkeypatch):
    monkeypatch.setenv("XR_ENABLED", "true")
    monkeypatch.setenv("XR_PROVIDER", "pico")
    monkeypatch.setenv("XR_CALLBACK_SECRET", "secret123")
    s = Settings()
    assert s.XR_ENABLED is True
    assert s.XR_PROVIDER == "pico"
    assert s.XR_CALLBACK_SECRET == "secret123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xr_config.py -v`
Expected: FAIL — `Settings` has no `XR_ENABLED` attribute

- [ ] **Step 3: Add XR settings to config.py**

Add three fields to `Settings` class in `app/config.py`:

```python
XR_ENABLED: bool = False
XR_PROVIDER: str = "null"
XR_CALLBACK_SECRET: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xr_config.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite for regression**

Run: `pytest -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add app/config.py tests/test_xr_config.py
git commit -m "feat: add XR feature flag and provider config settings"
```

---

### Task 2: XRResult + XRProvider Protocol + NullXRProvider + Provider Factory

**Files:**
- Create: `app/services/xr_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xr_provider.py
import pytest

from app.services.xr_provider import (
    XRResult,
    NullXRProvider,
    get_xr_provider,
)
from app.config import settings


class TestXRResult:
    def test_success_result(self):
        r = XRResult(success=True, external_session_id="ext-123")
        assert r.success is True
        assert r.external_session_id == "ext-123"
        assert r.error is None
        assert r.raw_response is None

    def test_failure_result(self):
        r = XRResult(success=False, error="timeout")
        assert r.success is False
        assert r.external_session_id is None
        assert r.error == "timeout"


class TestNullXRProvider:
    @pytest.fixture
    def provider(self):
        return NullXRProvider()

    async def test_name(self, provider):
        assert provider.name == "null"

    async def test_create_session_returns_success(self, provider):
        r = await provider.create_session(booking_id=1)
        assert r.success is True
        assert r.external_session_id is None

    async def test_cancel_session_returns_success(self, provider):
        r = await provider.cancel_session(session_id="any")
        assert r.success is True

    async def test_update_session_returns_success(self, provider):
        r = await provider.update_session(session_id="any", updates={})
        assert r.success is True


class TestGetXRProvider:
    def test_returns_null_by_default(self):
        p = get_xr_provider()
        assert isinstance(p, NullXRProvider)

    def test_returns_null_when_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "XR_PROVIDER", "null")
        p = get_xr_provider()
        assert isinstance(p, NullXRProvider)

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "XR_PROVIDER", "nonexistent_vendor")
        with pytest.raises(ValueError, match="Unknown XR provider"):
            get_xr_provider()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xr_provider.py -v`
Expected: FAIL — module `xr_provider` does not exist

- [ ] **Step 3: Implement xr_provider.py**

```python
"""XR Provider protocol, null implementation, and provider factory."""
from __future__ import annotations

import dataclasses
from typing import Any, Protocol, runtime_checkable

from app.config import settings


@dataclasses.dataclass
class XRResult:
    """Return type for all XR provider calls."""
    success: bool
    external_session_id: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None


@runtime_checkable
class XRProvider(Protocol):
    """Abstract interface for XR platform integration.

    Implement this Protocol to add a new XR vendor.
    The NullXRProvider below is the default no-op implementation.
    """

    @property
    def name(self) -> str: ...

    async def create_session(self, *, booking_id: int) -> XRResult: ...

    async def cancel_session(self, *, session_id: str) -> XRResult: ...

    async def update_session(self, *, session_id: str, updates: dict) -> XRResult: ...


class NullXRProvider:
    """No-op XR provider. All methods succeed without external calls."""

    @property
    def name(self) -> str:
        return "null"

    async def create_session(self, *, booking_id: int) -> XRResult:
        return XRResult(success=True)

    async def cancel_session(self, *, session_id: str) -> XRResult:
        return XRResult(success=True)

    async def update_session(self, *, session_id: str, updates: dict) -> XRResult:
        return XRResult(success=True)


_PROVIDER_REGISTRY: dict[str, type] = {
    "null": NullXRProvider,
}


def get_xr_provider() -> XRProvider:
    """Return the configured XR provider instance."""
    provider_name = settings.XR_PROVIDER
    cls = _PROVIDER_REGISTRY.get(provider_name)
    if cls is None:
        raise ValueError(f"Unknown XR provider: {provider_name}")
    return cls()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xr_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/xr_provider.py tests/test_xr_provider.py
git commit -m "feat: add XRProvider protocol, NullXRProvider, and provider factory"
```

---

### Task 3: XRSession Model + XREvent Model + Model Registration

**Files:**
- Create: `app/models/xr_session.py`
- Create: `app/models/xr_event.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xr_models.py
import datetime

import pytest
from sqlalchemy import select

from app.models.xr_session import XRSession
from app.models.xr_event import XREvent


async def test_create_xr_session(db_session):
    xr = XRSession(
        booking_id=1,
        provider="null",
        status="pending",
    )
    db_session.add(xr)
    await db_session.flush()

    result = await db_session.execute(select(XRSession).where(XRSession.booking_id == 1))
    found = result.scalar_one()
    assert found.provider == "null"
    assert found.status == "pending"
    assert found.retry_count == 0
    assert found.external_session_id is None


async def test_xr_session_unique_booking_id(db_session):
    """One XR session per booking — unique constraint."""
    xr1 = XRSession(booking_id=1, provider="null", status="pending")
    db_session.add(xr1)
    await db_session.flush()

    xr2 = XRSession(booking_id=1, provider="null", status="pending")
    db_session.add(xr2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.flush()


async def test_create_xr_event(db_session):
    event = XREvent(
        event_id="evt-001",
        provider="null",
        event_type="session.started",
        payload='{"data": "test"}',
        signature_verified=True,
    )
    db_session.add(event)
    await db_session.flush()

    result = await db_session.execute(select(XREvent).where(XREvent.event_id == "evt-001"))
    found = result.scalar_one()
    assert found.provider == "null"
    assert found.event_type == "session.started"
    assert found.processed is False
    assert found.processing_error is None


async def test_xr_event_unique_event_id(db_session):
    """Dedup — event_id is unique."""
    e1 = XREvent(event_id="evt-dup", provider="null", event_type="session.started")
    db_session.add(e1)
    await db_session.flush()

    e2 = XREvent(event_id="evt-dup", provider="null", event_type="session.started")
    db_session.add(e2)
    with pytest.raises(Exception):
        await db_session.flush()


async def test_xr_event_unique_idempotency_key(db_session):
    """Dedup — idempotency_key is unique when present."""
    e1 = XREvent(
        event_id="evt-a", provider="null", event_type="session.started",
        idempotency_key="key-001",
    )
    db_session.add(e1)
    await db_session.flush()

    e2 = XREvent(
        event_id="evt-b", provider="null", event_type="session.started",
        idempotency_key="key-001",
    )
    db_session.add(e2)
    with pytest.raises(Exception):
        await db_session.flush()


async def test_xr_event_nullable_booking_id(db_session):
    """Events may not reference a known booking."""
    event = XREvent(
        event_id="evt-orphan",
        provider="null",
        event_type="system.heartbeat",
        booking_id=None,
    )
    db_session.add(event)
    await db_session.flush()

    result = await db_session.execute(select(XREvent).where(XREvent.event_id == "evt-orphan"))
    found = result.scalar_one()
    assert found.booking_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xr_models.py -v`
Expected: FAIL — module `xr_session` does not exist

- [ ] **Step 3: Create xr_session.py model**

```python
"""XR session binding — links a local booking to an external XR session."""
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class XRSession(Base):
    __tablename__ = "xr_sessions"
    __table_args__ = (
        Index("ix_xr_sessions_booking_id", "booking_id", unique=True),
        Index("ix_xr_sessions_status", "status"),
        Index("ix_xr_sessions_provider", "provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="null")
    external_session_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    request_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_retry_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False,
    )
```

- [ ] **Step 4: Create xr_event.py model**

```python
"""XR event log — records incoming callbacks and external events."""
import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow_naive


class XREvent(Base):
    __tablename__ = "xr_events"
    __table_args__ = (
        Index("ix_xr_events_event_id", "event_id", unique=True),
        Index("ix_xr_events_idempotency_key", "idempotency_key", unique=True),
        Index("ix_xr_events_booking_id", "booking_id"),
        Index("ix_xr_events_provider_type", "provider", "event_type"),
        Index("ix_xr_events_processed", "processed"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    booking_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True,
    )
    xr_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("xr_sessions.id", ondelete="SET NULL"), nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    signature_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow_naive, nullable=False,
    )
```

- [ ] **Step 5: Register models in `__init__.py`**

Add to `app/models/__init__.py`:

```python
from app.models.xr_session import XRSession
from app.models.xr_event import XREvent
```

And add `"XRSession"` and `"XREvent"` to `__all__`.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_xr_models.py -v`
Expected: PASS

- [ ] **Step 7: Run full test suite for regression**

Run: `pytest -x -q`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add app/models/xr_session.py app/models/xr_event.py app/models/__init__.py tests/test_xr_models.py
git commit -m "feat: add XRSession and XREvent models"
```

---

### Task 4: Migration for xr_sessions + xr_events

**Files:**
- Create: `alembic/versions/<hash>_add_xr_tables.py`

- [ ] **Step 1: Create migration file**

Create `alembic/versions/a1b2c3d4e5f7_add_xr_tables.py`:

```python
"""add xr sessions and events tables

Revision ID: a1b2c3d4e5f7
Revises: c1a2b3d4e5f6
Create Date: 2026-04-28 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('xr_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False, server_default='null'),
        sa.Column('external_session_id', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('request_payload', sa.Text(), nullable=True),
        sa.Column('response_payload', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_xr_sessions_booking_id', 'xr_sessions', ['booking_id'], unique=True)
    op.create_index('ix_xr_sessions_status', 'xr_sessions', ['status'], unique=False)
    op.create_index('ix_xr_sessions_provider', 'xr_sessions', ['provider'], unique=False)

    op.create_table('xr_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(length=200), nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=True),
        sa.Column('xr_session_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=200), nullable=True),
        sa.Column('signature_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'failed', 'cancelled')",
            name='chk_xr_session_status',
        ),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['xr_session_id'], ['xr_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_xr_events_event_id', 'xr_events', ['event_id'], unique=True)
    op.create_index('ix_xr_events_idempotency_key', 'xr_events', ['idempotency_key'], unique=True)
    op.create_index('ix_xr_events_booking_id', 'xr_events', ['booking_id'], unique=False)
    op.create_index('ix_xr_events_provider_type', 'xr_events', ['provider', 'event_type'], unique=False)
    op.create_index('ix_xr_events_processed', 'xr_events', ['processed'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_xr_events_processed', table_name='xr_events')
    op.drop_index('ix_xr_events_provider_type', table_name='xr_events')
    op.drop_index('ix_xr_events_booking_id', table_name='xr_events')
    op.drop_index('ix_xr_events_idempotency_key', table_name='xr_events')
    op.drop_index('ix_xr_events_event_id', table_name='xr_events')
    op.drop_table('xr_events')
    op.drop_index('ix_xr_sessions_provider', table_name='xr_sessions')
    op.drop_index('ix_xr_sessions_status', table_name='xr_sessions')
    op.drop_index('ix_xr_sessions_booking_id', table_name='xr_sessions')
    op.drop_table('xr_sessions')
```

Note: The CHECK constraint on `status` should be on `xr_sessions`, not `xr_events`. Place it correctly in the `create_table('xr_sessions', ...)` call. Move the `CheckConstraint` line from `xr_events` to `xr_sessions`:

```python
# In create_table('xr_sessions', ...) add:
sa.CheckConstraint(
    "status IN ('pending', 'active', 'completed', 'failed', 'cancelled')",
    name='chk_xr_session_status',
),
```

Remove the `CheckConstraint` from `xr_events`.

- [ ] **Step 2: Add CHECK constraint to XRSession model**

Update `app/models/xr_session.py` to include the CHECK:

```python
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index, CheckConstraint

class XRSession(Base):
    __tablename__ = "xr_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'failed', 'cancelled')",
            name="chk_xr_session_status",
        ),
        Index("ix_xr_sessions_booking_id", "booking_id", unique=True),
        Index("ix_xr_sessions_status", "status"),
        Index("ix_xr_sessions_provider", "provider"),
    )
```

- [ ] **Step 3: Verify migration upgrade/downgrade**

Run: `cd backend && alembic upgrade head`
Expected: No error

Run: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: No error

- [ ] **Step 4: Run full test suite**

Run: `pytest -x -q`
Expected: All pass (test DB uses `create_all`, not migrations)

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/a1b2c3d4e5f7_add_xr_tables.py app/models/xr_session.py
git commit -m "feat: add XR tables migration with CHECK constraints"
```

---

### Task 5: XR Schemas

**Files:**
- Create: `app/schemas/xr.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xr_schemas.py
import datetime
from app.schemas.xr import (
    XRSessionResponse,
    XREventResponse,
    XRSessionListResponse,
    XRSessionRetryResponse,
)


def test_xr_session_response():
    r = XRSessionResponse(
        id=1,
        booking_id=10,
        provider="null",
        external_session_id=None,
        status="pending",
        error_message=None,
        retry_count=0,
        created_at=datetime.datetime(2026, 1, 1),
        updated_at=datetime.datetime(2026, 1, 1),
    )
    assert r.provider == "null"
    assert r.status == "pending"


def test_xr_event_response():
    r = XREventResponse(
        id=1,
        event_id="evt-001",
        provider="null",
        event_type="session.started",
        processed=False,
        signature_verified=True,
        created_at=datetime.datetime(2026, 1, 1),
    )
    assert r.event_id == "evt-001"
    assert r.processed is False


def test_xr_session_list_response():
    r = XRSessionListResponse(items=[], total=0)
    assert r.total == 0


def test_xr_session_retry_response():
    r = XRSessionRetryResponse(session_id=1, status="pending", message="Retry scheduled")
    assert r.status == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xr_schemas.py -v`
Expected: FAIL — module `xr` does not exist in schemas

- [ ] **Step 3: Create xr.py schemas**

```python
"""XR response schemas."""
import datetime
from typing import Optional, List

from pydantic import BaseModel


class XRSessionResponse(BaseModel):
    id: int
    booking_id: int
    provider: str
    external_session_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    retry_count: int = 0
    last_retry_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class XRSessionListResponse(BaseModel):
    items: List[XRSessionResponse]
    total: int


class XREventResponse(BaseModel):
    id: int
    event_id: str
    provider: str
    event_type: str
    processed: bool
    processing_error: Optional[str] = None
    signature_verified: bool
    created_at: datetime.datetime


class XRSessionRetryResponse(BaseModel):
    session_id: int
    status: str
    message: str


class XRCallbackResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xr_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/xr.py tests/test_xr_schemas.py
git commit -m "feat: add XR response schemas"
```

---

### Task 6: XRService — Orchestration, Background Tasks, Signature Verification

**Files:**
- Create: `app/services/xr_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xr_service.py
import json
import pytest

from app.config import settings
from app.models.booking import Booking
from app.models.xr_session import XRSession
from app.models.xr_event import XREvent
from app.services.xr_service import (
    create_xr_session_for_booking,
    cancel_xr_session_for_booking,
    process_callback_event,
    retry_failed_session,
    verify_callback_signature,
)
from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_booking,
)


async def _setup_booking(db):
    user = await create_test_user(db, username="xr-user", role="admin")
    venue = await create_test_venue(db, name="XR Venue")
    booking = await create_test_booking(db, venue_id=venue.id, booked_by=user.id)
    return booking


class TestCreateXRSessionBackground:
    async def test_creates_session_when_enabled(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking = await _setup_booking(db_session)
        await db_session.commit()

        await create_xr_session_for_booking(booking.id)

        # Verify in new session
        from sqlalchemy import select
        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking.id)
        )
        xr = result.scalar_one_or_none()
        assert xr is not None
        assert xr.provider == "null"
        assert xr.status == "completed"

    async def test_skips_when_disabled(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", False)
        booking = await _setup_booking(db_session)
        await db_session.commit()

        await create_xr_session_for_booking(booking.id)

        from sqlalchemy import select
        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking.id)
        )
        assert result.scalar_one_or_none() is None


class TestCancelXRSessionBackground:
    async def test_cancels_existing_session(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking = await _setup_booking(db_session)
        await db_session.commit()

        await create_xr_session_for_booking(booking.id)
        await cancel_xr_session_for_booking(booking.id)

        from sqlalchemy import select
        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking.id)
        )
        xr = result.scalar_one()
        assert xr.status == "cancelled"


class TestProcessCallbackEvent:
    async def test_creates_event_and_returns_true(self, db_session):
        payload = {
            "event_id": "cb-001",
            "provider": "null",
            "event_type": "session.started",
            "data": {"session_id": "ext-abc"},
        }
        result = await process_callback_event(
            event_id="cb-001",
            provider="null",
            event_type="session.started",
            payload=payload,
            idempotency_key="key-001",
            signature_verified=True,
        )
        assert result is True

        from sqlalchemy import select
        ev_result = await db_session.execute(
            select(XREvent).where(XREvent.event_id == "cb-001")
        )
        ev = ev_result.scalar_one()
        assert ev.processed is True

    async def test_dedup_returns_false_for_duplicate(self, db_session):
        payload = {
            "event_id": "cb-dup",
            "provider": "null",
            "event_type": "session.started",
        }
        await process_callback_event(
            event_id="cb-dup",
            provider="null",
            event_type="session.started",
            payload=payload,
        )
        result = await process_callback_event(
            event_id="cb-dup",
            provider="null",
            event_type="session.started",
            payload=payload,
        )
        assert result is False


class TestRetryFailedSession:
    async def test_retries_and_increments_count(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking = await _setup_booking(db_session)
        await db_session.commit()

        # Create a failed session
        from app.database import async_session_maker
        async with async_session_maker() as session:
            xr = XRSession(
                booking_id=booking.id,
                provider="null",
                status="failed",
                error_message="timeout",
                retry_count=1,
            )
            session.add(xr)
            await session.commit()
            xr_id = xr.id

        result = await retry_failed_session(xr_id)
        assert result.success is True

        from sqlalchemy import select
        xr_result = await db_session.execute(
            select(XRSession).where(XRSession.id == xr_id)
        )
        xr = xr_result.scalar_one()
        assert xr.retry_count == 2
        assert xr.status == "completed"

    async def test_rejects_non_failed_session(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking = await _setup_booking(db_session)
        await db_session.commit()

        from app.database import async_session_maker
        async with async_session_maker() as session:
            xr = XRSession(
                booking_id=booking.id,
                provider="null",
                status="completed",
            )
            session.add(xr)
            await session.commit()
            xr_id = xr.id

        result = await retry_failed_session(xr_id)
        assert result.success is False
        assert "not in failed state" in (result.error or "")


class TestVerifyCallbackSignature:
    def test_valid_signature(self):
        secret = "test-secret"
        body = b'{"event_id": "test"}'
        import hmac, hashlib
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_callback_signature(secret, body, sig) is True

    def test_invalid_signature(self):
        assert verify_callback_signature("secret", b"body", "wrong") is False

    def test_no_secret_skips_verification(self):
        assert verify_callback_signature("", b"body", "") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xr_service.py -v`
Expected: FAIL — module `xr_service` does not exist

- [ ] **Step 3: Implement xr_service.py**

```python
"""XR service — orchestration layer for XR session lifecycle and callback processing.

All public functions open their own DB sessions (background-task safe).
BookingService has zero coupling to this module.
"""
import hashlib
import hmac
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker
from app.models.xr_event import XREvent
from app.models.xr_session import XRSession
from app.services.xr_provider import XRResult, get_xr_provider

logger = logging.getLogger(__name__)


def verify_callback_signature(secret: str, body: bytes, signature: str) -> bool:
    """HMAC-SHA256 signature verification. Returns True when secret is empty (skip)."""
    if not secret:
        return True
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def create_xr_session_for_booking(booking_id: int) -> None:
    """Background task: create an XR session after booking is committed."""
    if not settings.XR_ENABLED:
        return

    provider = get_xr_provider()
    async with async_session_maker() as session:
        try:
            result = await provider.create_session(booking_id=booking_id)

            xr_session = XRSession(
                booking_id=booking_id,
                provider=provider.name,
                external_session_id=result.external_session_id,
                status="completed" if result.success else "failed",
                response_payload=json.dumps(result.raw_response) if result.raw_response else None,
                error_message=result.error,
            )
            session.add(xr_session)
            await session.commit()
        except Exception:
            logger.exception("XR session creation failed for booking %d", booking_id)
            # Still create a record so admin can see and retry
            try:
                xr_session = XRSession(
                    booking_id=booking_id,
                    provider=provider.name,
                    status="failed",
                    error_message="Background task exception",
                )
                session.add(xr_session)
                await session.commit()
            except Exception:
                logger.exception("Failed to record XR failure for booking %d", booking_id)


async def cancel_xr_session_for_booking(booking_id: int) -> None:
    """Background task: cancel the XR session for a booking."""
    if not settings.XR_ENABLED:
        return

    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(XRSession).where(XRSession.booking_id == booking_id)
            )
            xr_session = result.scalar_one_or_none()
            if xr_session is None:
                return

            if xr_session.external_session_id:
                provider = get_xr_provider()
                await provider.cancel_session(session_id=xr_session.external_session_id)

            xr_session.status = "cancelled"
            await session.commit()
        except Exception:
            logger.exception("XR session cancellation failed for booking %d", booking_id)


async def process_callback_event(
    *,
    event_id: str,
    provider: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    signature_verified: bool = False,
) -> bool:
    """Process an incoming callback event. Returns True if newly processed, False if duplicate.

    Opens its own session — safe to call from router with `Depends(get_db)`.
    """
    async with async_session_maker() as session:
        try:
            # Dedup check
            existing = await session.execute(
                select(XREvent).where(XREvent.event_id == event_id)
            )
            if existing.scalar_one_or_none() is not None:
                return False

            # Also check idempotency_key if provided
            if idempotency_key:
                existing_key = await session.execute(
                    select(XREvent).where(XREvent.idempotency_key == idempotency_key)
                )
                if existing_key.scalar_one_or_none() is not None:
                    return False

            event = XREvent(
                event_id=event_id,
                provider=provider,
                event_type=event_type,
                payload=json.dumps(payload, default=str) if payload else None,
                idempotency_key=idempotency_key,
                signature_verified=signature_verified,
                processed=True,
                processed_at=_now(),
            )

            # Try to link to a booking if payload contains booking reference
            if payload and isinstance(payload, dict):
                booking_id = payload.get("booking_id")
                if booking_id:
                    event.booking_id = int(booking_id)

                    # Update related XRSession status if applicable
                    xr_result = await session.execute(
                        select(XRSession).where(XRSession.booking_id == int(booking_id))
                    )
                    xr_session = xr_result.scalar_one_or_none()
                    if xr_session:
                        event.xr_session_id = xr_session.id
                        _update_session_from_event(xr_session, event_type)

            session.add(event)
            await session.commit()
            return True
        except Exception:
            logger.exception("XR callback processing failed for event %s", event_id)
            await session.rollback()
            raise


async def retry_failed_session(session_id: int) -> XRResult:
    """Retry a failed XR session. Returns result with success status."""
    if not settings.XR_ENABLED:
        return XRResult(success=False, error="XR is disabled")

    provider = get_xr_provider()
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(XRSession).where(XRSession.id == session_id)
            )
            xr_session = result.scalar_one_or_none()
            if xr_session is None:
                return XRResult(success=False, error="XR session not found")
            if xr_session.status != "failed":
                return XRResult(
                    success=False,
                    error=f"Session not in failed state (current: {xr_session.status})",
                )

            # Load booking
            from app.models.booking import Booking
            booking_result = await session.execute(
                select(Booking).where(Booking.id == xr_session.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                return XRResult(success=False, error="Booking not found")

            provider_result = await provider.create_session(booking_id=booking.id)

            xr_session.retry_count += 1
            xr_session.last_retry_at = _now()
            xr_session.status = "completed" if provider_result.success else "failed"
            xr_session.error_message = provider_result.error
            xr_session.external_session_id = (
                provider_result.external_session_id or xr_session.external_session_id
            )
            await session.commit()

            return XRResult(
                success=provider_result.success,
                error=provider_result.error,
            )
        except Exception as e:
            logger.exception("XR retry failed for session %d", session_id)
            return XRResult(success=False, error=str(e))


def _update_session_from_event(xr_session: XRSession, event_type: str) -> None:
    """Map callback event_type to XRSession status update."""
    mapping = {
        "session.started": "active",
        "session.completed": "completed",
        "session.failed": "failed",
        "session.cancelled": "cancelled",
    }
    new_status = mapping.get(event_type)
    if new_status:
        xr_session.status = new_status


def _now():
    """UTC now as naive datetime."""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xr_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/xr_service.py tests/test_xr_service.py
git commit -m "feat: add XRService orchestration with background tasks and signature verification"
```

---

### Task 7: XR Router — Callback Endpoint, Session Query, Retry

**Files:**
- Create: `app/routers/xr.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xr_callbacks.py
import json
import hmac
import hashlib
import pytest

from app.config import settings
from app.models.xr_session import XRSession
from app.models.xr_event import XREvent
from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_booking,
    login_user,
    auth_headers,
)


async def _setup(client, db):
    admin = await create_test_user(db, username="xr-admin", role="admin")
    venue = await create_test_venue(db, name="XR Venue")
    booking = await create_test_booking(db, venue_id=venue.id, booked_by=admin.id)
    token = await login_user(client, "xr-admin")
    return booking, token


class TestCallbackEndpoint:
    async def test_receive_callback(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "")

        payload = {
            "event_id": "evt-cb-001",
            "provider": "null",
            "event_type": "session.started",
            "data": {"key": "value"},
        }
        resp = await client.post(
            "/api/v1/xr/callbacks",
            json=payload,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processed"
        assert body["event_id"] == "evt-cb-001"

    async def test_reject_duplicate_callback(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "")

        payload = {
            "event_id": "evt-dup-cb",
            "provider": "null",
            "event_type": "session.started",
        }
        resp1 = await client.post("/api/v1/xr/callbacks", json=payload)
        assert resp1.status_code == 200

        resp2 = await client.post("/api/v1/xr/callbacks", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "already_processed"

    async def test_reject_missing_event_id(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        resp = await client.post(
            "/api/v1/xr/callbacks",
            json={"provider": "null", "event_type": "test"},
        )
        assert resp.status_code == 400

    async def test_reject_invalid_signature(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "my-secret")

        payload = {"event_id": "evt-sig", "provider": "null", "event_type": "test"}
        resp = await client.post(
            "/api/v1/xr/callbacks",
            json=payload,
            headers={"X-XR-Signature": "wrong-signature"},
        )
        assert resp.status_code == 401

    async def test_accept_valid_signature(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        monkeypatch.setattr(settings, "XR_CALLBACK_SECRET", "my-secret")

        payload = {"event_id": "evt-sig-ok", "provider": "null", "event_type": "test"}
        body = json.dumps(payload).encode()
        sig = hmac.new(b"my-secret", body, hashlib.sha256).hexdigest()
        resp = await client.post(
            "/api/v1/xr/callbacks",
            json=payload,
            headers={"X-XR-Signature": sig},
        )
        assert resp.status_code == 200


class TestXRSessionEndpoint:
    async def test_list_sessions(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking, token = await _setup(client, db_session)

        # Create XR session directly
        xr = XRSession(booking_id=booking.id, provider="null", status="completed")
        db_session.add(xr)
        await db_session.flush()

        resp = await client.get(
            "/api/v1/xr/sessions",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    async def test_list_sessions_forbidden_for_teacher(self, client, db_session):
        teacher = await create_test_user(db_session, username="xr-teacher", role="teacher")
        token = await login_user(client, "xr-teacher")
        resp = await client.get("/api/v1/xr/sessions", headers=auth_headers(token))
        assert resp.status_code == 403


class TestXRRetryEndpoint:
    async def test_retry_failed_session(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        booking, token = await _setup(client, db_session)

        xr = XRSession(
            booking_id=booking.id, provider="null", status="failed",
            error_message="timeout", retry_count=1,
        )
        db_session.add(xr)
        await db_session.flush()
        xr_id = xr.id

        resp = await client.post(
            f"/api/v1/xr/sessions/{xr_id}/retry",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("pending", "completed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xr_callbacks.py -v`
Expected: FAIL — module `xr` does not exist in routers

- [ ] **Step 3: Create xr.py router**

```python
"""XR extension router — callbacks, session queries, and retry."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import require_role
from app.models.xr_session import XRSession
from app.models.xr_event import XREvent
from app.schemas.xr import (
    XRSessionResponse,
    XRSessionListResponse,
    XRSessionRetryResponse,
    XRCallbackResponse,
)
from app.services.xr_service import (
    process_callback_event,
    retry_failed_session,
    verify_callback_signature,
)

router = APIRouter(prefix="/api/v1/xr", tags=["xr"])


@router.post("/callbacks", response_model=XRCallbackResponse)
async def receive_callback(
    request: Request,
):
    """Receive and process an XR provider callback.

    Public endpoint (no auth) — security is via HMAC signature.
    """
    if not settings.XR_ENABLED:
        raise HTTPException(status_code=503, detail="XR integration is disabled")

    body = await request.body()

    # Signature verification
    if settings.XR_CALLBACK_SECRET:
        signature = request.headers.get("X-XR-Signature", "")
        if not verify_callback_signature(settings.XR_CALLBACK_SECRET, body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = payload.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event_id")

    provider = payload.get("provider", "unknown")
    event_type = payload.get("event_type", "unknown")
    idempotency_key = payload.get("idempotency_key")

    is_new = await process_callback_event(
        event_id=event_id,
        provider=provider,
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
        signature_verified=bool(settings.XR_CALLBACK_SECRET),
    )

    if not is_new:
        return XRCallbackResponse(status="already_processed", event_id=event_id)

    return XRCallbackResponse(status="processed", event_id=event_id)


@router.get("/sessions", response_model=XRSessionListResponse)
async def list_xr_sessions(
    status_filter: str | None = Query(None, alias="status"),
    provider: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    """List XR sessions with optional filters."""
    conditions = []
    if status_filter:
        conditions.append(XRSession.status == status_filter)
    if provider:
        conditions.append(XRSession.provider == provider)

    count_stmt = select(func.count()).select_from(XRSession)
    for c in conditions:
        count_stmt = count_stmt.where(c)
    total = (await db.execute(count_stmt)).scalar_one()

    data_stmt = select(XRSession).order_by(XRSession.created_at.desc())
    for c in conditions:
        data_stmt = data_stmt.where(c)
    data_stmt = data_stmt.limit(limit).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    items = [
        XRSessionResponse(
            id=r.id,
            booking_id=r.booking_id,
            provider=r.provider,
            external_session_id=r.external_session_id,
            status=r.status,
            error_message=r.error_message,
            retry_count=r.retry_count,
            last_retry_at=r.last_retry_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return XRSessionListResponse(items=items, total=total)


@router.post("/sessions/{session_id}/retry", response_model=XRSessionRetryResponse)
async def retry_xr_session(
    session_id: int,
    _current_user: dict = Depends(require_role(["admin", "facility_manager"])),
):
    """Retry a failed XR session."""
    if not settings.XR_ENABLED:
        raise HTTPException(status_code=503, detail="XR integration is disabled")

    result = await retry_failed_session(session_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return XRSessionRetryResponse(
        session_id=session_id,
        status="pending",
        message="Retry completed",
    )
```

- [ ] **Step 4: Register router in main.py**

Add to `app/main.py`:

```python
from app.routers import xr as xr_router
```

And:

```python
app.include_router(xr_router.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_xr_callbacks.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/routers/xr.py app/main.py tests/test_xr_callbacks.py
git commit -m "feat: add XR router with callback endpoint, session listing, and retry"
```

---

### Task 8: BookingService Integration — BackgroundTasks for XR

**Files:**
- Modify: `app/routers/bookings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xr_booking_integration.py
import pytest

from app.config import settings
from app.models.xr_session import XRSession
from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_equipment,
    login_user,
    auth_headers,
)


async def _setup_admin_with_venue(client, db):
    admin = await create_test_user(db, username="xr-bk-admin", role="admin")
    venue = await create_test_venue(db, name="XR Booking Venue")
    token = await login_user(client, "xr-bk-admin")
    return admin, venue, token


class TestBookingTriggersXR:
    async def test_create_booking_triggers_xr_session(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        admin, venue, token = await _setup_admin_with_venue(client, db_session)

        resp = await client.post(
            "/api/v1/bookings",
            json={
                "venue_id": venue.id,
                "title": "XR Booking",
                "start_time": "2026-07-01T09:00:00",
                "end_time": "2026-07-01T11:00:00",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        booking_id = resp.json()["id"]

        # Wait for background task
        import asyncio
        await asyncio.sleep(0.5)

        from sqlalchemy import select
        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking_id)
        )
        xr = result.scalar_one_or_none()
        assert xr is not None
        assert xr.status == "completed"

    async def test_create_booking_no_xr_when_disabled(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr(settings, "XR_ENABLED", False)
        admin, venue, token = await _setup_admin_with_venue(client, db_session)

        resp = await client.post(
            "/api/v1/bookings",
            json={
                "venue_id": venue.id,
                "title": "No XR Booking",
                "start_time": "2026-07-02T09:00:00",
                "end_time": "2026-07-02T11:00:00",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        booking_id = resp.json()["id"]

        import asyncio
        await asyncio.sleep(0.3)

        from sqlalchemy import select
        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_cancel_booking_triggers_xr_cancel(
        self, client, db_session, monkeypatch
    ):
        monkeypatch.setattr(settings, "XR_ENABLED", True)
        admin, venue, token = await _setup_admin_with_venue(client, db_session)

        resp = await client.post(
            "/api/v1/bookings",
            json={
                "venue_id": venue.id,
                "title": "Cancel XR",
                "start_time": "2026-08-01T09:00:00",
                "end_time": "2026-08-01T11:00:00",
            },
            headers=auth_headers(token),
        )
        booking_id = resp.json()["id"]

        import asyncio
        await asyncio.sleep(0.5)

        # Cancel booking
        resp = await client.post(
            f"/api/v1/bookings/{booking_id}/cancel",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

        await asyncio.sleep(0.5)

        from sqlalchemy import select
        result = await db_session.execute(
            select(XRSession).where(XRSession.booking_id == booking_id)
        )
        xr = result.scalar_one()
        assert xr.status == "cancelled"

    async def test_booking_succeeds_even_if_xr_fails(
        self, client, db_session, monkeypatch
    ):
        """Core guarantee: local booking never depends on XR success."""
        monkeypatch.setattr(settings, "XR_ENABLED", True)

        # Make XR provider fail
        from app.services import xr_provider as xp_module

        class FailingProvider(xp_module.NullXRProvider):
            @property
            def name(self):
                return "null"

            async def create_session(self, *, booking_id):
                return xp_module.XRResult(success=False, error="simulated failure")

        original_registry = xp_module._PROVIDER_REGISTRY.copy()
        xp_module._PROVIDER_REGISTRY["null"] = FailingProvider

        try:
            admin, venue, token = await _setup_admin_with_venue(client, db_session)

            resp = await client.post(
                "/api/v1/bookings",
                json={
                    "venue_id": venue.id,
                    "title": "Survives XR Failure",
                    "start_time": "2026-09-01T09:00:00",
                    "end_time": "2026-09-01T11:00:00",
                },
                headers=auth_headers(token),
            )
            assert resp.status_code == 201

            import asyncio
            await asyncio.sleep(0.5)

            from sqlalchemy import select
            result = await db_session.execute(
                select(XRSession).where(
                    XRSession.booking_id == resp.json()["id"]
                )
            )
            xr = result.scalar_one_or_none()
            assert xr is not None
            assert xr.status == "failed"
            assert xr.error_message is not None
        finally:
            xp_module._PROVIDER_REGISTRY = original_registry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_xr_booking_integration.py -v`
Expected: FAIL — booking router doesn't call XR

- [ ] **Step 3: Modify bookings.py router to add BackgroundTasks**

Update `app/routers/bookings.py` — add `BackgroundTasks` parameter to create and cancel endpoints:

Add import at the top:
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, BackgroundTasks
```

Add XR service imports:
```python
from app.config import settings
from app.services.xr_service import create_xr_session_for_booking, cancel_xr_session_for_booking
```

Modify `create_booking`:
```python
@router.post("", response_model=BookingResponse)
async def create_booking(
    data: BookingCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "facility_manager", "teacher"])),
    db: AsyncSession = Depends(get_db),
):
    booked_by = current_user["id"]
    svc = BookingService(db)
    booking, is_idempotent = await svc.create(data, actor_id=booked_by)

    if settings.XR_ENABLED and not is_idempotent:
        background_tasks.add_task(create_xr_session_for_booking, booking.id)

    response.status_code = status.HTTP_200_OK if is_idempotent else status.HTTP_201_CREATED
    return await _enrich_booking(db, booking)
```

Modify `cancel_booking`:
```python
@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = BookingService(db)
    booking = await svc.get(booking_id)

    role = current_user["role"]
    if role not in ("admin", "facility_manager"):
        if booking.booked_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="权限不足")

    booking = await svc.cancel(booking_id, actor_id=current_user["id"])

    if settings.XR_ENABLED:
        background_tasks.add_task(cancel_xr_session_for_booking, booking.id)

    return await _enrich_booking(db, booking)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_xr_booking_integration.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite for regression**

Run: `pytest -x -q`
Expected: All pass (existing booking tests should still work — BackgroundTasks is a no-op in test client)

- [ ] **Step 6: Commit**

```bash
git add app/routers/bookings.py tests/test_xr_booking_integration.py
git commit -m "feat: integrate XR background tasks into booking create and cancel flows"
```

---

### Task 9: Full Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

- [ ] **Step 2: Verify migration chain**

Run: `cd backend && alembic upgrade head`
Expected: No error

Run: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: No error

- [ ] **Step 3: Verify XR feature flag works**

Run: `XR_ENABLED=false pytest tests/test_xr_booking_integration.py -v`
Expected: All pass

- [ ] **Step 4: Verify existing API regression**

Run: `pytest tests/test_auth.py tests/test_bookings.py tests/test_venues.py tests/test_equipment.py -v`
Expected: All pass

- [ ] **Step 5: Verify no XR coupling in BookingService**

Run: `grep -rn "xr" app/services/booking_service.py`
Expected: Zero matches — BookingService has no XR imports

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: PR6 XR extension stubs — provider protocol, binding model, callback infrastructure"
```

---

## Provider / Adapter Contract

### XRProvider Protocol

```python
class XRProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def create_session(self, *, booking_id: int) -> XRResult: ...
    async def cancel_session(self, *, session_id: str) -> XRResult: ...
    async def update_session(self, *, session_id: str, updates: dict) -> XRResult: ...
```

### XRResult

```python
@dataclass
class XRResult:
    success: bool
    external_session_id: str | None = None
    error: str | None = None
    raw_response: dict | None = None
```

### Adding a new provider

1. Create `app/services/xr_pico_provider.py` implementing `XRProvider`
2. Register in `_PROVIDER_REGISTRY` in `xr_provider.py`
3. Set `XR_PROVIDER=pico` in environment

---

## Failure Isolation and Retry Strategy

| Scenario | Behavior |
|----------|----------|
| XR_ENABLED=False | All XR code skipped. Zero overhead. |
| Provider.create_session() raises exception | XRSession created with status="failed". Booking succeeds. |
| Provider returns XRResult(success=False) | XRSession.status="failed", error_message recorded. Booking succeeds. |
| Background task fails entirely | No XRSession record created. Admin sees gap. Can retry manually. |
| Callback with duplicate event_id | Returns 200 with status="already_processed". No re-processing. |
| Callback with invalid signature | Returns 401. No record created. |
| Retry a failed session | Increments retry_count, updates status, records last_retry_at. |

**Retry limits:** No hard cap in V1 — admin decides via dashboard. retry_count tracks attempts for visibility.

**Compensation path:** Admin can query XRSession where status="failed", inspect error_message, and call POST `/api/v1/xr/sessions/{id}/retry`.

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Callback authentication | HMAC-SHA256 signature verification via `X-XR-Signature` header. Skipped when `XR_CALLBACK_SECRET=""` (testing only). |
| Event replay / dedup | `event_id` UNIQUE constraint + `idempotency_key` UNIQUE constraint. Duplicate callbacks return 200 without re-processing. |
| SQL injection in payload | Payload stored as JSON TEXT, never evaluated as SQL. |
| Feature flag isolation | `XR_ENABLED=False` completely bypasses all XR code paths — no provider calls, no session creation, no callback acceptance. |
| Provider secrets | `XR_CALLBACK_SECRET` loaded from env var, never logged or exposed in API responses. |
| Admin-only management | Session listing and retry endpoints require admin/facility_manager role. |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| BackgroundTasks lost on server restart | V1 acceptable — XRSession with status="pending" can be detected and retried. Future: use Celery/ARQ for durable task queue. |
| Race condition: booking cancelled before XR background fires | `cancel_xr_session_for_booking` checks booking status and skips if already cancelled. |
| Provider takes too long | NullXRProvider is instant. Real providers should have timeouts. XRService catches all exceptions. |
| Multiple XR sessions for same booking | UNIQUE constraint on booking_id prevents duplicates. |
| Callback references unknown booking | XREvent.booking_id is nullable. Event is still recorded for audit trail. |
| Test timing: background tasks in tests | Tests use `asyncio.sleep(0.5)` to wait for background tasks. Acceptable for integration tests. |

---

## Definition of Done / Merge Bar

- [ ] All 9 tasks complete with passing tests
- [ ] `pytest -v` zero failures
- [ ] `alembic upgrade head` + `alembic downgrade -1 && alembic upgrade head` both succeed
- [ ] BookingService has zero XR imports (`grep -rn "xr" app/services/booking_service.py` returns nothing)
- [ ] Feature flag works: `XR_ENABLED=False` → no XR sessions created, callbacks rejected
- [ ] HMAC signature verification works for callbacks
- [ ] Event dedup works: duplicate event_id returns "already_processed"
- [ ] Retry works on failed sessions
- [ ] No regression on existing booking/venue/equipment routes
- [ ] XRSession + XREvent models registered and migrated
- [ ] NullXRProvider creates sessions with status="completed" (no external call)
- [ ] Booking succeeds even when XR provider fails (core isolation guarantee)
