import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    VenueStatusUpdate,
    AvailabilitySlotsUpdate,
    BlackoutCreate,
    BlackoutResponse,
)
from app.services.audit import audit_log

router = APIRouter(prefix="/api/v1/venues", tags=["venues"])


def _venue_to_response(venue: Venue, availability: list[dict] | None = None) -> dict:
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


async def _get_venue_or_404(db: AsyncSession, venue_id: int) -> Venue:
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="场地不存在")
    return venue


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
    status_filter: str | None = Query(None, alias="status"),
    capacity_min: int | None = Query(None),
    capacity_max: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Venue)
    count_query = select(func.count()).select_from(Venue)

    if current_user["role"] == "teacher":
        query = query.where(Venue.status == "active")
        count_query = count_query.where(Venue.status == "active")
    elif current_user["role"] not in ("admin", "facility_manager"):
        raise HTTPException(status_code=403, detail="权限不足")

    if status_filter:
        query = query.where(Venue.status == status_filter)
        count_query = count_query.where(Venue.status == status_filter)
    if capacity_min is not None:
        query = query.where(Venue.capacity >= capacity_min)
        count_query = count_query.where(Venue.capacity >= capacity_min)
    if capacity_max is not None:
        query = query.where(Venue.capacity <= capacity_max)
        count_query = count_query.where(Venue.capacity <= capacity_max)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

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
    venue = await _get_venue_or_404(db, venue_id)

    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="权限不足")

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
    venue = await _get_venue_or_404(db, venue_id)

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
    data: VenueStatusUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    venue = await _get_venue_or_404(db, venue_id)

    old_status = venue.status
    venue.status = data.status
    await db.flush()

    await audit_log(
        db,
        entity_type="venue",
        entity_id=venue.id,
        action="status_change",
        actor_id=current_user["id"],
        changes={"old_status": old_status, "new_status": data.status},
    )

    availability = await _get_availability(db, venue.id)
    return _venue_to_response(venue, availability)


# ---------------------------------------------------------------------------
# Availability Endpoints
# ---------------------------------------------------------------------------


@router.put("/{venue_id}/availability", response_model=VenueResponse)
async def set_availability(
    venue_id: int,
    data: AvailabilitySlotsUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    venue = await _get_venue_or_404(db, venue_id)

    await db.execute(
        delete(VenueAvailability).where(VenueAvailability.venue_id == venue_id)
    )

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


@router.post(
    "/{venue_id}/blackouts",
    response_model=BlackoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_blackout(
    venue_id: int,
    data: BlackoutCreate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    await _get_venue_or_404(db, venue_id)

    blackout = VenueBlackout(
        venue_id=venue_id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
    )
    db.add(blackout)
    await db.flush()

    await audit_log(
        db,
        entity_type="venue",
        entity_id=venue_id,
        action="create_blackout",
        actor_id=current_user["id"],
        changes={
            "start_date": str(data.start_date),
            "end_date": str(data.end_date),
            "reason": data.reason,
        },
    )

    return {
        "id": blackout.id,
        "venue_id": blackout.venue_id,
        "start_date": blackout.start_date,
        "end_date": blackout.end_date,
        "reason": blackout.reason,
    }


@router.get("/{venue_id}/blackouts", response_model=list[BlackoutResponse])
async def list_blackouts(
    venue_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    venue = await _get_venue_or_404(db, venue_id)

    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="权限不足")

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
            "start_date": b.start_date,
            "end_date": b.end_date,
            "reason": b.reason,
        }
        for b in blackouts
    ]


@router.delete(
    "/{venue_id}/blackouts/{blackout_id}",
    status_code=status.HTTP_200_OK,
)
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
        raise HTTPException(status_code=404, detail="封场记录不存在")

    await db.delete(blackout)
    await db.flush()

    await audit_log(
        db,
        entity_type="venue",
        entity_id=venue_id,
        action="delete_blackout",
        actor_id=current_user["id"],
        changes={"blackout_id": blackout_id},
    )

    return {"id": blackout_id, "deleted": True}
