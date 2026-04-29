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
