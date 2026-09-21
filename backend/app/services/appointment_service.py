from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.models import (
    Appointment,
    AppointmentNote,
    AppointmentStatus,
    AppointmentStatusHistory,
    User,
    UserRole,
)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.professional_repository import ProfessionalRepository
from app.repositories.user_repository import UserRepository
from app.schemas.appointments import (
    AdminAppointmentCreate,
    AdminAppointmentUpdate,
    ConsultationNoteCreate,
    AppointmentCancelRequest,
    ConsultationNoteUpdate,
    ProfessionalAppointmentStatusUpdate,
    ProfessionalAppointmentCreate,
)


class AppointmentNotFoundError(Exception):
    pass


class AppointmentAccessError(Exception):
    pass


class AppointmentValidationError(Exception):
    pass


class AppointmentConflictError(Exception):
    pass


class AppointmentService:
    def __init__(
        self,
        appointments: AppointmentRepository,
        users: UserRepository,
        professionals: ProfessionalRepository,
    ):
        self.appointments = appointments
        self.users = users
        self.professionals = professionals

    def create_appointment(self, data: AdminAppointmentCreate) -> Appointment:
        patient = self._get_user(data.patient_id, UserRole.PATIENT)
        professional = self._get_user(data.professional_id, UserRole.PROFESSIONAL)
        if data.end_time <= data.start_time:
            raise AppointmentValidationError("end_time must be after start_time")

        appointment = Appointment(
            patient_id=patient.id,
            professional_id=professional.id,
            start_time=data.start_time,
            end_time=data.end_time,
            type=data.type,
            reason=data.reason,
        )
        return self._create_appointment(appointment)

    def update_as_admin(
        self,
        appointment_id,
        data: AdminAppointmentUpdate,
        changed_by: User,
    ) -> Appointment:
        appointment = self._get_appointment(appointment_id)
        values = data.model_dump(exclude_unset=True)
        old_status = appointment.status
        start_time = values.get("start_time", appointment.start_time)
        end_time = values.get("end_time", appointment.end_time)
        if end_time <= start_time:
            raise AppointmentValidationError("end_time must be after start_time")

        status_changed = "status" in values and values["status"] != old_status
        try:
            updated = self.appointments.update_appointment(appointment, values)
            if status_changed:
                self.appointments.create_status_history(
                    AppointmentStatusHistory(
                        appointment_id=appointment.id,
                        old_status=old_status,
                        new_status=values["status"],
                        changed_by=changed_by.id,
                        reason=data.reason,
                    )
                )
            return updated
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError(
                "Appointment conflicts with an existing booking"
            ) from error

    def create_for_professional(
        self,
        professional_id,
        current_user: User,
        data: ProfessionalAppointmentCreate,
    ) -> Appointment:
        self._require_path_identity(professional_id, current_user.id)
        patient = self._get_user(data.patient_id, UserRole.PATIENT)
        if not self.professionals.has_patient_assignment(
            professional_id, data.patient_id
        ):
            raise AppointmentAccessError("Patient is not assigned to this professional")

        appointment = Appointment(
            patient_id=patient.id,
            professional_id=professional_id,
            start_time=data.start_time,
            end_time=data.end_time,
            type=data.type,
            reason=data.reason,
        )
        return self._create_appointment(appointment)

    def create_consultation_note(
        self,
        professional_id,
        current_user: User,
        data: ConsultationNoteCreate,
    ) -> AppointmentNote:
        self._require_path_identity(professional_id, current_user.id)
        appointment = self._get_appointment(data.appointment_id)
        if appointment.professional_id != professional_id:
            raise AppointmentAccessError("Appointment does not belong to this professional")

        note = AppointmentNote(
            appointment_id=appointment.id,
            professional_id=professional_id,
            clinical_notes=data.clinical_notes,
            patient_summary=data.patient_summary,
            diagnosis=data.diagnosis,
        )
        try:
            return self.appointments.create_note(note)
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError(
                "A consultation note already exists for this appointment"
            ) from error

    def update_status_as_professional(
        self,
        professional_id,
        current_user: User,
        appointment_id,
        data: ProfessionalAppointmentStatusUpdate,
    ) -> Appointment:
        self._require_path_identity(professional_id, current_user.id)
        appointment = self._get_appointment(appointment_id)
        self._require_appointment_owner(appointment, professional_id)
        old_status = appointment.status
        if data.status == old_status:
            return appointment

        try:
            updated = self.appointments.update_appointment(
                appointment, {"status": data.status}
            )
            self.appointments.create_status_history(
                AppointmentStatusHistory(
                    appointment_id=appointment.id,
                    old_status=old_status,
                    new_status=data.status,
                    changed_by=professional_id,
                    reason=data.reason,
                )
            )
            return updated
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError("Could not update appointment status") from error

    def cancel_appointment(
        self,
        actor_path_id,
        appointment_id,
        current_user: User,
        data: AppointmentCancelRequest,
        enforce_patient_notice: bool,
    ) -> Appointment:
        if actor_path_id != current_user.id:
            raise AppointmentAccessError("User identity does not match the URL")
        appointment = self._get_appointment(appointment_id)
        if current_user.role == UserRole.PATIENT:
            if appointment.patient_id != current_user.id:
                raise AppointmentAccessError("Appointment does not belong to this patient")
        elif current_user.role == UserRole.PROFESSIONAL:
            self._require_appointment_owner(appointment, current_user.id)
        else:
            raise AppointmentAccessError("User cannot cancel this appointment")

        if enforce_patient_notice:
            minimum_cancel_time = datetime.now(timezone.utc) + timedelta(hours=24)
            if appointment.start_time <= minimum_cancel_time:
                raise AppointmentValidationError(
                    "Appointments can only be cancelled more than 24 hours before start time"
                )

        old_status = appointment.status
        if old_status == AppointmentStatus.CANCELLED:
            return appointment
        try:
            updated = self.appointments.update_appointment(
                appointment, {"status": AppointmentStatus.CANCELLED}
            )
            self.appointments.create_status_history(
                AppointmentStatusHistory(
                    appointment_id=appointment.id,
                    old_status=old_status,
                    new_status=AppointmentStatus.CANCELLED,
                    changed_by=current_user.id,
                    reason=data.reason,
                )
            )
            return updated
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError("Could not cancel appointment") from error

    def update_consultation_note(
        self,
        professional_id,
        current_user: User,
        note_id,
        data: ConsultationNoteUpdate,
    ) -> AppointmentNote:
        self._require_path_identity(professional_id, current_user.id)
        note = self.appointments.get_note(note_id)
        if note is None:
            raise AppointmentNotFoundError("Consultation note not found")
        if note.professional_id != professional_id:
            raise AppointmentAccessError("Consultation note does not belong to this professional")
        try:
            return self.appointments.update_note(
                note, data.model_dump(exclude_unset=True)
            )
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError("Could not update consultation note") from error

    def _get_appointment(self, appointment_id) -> Appointment:
        appointment = self.appointments.get_appointment(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError("Appointment not found")
        return appointment

    def _get_user(self, user_id, role: UserRole) -> User:
        user = self.users.get_by_id(user_id)
        if user is None or user.role != role:
            raise AppointmentNotFoundError(f"{role.value.capitalize()} not found")
        return user

    def _create_appointment(self, appointment: Appointment) -> Appointment:
        try:
            return self.appointments.create_appointment(appointment)
        except IntegrityError as error:
            self.appointments.rollback()
            raise AppointmentConflictError(
                "Appointment conflicts with an existing booking"
            ) from error

    @staticmethod
    def _require_appointment_owner(appointment: Appointment, professional_id) -> None:
        if appointment.professional_id != professional_id:
            raise AppointmentAccessError("Appointment does not belong to this professional")

    @staticmethod
    def _require_path_identity(path_id, current_user_id) -> None:
        if path_id != current_user_id:
            raise AppointmentAccessError("Professional identity does not match the URL")
