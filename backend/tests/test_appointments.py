import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import AppointmentStatus, AppointmentType, UserRole
from app.schemas.appointments import (
    AdminAppointmentUpdate,
    AppointmentCancelRequest,
    ConsultationNoteCreate,
    ConsultationNoteUpdate,
    ProfessionalAppointmentStatusUpdate,
    ProfessionalAppointmentCreate,
    ProfessionalScheduleUpdate,
)
from app.services.appointment_service import (
    AppointmentAccessError,
    AppointmentService,
)


class FakeAppointmentRepository:
    def __init__(self, appointment):
        self.appointment = appointment
        self.history = []
        self.notes = []
        self.created_appointments = []
        self.rolled_back = False

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
        self.created_appointments.append(appointment)
        return appointment

    def create_note(self, note):
        self.notes.append(note)
        return note

    def get_schedule(self, schedule_id):
        return self.schedule if self.schedule.id == schedule_id else None

    def get_note(self, note_id):
        return self.note if self.note.id == note_id else None

    def update_schedule(self, schedule, values):
        for field, value in values.items():
            setattr(schedule, field, value)
        return schedule

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
        self.schedule = SimpleNamespace(
            id=uuid.uuid4(),
            professional_id=self.professional_id,
            day_of_week=0,
            start_time=datetime(2026, 9, 22, 9, tzinfo=timezone.utc).time(),
            end_time=datetime(2026, 9, 22, 17, tzinfo=timezone.utc).time(),
            slot_duration_min=30,
            is_active=True,
        )
        self.note = SimpleNamespace(
            id=uuid.uuid4(),
            appointment_id=self.appointment_id,
            professional_id=self.professional_id,
            clinical_notes="Initial note",
            patient_summary="Initial summary",
            diagnosis="Initial diagnosis",
        )
        self.repository.schedule = self.schedule
        self.repository.note = self.note

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

    def test_professional_schedule_update_is_partial_and_validates_range(self):
        result = self.service.update_schedule_as_professional(
            self.professional_id,
            self.professional,
            self.schedule.id,
            ProfessionalScheduleUpdate(slot_duration_min=45),
        )
        self.assertEqual(result.slot_duration_min, 45)
        self.assertEqual(result.start_time.hour, 9)

        self.schedule.end_time = datetime(2026, 9, 22, 8, tzinfo=timezone.utc).time()
        with self.assertRaises(Exception):
            self.service.update_schedule_as_professional(
                self.professional_id,
                self.professional,
                self.schedule.id,
                ProfessionalScheduleUpdate(is_active=False),
            )

    def test_consultation_note_update_does_not_change_appointment_id(self):
        result = self.service.update_consultation_note(
            self.professional_id,
            self.professional,
            self.note.id,
            ConsultationNoteUpdate(clinical_notes="Updated note"),
        )

        self.assertEqual(result.clinical_notes, "Updated note")
        self.assertEqual(result.appointment_id, self.appointment_id)

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
