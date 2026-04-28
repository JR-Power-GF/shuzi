"""Booking service — business logic for creating, updating, and cancelling bookings.

All-or-nothing conflict detection: venue and equipment time overlaps are checked
*before* any rows are written.  Pessimistic row locks on Venue and Equipment
ensure serialisable scheduling under concurrency.
"""
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.schemas.booking import BookingCreate, BookingUpdate
from app.services.audit import audit_log
from app.services.booking_utils import check_time_overlap, acquire_row_lock


class BookingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_booking_or_404(self, booking_id: int) -> Booking:
        stmt = select(Booking).where(Booking.id == booking_id)
        result = await self.db.execute(stmt)
        booking = result.scalar_one_or_none()
        if booking is None:
            raise HTTPException(status_code=404, detail="预约不存在")
        return booking

    async def _validate_venue(self, venue_id: int) -> Venue:
        venue = await acquire_row_lock(self.db, Venue, venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="场地不存在")
        if venue.status != "active":
            raise HTTPException(status_code=400, detail="场地不可用")
        return venue

    async def _validate_equipment(self, equipment_id: int) -> Equipment:
        equip = await acquire_row_lock(self.db, Equipment, equipment_id)
        if equip is None:
            raise HTTPException(status_code=400, detail=f"设备 {equipment_id} 不存在")
        if equip.status != "active":
            raise HTTPException(status_code=400, detail=f"设备 {equip.name} 不可用")
        return equip

    async def _check_conflicts(
        self,
        *,
        venue_id: int,
        equipment_ids: list[int],
        start: datetime,
        end: datetime,
        exclude_booking_id: int | None = None,
    ) -> None:
        """Raise 409 if any resource is already booked in [start, end).

        All checks run *before* any writes so the operation is all-or-nothing.
        """
        # --- venue overlap ---
        venue_overlap = await check_time_overlap(
            self.db,
            table=Booking,
            resource_id_column=Booking.venue_id,
            resource_id=venue_id,
            start_column=Booking.start_time,
            end_column=Booking.end_time,
            new_start=start,
            new_end=end,
            exclude_id=exclude_booking_id,
            exclude_id_column=Booking.id,
        )
        if venue_overlap:
            raise HTTPException(status_code=409, detail="场地时间冲突")

        # --- equipment overlaps (inline JOIN query) ---
        for eid in equipment_ids:
            stmt = (
                select(Booking.id)
                .join(BookingEquipment, BookingEquipment.booking_id == Booking.id)
                .where(
                    BookingEquipment.equipment_id == eid,
                    Booking.start_time < end,
                    Booking.end_time > start,
                )
            )
            if exclude_booking_id is not None:
                stmt = stmt.where(Booking.id != exclude_booking_id)
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail=f"设备 {eid} 时间冲突")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def create(self, data: BookingCreate, actor_id: int) -> Booking:
        # Idempotency via client_ref
        if data.client_ref is not None:
            stmt = select(Booking).where(Booking.client_ref == data.client_ref)
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing

        # Validate resources (with row locks, ordered to prevent deadlock)
        await self._validate_venue(data.venue_id)

        equipment_ids = sorted(set(data.equipment_ids))
        for eid in equipment_ids:
            await self._validate_equipment(eid)

        # Conflict detection (all-or-nothing)
        await self._check_conflicts(
            venue_id=data.venue_id,
            equipment_ids=equipment_ids,
            start=data.start_time,
            end=data.end_time,
        )

        # Create booking
        booking = Booking(
            venue_id=data.venue_id,
            title=data.title,
            purpose=data.purpose,
            start_time=data.start_time,
            end_time=data.end_time,
            booked_by=actor_id,
            status="approved",
            course_id=data.course_id,
            class_id=data.class_id,
            task_id=data.task_id,
            client_ref=data.client_ref,
        )
        self.db.add(booking)
        await self.db.flush()

        # Create equipment link rows
        for eid in equipment_ids:
            self.db.add(BookingEquipment(booking_id=booking.id, equipment_id=eid))
        await self.db.flush()

        # Audit log
        await audit_log(
            self.db,
            entity_type="booking",
            entity_id=booking.id,
            action="create",
            actor_id=actor_id,
            changes={"title": data.title, "venue_id": data.venue_id},
        )

        return booking

    async def update(
        self, booking_id: int, data: BookingUpdate, actor_id: int
    ) -> Booking:
        booking = await self._get_booking_or_404(booking_id)

        if booking.status == "cancelled":
            raise HTTPException(status_code=400, detail="已取消的预约无法修改")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return booking

        # Resolve effective time range
        eff_start = update_data.get("start_time", booking.start_time)
        eff_end = update_data.get("end_time", booking.end_time)

        # Resolve effective equipment list
        if "equipment_ids" in update_data:
            eff_equip_ids = sorted(set(update_data["equipment_ids"]))
        else:
            stmt = (
                select(BookingEquipment.equipment_id)
                .where(BookingEquipment.booking_id == booking.id)
            )
            result = await self.db.execute(stmt)
            eff_equip_ids = sorted(row[0] for row in result.all())

        # If time or equipment changed, re-validate and re-check conflicts
        time_changed = "start_time" in update_data or "end_time" in update_data
        equip_changed = "equipment_ids" in update_data

        if time_changed or equip_changed:
            await self._validate_venue(booking.venue_id)
            for eid in eff_equip_ids:
                await self._validate_equipment(eid)
            await self._check_conflicts(
                venue_id=booking.venue_id,
                equipment_ids=eff_equip_ids,
                start=eff_start,
                end=eff_end,
                exclude_booking_id=booking.id,
            )

        # Apply field updates
        for field, value in update_data.items():
            if field != "equipment_ids" and hasattr(booking, field):
                setattr(booking, field, value)
        await self.db.flush()

        # Replace equipment link rows if changed
        if equip_changed:
            await self.db.execute(
                delete(BookingEquipment).where(
                    BookingEquipment.booking_id == booking.id
                )
            )
            for eid in eff_equip_ids:
                self.db.add(
                    BookingEquipment(booking_id=booking.id, equipment_id=eid)
                )
            await self.db.flush()

        # Audit log
        await audit_log(
            self.db,
            entity_type="booking",
            entity_id=booking.id,
            action="update",
            actor_id=actor_id,
            changes=update_data,
        )

        return booking

    async def cancel(self, booking_id: int, actor_id: int) -> Booking:
        booking = await self._get_booking_or_404(booking_id)

        if booking.status == "cancelled":
            return booking

        if booking.end_time <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="已结束的预约无法取消")

        old_status = booking.status
        booking.status = "cancelled"
        await self.db.flush()

        await audit_log(
            self.db,
            entity_type="booking",
            entity_id=booking.id,
            action="cancel",
            actor_id=actor_id,
            changes={"old_status": old_status, "new_status": "cancelled"},
        )

        return booking

    async def get(self, booking_id: int) -> Booking:
        return await self._get_booking_or_404(booking_id)

    async def list_bookings(
        self,
        *,
        venue_id: int | None = None,
        booked_by: int | None = None,
        status_filter: str | None = None,
        start_after: datetime | None = None,
        start_before: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Booking], int]:
        limit = min(limit, 100)

        # Build filters
        conditions = []
        if venue_id is not None:
            conditions.append(Booking.venue_id == venue_id)
        if booked_by is not None:
            conditions.append(Booking.booked_by == booked_by)
        if status_filter is not None:
            conditions.append(Booking.status == status_filter)
        if start_after is not None:
            conditions.append(Booking.start_time >= start_after)
        if start_before is not None:
            conditions.append(Booking.start_time <= start_before)

        # Count query
        count_stmt = select(func.count()).select_from(Booking)
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()

        # Data query
        data_stmt = select(Booking).order_by(Booking.start_time.desc())
        for cond in conditions:
            data_stmt = data_stmt.where(cond)
        data_stmt = data_stmt.limit(limit).offset(offset)
        data_result = await self.db.execute(data_stmt)
        bookings = list(data_result.scalars().all())

        return bookings, total
