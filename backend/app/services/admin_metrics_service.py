from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import UserRole
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin_metrics import AdminMonthlyMetricsResponse, MonthlyActivity, MonthlyMetric


class AdminMetricsService:
    def __init__(self, users: UserRepository, appointments: AppointmentRepository):
        self.users = users
        self.appointments = appointments

    @staticmethod
    def metric(total: int, months: list[int]) -> MonthlyMetric:
        current, previous = months[-1], months[-2]
        change = round((current - previous) * 100 / previous, 1) if previous else (0.0 if current == 0 else None)
        return MonthlyMetric(total=total, current_month=current, previous_month=previous, change_percent=change)

    def monthly(self, months: int = 6, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        local = now.astimezone(ZoneInfo("Europe/Madrid"))
        current_index = local.year * 12 + local.month - 1
        starts = [datetime(index // 12, index % 12 + 1, 1, tzinfo=local.tzinfo)
                  for index in range(current_index - months + 1, current_index + 2)]
        boundaries = [(start.astimezone(timezone.utc), end.astimezone(timezone.utc))
                      for start, end in zip(starts, starts[1:])]
        users = self.users.registration_metrics(boundaries)
        counts = {role: users.get(role, {"total": 0, "months": [0] * months}) for role in UserRole}
        user_months = [sum(counts[role]["months"][index] for role in UserRole) for index in range(months)]
        appointment_months = self.appointments.monthly_totals(boundaries)
        return AdminMonthlyMetricsResponse(
            generated_at=now, month_start=boundaries[-1][0], month_end=boundaries[-1][1],
            month_start_date=starts[-2].date(), month_end_date=starts[-1].date() - timedelta(days=1),
            users=self.metric(sum(item["total"] for item in counts.values()), user_months),
            patients=self.metric(counts[UserRole.PATIENT]["total"], counts[UserRole.PATIENT]["months"]),
            professionals=self.metric(counts[UserRole.PROFESSIONAL]["total"], counts[UserRole.PROFESSIONAL]["months"]),
            appointments=self.metric(appointment_months[-1], appointment_months),
            series=[MonthlyActivity(month=start.strftime("%Y-%m"), users=user_months[index],
                                    patients=counts[UserRole.PATIENT]["months"][index],
                                    professionals=counts[UserRole.PROFESSIONAL]["months"][index],
                                    appointments=appointment_months[index]) for index, start in enumerate(starts[:-1])],
        )
