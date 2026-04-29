from pydantic import BaseModel


class DailyCount(BaseModel):
    date: str
    count: int


class AdminDashboardResponse(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    total_classes: int
    total_active_courses: int
    total_archived_courses: int
    total_active_tasks: int
    total_archived_tasks: int
    total_submissions: int
    pending_grades: int
    graded: int
    late_submissions: int
    avg_score: float | None
    nearby_deadline: str | None
    daily_submissions_last_7d: list[DailyCount]


class TeacherDashboardResponse(BaseModel):
    my_classes: int
    my_active_courses: int
    my_archived_courses: int
    my_active_tasks: int
    my_archived_tasks: int
    my_total_submissions: int
    my_pending_grades: int
    my_graded: int
    my_late_submissions: int
    my_avg_score: float | None
    my_nearby_deadline: str | None
    my_daily_submissions_last_7d: list[DailyCount]


class CourseStatItem(BaseModel):
    course_id: int
    course_name: str
    teacher_name: str
    task_count: int
    submission_count: int
    pending_grade_count: int
    graded_count: int
    average_score: float | None


class CourseStatsResponse(BaseModel):
    courses: list[CourseStatItem]
