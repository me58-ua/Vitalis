import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.models import AppointmentStatus, AppointmentType, UserRole
from app.schemas.appointments import (
    AdminAppointmentCreate,
    AdminAppointmentUpdate,
    AppointmentCancelRequest,
    ConsultationNoteCreate,
    ConsultationNoteUpdate,
    ProfessionalAppointmentStatusUpdate,
    ProfessionalAppointmentCreate,
)
from app.services.appointment_service import (
    AppointmentAccessError,
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentService,
    AppointmentValidationError,
)


class FakeAppointmentRepository:
    def __init__(self, appointment):
        self.appointment = appointment
        self.history = []
        self.notes = []
        self.created_appointments = []
        self.rolled_back = False
        self.fail_create_appointment = False

    def get_appointment(self, appointment_id):
        return self.appointment if self.appointment and self.appointment.id == appointment_id else None

    def update_appointment(self, appointment, values):
        for field, value in values.items():
            setattr(appointment, field, value)
        return appointment

    def create_status_history(self, history):
        self.history.append(history)
        return history

    def create_appointment(self, appointment):
        if self.fail_create_appointment:
            raise IntegrityError("insert appointment", {}, Exception("conflict"))
        self.created_appointments.append(appointment)
        return appointment

    def create_note(self, note):
        self.notes.append(note)
        return note

    def get_note(self, note_id):
        return self.note if self.note.id == note_id else None

    def update_note(self, note, values):
        for field, value in values.items():
            setattr(note, field, value)
        return note

    def rollback(self):
        self.rolled_back = True


class FakeUserRepository:
    def __init__(self, users):
        self.users = {user.id: user for user in users}

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class FakeProfessionalRepository:
    def __init__(self, assigned_patient_id):
        self.assigned_patient_id = assigned_patient_id

    def has_patient_assignment(self, professional_id, patient_id):
        return patient_id == self.assigned_patient_id


class FakeAuditRepository:
    def __init__(self):
        self.logs = []

    def create(self, log):
        self.logs.append(log)
        return log


class AppointmentServiceTests(unittest.TestCase):
    def setUp(self):
        self.professional_id = uuid.uuid4()
        self.patient_id = uuid.uuid4()
        self.appointment_id = uuid.uuid4()
        self.admin_id = uuid.uuid4()
        self.professional = SimpleNamespace(id=self.professional_id, role=UserRole.PROFESSIONAL)
        self.patient = SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT)
        self.admin = SimpleNamespace(id=self.admin_id, role=UserRole.ADMIN)
        self.appointment = SimpleNamespace(
            id=self.appointment_id,
            patient_id=self.patient_id,
            professional_id=self.professional_id,
            start_time=datetime(2026, 9, 22, 10, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 22, 11, tzinfo=timezone.utc),
            status=AppointmentStatus.PENDING,
            type=AppointmentType.VIDEO,
            reason=None,
        )
        self.repository = FakeAppointmentRepository(self.appointment)
        self.users = FakeUserRepository([self.patient, self.professional])
        self.professionals = FakeProfessionalRepository(self.patient_id)
        self.service = AppointmentService(self.repository, self.users, self.professionals)
        self.note = SimpleNamespace(
            id=uuid.uuid4(),
            appointment_id=self.appointment_id,
            professional_id=self.professional_id,
            clinical_notes="Initial note",
            patient_summary="Initial summary",
            diagnosis="Initial diagnosis",
            created_at=datetime.now(timezone.utc),
        )
        self.repository.note = self.note

    def _admin_appointment_data(self, **overrides):
        values = {
            "patient_id": self.patient_id,
            "professional_id": self.professional_id,
            "start_time": datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
            "end_time": datetime(2026, 9, 22, 13, tzinfo=timezone.utc),
            "type": AppointmentType.VIDEO,
            "reason": "Follow-up",
        }
        values.update(overrides)
        return AdminAppointmentCreate(**values)

    def test_admin_can_create_appointment_for_valid_users(self):
        result = self.service.create_appointment(self._admin_appointment_data())

        self.assertEqual(result.patient_id, self.patient_id)
        self.assertEqual(result.professional_id, self.professional_id)
        self.assertEqual(len(self.repository.created_appointments), 1)

    def test_admin_create_rejects_missing_or_wrong_role_users(self):
        cases = (
            {"patient_id": uuid.uuid4()},
            {"patient_id": self.professional_id},
            {"professional_id": uuid.uuid4()},
            {"professional_id": self.patient_id},
        )

        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(AppointmentNotFoundError):
                    self.service.create_appointment(self._admin_appointment_data(**overrides))

    def test_admin_create_rejects_invalid_time_range(self):
        data = AdminAppointmentCreate.model_construct(
            patient_id=self.patient_id,
            professional_id=self.professional_id,
            start_time=datetime(2026, 9, 22, 13, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
            type=AppointmentType.VIDEO,
            reason=None,
        )

        with self.assertRaises(AppointmentValidationError):
            self.service.create_appointment(data)

    def test_admin_create_translates_conflict_and_rolls_back(self):
        self.repository.fail_create_appointment = True

        with self.assertRaises(AppointmentConflictError):
            self.service.create_appointment(self._admin_appointment_data())

        self.assertTrue(self.repository.rolled_back)

    def test_get_user_returns_matching_role_and_rejects_missing_or_wrong_role(self):
        self.assertIs(self.service._get_user(self.patient_id, UserRole.PATIENT), self.patient)

        with self.assertRaises(AppointmentNotFoundError):
            self.service._get_user(uuid.uuid4(), UserRole.PATIENT)
        with self.assertRaises(AppointmentNotFoundError):
            self.service._get_user(self.professional_id, UserRole.PATIENT)

    def test_professional_can_create_for_assigned_patient(self):
        data = ProfessionalAppointmentCreate(
            patient_id=self.patient_id,
            start_time=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 22, 13, tzinfo=timezone.utc),
            type=AppointmentType.IN_PERSON,
        )

        result = self.service.create_for_professional(
            self.professional_id, self.professional, data
        )

        self.assertEqual(result.patient_id, self.patient_id)
        self.assertEqual(result.professional_id, self.professional_id)

    def test_professional_create_rejects_identity_patient_and_assignment_errors(self):
        data = ProfessionalAppointmentCreate(
            patient_id=self.patient_id,
            start_time=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 22, 13, tzinfo=timezone.utc),
            type=AppointmentType.IN_PERSON,
        )

        with self.assertRaises(AppointmentAccessError):
            self.service.create_for_professional(uuid.uuid4(), self.professional, data)

        for patient_id in (uuid.uuid4(), self.professional_id):
            with self.subTest(patient_id=patient_id):
                invalid_data = data.model_copy(update={"patient_id": patient_id})
                with self.assertRaises(AppointmentNotFoundError):
                    self.service.create_for_professional(
                        self.professional_id, self.professional, invalid_data
                    )

        self.professionals.assigned_patient_id = uuid.uuid4()
        with self.assertRaises(AppointmentAccessError):
            self.service.create_for_professional(self.professional_id, self.professional, data)

    def test_professional_create_translates_conflict(self):
        self.repository.fail_create_appointment = True
        data = ProfessionalAppointmentCreate(
            patient_id=self.patient_id,
            start_time=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 22, 13, tzinfo=timezone.utc),
            type=AppointmentType.IN_PERSON,
        )

        with self.assertRaises(AppointmentConflictError):
            self.service.create_for_professional(self.professional_id, self.professional, data)

    def test_admin_status_update_records_old_new_actor_and_reason(self):
        result = self.service.update_as_admin(
            self.appointment_id,
            AdminAppointmentUpdate(
                status=AppointmentStatus.CONFIRMED,
                reason="Patient confirmed",
            ),
            self.admin,
        )

        self.assertEqual(result.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(len(self.repository.history), 1)
        history = self.repository.history[0]
        self.assertEqual(history.old_status, AppointmentStatus.PENDING)
        self.assertEqual(history.new_status, AppointmentStatus.CONFIRMED)
        self.assertEqual(history.changed_by, self.admin_id)
        self.assertEqual(history.reason, "Patient confirmed")

    def test_professional_can_book_assigned_patient(self):
        data = ProfessionalAppointmentCreate(
            patient_id=self.patient_id,
            start_time=datetime(2026, 9, 22, 12, tzinfo=timezone.utc),
            end_time=datetime(2026, 9, 22, 13, tzinfo=timezone.utc),
            type=AppointmentType.IN_PERSON,
        )

        result = self.service.create_for_professional(
            self.professional_id, self.professional, data
        )

        self.assertEqual(result.patient_id, self.patient_id)
        self.assertEqual(result.professional_id, self.professional_id)
        self.assertEqual(result.status, None)
        self.assertEqual(len(self.repository.created_appointments), 1)

    def test_professional_cannot_write_note_for_another_professional(self):
        other_professional_id = uuid.uuid4()
        data = ConsultationNoteCreate(
            appointment_id=self.appointment_id,
            clinical_notes="Private note",
            patient_summary="Summary",
            diagnosis="Diagnosis",
        )

        with self.assertRaises(AppointmentAccessError):
            self.service.create_consultation_note(
                other_professional_id,
                SimpleNamespace(id=other_professional_id, role=UserRole.PROFESSIONAL),
                data,
            )

    def test_professional_can_create_consultation_note_for_owned_appointment(self):
        data = ConsultationNoteCreate(
            appointment_id=self.appointment_id,
            clinical_notes="Private note",
            patient_summary="Summary",
            diagnosis="Diagnosis",
        )

        result = self.service.create_consultation_note(
            self.professional_id, self.professional, data
        )

        self.assertEqual(result.appointment_id, self.appointment_id)
        self.assertEqual(result.professional_id, self.professional_id)
        self.assertEqual(len(self.repository.notes), 1)

    def test_professional_status_update_records_audit_history(self):
        result = self.service.update_status_as_professional(
            self.professional_id,
            self.professional,
            self.appointment_id,
            ProfessionalAppointmentStatusUpdate(
                status=AppointmentStatus.COMPLETED,
                reason="Consultation finished",
            ),
        )

        self.assertEqual(result.status, AppointmentStatus.COMPLETED)
        self.assertEqual(self.repository.history[-1].old_status, AppointmentStatus.PENDING)
        self.assertEqual(self.repository.history[-1].changed_by, self.professional_id)

    def test_consultation_note_update_does_not_change_appointment_id(self):
        result = self.service.update_consultation_note(
            self.professional_id,
            self.professional,
            self.note.id,
            ConsultationNoteUpdate(clinical_notes="Updated note"),
        )

        self.assertEqual(result.clinical_notes, "Updated note")
        self.assertEqual(result.appointment_id, self.appointment_id)

    def test_consultation_note_can_be_updated_within_edit_window(self):
        self.note.created_at = datetime.now(timezone.utc) - timedelta(hours=23)

        result = self.service.update_consultation_note(
            self.professional_id,
            self.professional,
            self.note.id,
            ConsultationNoteUpdate(diagnosis="Updated diagnosis"),
        )

        self.assertEqual(result.diagnosis, "Updated diagnosis")

    def test_consultation_note_cannot_be_updated_after_edit_window(self):
        self.note.created_at = datetime.now(timezone.utc) - timedelta(hours=24, seconds=1)

        with self.assertRaises(AppointmentValidationError):
            self.service.update_consultation_note(
                self.professional_id,
                self.professional,
                self.note.id,
                ConsultationNoteUpdate(diagnosis="Should not be saved"),
            )

        self.assertEqual(self.note.diagnosis, "Initial diagnosis")

    def test_patient_cancellation_is_audited_when_more_than_24_hours_away(self):
        self.appointment.start_time = datetime.now(timezone.utc) + timedelta(hours=48)

        result = self.service.cancel_appointment(
            self.patient_id,
            self.appointment_id,
            self.patient,
            AppointmentCancelRequest(reason="Schedule changed"),
            enforce_patient_notice=True,
        )

        self.assertEqual(result.status, AppointmentStatus.CANCELLED)
        history = self.repository.history[-1]
        self.assertEqual(history.old_status, AppointmentStatus.PENDING)
        self.assertEqual(history.new_status, AppointmentStatus.CANCELLED)
        self.assertEqual(history.changed_by, self.patient_id)
        self.assertEqual(history.reason, "Schedule changed")

    def test_cancellation_audit_is_a_modification_of_the_appointment(self):
        self.appointment.start_time = datetime.now(timezone.utc) + timedelta(hours=48)
        audits = FakeAuditRepository()
        service = AppointmentService(self.repository, self.users, self.professionals, audits=audits)

        service.cancel_appointment(
            self.patient_id,
            self.appointment_id,
            self.patient,
            AppointmentCancelRequest(reason="Schedule changed"),
            enforce_patient_notice=True,
        )

        self.assertEqual(len(audits.logs), 1)
        self.assertEqual(audits.logs[0].accion.value, "modificacion")
        self.assertEqual(audits.logs[0].entidad, "appointment")
        self.assertEqual(audits.logs[0].entidad_id, self.appointment_id)
        self.assertEqual(audits.logs[0].patient_id, self.patient_id)

    def test_routine_appointment_creation_is_not_audited(self):
        audits = FakeAuditRepository()
        service = AppointmentService(self.repository, self.users, self.professionals, audits=audits)

        service.create_appointment(self._admin_appointment_data())

        self.assertEqual(audits.logs, [])

    def test_clinical_note_creation_and_edit_are_audited(self):
        audits = FakeAuditRepository()
        service = AppointmentService(self.repository, self.users, self.professionals, audits=audits)
        created = service.create_consultation_note(
            self.professional_id,
            self.professional,
            ConsultationNoteCreate(appointment_id=self.appointment_id, diagnosis="Initial"),
        )
        created.created_at = datetime.now(timezone.utc)
        self.repository.note = created
        service.update_consultation_note(
            self.professional_id,
            self.professional,
            created.id,
            ConsultationNoteUpdate(diagnosis="Updated"),
        )

        self.assertEqual([log.accion.value for log in audits.logs], ["creacion", "modificacion"])
        self.assertEqual(audits.logs[0].entidad, "clinical_note")

    def test_patient_cannot_cancel_within_24_hours(self):
        self.appointment.start_time = datetime.now(timezone.utc) + timedelta(hours=23)

        with self.assertRaises(Exception):
            self.service.cancel_appointment(
                self.patient_id,
                self.appointment_id,
                self.patient,
                AppointmentCancelRequest(reason="Too late"),
                enforce_patient_notice=True,
            )
        self.assertEqual(self.appointment.status, AppointmentStatus.PENDING)
        self.assertEqual(self.repository.history, [])

    def test_professional_can_cancel_without_24_hour_restriction(self):
        self.appointment.start_time = datetime.now(timezone.utc) + timedelta(hours=1)

        result = self.service.cancel_appointment(
            self.professional_id,
            self.appointment_id,
            self.professional,
            AppointmentCancelRequest(reason="Professional emergency"),
            enforce_patient_notice=False,
        )

        self.assertEqual(result.status, AppointmentStatus.CANCELLED)
        self.assertEqual(self.repository.history[-1].changed_by, self.professional_id)


if __name__ == "__main__":
    unittest.main()
