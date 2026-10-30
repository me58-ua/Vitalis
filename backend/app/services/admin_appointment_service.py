from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import AppointmentStatus
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.admin_appointments import AdminAppointmentsQuery, AdminAppointmentListResponse, AdminUpcomingAppointmentsResponse


class AdminAppointmentQueryService:
    def __init__(self, appointments: AppointmentRepository):
        self.appointments = appointments

    @staticmethod
    def month_bounds(now: datetime):
        local = now.astimezone(ZoneInfo("Europe/Madrid"))
        end = local.replace(year=local.year + (local.month == 12), month=local.month % 12 + 1,
                            day=1, hour=0, minute=0, second=0, microsecond=0)
        return now.astimezone(timezone.utc), end.astimezone(timezone.utc)

    def list(self, query: AdminAppointmentsQuery, now: datetime | None = None):
        zone = ZoneInfo("Europe/Madrid")
        start = datetime.combine(query.from_date, time.min, zone).astimezone(timezone.utc) if query.from_date else None
        end = datetime.combine(query.to_date + timedelta(days=1), time.min, zone).astimezone(timezone.utc) if query.to_date and query.to_date < date.max else None
        statuses = None
        if query.upcoming_month:
            month_start, month_end = self.month_bounds(now or datetime.now(timezone.utc))
            start = max(start, month_start) if start else month_start
            end = min(end, month_end) if end else month_end
            statuses = [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
        items, total = self.appointments.list_admin(query.patient_id, query.professional_id, start, end, statuses,
                                                     (query.page - 1) * query.page_size, query.page_size)
        return AdminAppointmentListResponse(appointments=items, total=total, page=query.page, page_size=query.page_size)

    def upcoming_month(self, limit: int = 3):
        now = datetime.now(timezone.utc)
        start, end = self.month_bounds(now)
        result = self.list(AdminAppointmentsQuery(upcoming_month=True, page_size=limit), now)
        return AdminUpcomingAppointmentsResponse(appointments=result.appointments, total=result.total, period_start=start, period_end=end)
