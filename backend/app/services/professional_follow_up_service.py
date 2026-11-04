# Servicio de seguimiento profesional: consulta pacientes, citas, historial y recetas para el seguimiento clínico.
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from app.models import AppointmentStatus, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.appointments import (
    ProfessionalAppointmentHistoryListResponse,
    ProfessionalAppointmentHistoryResponse,
)
from app.schemas.prescriptions import PrescriptionListResponse
from app.services.appointment_service import AppointmentAccessError


class ProfessionalFollowUpService:
    def __init__(
        self,
        appointments: AppointmentRepository,
        prescriptions: PrescriptionRepository,
        profiles: ProfileRepository,
        now=None,
    ):
        self.appointments = appointments
        self.prescriptions = prescriptions
        self.profiles = profiles
        self.now = now or (lambda: datetime.now(timezone.utc))

    def list_past_appointments(
        self,
        professional_id: UUID,
        current_user: User,
        patient_id: UUID | None,
        patient_search: str | None,
        start_date: date | None,
        end_date: date | None,
        appointment_status: AppointmentStatus | None,
        page: int,
        page_size: int,
    ) -> ProfessionalAppointmentHistoryListResponse:
        self._require_identity(professional_id, current_user.id)
        start, end = self._date_range(start_date, end_date)
        records, total = self.appointments.list_past_for_professional(
            professional_id,
            self.now(),
            patient_id,
            patient_search,
            start,
            end,
            appointment_status,
            (page - 1) * page_size,
            page_size,
        )
        return ProfessionalAppointmentHistoryListResponse(
            appointments=[
                ProfessionalAppointmentHistoryResponse(
                    id=appointment.id,
                    patient_id=appointment.patient_id,
                    professional_id=appointment.professional_id,
                    start_time=appointment.start_time,
                    end_time=appointment.end_time,
                    status=appointment.status,
                    type=appointment.type,
                    appointment_reason=appointment.appointment_reason,
                    cancellation_reason=getattr(appointment, "cancellation_reason", None),
                    room_id=appointment.room_id,
                    created_at=appointment.created_at,
                    updated_at=appointment.updated_at,
                    patient_name=patient.name,
                    patient_username=patient.username,
                    patient_email=patient.email,
                    clinical_notes=note.clinical_notes if note else None,
                    patient_summary=note.patient_summary if note else None,
                    diagnosis=note.diagnosis if note else None,
                )
                for appointment, patient, note in records
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_prescriptions(
        self,
        professional_id: UUID,
        current_user: User,
        patient_id: UUID | None,
        start_date: date | None,
        end_date: date | None,
        page: int,
        page_size: int,
    ) -> PrescriptionListResponse:
        self._require_identity(professional_id, current_user.id)
        professional_profile = self.profiles.get_professional(professional_id)
        if professional_profile is None:
            raise AppointmentAccessError("Professional profile not found")
        start, end = self._date_range(start_date, end_date)
        records, total = self.prescriptions.list_for_professional(
            professional_profile.id,
            patient_id,
            start,
            end,
            (page - 1) * page_size,
            page_size,
        )
        return PrescriptionListResponse(
            prescriptions=records,
            total=total,
            page=page,
            page_size=page_size,
            message=(
                "No se encontraron recetas para este paciente"
                if patient_id is not None and not records
                else None
            ),
        )

    @staticmethod
    def _date_range(start_date: date | None, end_date: date | None):
        if start_date is not None and end_date is not None and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        start = datetime.combine(start_date, time.min, tzinfo=timezone.utc) if start_date else None
        end = datetime.combine(end_date, time.min, tzinfo=timezone.utc) + timedelta(days=1) if end_date else None
        return start, end

    @staticmethod
    def _require_identity(path_id: UUID, user_id: UUID) -> None:
        if path_id != user_id:
            raise AppointmentAccessError("Professional identity does not match the URL")
