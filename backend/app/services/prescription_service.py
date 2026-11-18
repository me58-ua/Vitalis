# Servicio de recetas: crea, consulta, autoriza, descarga y gestiona recetas médicas.
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.models import AppointmentStatus, Notification, Prescription, User
from app.models.prescription import LatePrescriptionRequest
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.prescriptions import PrescriptionMetadata
from app.models import AuditAction
from app.services.audit_service import AuditService
from app.services.file_storage import FileStorage


class PrescriptionNotFoundError(Exception):
    pass


class PrescriptionAccessError(Exception):
    pass


class PrescriptionWindowExpiredError(PrescriptionAccessError):
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
        notifications: NotificationRepository | None = None,
    ):
        self.appointments = appointments
        self.profiles = profiles
        self.prescriptions = prescriptions
        self.storage = storage
        self.emission_window = emission_window
        self.max_file_size = max_file_size
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.audit = AuditService(audits)
        self.notifications = notifications

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
        late_reason: str | None = None,
    ) -> Prescription | LatePrescriptionRequest:
        self._require_identity(professional_id, current_user.id)
        appointment = self.appointments.lock_appointment(appointment_id)
        if appointment is None:
            raise PrescriptionNotFoundError("Appointment not found")
        if appointment.professional_id != professional_id:
            raise PrescriptionAccessError("Appointment does not belong to this professional")
        if appointment.status != AppointmentStatus.COMPLETED:
            raise PrescriptionValidationError("Prescription requires a completed appointment")
        within_window = self.can_upload_prescription(appointment)
        if not within_window and late_reason is None:
            raise PrescriptionWindowExpiredError("ventana de emisión de receta expirada")
        if late_reason is not None:
            late_reason = late_reason.strip()
            if within_window or not late_reason:
                raise PrescriptionValidationError("Indica un motivo para una emisión fuera de plazo")
        if content_type not in ALLOWED_PRESCRIPTION_CONTENT_TYPES:
            raise PrescriptionValidationError("Prescription must be a PDF, JPEG, or PNG file")

        patient_profile = self.profiles.get_patient(appointment.patient_id)
        professional_profile = self.profiles.get_professional(professional_id)
        if patient_profile is None or professional_profile is None:
            raise PrescriptionValidationError("Prescription profiles are not available")

        if late_reason is not None:
            return self._request_late_issue(appointment, current_user, file, content_type, notas, metadata, late_reason)
        key = self._storage_key(appointment.id, filename)
        values = {**metadata.model_dump(), "notas": notas, "file_url": key,
                  "patient_id": patient_profile.id, "professional_id": professional_profile.id}
        try:
            self.storage.save(file, key, self.max_file_size)
            result, action = self._publish(appointment.id, values)
            self.audit.record(current_user.id, current_user.role, action, "prescription", result.id,
                              appointment.patient_id)
            return result
        except ValueError as error:
            raise PrescriptionValidationError(str(error)) from error
        except IntegrityError as error:
            self.prescriptions.rollback()
            raise PrescriptionConflictError("Could not save prescription") from error

    def _publish(self, appointment_id: UUID, values: dict) -> tuple[Prescription, AuditAction]:
        existing = self.prescriptions.get_by_appointment(appointment_id)
        if existing:
            return self.prescriptions.update(existing, values), AuditAction.UPDATE
        return self.prescriptions.create(Prescription(appointment_id=appointment_id, **values)), AuditAction.CREATE

    def _request_late_issue(self, appointment, professional, file, content_type, notes, metadata, reason):
        notifications = self.notifications
        if notifications is None:
            raise RuntimeError("Late prescriptions require a notification repository")
        if self.prescriptions.get_pending_request(appointment.id) is not None:
            raise PrescriptionConflictError("Ya hay una solicitud pendiente para esta cita")
        admin_ids = notifications.active_admin_ids()
        if not admin_ids:
            raise PrescriptionConflictError("No hay administradores disponibles para revisar la solicitud")
        request_id = uuid4()
        extension = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}[content_type]
        key = f"prescriptions/late/{request_id}{extension}"
        draft = {**metadata.model_dump(mode="json"), "notas": notes, "file_url": key}
        try:
            request = self.prescriptions.create_late_request(LatePrescriptionRequest(
                id=request_id, appointment_id=appointment.id, requested_by=professional.id,
                reason=reason, draft=draft,
            ))
            for admin_id in admin_ids:
                notifications.create(Notification(
                    recipient_id=admin_id, type="late_prescription_pending",
                    entity="late_prescription_request", entity_id=request.id,
                    title="Urgente · Solicitud de emisión fuera de plazo",
                    message=f"Profesional: {professional.name}\nMotivo de la demora: {reason}",
                    scheduled_for=appointment.start_time,
                ))
            self.audit.record(professional.id, professional.role, AuditAction.CREATE,
                              "late_prescription_request", request.id)
            self.storage.save(file, key, self.max_file_size)
            return request
        except ValueError as error:
            raise PrescriptionValidationError(str(error)) from error
        except IntegrityError as error:
            raise PrescriptionConflictError("No se pudo registrar la solicitud o ya hay una pendiente") from error

    def authorize_late_issue(self, request_id: UUID, current_admin: User) -> None:
        notifications = self.notifications
        if notifications is None:
            raise RuntimeError("Late prescriptions require a notification repository")
        request = self.prescriptions.lock_late_request(request_id)
        if request is None:
            raise PrescriptionNotFoundError("Solicitud no encontrada")
        if request.approved_at is not None:
            return
        appointment = self.appointments.get_appointment(request.appointment_id)
        if appointment is None:
            raise PrescriptionNotFoundError("Appointment not found")
        if appointment.status != AppointmentStatus.COMPLETED or appointment.professional_id != request.requested_by:
            raise PrescriptionConflictError("La cita ya no admite esta solicitud")
        patient = self.profiles.get_patient(appointment.patient_id)
        professional = self.profiles.get_professional(request.requested_by)
        draft = request.draft
        if patient is None or professional is None or not draft or not self.storage.path_for(draft["file_url"]).is_file():
            raise PrescriptionConflictError("No se pudo vincular la receta a la cita")
        metadata = PrescriptionMetadata.model_validate(draft)
        try:
            self._publish(appointment.id, {
                **metadata.model_dump(), "notas": draft["notas"], "file_url": draft["file_url"],
                "patient_id": patient.id, "professional_id": professional.id,
            })
            request.approved_by = current_admin.id
            request.approved_at = self.now()
            request.draft = None
            self.audit.record(current_admin.id, current_admin.role, AuditAction.UPDATE,
                              "late_prescription_request", request.id)
            notifications.complete_late_prescription_alerts(request.id, request.approved_at)
            notifications.create(Notification(
                recipient_id=request.requested_by, type="late_prescription_approved",
                entity="late_prescription_request", entity_id=request.id, scheduled_for=appointment.start_time,
                title="Emisión fuera de plazo autorizada",
                message="Se concedió el permiso y la receta ya está vinculada a la cita y disponible para el paciente.",
            ))
        except IntegrityError as error:
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
