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

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


def _resolve_window(
    start_date: datetime.date | None,
    end_date: datetime.date | None,
) -> tuple[datetime.date, datetime.date]:
    if end_date is None:
        end_date = _utcnow_naive().date()
    if start_date is None:
        start_date = end_date - datetime.timedelta(days=6)
    return start_date, end_date


def _validate_window(start_date: datetime.date, end_date: datetime.date) -> None:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")
    if (end_date - start_date).days > 90:
        raise HTTPException(
            status_code=400, detail="Date window must not exceed 90 days"
        )


@router.get("/venue-utilization", response_model=VenueUtilizationResponse)
async def get_venue_utilization(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_role(["admin", "facility_manager"])),
):
    start_date, end_date = _resolve_window(start_date, end_date)
    _validate_window(start_date, end_date)

    service = StatsService(db)
    items_data = await service.venue_utilization(start_date, end_date, limit)

    items = [VenueUtilizationItem(**row) for row in items_data]
    return VenueUtilizationResponse(
        window=StatsWindow(start_date=start_date, end_date=end_date),
        items=items,
    )


@router.get("/equipment-usage", response_model=EquipmentUsageResponse)
async def get_equipment_usage(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_role(["admin", "facility_manager"])),
):
    start_date, end_date = _resolve_window(start_date, end_date)
    _validate_window(start_date, end_date)

    service = StatsService(db)
    items_data = await service.equipment_usage(start_date, end_date, limit)

    items = [EquipmentUsageItem(**row) for row in items_data]
    return EquipmentUsageResponse(
        window=StatsWindow(start_date=start_date, end_date=end_date),
        items=items,
    )


@router.get("/peak-hours", response_model=PeakHoursResponse)
async def get_peak_hours(
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_role(["admin", "facility_manager"])),
):
    start_date, end_date = _resolve_window(start_date, end_date)
    _validate_window(start_date, end_date)

    service = StatsService(db)
    hours_data = await service.peak_hours(start_date, end_date)

    hours = [PeakHourItem(**row) for row in hours_data]
    return PeakHoursResponse(
        window=StatsWindow(start_date=start_date, end_date=end_date),
        hours=hours,
    )
