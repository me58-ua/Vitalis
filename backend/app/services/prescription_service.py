# Servicio de recetas: crea, consulta, autoriza, descarga y gestiona recetas médicas.
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.models import AppointmentStatus, Prescription, PrescriptionAuthorization, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.prescriptions import PrescriptionAuthorizationCreate, PrescriptionMetadata
from app.models import AuditAction
from app.services.audit_service import AuditService
from app.services.file_storage import FileStorage


class PrescriptionNotFoundError(Exception):
    pass


class PrescriptionAccessError(Exception):
    pass


class PrescriptionValidationError(Exception):
    pass


class PrescriptionConflictError(Exception):
    pass


DEFAULT_PRESCRIPTION_EMISSION_WINDOW = timedelta(hours=8)
PRESCRIPTION_MAX_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_PRESCRIPTION_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


class PrescriptionService:
    def __init__(
        self,
        appointments: AppointmentRepository,
        profiles: ProfileRepository,
        prescriptions: PrescriptionRepository,
        storage: FileStorage,
        emission_window: timedelta = DEFAULT_PRESCRIPTION_EMISSION_WINDOW,
        max_file_size: int = PRESCRIPTION_MAX_SIZE_BYTES,
        now=None,
        audits: AuditRepository | None = None,
    ):
        self.appointments = appointments
        self.profiles = profiles
        self.prescriptions = prescriptions
        self.storage = storage
        self.emission_window = emission_window
        self.max_file_size = max_file_size
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.audit = AuditService(audits)

    def upload(
        self,
        professional_id: UUID,
        current_user: User,
        appointment_id: UUID,
        file: BinaryIO,
        filename: str,
        content_type: str | None,
        notas: str | None,
        *,
        metadata: PrescriptionMetadata,
    ) -> Prescription:
        self._require_identity(professional_id, current_user.id)
        appointment = self.appointments.get_appointment(appointment_id)
        if appointment is None:
            raise PrescriptionNotFoundError("Appointment not found")
        if appointment.professional_id != professional_id:
            raise PrescriptionAccessError("Appointment does not belong to this professional")
        if appointment.status != AppointmentStatus.COMPLETED:
            raise PrescriptionValidationError("Prescription requires a completed appointment")
        authorization = self.prescriptions.get_authorization(appointment.id)
        if not self.can_upload_prescription(appointment) and authorization is None:
            raise PrescriptionAccessError("ventana de emisión de receta expirada")
        if content_type not in ALLOWED_PRESCRIPTION_CONTENT_TYPES:
            raise PrescriptionValidationError("Prescription must be a PDF, JPEG, or PNG file")

        patient_profile = self.profiles.get_patient(appointment.patient_id)
        professional_profile = self.profiles.get_professional(professional_id)
        if patient_profile is None or professional_profile is None:
            raise PrescriptionValidationError("Prescription profiles are not available")

        existing = self.prescriptions.get_by_appointment(appointment.id)
        key = self._storage_key(appointment.id, filename)
        values = {**metadata.model_dump(), "notas": notas, "file_url": key,
                  "patient_id": patient_profile.id, "professional_id": professional_profile.id}
        try:
            self.storage.save(file, key, self.max_file_size)
            if existing:
                result = self.prescriptions.update(
                    existing,
                    values,
                )
                action = AuditAction.UPDATE
            else:
                result = self.prescriptions.create(
                    Prescription(
                        appointment_id=appointment.id,
                        **values,
                    )
                )
                action = AuditAction.CREATE
            self.audit.record(
                current_user.id,
                current_user.role,
                action,
                "prescription",
                result.id,
                patient_profile.user_id,
            )
            return result
        except ValueError as error:
            raise PrescriptionValidationError(str(error)) from error
        except IntegrityError as error:
            self.prescriptions.rollback()
            raise PrescriptionConflictError("Could not save prescription") from error

    def authorize_late_issue(
        self,
        appointment_id: UUID,
        current_admin: User,
        data: PrescriptionAuthorizationCreate,
    ) -> PrescriptionAuthorization:
        appointment = self.appointments.get_appointment(appointment_id)
        if appointment is None:
            raise PrescriptionNotFoundError("Appointment not found")
        if appointment.status != AppointmentStatus.COMPLETED:
            raise PrescriptionValidationError("Prescription requires a completed appointment")
        existing = self.prescriptions.get_authorization(appointment_id)
        if existing is not None:
            return existing
        try:
            result = self.prescriptions.create_authorization(
                PrescriptionAuthorization(
                    appointment_id=appointment_id,
                    authorized_by=current_admin.id,
                    reason=data.reason,
                )
            )
            patient_profile = self.profiles.get_patient(appointment.patient_id)
            self.audit.record(
                current_admin.id,
                current_admin.role,
                AuditAction.CREATE,
                "prescription_authorization",
                result.id,
                patient_profile.user_id if patient_profile else None,
            )
            return result
        except IntegrityError as error:
            self.prescriptions.rollback()
            raise PrescriptionConflictError("Could not authorize late prescription") from error

    def download_for_patient(self, appointment_id: UUID, current_user: User):
        appointment = self.appointments.get_appointment(appointment_id)
        if appointment is None:
            raise PrescriptionNotFoundError("Appointment not found")
        if appointment.patient_id != current_user.id:
            raise PrescriptionAccessError("Appointment does not belong to this patient")
        prescription = self.prescriptions.get_by_appointment(appointment_id)
        if prescription is None:
            raise PrescriptionNotFoundError("Prescription not found")
        path = self.storage.path_for(prescription.file_url)
        if not path.is_file():
            raise PrescriptionNotFoundError("Prescription file not found")
        return prescription, path

    def download_for_professional(self, professional_id: UUID, appointment_id: UUID, current_user: User):
        self._require_identity(professional_id, current_user.id)
        appointment = self.appointments.get_appointment(appointment_id)
        if appointment is None:
            raise PrescriptionNotFoundError("Appointment not found")
        if appointment.professional_id != professional_id:
            raise PrescriptionAccessError("Appointment does not belong to this professional")
        prescription = self.prescriptions.get_by_appointment(appointment_id)
        if prescription is None:
            raise PrescriptionNotFoundError("Prescription not found")
        path = self.storage.path_for(prescription.file_url)
        if not path.is_file():
            raise PrescriptionNotFoundError("Prescription file not found")
        return prescription, path

    def list_for_patient_view(
        self, patient_id: UUID, current_user: User, professional_id: UUID | None = None
    ) -> list[dict]:
        self._require_patient_identity(patient_id, current_user.id)
        patient_profile = self.profiles.get_patient(current_user.id)
        if patient_profile is None:
            raise PrescriptionNotFoundError("Patient profile not found")
        rows = self.prescriptions.list_for_patient_view(current_user.id, professional_id)
        return [
            {
                "id": prescription.id,
                "appointment_id": prescription.appointment_id,
                "patient_id": prescription.patient_id,
                "professional_id": prescription.professional_id,
                "professional_name": professional.name,
                "appointment_date": appointment.start_time,
                "appointment_reason": appointment.appointment_reason,
                "file_url": prescription.file_url,
                "download_url": f"/patients/me/appointments/{prescription.appointment_id}/prescription",
                "notas": prescription.notas,
                "created_at": prescription.created_at,
                **{field: getattr(prescription, field) for field in PrescriptionMetadata.model_fields},
            }
            for prescription, appointment, professional in rows
        ]

    def can_upload_prescription(self, appointment) -> bool:
        if appointment.status != AppointmentStatus.COMPLETED:
            return False
        end_time = appointment.end_time
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        return self.now() <= end_time + self.emission_window

    @staticmethod
    def _require_identity(path_id: UUID, user_id: UUID) -> None:
        if path_id != user_id:
            raise PrescriptionAccessError("Professional identity does not match the URL")

    @staticmethod
    def _require_patient_identity(path_id: UUID, user_id: UUID) -> None:
        if path_id != user_id:
            raise PrescriptionAccessError("Patient identity does not match the URL")

    @staticmethod
    def _storage_key(appointment_id: UUID, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return f"prescriptions/{appointment_id}{suffix}"
