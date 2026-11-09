# Servicio de horarios: crea, consulta y actualiza la disponibilidad de los profesionales.
from sqlalchemy.exc import IntegrityError

from app.models import ProfessionalSchedule, User, UserRole
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointments import AdminScheduleCreate, ProfessionalScheduleUpdate
from app.services.appointment_service import (
    AppointmentAccessError,
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentValidationError,
)


class ScheduleService:
    def __init__(self, appointments: AppointmentRepository, users: UserRepository):
        self.appointments = appointments
        self.users = users

    def create_schedule(self, data: AdminScheduleCreate) -> ProfessionalSchedule:
        professional = self._get_professional(data.professional_id)
        schedule = ProfessionalSchedule(
            professional_id=professional.id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_duration_min=data.slot_duration_min,
            is_active=data.is_active,
            channel=data.channel,
        )
        try:
            return self.appointments.create_schedule(schedule)
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError("Could not create schedule") from error

    def update_schedule_as_professional(
        self,
        professional_id,
        current_user: User,
        schedule_id,
        data: ProfessionalScheduleUpdate,
    ) -> ProfessionalSchedule:
        if professional_id != current_user.id:
            raise AppointmentAccessError("Professional identity does not match the URL")
        schedule = self.appointments.get_schedule(schedule_id)
        if schedule is None:
            raise AppointmentNotFoundError("Schedule not found")
        if schedule.professional_id != professional_id:
            raise AppointmentAccessError("Schedule does not belong to this professional")

        values = data.model_dump(exclude_unset=True)
        start_time = values.get("start_time", schedule.start_time)
        end_time = values.get("end_time", schedule.end_time)
        if end_time <= start_time:
            raise AppointmentValidationError("end_time must be after start_time")
        channel = values.get("channel", getattr(schedule, "channel", "consultation"))
        slot = values.get("slot_duration_min", schedule.slot_duration_min)
        minutes = (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)
        if channel == "consultation" and slot > minutes:
            raise AppointmentValidationError("SCHEDULE_SLOT_TOO_LONG")
        try:
            return self.appointments.update_schedule(schedule, values)
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError("Could not update schedule") from error

    def _get_professional(self, professional_id) -> User:
        professional = self.users.get_by_id(professional_id)
        if professional is None or professional.role != UserRole.PROFESSIONAL:
            raise AppointmentNotFoundError("Professional not found")
        return professional
