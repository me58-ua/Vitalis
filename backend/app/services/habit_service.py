# Servicio de hábitos: gestiona hábitos del paciente, su seguimiento y los registros asociados.
from datetime import date
from uuid import UUID

from app.models import HabitType, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.habit_repository import HabitRepository
from app.repositories.profile_repository import ProfileRepository


class HabitAccessError(Exception):
    pass


class HabitValidationError(Exception):
    pass


class HabitService:
    def __init__(
        self,
        habits: HabitRepository,
        profiles: ProfileRepository,
        appointments: AppointmentRepository,
    ):
        self.habits = habits
        self.profiles = profiles
        self.appointments = appointments

    def list_for_patient(
        self,
        current_user: User,
        habit_type: HabitType | None,
        search: str | None,
        start_date: date | None,
        end_date: date | None,
        page: int,
        page_size: int,
    ) -> dict:
        profile = self.profiles.get_patient(current_user.id)
        if profile is None:
            raise HabitValidationError("Patient profile not found")
        return self._list(profile.id, habit_type, search, start_date, end_date, page, page_size)

    def list_for_professional(
        self,
        patient_id: UUID,
        professional_id: UUID,
        habit_type: HabitType | None,
        search: str | None,
        start_date: date | None,
        end_date: date | None,
        page: int,
        page_size: int,
    ) -> dict:
        profile = self.profiles.get_patient(patient_id)
        if profile is None:
            raise HabitValidationError("Patient profile not found")
        if self.appointments.health_sharing_scope(profile, professional_id) not in ("basic", "full"):
            raise HabitAccessError("The patient has not shared health data")
        return self._list(profile.id, habit_type, search, start_date, end_date, page, page_size)

    def _list(self, patient_id, habit_type, search, start_date, end_date, page, page_size):
        if habit_type == "alcohol" or getattr(habit_type, "value", None) == "alcohol":
            raise HabitValidationError("Alcohol is stored in alcohol_logs")
        if start_date and end_date and start_date > end_date:
            raise HabitValidationError("start_date cannot be later than end_date")
        offset = (page - 1) * page_size
        items, total = self.habits.list_filtered(
            patient_id, habit_type, search, start_date, end_date, offset, page_size
        )
        return {
            "habits": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "aggregates": self.habits.aggregate(patient_id, habit_type, search, start_date, end_date),
        }
