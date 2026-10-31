from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.schemas.professional_dashboard import (
    ProfessionalAppointmentsQuery, ProfessionalAppointmentsResponse, ProfessionalDashboardResponse,
)


class ProfessionalDashboardService:
    """Counts and lists for the authenticated professional; no cross-account queries."""

    def __init__(self, appointments: AppointmentRepository, professionals: ProfessionalRepository, now=None):
        self.appointments = appointments
        self.professionals = professionals
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.zone = ZoneInfo("Europe/Madrid")

    def midnight(self, day: date):
        return datetime.combine(day, time.min, self.zone).astimezone(timezone.utc)

    def list_appointments(self, professional_id, query: ProfessionalAppointmentsQuery):
        start = self.midnight(query.from_date) if query.from_date else None
        end = self.midnight(query.to_date + timedelta(days=1)) if query.to_date and query.to_date < date.max else None
        records, total = self.appointments.list_for_professional(
            professional_id, self.now(), start, end, query.status, query.upcoming_only,
            (query.page - 1) * query.page_size, query.page_size,
        )
        return ProfessionalAppointmentsResponse(appointments=records, total=total, page=query.page, page_size=query.page_size)

    def dashboard(self, professional_id):
        now = self.now()
        today = now.astimezone(self.zone).date()
        monday = today - timedelta(days=today.weekday())
        dates = [monday + timedelta(days=index) for index in range(7)]
        bounds = [(self.midnight(day), self.midnight(day + timedelta(days=1))) for day in dates]
        counts = self.appointments.professional_counts(
            professional_id,
            (self.midnight(today), self.midnight(today + timedelta(days=1)), self.midnight(today - timedelta(days=1))),
            bounds,
        )
        _, patients = self.professionals.list_patients(professional_id, None, 0, 1)
        upcoming = self.list_appointments(professional_id, ProfessionalAppointmentsQuery(page_size=5))
        return ProfessionalDashboardResponse(
            generated_at=now, date=today, week_start=monday, week_end=dates[-1],
            appointments_today=counts[0], appointments_yesterday=counts[1], completed_today=counts[2],
            scheduled_today=counts[3], assigned_patients=patients,
            weekly_distribution=[{"date": day, "count": count} for day, count in zip(dates, counts[4:])],
            upcoming_appointments=upcoming.appointments, upcoming_total=upcoming.total,
        )
