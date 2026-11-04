from datetime import date, datetime
from pydantic import BaseModel


class MonthlyMetric(BaseModel):
    total: int
    current_month: int
    previous_month: int
    change_percent: float | None


class MonthlyActivity(BaseModel):
    month: str
    users: int
    patients: int
    professionals: int
    appointments: int


class AdminMonthlyMetricsResponse(BaseModel):
    timezone: str = "Europe/Madrid"
    generated_at: datetime
    month_start: datetime
    month_end: datetime
    month_start_date: date
    month_end_date: date
    users: MonthlyMetric
    patients: MonthlyMetric
    professionals: MonthlyMetric
    appointments: MonthlyMetric
    series: list[MonthlyActivity]
