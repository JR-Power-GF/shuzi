import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.schemas.booking import (
    BookingCreate,
    BookingListResponse,
    BookingResponse,
    BookingUpdate,
)
from app.services.booking_service import BookingService
from app.services.xr_service import cancel_xr_session_for_booking, create_xr_session_for_booking

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


def _booking_to_response(booking, venue_name=None, equipment_items=None):
    """Convert a Booking ORM object into a response dict with derived_status."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    if booking.status == "cancelled":
        derived_status = "cancelled"
    elif booking.start_time <= now < booking.end_time:
        derived_status = "active"
    elif booking.end_time <= now:
        derived_status = "completed"
    else:
        derived_status = "approved"

    return {
        "id": booking.id,
        "venue_id": booking.venue_id,
        "venue_name": venue_name,
        "title": booking.title,
        "purpose": booking.purpose,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "booked_by": booking.booked_by,
        "status": booking.status,
        "derived_status": derived_status,
        "course_id": booking.course_id,
        "class_id": booking.class_id,
        "task_id": booking.task_id,
        "client_ref": booking.client_ref,
        "equipment": equipment_items or [],
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
    }


async def _enrich_booking(db: AsyncSession, booking) -> dict:
    """Load venue name and equipment items, then build the response dict."""
    # Venue name
    result = await db.execute(select(Venue.name).where(Venue.id == booking.venue_id))
    venue_name = result.scalar_one_or_none()

    # Equipment items
    result = await db.execute(
        select(BookingEquipment.equipment_id).where(
            BookingEquipment.booking_id == booking.id
        )
    )
    equip_ids = [row[0] for row in result.all()]

    equip_items = []
    if equip_ids:
        result = await db.execute(
            select(Equipment.id, Equipment.name).where(Equipment.id.in_(equip_ids))
        )
        equip_items = [{"id": row[0], "name": row[1]} for row in result.all()]

    return _booking_to_response(booking, venue_name, equip_items)


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


@router.get("", response_model=BookingListResponse)
async def list_bookings(
    venue_id: int | None = Query(None),
    booked_by: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    start_after: datetime.datetime | None = Query(None),
    start_before: datetime.datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current_user["role"]

    if role == "student":
        raise HTTPException(status_code=403, detail="权限不足")

    # Teachers can only see their own bookings
    if role == "teacher":
        booked_by = current_user["id"]

    svc = BookingService(db)
    bookings, total = await svc.list_bookings(
        venue_id=venue_id,
        booked_by=booked_by,
        status_filter=status_filter,
        start_after=start_after,
        start_before=start_before,
        limit=limit,
        offset=offset,
    )

    items = [await _enrich_booking(db, b) for b in bookings]
    return {"items": items, "total": total}


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = BookingService(db)
    booking = await svc.get(booking_id)

    role = current_user["role"]
    if role == "student":
        raise HTTPException(status_code=403, detail="权限不足")
    if role == "teacher" and booking.booked_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="权限不足")

    return await _enrich_booking(db, booking)


@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    data: BookingUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = BookingService(db)
    booking = await svc.get(booking_id)

    role = current_user["role"]
    if role not in ("admin", "facility_manager"):
        if booking.booked_by != current_user["id"]:
            raise HTTPException(status_code=403, detail="权限不足")

    booking = await svc.update(booking_id, data, actor_id=current_user["id"])
    return await _enrich_booking(db, booking)


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
