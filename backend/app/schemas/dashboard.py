from pydantic import BaseModel


class DailyCount(BaseModel):
    date: str
    count: int


class AdminDashboardResponse(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    total_active_courses: int
    total_active_tasks: int
    total_submissions: int
    late_submissions: int
    pending_grades: int
    avg_score: float | None
    daily_submissions_last_7d: list[DailyCount]


class TeacherDashboardResponse(BaseModel):
    my_active_courses: int
    my_active_tasks: int
    my_total_submissions: int
    my_late_submissions: int
    my_pending_grades: int
    my_avg_score: float | None
    my_daily_submissions_last_7d: list[DailyCount]
