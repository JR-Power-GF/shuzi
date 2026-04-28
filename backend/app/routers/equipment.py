from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentUpdate,
    EquipmentResponse,
    EquipmentListResponse,
    EquipmentStatusUpdate,
)
from app.services.audit import audit_log

router = APIRouter(prefix="/api/v1/equipment", tags=["equipment"])


async def _get_equipment_or_404(db: AsyncSession, equipment_id: int) -> Equipment:
    result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
    equip = result.scalar_one_or_none()
    if not equip:
        raise HTTPException(status_code=404, detail="设备不存在")
    return equip


async def _get_venue_name(db: AsyncSession, venue_id: int | None) -> str | None:
    if venue_id is None:
        return None
    result = await db.execute(select(Venue.name).where(Venue.id == venue_id))
    return result.scalar_one_or_none()


def _equip_to_response(equip: Equipment, venue_name: str | None = None) -> dict:
    return {
        "id": equip.id,
        "name": equip.name,
        "category": equip.category,
        "serial_number": equip.serial_number,
        "status": equip.status,
        "venue_id": equip.venue_id,
        "venue_name": venue_name,
        "description": equip.description,
        "external_id": equip.external_id,
        "created_at": equip.created_at,
        "updated_at": equip.updated_at,
    }


@router.post("", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
async def create_equipment(
    data: EquipmentCreate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    if data.venue_id is not None:
        result = await db.execute(select(Venue).where(Venue.id == data.venue_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="场地不存在")

    equip = Equipment(
        name=data.name,
        category=data.category,
        serial_number=data.serial_number,
        venue_id=data.venue_id,
        description=data.description,
        external_id=data.external_id,
    )
    db.add(equip)
    try:
        await db.flush()
    except IntegrityError as exc:
        if data.serial_number and "serial_number" in str(exc.orig):
            raise HTTPException(status_code=409, detail="序列号已存在")
        raise

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="create", actor_id=current_user["id"],
        changes={"name": data.name},
    )

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)


@router.get("", response_model=EquipmentListResponse)
async def list_equipment(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    venue_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Equipment)
    count_query = select(func.count()).select_from(Equipment)

    if current_user["role"] == "teacher":
        query = query.where(Equipment.status == "active")
        count_query = count_query.where(Equipment.status == "active")
    elif current_user["role"] not in ("admin", "facility_manager"):
        raise HTTPException(status_code=403, detail="权限不足")

    if status_filter:
        query = query.where(Equipment.status == status_filter)
        count_query = count_query.where(Equipment.status == status_filter)
    if category:
        query = query.where(Equipment.category == category)
        count_query = count_query.where(Equipment.category == category)
    if venue_id is not None:
        query = query.where(Equipment.venue_id == venue_id)
        count_query = count_query.where(Equipment.venue_id == venue_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(Equipment.id).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    # Batch resolve venue names
    venue_ids = {e.venue_id for e in items if e.venue_id is not None}
    venue_names = {}
    if venue_ids:
        vresult = await db.execute(select(Venue.id, Venue.name).where(Venue.id.in_(venue_ids)))
        venue_names = dict(vresult.all())

    response_items = [_equip_to_response(e, venue_names.get(e.venue_id)) for e in items]
    return {"items": response_items, "total": total}


@router.get("/{equipment_id}", response_model=EquipmentResponse)
async def get_equipment(
    equipment_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    if current_user["role"] == "student":
        raise HTTPException(status_code=403, detail="权限不足")
    if current_user["role"] == "teacher" and equip.status != "active":
        raise HTTPException(status_code=404, detail="设备不存在")

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)


@router.put("/{equipment_id}", response_model=EquipmentResponse)
async def update_equipment(
    equipment_id: int,
    data: EquipmentUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    update_data = data.model_dump(exclude_unset=True)

    if "venue_id" in update_data and update_data["venue_id"] is not None:
        result = await db.execute(select(Venue).where(Venue.id == update_data["venue_id"]))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="场地不存在")

    for field, value in update_data.items():
        setattr(equip, field, value)
    try:
        await db.flush()
    except IntegrityError as exc:
        if "serial_number" in str(exc.orig):
            raise HTTPException(status_code=409, detail="序列号已存在")
        raise

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="update", actor_id=current_user["id"],
        changes=update_data,
    )

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)


@router.patch("/{equipment_id}/status", response_model=EquipmentResponse)
async def change_equipment_status(
    equipment_id: int,
    data: EquipmentStatusUpdate,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    old_status = equip.status
    equip.status = data.status
    await db.flush()

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="status_change", actor_id=current_user["id"],
        changes={"old_status": old_status, "new_status": data.status},
    )

    venue_name = await _get_venue_name(db, equip.venue_id)
    return _equip_to_response(equip, venue_name)


@router.post("/{equipment_id}/unassign-venue", response_model=EquipmentResponse)
async def unassign_equipment_venue(
    equipment_id: int,
    current_user: dict = Depends(require_role(["admin", "facility_manager"])),
    db: AsyncSession = Depends(get_db),
):
    equip = await _get_equipment_or_404(db, equipment_id)

    if equip.venue_id is None:
        raise HTTPException(status_code=400, detail="设备未绑定场地")

    old_venue_id = equip.venue_id
    equip.venue_id = None
    await db.flush()

    await audit_log(
        db, entity_type="equipment", entity_id=equip.id,
        action="unassign_venue", actor_id=current_user["id"],
        changes={"old_venue_id": old_venue_id},
    )

    return _equip_to_response(equip)
