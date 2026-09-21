from sqlalchemy.exc import IntegrityError

from app.models import Appointment, ProfessionalSchedule, User, UserRole
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointments import AdminAppointmentCreate, AdminScheduleCreate


class AdminAppointmentNotFoundError(Exception):
    pass


class AdminAppointmentConflictError(Exception):
    pass


class AdminAppointmentService:
    def __init__(self, appointments: AppointmentRepository, users: UserRepository):
        self.appointments = appointments
        self.users = users

    def create_schedule(self, data: AdminScheduleCreate) -> ProfessionalSchedule:
        professional = self._get_user(data.professional_id, UserRole.PROFESSIONAL)
        schedule = ProfessionalSchedule(
            professional_id=professional.id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_duration_min=data.slot_duration_min,
            is_active=data.is_active,
        )
        return self._create(schedule, "Could not create schedule")

    def create_appointment(self, data: AdminAppointmentCreate) -> Appointment:
        patient = self._get_user(data.patient_id, UserRole.PATIENT)
        professional = self._get_user(data.professional_id, UserRole.PROFESSIONAL)
        appointment = Appointment(
            patient_id=patient.id,
            professional_id=professional.id,
            start_time=data.start_time,
            end_time=data.end_time,
            type=data.type,
            reason=data.reason,
        )
        return self._create(appointment, "Appointment conflicts with an existing booking")

    def _get_user(self, user_id, role: UserRole) -> User:
        user = self.users.get_by_id(user_id)
        if user is None or user.role != role:
            raise AdminAppointmentNotFoundError(f"{role.value.capitalize()} not found")
        return user

    def _create(self, record, conflict_detail: str):
        try:
            if isinstance(record, ProfessionalSchedule):
                return self.appointments.create_schedule(record)
            return self.appointments.create_appointment(record)
        except IntegrityError as error:
            self.appointments.rollback()
            constraint_name = getattr(getattr(error, "orig", None), "diag", None)
            constraint_name = getattr(constraint_name, "constraint_name", None)
            if constraint_name == "no_overlapping_appointments":
                raise AdminAppointmentConflictError(conflict_detail) from error
            raise AdminAppointmentConflictError("Could not create record") from error