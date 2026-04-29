# PR5: 利用率统计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供场地利用率、设备使用频次、高峰时段三项基础统计，明确口径，守住性能边界。

**Architecture:** 新建独立 stats 路由模块 + service 层。统计口径在 service 层实现，路由层只做参数校验和权限。分子通过 SQL 聚合查询（复用 bookings 表索引），分母通过 Python 计算（VenueAvailability + VenueBlackout），避免复杂 SQL。前端提供 admin/fm 专用统计页面。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + MySQL 8 + Pydantic v2 + Vue 3 + Element Plus + ECharts

---

## Metric Definitions

### M1: 场地利用率 (Venue Utilization)

| 维度 | 定义 |
|------|------|
| **分子** | 查询窗口内 `status='approved'` 预约占用时长，裁剪到窗口边界，单位小时 |
| **分母** | 查询窗口内场地可用时长（VenueAvailability 定义 → 按天累加；无定义 → 24h/天；减去 Blackout 日期的可用时长） |
| **取消单** | 不计入分子 |
| **停用/维修** | 当前非 active 的场地排除出结果（不返回统计） |
| **跨日预约** | 按窗口边界裁剪，不做日拆分（V1 按整体计算） |
| **零可用时长** | `utilization_rate = null`，`available_hours = 0` |
| **公式** | `rate = booked_hours / available_hours`（available_hours=0 时 rate=null） |

### M2: 设备使用频次 (Equipment Usage)

| 维度 | 定义 |
|------|------|
| **计数** | 查询窗口内包含该设备的 `status='approved'` 预约数量（DISTINCT booking_id） |
| **总时长** | 上述预约在窗口内的占用时长（小时），裁剪到窗口边界 |
| **取消单** | 不计入 |
| **无预约设备** | `booking_count = 0`，`total_hours = 0` |
| **频次** | 非比率，无需分母 |

### M3: 高峰时段 (Peak Hours)

| 维度 | 定义 |
|------|------|
| **统计** | 查询窗口内按 `HOUR(start_time)` 分组的 `status='approved'` 预约计数 |
| **范围** | 0-23 共 24 个时段 |
| **取消单** | 不计入 |
| **跨日** | 按 start_time 的 hour 归属，不拆分 |

### 通用规则

| 规则 | 值 |
|------|-----|
| 默认查询窗口 | 最近 7 天（含今日） |
| 最大查询窗口 | 90 天 |
| 最大返回资源数 | 100 |
| 权限 | `admin` + `facility_manager` |
| 零结果 | 返回空列表 `items=[]`，不返回 404 |

---

## API Design

### Endpoints

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/v1/stats/venue-utilization` | 场地利用率 |
| GET | `/api/v1/stats/equipment-usage` | 设备使用频次 |
| GET | `/api/v1/stats/peak-hours` | 高峰时段分布 |

### Query Parameters (共用)

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| start_date | date | 否 | 7 天前 | 窗口起始 |
| end_date | date | 否 | 今日 | 窗口结束 |
| limit | int | 否 | 100 | 最多返回资源数 (1-100) |

### Response Schemas

**Venue Utilization:**
```json
{
  "window": {"start_date": "2026-04-21", "end_date": "2026-04-28"},
  "items": [
    {
      "venue_id": 1,
      "venue_name": "Lab A",
      "booked_hours": 24.5,
      "available_hours": 56.0,
      "utilization_rate": 0.438,
      "booking_count": 8
    }
  ]
}
```

**Equipment Usage:**
```json
{
  "window": {"start_date": "2026-04-21", "end_date": "2026-04-28"},
  "items": [
    {
      "equipment_id": 1,
      "equipment_name": "VR Headset",
      "category": "VR",
      "booking_count": 12,
      "total_hours": 18.5
    }
  ]
}
```

**Peak Hours:**
```json
{
  "window": {"start_date": "2026-04-21", "end_date": "2026-04-28"},
  "hours": [
    {"hour": 8, "booking_count": 5},
    {"hour": 9, "booking_count": 12}
  ]
}
```

---

## Files

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `app/schemas/stats.py` | Pydantic 请求/响应模型 |
| Create | `app/services/stats_service.py` | 统计计算业务逻辑 |
| Create | `app/routers/stats.py` | HTTP 端点 + 参数校验 + 权限 |
| Create | `tests/test_resource_statistics.py` | 全部统计测试 |
| Modify | `app/main.py` | 注册 stats router |
| Create | `frontend/src/views/admin/ResourceStats.vue` | 前端统计页面 |
| Modify | `frontend/src/router/index.js` | 添加路由 |
| Modify | `frontend/src/layouts/MainLayout.vue` | 添加导航项 |

---

## Implementation Tasks

### Task 1: Stats Schemas

**Files:**
- Create: `app/schemas/stats.py`

- [ ] **Step 1: Write the schema file**

```python
"""Schemas for resource utilization statistics."""
import datetime

from pydantic import BaseModel


class StatsWindow(BaseModel):
    start_date: datetime.date
    end_date: datetime.date


class VenueUtilizationItem(BaseModel):
    venue_id: int
    venue_name: str
    booked_hours: float
    available_hours: float
    utilization_rate: float | None
    booking_count: int


class VenueUtilizationResponse(BaseModel):
    window: StatsWindow
    items: list[VenueUtilizationItem]


class EquipmentUsageItem(BaseModel):
    equipment_id: int
    equipment_name: str
    category: str | None
    booking_count: int
    total_hours: float


class EquipmentUsageResponse(BaseModel):
    window: StatsWindow
    items: list[EquipmentUsageItem]


class PeakHourItem(BaseModel):
    hour: int
    booking_count: int


class PeakHoursResponse(BaseModel):
    window: StatsWindow
    hours: list[PeakHourItem]
```

- [ ] **Step 2: Verify schema import**

Run: `cd backend && .venv/bin/python -c "from app.schemas.stats import VenueUtilizationResponse, EquipmentUsageResponse, PeakHoursResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/schemas/stats.py
git commit -m "feat(pr5): add utilization statistics Pydantic schemas"
```

---

### Task 2: Stats Service — Denominator Helper

**Files:**
- Create: `app/services/stats_service.py`

This task builds the denominator calculation (available hours) as an isolated helper, tested independently.

- [ ] **Step 1: Write the failing test for `_available_hours_in_window`**

In `tests/test_resource_statistics.py`:

```python
"""Tests for resource utilization statistics.

Covers: venue utilization, equipment usage, peak hours,
metric definitions, permissions, performance guardrails.
"""
import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.models.venue_availability import VenueAvailability
from app.models.venue_blackout import VenueBlackout
from app.services.stats_service import _available_hours_in_window, StatsService

from tests.helpers import (
    create_test_user,
    create_test_venue,
    create_test_equipment,
    create_test_booking,
    login_user,
)


async def _login(client, username: str) -> str:
    return await login_user(client, username)


# ===================================================================
# Helper: _available_hours_in_window
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_available_hours_no_availability_no_blackout(db_session):
    """No VenueAvailability rows → assume 24h/day."""
    venue = await create_test_venue(db_session, name="V1")
    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),  # Monday
        end_date=datetime.date(2026, 4, 26),     # Sunday
        availability_slots=[],
        blackout_dates=[],
    )
    # 7 days × 24h = 168
    assert hours == 168.0


@pytest.mark.asyncio(loop_scope="session")
async def test_available_hours_with_blackout(db_session):
    """Blackout dates deduct available hours."""
    venue = await create_test_venue(db_session, name="V2")
    # Blackout Wed-Fri (3 days)
    bo = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 22),
        end_date=datetime.date(2026, 4, 24),
    )
    db_session.add(bo)
    await db_session.flush()

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
        availability_slots=[],
        blackout_dates=[bo],
    )
    # 7 days - 3 blackout = 4 days × 24h = 96
    assert hours == 96.0


@pytest.mark.asyncio(loop_scope="session")
async def test_available_hours_with_availability_slots(db_session):
    """VenueAvailability defines operating hours per day_of_week."""
    venue = await create_test_venue(db_session, name="V3")
    # Mon-Fri 8:00-18:00 = 10h/day
    for dow in range(5):
        slot = VenueAvailability(
            venue_id=venue.id,
            day_of_week=dow,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(18, 0),
        )
        db_session.add(slot)
    await db_session.flush()
    slots = list((await db_session.execute(
        __import__("sqlalchemy").select(VenueAvailability).where(
            VenueAvailability.venue_id == venue.id
        )
    )).scalars().all())

    # April 20-26, 2026: Mon-Fri (5 weekdays) × 10h = 50h
    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
        availability_slots=slots,
        blackout_dates=[],
    )
    assert hours == 50.0


@pytest.mark.asyncio(loop_scope="session")
async def test_available_hours_all_blacked_out(db_session):
    """Entire window blacked out → 0 available hours."""
    venue = await create_test_venue(db_session, name="V4")
    bo = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    db_session.add(bo)
    await db_session.flush()

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
        availability_slots=[],
        blackout_dates=[bo],
    )
    assert hours == 0.0


@pytest.mark.asyncio(loop_scope="session")
async def test_available_hours_blackout_partial_overlap(db_session):
    """Blackout partially overlaps window — only overlapping days deducted."""
    venue = await create_test_venue(db_session, name="V5")
    # Blackout April 25-28 (Sat-Mon), window is April 20-26 (Mon-Sun)
    bo = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 25),
        end_date=datetime.date(2026, 4, 28),
    )
    db_session.add(bo)
    await db_session.flush()

    hours = _available_hours_in_window(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
        availability_slots=[],
        blackout_dates=[bo],
    )
    # 7 days - 2 overlapping (25, 26) = 5 × 24 = 120
    assert hours == 120.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py::test_available_hours_no_availability_no_blackout -v`
Expected: FAIL — `ImportError: cannot import name '_available_hours_in_window' from 'app.services.stats_service'`

- [ ] **Step 3: Implement `_available_hours_in_window`**

Create `app/services/stats_service.py`:

```python
"""Resource utilization statistics service.

Metric definitions:
  - Venue utilization: booked_hours / available_hours (approved only, clipped to window)
  - Equipment usage: booking_count + total_hours (approved only)
  - Peak hours: booking count grouped by HOUR(start_time) (approved only)

Denominator (available hours):
  - If venue has VenueAvailability slots: sum per day_of_week
  - If no slots: 24h/day default
  - Blackout dates fully deducted per-day
  - Non-active venues excluded from results
"""
import datetime
from typing import Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.models.venue_availability import VenueAvailability
from app.models.venue_blackout import VenueBlackout

_MAX_WINDOW_DAYS = 90
_DEFAULT_LIMIT = 100


def _available_hours_in_window(
    *,
    venue_id: int,
    start_date: datetime.date,
    end_date: datetime.date,
    availability_slots: list,
    blackout_dates: list,
) -> float:
    """Calculate total available hours for a venue in [start_date, end_date].

    - availability_slots: list of VenueAvailability rows for this venue
    - blackout_dates: list of VenueBlackout rows for this venue
    - Returns 0.0 if all days are blacked out
    """
    # Build blackout date set
    blackout_set: set[datetime.date] = set()
    for bo in blackout_dates:
        current = max(bo.start_date, start_date)
        bo_end = min(bo.end_date, end_date)
        while current <= bo_end:
            blackout_set.add(current)
            current += datetime.timedelta(days=1)

    # Build daily hours lookup: day_of_week -> hours
    if availability_slots:
        daily_hours: dict[int, float] = {}
        for slot in availability_slots:
            delta = datetime.datetime.combine(
                datetime.date.min, slot.end_time
            ) - datetime.datetime.combine(datetime.date.min, slot.start_time)
            h = delta.seconds / 3600.0
            daily_hours[slot.day_of_week] = daily_hours.get(slot.day_of_week, 0.0) + h
    else:
        daily_hours = {dow: 24.0 for dow in range(7)}

    total = 0.0
    current = start_date
    while current <= end_date:
        if current not in blackout_set:
            total += daily_hours.get(current.weekday(), 0.0)
        current += datetime.timedelta(days=1)

    return total
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/stats_service.py tests/test_resource_statistics.py
git commit -m "feat(pr5): add available hours denominator calculation with tests"
```

---

### Task 3: Stats Service — Venue Utilization

**Files:**
- Modify: `app/services/stats_service.py`
- Modify: `tests/test_resource_statistics.py`

- [ ] **Step 1: Write failing tests for venue utilization**

Append to `tests/test_resource_statistics.py`:

```python
# ===================================================================
# Venue Utilization
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_utilization_basic(db_session):
    """Basic utilization: 2 bookings in window, no availability constraints."""
    admin = await create_test_user(db_session, username="stat_adm", role="admin")

    venue = await create_test_venue(db_session, name="Stat Venue")
    # 2 bookings: each 2 hours on same day
    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base + datetime.timedelta(hours=4),
        end_time=base + datetime.timedelta(hours=6),
    )

    svc = StatsService(db_session)
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    assert len(result) == 1
    item = result[0]
    assert item["venue_id"] == venue.id
    assert item["booked_hours"] == 4.0  # 2 + 2
    assert item["available_hours"] == 24.0  # 1 day × 24h (no availability)
    assert abs(item["utilization_rate"] - 4.0 / 24.0) < 0.001
    assert item["booking_count"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_utilization_excludes_cancelled(db_session):
    """Cancelled bookings do not count toward booked_hours."""
    admin = await create_test_user(db_session, username="stat_cxl", role="admin")

    venue = await create_test_venue(db_session, name="CXL Venue")
    base = datetime.datetime(2026, 4, 22, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
        status="approved",
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base + datetime.timedelta(hours=4),
        end_time=base + datetime.timedelta(hours=6),
        status="cancelled",
    )

    svc = StatsService(db_session)
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 22),
        end_date=datetime.date(2026, 4, 22),
    )
    assert len(result) == 1
    assert result[0]["booked_hours"] == 2.0
    assert result[0]["booking_count"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_utilization_excludes_maintenance(db_session):
    """Venues with status != 'active' are excluded from results."""
    await create_test_venue(db_session, name="Active Venue", status="active")
    await create_test_venue(db_session, name="Maint Venue", status="maintenance")
    await create_test_venue(db_session, name="Inactive Venue", status="inactive")

    svc = StatsService(db_session)
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    venue_names = [r["venue_name"] for r in result]
    assert "Active Venue" in venue_names
    assert "Maint Venue" not in venue_names
    assert "Inactive Venue" not in venue_names


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_utilization_zero_available_hours(db_session):
    """All days blacked out → rate = None, available_hours = 0."""
    admin = await create_test_user(db_session, username="stat_zh", role="admin")
    venue = await create_test_venue(db_session, name="Zero Venue")

    bo = VenueBlackout(
        venue_id=venue.id,
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    db_session.add(bo)
    await db_session.flush()

    svc = StatsService(db_session)
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["available_hours"] == 0.0
    assert item["utilization_rate"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_utilization_clips_to_window(db_session):
    """Booking extending beyond window is clipped to window boundaries."""
    admin = await create_test_user(db_session, username="stat_clip", role="admin")
    venue = await create_test_venue(db_session, name="Clip Venue")

    # Booking spans April 20 22:00 to April 22 10:00 (36h total)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=datetime.datetime(2026, 4, 20, 22, 0),
        end_time=datetime.datetime(2026, 4, 22, 10, 0),
    )

    svc = StatsService(db_session)
    # Window: April 21 only → clip to 24h
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["venue_id"] == venue.id)
    assert item["booked_hours"] == 24.0  # Full day clipped


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_utilization_no_bookings(db_session):
    """Venue with no bookings → booked_hours=0, rate=0."""
    await create_test_venue(db_session, name="Empty Venue")

    svc = StatsService(db_session)
    result = await svc.venue_utilization(
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    item = next(r for r in result if r["venue_name"] == "Empty Venue")
    assert item["booked_hours"] == 0.0
    assert item["utilization_rate"] == 0.0
    assert item["booking_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py::test_venue_utilization_basic -v`
Expected: FAIL — `AttributeError: 'StatsService' object has no attribute 'venue_utilization'`

- [ ] **Step 3: Implement `venue_utilization` method**

Append to `StatsService` class in `app/services/stats_service.py`:

```python
class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def venue_utilization(
        self,
        *,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict]:
        """Calculate per-venue utilization for [start_date, end_date]."""
        limit = min(limit, _DEFAULT_LIMIT)
        window_start = datetime.datetime.combine(start_date, datetime.time.min)
        window_end = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # Active venues only
        venues_result = await self.db.execute(
            select(Venue).where(Venue.status == "active").limit(limit)
        )
        venues = list(venues_result.scalars().all())
        if not venues:
            return []

        venue_ids = [v.id for v in venues]
        venue_map = {v.id: v for v in venues}

        # Numerator: approved bookings clipped to window
        # Use raw SQL for TIMESTAMPDIFF — MySQL-specific but SQLAlchemy doesn't
        # bind the unit keyword correctly via func.timestampdiff()
        seconds_expr = func.sum(
            text(
                "TIMESTAMPDIFF(SECOND, "
                "GREATEST(bookings.start_time, :_ws), "
                "LEAST(bookings.end_time, :_we))"
            )
        ).label("total_seconds")
        booked_stmt = (
            select(
                Booking.venue_id,
                seconds_expr,
                func.count(Booking.id).label("booking_count"),
            )
            .where(
                Booking.venue_id.in_(venue_ids),
                Booking.status == "approved",
                Booking.start_time < window_end,
                Booking.end_time > window_start,
            )
            .group_by(Booking.venue_id)
        )
        booked_stmt = booked_stmt.params(_ws=window_start, _we=window_end)
        booked_result = await self.db.execute(booked_stmt)
        booked_data = {
            row.venue_id: {
                "booked_hours": round(row.total_seconds / 3600.0, 2) if row.total_seconds else 0.0,
                "booking_count": row.booking_count,
            }
            for row in booked_result.all()
        }

        # Denominator: batch fetch availability + blackout for all venues
        avail_result = await self.db.execute(
            select(VenueAvailability).where(
                VenueAvailability.venue_id.in_(venue_ids)
            )
        )
        all_slots = list(avail_result.scalars().all())

        blackout_result = await self.db.execute(
            select(VenueBlackout).where(
                VenueBlackout.venue_id.in_(venue_ids),
                VenueBlackout.start_date <= end_date,
                VenueBlackout.end_date >= start_date,
            )
        )
        all_blackouts = list(blackout_result.scalars().all())

        # Group by venue
        slots_by_venue: dict[int, list] = {}
        for s in all_slots:
            slots_by_venue.setdefault(s.venue_id, []).append(s)

        bo_by_venue: dict[int, list] = {}
        for b in all_blackouts:
            bo_by_venue.setdefault(b.venue_id, []).append(b)

        results = []
        for v in venues:
            booked = booked_data.get(v.id, {"booked_hours": 0.0, "booking_count": 0})
            avail_hours = _available_hours_in_window(
                venue_id=v.id,
                start_date=start_date,
                end_date=end_date,
                availability_slots=slots_by_venue.get(v.id, []),
                blackout_dates=bo_by_venue.get(v.id, []),
            )
            rate = (
                round(booked["booked_hours"] / avail_hours, 4)
                if avail_hours > 0
                else None
            )
            results.append({
                "venue_id": v.id,
                "venue_name": v.name,
                "booked_hours": booked["booked_hours"],
                "available_hours": round(avail_hours, 2),
                "utilization_rate": rate,
                "booking_count": booked["booking_count"],
            })
        return results
```

Also add the import for `StatsService` at the bottom of the test file's imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py -k venue_utilization -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/stats_service.py tests/test_resource_statistics.py
git commit -m "feat(pr5): add venue utilization calculation with tests"
```

---

### Task 4: Stats Service — Equipment Usage

**Files:**
- Modify: `app/services/stats_service.py`
- Modify: `tests/test_resource_statistics.py`

- [ ] **Step 1: Write failing tests for equipment usage**

Append to `tests/test_resource_statistics.py`:

```python
# ===================================================================
# Equipment Usage
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_usage_basic(db_session):
    """Equipment used in 2 approved bookings → count=2, hours summed."""
    admin = await create_test_user(db_session, username="eq_adm", role="admin")
    venue = await create_test_venue(db_session, name="Eq Venue")
    equip = await create_test_equipment(db_session, name="Projector", category="AV")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
        equipment_ids=[equip.id],
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base + datetime.timedelta(hours=4),
        end_time=base + datetime.timedelta(hours=6),
        equipment_ids=[equip.id],
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["equipment_id"] == equip.id)
    assert item["booking_count"] == 2
    assert item["total_hours"] == 4.0


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_usage_excludes_cancelled(db_session):
    """Cancelled booking does not count for equipment."""
    admin = await create_test_user(db_session, username="eq_cxl", role="admin")
    venue = await create_test_venue(db_session, name="EqCXL Venue")
    equip = await create_test_equipment(db_session, name="Camera")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base, end_time=base + datetime.timedelta(hours=2),
        equipment_ids=[equip.id], status="approved",
    )
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base + datetime.timedelta(hours=3),
        end_time=base + datetime.timedelta(hours=5),
        equipment_ids=[equip.id], status="cancelled",
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item = next(r for r in result if r["equipment_id"] == equip.id)
    assert item["booking_count"] == 1
    assert item["total_hours"] == 2.0


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_usage_no_bookings(db_session):
    """Equipment with no bookings → count=0, hours=0."""
    await create_test_equipment(db_session, name="Unused Device")

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    item = next(r for r in result if r["equipment_name"] == "Unused Device")
    assert item["booking_count"] == 0
    assert item["total_hours"] == 0.0


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_usage_multi_equipment_booking(db_session):
    """One booking with 2 equipments → each equipment gets count=1."""
    admin = await create_test_user(db_session, username="eq_multi", role="admin")
    venue = await create_test_venue(db_session, name="MultiEq Venue")
    e1 = await create_test_equipment(db_session, name="DevA")
    e2 = await create_test_equipment(db_session, name="DevB")

    base = datetime.datetime(2026, 4, 21, 9, 0)
    await create_test_booking(
        db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=base, end_time=base + datetime.timedelta(hours=3),
        equipment_ids=[e1.id, e2.id],
    )

    svc = StatsService(db_session)
    result = await svc.equipment_usage(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    item_a = next(r for r in result if r["equipment_id"] == e1.id)
    item_b = next(r for r in result if r["equipment_id"] == e2.id)
    assert item_a["booking_count"] == 1
    assert item_b["booking_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py::test_equipment_usage_basic -v`
Expected: FAIL — `AttributeError: 'StatsService' object has no attribute 'equipment_usage'`

- [ ] **Step 3: Implement `equipment_usage` method**

Append to `StatsService` class:

```python
    async def equipment_usage(
        self,
        *,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[dict]:
        """Calculate per-equipment usage for [start_date, end_date]."""
        limit = min(limit, _DEFAULT_LIMIT)
        window_start = datetime.datetime.combine(start_date, datetime.time.min)
        window_end = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # All equipment (active, inactive, maintenance — all included)
        equip_result = await self.db.execute(
            select(Equipment).limit(limit)
        )
        equipments = list(equip_result.scalars().all())
        if not equipments:
            return []

        equip_ids = [e.id for e in equipments]
        equip_map = {e.id: e for e in equipments}

        # Usage from approved bookings
        seconds_expr = func.sum(
            text(
                "TIMESTAMPDIFF(SECOND, "
                "GREATEST(bookings.start_time, :_ws), "
                "LEAST(bookings.end_time, :_we))"
            )
        ).label("total_seconds")
        usage_stmt = (
            select(
                BookingEquipment.equipment_id,
                func.count(func.distinct(Booking.id)).label("booking_count"),
                seconds_expr,
            )
            .join(Booking, Booking.id == BookingEquipment.booking_id)
            .where(
                BookingEquipment.equipment_id.in_(equip_ids),
                Booking.status == "approved",
                Booking.start_time < window_end,
                Booking.end_time > window_start,
            )
            .group_by(BookingEquipment.equipment_id)
        )
        usage_stmt = usage_stmt.params(_ws=window_start, _we=window_end)
        usage_result = await self.db.execute(usage_stmt)
        usage_data = {
            row.equipment_id: {
                "booking_count": row.booking_count,
                "total_hours": round(row.total_seconds / 3600.0, 2) if row.total_seconds else 0.0,
            }
            for row in usage_result.all()
        }

        results = []
        for e in equipments:
            usage = usage_data.get(e.id, {"booking_count": 0, "total_hours": 0.0})
            results.append({
                "equipment_id": e.id,
                "equipment_name": e.name,
                "category": e.category,
                "booking_count": usage["booking_count"],
                "total_hours": usage["total_hours"],
            })
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py -k equipment_usage -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/stats_service.py tests/test_resource_statistics.py
git commit -m "feat(pr5): add equipment usage statistics with tests"
```

---

### Task 5: Stats Service — Peak Hours

**Files:**
- Modify: `app/services/stats_service.py`
- Modify: `tests/test_resource_statistics.py`

- [ ] **Step 1: Write failing tests for peak hours**

Append to `tests/test_resource_statistics.py`:

```python
# ===================================================================
# Peak Hours
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_basic(db_session):
    """Bookings distributed across hours → correct counts."""
    admin = await create_test_user(db_session, username="pk_adm", role="admin")
    venue = await create_test_venue(db_session, name="Peak Venue")

    # 3 bookings starting at hour 9, 2 at hour 14
    base = datetime.datetime(2026, 4, 21, 9, 0)
    for _ in range(3):
        await create_test_booking(
            db_session, venue_id=venue.id, booked_by=admin.id,
            start_time=base, end_time=base + datetime.timedelta(hours=1),
        )
        base = base + datetime.timedelta(hours=1)  # next booking starts next hour

    # Actually let's use fixed times for clarity
    day = datetime.datetime(2026, 4, 21)
    await create_test_booking(db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=day.replace(hour=14), end_time=day.replace(hour=16))
    await create_test_booking(db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=day.replace(hour=14, minute=30), end_time=day.replace(hour=15, minute=30))

    svc = StatsService(db_session)
    result = await svc.peak_hours(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    # Find hours with bookings
    hour_map = {h["hour"]: h["booking_count"] for h in result}
    assert hour_map.get(9, 0) == 1   # first booking at 9
    assert hour_map.get(14, 0) == 2  # two bookings at 14
    # Hours with no bookings should not appear (or have count 0)
    assert hour_map.get(3, 0) == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_excludes_cancelled(db_session):
    """Cancelled bookings not counted in peak hours."""
    admin = await create_test_user(db_session, username="pk_cxl", role="admin")
    venue = await create_test_venue(db_session, name="PeakCXL Venue")

    day = datetime.datetime(2026, 4, 21)
    await create_test_booking(db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=day.replace(hour=10), end_time=day.replace(hour=12),
        status="approved")
    await create_test_booking(db_session, venue_id=venue.id, booked_by=admin.id,
        start_time=day.replace(hour=14), end_time=day.replace(hour=16),
        status="cancelled")

    svc = StatsService(db_session)
    result = await svc.peak_hours(
        start_date=datetime.date(2026, 4, 21),
        end_date=datetime.date(2026, 4, 21),
    )
    hour_map = {h["hour"]: h["booking_count"] for h in result}
    assert hour_map.get(10, 0) == 1
    assert 14 not in hour_map


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_no_bookings(db_session):
    """No bookings → empty list."""
    svc = StatsService(db_session)
    result = await svc.peak_hours(
        start_date=datetime.date(2026, 4, 20),
        end_date=datetime.date(2026, 4, 26),
    )
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py::test_peak_hours_basic -v`
Expected: FAIL

- [ ] **Step 3: Implement `peak_hours` method**

Append to `StatsService` class:

```python
    async def peak_hours(
        self,
        *,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
        """Count approved bookings grouped by HOUR(start_time)."""
        window_start = datetime.datetime.combine(start_date, datetime.time.min)
        window_end = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        result = await self.db.execute(
            select(
                func.extract("hour", Booking.start_time).label("hour"),
                func.count(Booking.id).label("booking_count"),
            )
            .where(
                Booking.status == "approved",
                Booking.start_time >= window_start,
                Booking.start_time < window_end,
            )
            .group_by(text("hour"))
            .order_by(text("hour"))
        )

        return [
            {"hour": int(row.hour), "booking_count": row.booking_count}
            for row in result.all()
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py -k peak_hours -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/stats_service.py tests/test_resource_statistics.py
git commit -m "feat(pr5): add peak hours statistics with tests"
```

---

### Task 6: Stats Router

**Files:**
- Create: `app/routers/stats.py`
- Modify: `app/main.py`

- [ ] **Step 1: Write failing tests for router endpoints**

Append to `tests/test_resource_statistics.py`:

```python
# ===================================================================
# Router: Permissions & Validation
# ===================================================================


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_stats_admin_ok(client, db_session):
    """Admin can access venue utilization."""
    admin = await create_test_user(db_session, username="stat_r_adm", role="admin")
    token = await _login(client, "stat_r_adm")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "window" in data
    assert "items" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_stats_fm_ok(client, db_session):
    """Facility manager can access venue utilization."""
    fm = await create_test_user(db_session, username="stat_r_fm", role="facility_manager")
    token = await _login(client, "stat_r_fm")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_stats_teacher_forbidden(client, db_session):
    """Teacher cannot access stats."""
    teacher = await create_test_user(db_session, username="stat_r_tc", role="teacher")
    token = await _login(client, "stat_r_tc")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_venue_stats_student_forbidden(client, db_session):
    """Student cannot access stats."""
    student = await create_test_user(db_session, username="stat_r_st", role="student")
    token = await _login(client, "stat_r_st")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_stats_rejects_window_over_90_days(client, db_session):
    """Query window > 90 days → 400."""
    admin = await create_test_user(db_session, username="stat_r_w", role="admin")
    token = await _login(client, "stat_r_w")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        params={"start_date": "2026-01-01", "end_date": "2026-04-30"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_stats_default_window(client, db_session):
    """No dates provided → defaults to last 7 days."""
    admin = await create_test_user(db_session, username="stat_r_d", role="admin")
    token = await _login(client, "stat_r_d")
    resp = await client.get(
        "/api/v1/stats/venue-utilization",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["window"]["start_date"] is not None
    assert data["window"]["end_date"] is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_equipment_usage_endpoint(client, db_session):
    """Equipment usage endpoint returns correct shape."""
    admin = await create_test_user(db_session, username="stat_r_eq", role="admin")
    token = await _login(client, "stat_r_eq")
    resp = await client.get(
        "/api/v1/stats/equipment-usage",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_peak_hours_endpoint(client, db_session):
    """Peak hours endpoint returns correct shape."""
    admin = await create_test_user(db_session, username="stat_r_pk", role="admin")
    token = await _login(client, "stat_r_pk")
    resp = await client.get(
        "/api/v1/stats/peak-hours",
        params={"start_date": "2026-04-20", "end_date": "2026-04-26"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "hours" in resp.json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py::test_venue_stats_admin_ok -v`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Create the router**

Create `app/routers/stats.py`:

```python
"""Resource utilization statistics endpoints."""
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import _utcnow_naive, get_db
from app.dependencies.auth import require_role
from app.schemas.stats import (
    VenueUtilizationResponse,
    EquipmentUsageResponse,
    PeakHoursResponse,
    StatsWindow,
    VenueUtilizationItem,
    EquipmentUsageItem,
    PeakHourItem,
)
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api/v1/stats", tags=["statistics"])

_MAX_WINDOW_DAYS = 90


def _validate_window(start_date: datetime.date, end_date: datetime.date) -> None:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date 不能晚于 end_date")
    if (end_date - start_date).days > _MAX_WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"查询窗口不能超过 {_MAX_WINDOW_DAYS} 天",
        )


@router.get("/venue-utilization", response_model=VenueUtilizationResponse)
async def venue_utilization(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    limit: int = Query(100, ge=1, le=100),
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    if end_date is None:
        end_date = _utcnow_naive().date()
    if start_date is None:
        start_date = end_date - datetime.timedelta(days=6)
    _validate_window(start_date, end_date)

    svc = StatsService(db)
    items = await svc.venue_utilization(
        start_date=start_date, end_date=end_date, limit=limit,
    )
    return VenueUtilizationResponse(
        window=StatsWindow(start_date=start_date, end_date=end_date),
        items=[VenueUtilizationItem(**item) for item in items],
    )


@router.get("/equipment-usage", response_model=EquipmentUsageResponse)
async def equipment_usage(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    limit: int = Query(100, ge=1, le=100),
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    if end_date is None:
        end_date = _utcnow_naive().date()
    if start_date is None:
        start_date = end_date - datetime.timedelta(days=6)
    _validate_window(start_date, end_date)

    svc = StatsService(db)
    items = await svc.equipment_usage(
        start_date=start_date, end_date=end_date, limit=limit,
    )
    return EquipmentUsageResponse(
        window=StatsWindow(start_date=start_date, end_date=end_date),
        items=[EquipmentUsageItem(**item) for item in items],
    )


@router.get("/peak-hours", response_model=PeakHoursResponse)
async def peak_hours(
    start_date: datetime.date | None = Query(None),
    end_date: datetime.date | None = Query(None),
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    if end_date is None:
        end_date = _utcnow_naive().date()
    if start_date is None:
        start_date = end_date - datetime.timedelta(days=6)
    _validate_window(start_date, end_date)

    svc = StatsService(db)
    hours = await svc.peak_hours(start_date=start_date, end_date=end_date)
    return PeakHoursResponse(
        window=StatsWindow(start_date=start_date, end_date=end_date),
        hours=[PeakHourItem(**h) for h in hours],
    )
```

- [ ] **Step 4: Register router in `app/main.py`**

Add to `app/main.py` (after existing router imports):

```python
from app.routers import stats as stats_router
app.include_router(stats_router.router)
```

- [ ] **Step 5: Fix the test typo and run all stats tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py -v`
Expected: all passed

- [ ] **Step 6: Run full test suite for regression**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v --tb=short`
Expected: all passed (523+)

- [ ] **Step 7: Commit**

```bash
git add app/routers/stats.py app/main.py tests/test_resource_statistics.py
git commit -m "feat(pr5): add utilization statistics router with permissions and validation"
```

---

### Task 7: Frontend Stats Page

**Files:**
- Create: `frontend/src/views/admin/ResourceStats.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Create the ResourceStats.vue component**

The page has 3 tabs (Element Plus `el-tabs`): Venue Utilization, Equipment Usage, Peak Hours. Each tab shows an `el-table` with data fetched from the stats API. Venue utilization tab also shows a simple bar chart.

Create `frontend/src/views/admin/ResourceStats.vue`:

```vue
<template>
  <div v-loading="loading">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>资源利用率统计</span>
          <div>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              :clearable="false"
              style="margin-right: 12px"
            />
            <el-button type="primary" @click="fetchData">查询</el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="fetchData">
        <el-tab-pane label="场地利用率" name="venue">
          <el-table :data="venueItems" stripe style="width: 100%">
            <el-table-column prop="venue_name" label="场地" />
            <el-table-column prop="booked_hours" label="预约时长(h)" width="120" />
            <el-table-column prop="available_hours" label="可用时长(h)" width="120" />
            <el-table-column label="利用率" width="160">
              <template #default="{ row }">
                <template v-if="row.utilization_rate !== null">
                  <el-progress
                    :percentage="Math.round(row.utilization_rate * 100)"
                    :stroke-width="16"
                    :text-inside="true"
                  />
                </template>
                <template v-else>
                  <el-tag type="info">无可用时长</el-tag>
                </template>
              </template>
            </el-table-column>
            <el-table-column prop="booking_count" label="预约数" width="100" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="设备使用频次" name="equipment">
          <el-table :data="equipmentItems" stripe style="width: 100%">
            <el-table-column prop="equipment_name" label="设备" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column prop="booking_count" label="预约次数" width="120" sortable />
            <el-table-column prop="total_hours" label="使用时长(h)" width="120" sortable />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="高峰时段" name="peak">
          <div ref="chartRef" style="height: 400px" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const loading = ref(false)
const activeTab = ref('venue')
const dateRange = ref([])
const venueItems = ref([])
const equipmentItems = ref([])
const chartRef = ref(null)
let chartInstance = null

function defaultRange() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 6)
  const fmt = (d) => d.toISOString().slice(0, 10)
  return [fmt(start), fmt(end)]
}

onMounted(async () => {
  dateRange.value = defaultRange()
  await fetchData()
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

async function fetchData() {
  if (!dateRange.value || dateRange.value.length !== 2) return
  loading.value = true
  try {
    const params = {
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
    }
    if (activeTab.value === 'venue') {
      const resp = await api.get('/v1/stats/venue-utilization', { params })
      venueItems.value = resp.data.items
    } else if (activeTab.value === 'equipment') {
      const resp = await api.get('/v1/stats/equipment-usage', { params })
      equipmentItems.value = resp.data.items
    } else {
      const resp = await api.get('/v1/stats/peak-hours', { params })
      await nextTick()
      renderChart(resp.data.hours)
    }
  } catch {
    ElMessage.error('加载统计数据失败')
  } finally {
    loading.value = false
  }
}

function renderChart(hours) {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = window.echarts.init(chartRef.value)

  const allHours = Array.from({ length: 24 }, (_, i) => i)
  const countMap = Object.fromEntries(hours.map((h) => [h.hour, h.booking_count]))

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: allHours.map((h) => `${h}:00`) },
    yAxis: { type: 'value', name: '预约数' },
    series: [{
      type: 'bar',
      data: allHours.map((h) => countMap[h] || 0),
      itemStyle: { color: '#409EFF' },
    }],
  })
  window.addEventListener('resize', () => chartInstance?.resize())
}
</script>
```

- [ ] **Step 2: Add route to `frontend/src/router/index.js`**

Add to the admin routes children array:

```javascript
{
  path: 'resource-stats',
  name: 'ResourceStats',
  component: () => import('../views/admin/ResourceStats.vue'),
  meta: { roles: ['admin', 'facility_manager'] },
},
```

- [ ] **Step 3: Add nav item to `frontend/src/layouts/MainLayout.vue`**

In the sidebar menu, add after the existing admin menu items (inside the admin/fm role check):

```html
<el-menu-item index="/resource-stats" v-if="['admin', 'facility_manager'].includes(auth.userRole)">
  <span>资源统计</span>
</el-menu-item>
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/admin/ResourceStats.vue frontend/src/router/index.js frontend/src/layouts/MainLayout.vue
git commit -m "feat(pr5): add resource statistics frontend page with venue/equipment/peak tabs"
```

---

### Task 8: Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All passed (523+)

- [ ] **Step 2: Verify test count for stats module**

Run: `cd backend && .venv/bin/python -m pytest tests/test_resource_statistics.py -v`
Expected: ~22 tests (5 denominator + 6 venue + 4 equipment + 3 peak + 8 router)

- [ ] **Step 3: Check API accessibility**

Run: `cd backend && .venv/bin/python -c "
from app.main import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
stats = [r for r in routes if '/stats/' in r]
print('Stats routes:', stats)
"`
Expected: 3 stats routes listed

- [ ] **Step 4: Run regression on existing endpoints**

Run: `cd backend && .venv/bin/python -m pytest tests/test_venues.py tests/test_equipment.py tests/test_bookings.py -v --tb=short`
Expected: All passed

- [ ] **Step 5: Commit (if any fixes were needed)**

---

## Query Strategy & Performance Guardrails

### Index Utilization

| Query | Used Index |
|-------|-----------|
| Venue numerator | `ix_bookings_venue_time` on `(venue_id, start_time, end_time)` |
| Equipment numerator | `ix_booking_equipment_equip` on `(equipment_id, booking_id)` + PK on bookings |
| Peak hours | Full scan on bookings filtered by status + time range (acceptable for ≤90 days) |

### Guardrails

| Rule | Value | Enforcement |
|------|-------|-------------|
| Max window | 90 days | Router validates before calling service |
| Default window | 7 days | Router default |
| Max resources | 100 | LIMIT in SQL + router param max |
| No materialized views | — | Real-time aggregation queries only |

### Denominator Performance

- Availability slots: at most 7 rows per venue (1 per day_of_week), loaded in one batch query
- Blackout dates: filtered to window, loaded in one batch query
- Day-by-day iteration: O(days × venues), acceptable for ≤90 days × ≤100 venues

---

## Risks & Edge Cases

| Risk | Mitigation |
|------|------------|
| `TIMESTAMPDIFF` MySQL-specific | Accepted — project already targets MySQL 8. Alternative: Python-side calculation for portability |
| No status history for venues | V1 uses current status only. Historical status changes not tracked — venues currently in maintenance are excluded, even if they were active during the window |
| `day_of_week` convention mismatch | Assumed `VenueAvailability.day_of_week` matches Python's `weekday()` (0=Mon). Must verify during implementation |
| Very large number of venues/equipment | LIMIT 100 per request. Client can paginate if needed (future) |
| No data → empty results | Returns `{items: [], hours: []}` — client handles gracefully |
| Window spanning future dates | Accepted — future approved bookings count toward utilization |
| VenueAvailability has overlapping slots | Possible but UNIQUE constraint `(venue_id, day_of_week, start_time, end_time)` prevents exact duplicates. Overlapping different times are not prevented but would over-count available hours. Accepted for V1 |

---

## Definition of Done / Merge Bar

- [ ] 3 API endpoints return correct metric values
- [ ] All metric definitions match spec (cancelled excluded, clipped to window, maintenance excluded)
- [ ] Permissions enforced (admin + fm only, teacher/student 403)
- [ ] Window validation (max 90 days, start ≤ end)
- [ ] Default window (7 days) works
- [ ] Zero available hours returns `rate = null` (not division by zero)
- [ ] ≥20 tests covering service logic, router permissions, edge cases
- [ ] No regression in existing 523+ tests
- [ ] Frontend page renders 3 tabs with data
- [ ] No N+1 queries (batch fetch for denominator)
