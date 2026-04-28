import datetime

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingEquipment
from app.models.equipment import Equipment
from app.models.venue import Venue
from app.models.venue_availability import VenueAvailability
from app.models.venue_blackout import VenueBlackout


def _available_hours_in_window(
    venue_id: int,
    start_date: datetime.date,
    end_date: datetime.date,
    availability_slots: list[VenueAvailability],
    blackout_dates: list[VenueBlackout],
) -> float:
    """Calculate available hours for a venue within a date window.

    Pure function — no DB access.

    - If no availability_slots: assume 24h/day.
    - If slots exist: sum per-day_of_week hours.
    - Deduct full blackout dates.
    """
    # Build the set of blackout dates for this venue
    blacked_out: set[datetime.date] = set()
    for bo in blackout_dates:
        # Clip blackout to the window
        bo_start = max(bo.start_date, start_date)
        bo_end = min(bo.end_date, end_date)
        if bo_start <= bo_end:
            n = (bo_end - bo_start).days + 1
            for i in range(n):
                blacked_out.add(bo_start + datetime.timedelta(days=i))

    total_days = (end_date - start_date).days + 1

    if not availability_slots:
        # Default: 24h per non-blacked-out day
        non_blacked = total_days - len(blacked_out)
        return max(non_blacked, 0) * 24.0

    # Build per-day_of_week hours map
    dow_hours: dict[int, float] = {}
    for slot in availability_slots:
        # Calculate hours from time objects
        dt_start = datetime.datetime.combine(datetime.date.min, slot.start_time)
        dt_end = datetime.datetime.combine(datetime.date.min, slot.end_time)
        hours = (dt_end - dt_start).total_seconds() / 3600.0
        dow_hours[slot.day_of_week] = dow_hours.get(slot.day_of_week, 0.0) + hours

    total = 0.0
    current = start_date
    one_day = datetime.timedelta(days=1)
    while current <= end_date:
        if current not in blacked_out:
            total += dow_hours.get(current.weekday(), 0.0)
        current += one_day

    return total


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def venue_utilization(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int = 100,
    ) -> list[dict]:
        """Calculate venue utilization statistics."""
        window_start = datetime.datetime.combine(start_date, datetime.time.min)
        window_end = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # Fetch active venues
        venues_result = await self.db.execute(
            select(Venue).where(Venue.status == "active").limit(limit)
        )
        venues = list(venues_result.scalars().all())

        if not venues:
            return []

        venue_ids = [v.id for v in venues]

        # Aggregate booked seconds per venue
        seconds_expr = func.sum(
            text(
                "TIMESTAMPDIFF(SECOND, GREATEST(bookings.start_time, :_ws), "
                "LEAST(bookings.end_time, :_we))"
            )
        ).label("total_seconds")

        count_expr = func.count(Booking.id).label("booking_count")

        booking_stmt = (
            select(
                Booking.venue_id,
                seconds_expr,
                count_expr,
            )
            .where(
                Booking.venue_id.in_(venue_ids),
                Booking.status == "approved",
                Booking.start_time < window_end,
                Booking.end_time > window_start,
            )
            .group_by(Booking.venue_id)
        )
        booking_stmt = booking_stmt.params(_ws=window_start, _we=window_end)

        booking_result = await self.db.execute(booking_stmt)
        booking_rows = booking_result.all()

        booked_map: dict[int, tuple[float, int]] = {}
        for row in booking_rows:
            venue_id = row[0]
            total_seconds = float(row[1] or 0)
            booking_count = int(row[2] or 0)
            booked_map[venue_id] = (total_seconds / 3600.0, booking_count)

        # Batch fetch availability slots for all venues
        avail_result = await self.db.execute(
            select(VenueAvailability).where(
                VenueAvailability.venue_id.in_(venue_ids)
            )
        )
        all_slots = list(avail_result.scalars().all())

        avail_by_venue: dict[int, list[VenueAvailability]] = {}
        for slot in all_slots:
            avail_by_venue.setdefault(slot.venue_id, []).append(slot)

        # Batch fetch blackouts for all venues
        blackout_result = await self.db.execute(
            select(VenueBlackout).where(
                VenueBlackout.venue_id.in_(venue_ids),
                VenueBlackout.end_date >= start_date,
                VenueBlackout.start_date <= end_date,
            )
        )
        all_blackouts = list(blackout_result.scalars().all())

        blackout_by_venue: dict[int, list[VenueBlackout]] = {}
        for bo in all_blackouts:
            blackout_by_venue.setdefault(bo.venue_id, []).append(bo)

        # Build result
        results = []
        for venue in venues:
            booked_hours, booking_count = booked_map.get(venue.id, (0.0, 0))

            slots = avail_by_venue.get(venue.id, [])
            blackouts = blackout_by_venue.get(venue.id, [])

            available_hours = _available_hours_in_window(
                venue_id=venue.id,
                start_date=start_date,
                end_date=end_date,
                availability_slots=slots,
                blackout_dates=blackouts,
            )

            if available_hours == 0.0:
                rate = None
            else:
                rate = booked_hours / available_hours

            results.append({
                "venue_id": venue.id,
                "venue_name": venue.name,
                "booked_hours": booked_hours,
                "available_hours": available_hours,
                "utilization_rate": rate,
                "booking_count": booking_count,
            })

        return results

    async def equipment_usage(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        limit: int = 100,
    ) -> list[dict]:
        """Calculate equipment usage statistics."""
        window_start = datetime.datetime.combine(start_date, datetime.time.min)
        window_end = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        # Fetch ALL equipment (any status)
        equip_result = await self.db.execute(
            select(Equipment).limit(limit)
        )
        equipment_list = list(equip_result.scalars().all())

        if not equipment_list:
            return []

        equip_ids = [e.id for e in equipment_list]

        # Aggregate usage per equipment via LEFT JOIN
        seconds_expr = func.sum(
            text(
                "TIMESTAMPDIFF(SECOND, GREATEST(bookings.start_time, :_ws), "
                "LEAST(bookings.end_time, :_we))"
            )
        ).label("total_seconds")

        count_expr = func.count(
            func.distinct(BookingEquipment.booking_id)
        ).label("booking_count")

        usage_stmt = (
            select(
                Equipment.id,
                Equipment.name,
                Equipment.category,
                count_expr,
                seconds_expr,
            )
            .outerjoin(
                BookingEquipment,
                Equipment.id == BookingEquipment.equipment_id,
            )
            .outerjoin(
                Booking,
                BookingEquipment.booking_id == Booking.id,
            )
            .where(
                Equipment.id.in_(equip_ids),
                # Include equipment with no bookings (LEFT JOIN)
                # Filter bookings that overlap window and are approved
                # Use OR to include rows with no booking at all
            )
            .group_by(Equipment.id, Equipment.name, Equipment.category)
        )

        # We need a more careful query: LEFT JOIN with conditions
        # Let's use a subquery approach instead
        usage_subquery = (
            select(
                BookingEquipment.equipment_id,
                func.count(func.distinct(BookingEquipment.booking_id)).label(
                    "booking_count"
                ),
                func.sum(
                    text(
                        "TIMESTAMPDIFF(SECOND, GREATEST(bookings.start_time, :_ws), "
                        "LEAST(bookings.end_time, :_we))"
                    )
                ).label("total_seconds"),
            )
            .select_from(BookingEquipment)
            .join(Booking, BookingEquipment.booking_id == Booking.id)
            .where(
                Booking.status == "approved",
                Booking.start_time < window_end,
                Booking.end_time > window_start,
            )
            .group_by(BookingEquipment.equipment_id)
        )
        usage_subquery = usage_subquery.params(_ws=window_start, _we=window_end)

        usage_result = await self.db.execute(usage_subquery)
        usage_rows = usage_result.all()

        usage_map: dict[int, tuple[int, float]] = {}
        for row in usage_rows:
            equip_id = row[0]
            booking_count = int(row[1] or 0)
            total_seconds = float(row[2] or 0)
            usage_map[equip_id] = (booking_count, total_seconds / 3600.0)

        results = []
        for equip in equipment_list:
            booking_count, total_hours = usage_map.get(equip.id, (0, 0.0))
            results.append({
                "equipment_id": equip.id,
                "equipment_name": equip.name,
                "category": equip.category,
                "booking_count": booking_count,
                "total_hours": total_hours,
            })

        return results

    async def peak_hours(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
        """Calculate peak hours (booking count per start hour)."""
        window_start = datetime.datetime.combine(start_date, datetime.time.min)
        window_end = datetime.datetime.combine(
            end_date + datetime.timedelta(days=1), datetime.time.min
        )

        hour_expr = func.extract("hour", Booking.start_time).label("hour")
        count_expr = func.count(Booking.id).label("booking_count")

        stmt = (
            select(hour_expr, count_expr)
            .where(
                Booking.status == "approved",
                Booking.start_time >= window_start,
                Booking.start_time < window_end,
            )
            .group_by(hour_expr)
            .order_by(hour_expr)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [{"hour": int(row[0]), "booking_count": int(row[1])} for row in rows]
