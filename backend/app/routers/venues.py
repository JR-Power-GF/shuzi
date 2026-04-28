import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.venue import Venue
from app.models.venue_availability import VenueAvailability
from app.models.venue_blackout import VenueBlackout
from app.schemas.venue import (
    VenueCreate,
    VenueUpdate,
    VenueResponse,
    VenueListResponse,
    AvailabilitySlotsUpdate,
    BlackoutCreate,
    BlackoutResponse,
)
from app.services.audit import audit_log

router = APIRouter(prefix="/api/v1/venues", tags=["venues"])


def _venue_to_response(venue: Venue, availability: list[dict] | None = None) -> dict:
    """Convert a Venue ORM object to a response dict."""
    avail = availability if availability is not None else []
    return {
        "id": venue.id,
        "name": venue.name,
        "capacity": venue.capacity,
        "location": venue.location,
        "description": venue.description,
        "status": venue.status,
        "external_id": venue.external_id,
        "availability": avail,
        "created_at": venue.created_at,
        "updated_at": venue.updated_at,
    }


async def _get_availability(db: AsyncSession, venue_id: int) -> list[dict]:
    """Fetch availability slots for a venue as list of dicts."""
    result = await db.execute(
        select(VenueAvailability)
        .where(VenueAvailability.venue_id == venue_id)
        .order_by(VenueAvailability.day_of_week, VenueAvailability.start_time)
    )
    slots = result.scalars().all()
    return [
        {
            "id": s.id,
            "day_of_week": s.day_of_week,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
        }
        for s in slots
    ]


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(
    data: VenueCreate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    venue = Venue(
        name=data.name,
        capacity=data.capacity,
        location=data.location,
        description=data.description,
        external_id=data.external_id,
    )
    db.add(venue)
    await db.flush()

    await audit_log(
        db,
        entity_type="venue",
        entity_id=venue.id,
        action="create",
        actor_id=current_user["id"],
        changes={"name": data.name},
    )

    return _venue_to_response(venue)


@router.get("", response_model=VenueListResponse)
async def list_venues(
    status_filter: Optional[str] = Query(None, alias="status"),
    capacity_min: Optional[int] = Query(None),
    capacity_max: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Base query
    query = select(Venue)
    count_query = select(func.count()).select_from(Venue)

    # Teachers can only see active venues
    if current_user["role"] == "teacher":
        query = query.where(Venue.status == "active")
        count_query = count_query.where(Venue.status == "active")
    elif current_user["role"] not in ("admin", "facility_manager"):
        raise HTTPException(status_code=403, detail="权限不足")

    # Filters
    if status_filter:
        query = query.where(Venue.status == status_filter)
        count_query = count_query.where(Venue.status == status_filter)
    if capacity_min is not None:
        query = query.where(Venue.capacity >= capacity_min)
        count_query = count_query.where(Venue.capacity >= capacity_min)
    if capacity_max is not None:
        query = query.where(Venue.capacity <= capacity_max)
        count_query = count_query.where(Venue.capacity <= capacity_max)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Pagination
    query = query.order_by(Venue.id).limit(limit).offset(offset)
    result = await db.execute(query)
    venues = result.scalars().all()

    items = [_venue_to_response(v) for v in venues]
    return {"items": items, "total": total}


@router.get("/{venue_id}", response_model=VenueResponse)
async def get_venue(
    venue_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="场地不存在")

    # Teachers can only see active venues (404, not 403, to prevent probing)
    if current_user["role"] == "teacher" and venue.status != "active":
        raise HTTPException(status_code=404, detail="场地不存在")

    availability = await _get_availability(db, venue.id)
    return _venue_to_response(venue, availability)


@router.put("/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: int,
    data: VenueUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="场地不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(venue, field, value)
    await db.flush()

    await audit_log(
        db,
        entity_type="venue",
        entity_id=venue.id,
        action="update",
        actor_id=current_user["id"],
        changes=update_data,
    )

    availability = await _get_availability(db, venue.id)
    return _venue_to_response(venue, availability)


@router.patch("/{venue_id}/status", response_model=VenueResponse)
async def change_venue_status(
    venue_id: int,
    data: dict,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    new_status = data.get("status")
    if new_status not in ("active", "inactive", "maintenance"):
        raise HTTPException(
            status_code=422,
            detail="无效的状态值",
        )

    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="场地不存在")

    old_status = venue.status
    venue.status = new_status
    await db.flush()

    await audit_log(
        db,
        entity_type="venue",
        entity_id=venue.id,
        action="status_change",
        actor_id=current_user["id"],
        changes={"old_status": old_status, "new_status": new_status},
    )

    availability = await _get_availability(db, venue.id)
    return _venue_to_response(venue, availability)


# ---------------------------------------------------------------------------
# Availability Endpoints
# ---------------------------------------------------------------------------


@router.put("/{venue_id}/availability")
async def set_availability(
    venue_id: int,
    data: AvailabilitySlotsUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="场地不存在")

    # Delete existing availability slots
    await db.execute(
        delete(VenueAvailability).where(VenueAvailability.venue_id == venue_id)
    )

    # Create new slots
    for slot in data.slots:
        start = datetime.datetime.strptime(slot.start_time, "%H:%M").time()
        end = datetime.datetime.strptime(slot.end_time, "%H:%M").time()
        avail = VenueAvailability(
            venue_id=venue_id,
            day_of_week=slot.day_of_week,
            start_time=start,
            end_time=end,
        )
        db.add(avail)

    await db.flush()

    await audit_log(
        db,
        entity_type="venue",
        entity_id=venue.id,
        action="update_availability",
        actor_id=current_user["id"],
        changes={"slots_count": len(data.slots)},
    )

    availability = await _get_availability(db, venue_id)
    return _venue_to_response(venue, availability)


# ---------------------------------------------------------------------------
# Blackout Endpoints
# ---------------------------------------------------------------------------


@router.post("/{venue_id}/blackouts", status_code=status.HTTP_201_CREATED)
async def create_blackout(
    venue_id: int,
    data: BlackoutCreate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="场地不存在")

    start_date = datetime.date.fromisoformat(data.start_date)
    end_date = datetime.date.fromisoformat(data.end_date)

    blackout = VenueBlackout(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
        reason=data.reason,
    )
    db.add(blackout)
    await db.flush()

    return {
        "id": blackout.id,
        "venue_id": blackout.venue_id,
        "start_date": blackout.start_date.isoformat(),
        "end_date": blackout.end_date.isoformat(),
        "reason": blackout.reason,
    }


@router.get("/{venue_id}/blackouts")
async def list_blackouts(
    venue_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify venue exists
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="场地不存在")

    # Teachers can only see blackouts for active venues
    if current_user["role"] == "teacher" and venue.status != "active":
        raise HTTPException(status_code=404, detail="场地不存在")

    result = await db.execute(
        select(VenueBlackout)
        .where(VenueBlackout.venue_id == venue_id)
        .order_by(VenueBlackout.start_date)
    )
    blackouts = result.scalars().all()

    return [
        {
            "id": b.id,
            "venue_id": b.venue_id,
            "start_date": b.start_date.isoformat(),
            "end_date": b.end_date.isoformat(),
            "reason": b.reason,
        }
        for b in blackouts
    ]


@router.delete("/{venue_id}/blackouts/{blackout_id}")
async def delete_blackout(
    venue_id: int,
    blackout_id: int,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VenueBlackout).where(
            VenueBlackout.id == blackout_id,
            VenueBlackout.venue_id == venue_id,
        )
    )
    blackout = result.scalar_one_or_none()
    if not blackout:
        raise HTTPException(status_code=404, detail="黑名单记录不存在")

    await db.delete(blackout)
    await db.flush()

    return {"id": blackout_id, "deleted": True}
