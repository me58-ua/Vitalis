import unittest
import uuid
from datetime import time
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.models import UserRole
from app.schemas.appointments import AdminScheduleCreate, ProfessionalScheduleUpdate
from app.services.appointment_service import (
    AppointmentAccessError,
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentValidationError,
)
from app.services.schedule_service import ScheduleService


class FakeScheduleRepository:
    def __init__(self, schedule):
        self.schedule = schedule
        self.created_schedules = []
        self.rolled_back = False
        self.fail_create_schedule = False
        self.fail_update_schedule = False

    def create_schedule(self, schedule):
        if self.fail_create_schedule:
            raise IntegrityError("insert schedule", {}, Exception("conflict"))
        self.created_schedules.append(schedule)
        return schedule

    def get_schedule(self, schedule_id):
        if self.schedule and self.schedule.id == schedule_id:
            return self.schedule
        return None

    def update_schedule(self, schedule, values):
        if self.fail_update_schedule:
            raise IntegrityError("update schedule", {}, Exception("conflict"))
        for field, value in values.items():
            setattr(schedule, field, value)
        return schedule

    def rollback(self):
        self.rolled_back = True


class FakeUserRepository:
    def __init__(self, users):
        self.users = {user.id: user for user in users}

    def get_by_id(self, user_id):
        return self.users.get(user_id)


class ScheduleServiceTests(unittest.TestCase):
    def setUp(self):
        self.professional_id = uuid.uuid4()
        self.patient_id = uuid.uuid4()
        self.professional = SimpleNamespace(
            id=self.professional_id, role=UserRole.PROFESSIONAL
        )
        self.patient = SimpleNamespace(id=self.patient_id, role=UserRole.PATIENT)
        self.schedule = SimpleNamespace(
            id=uuid.uuid4(),
            professional_id=self.professional_id,
            channel="in_person",
            day_of_week=0,
            start_time=time(9),
            end_time=time(17),
            slot_duration_min=30,
            is_active=True,
        )
        self.repository = FakeScheduleRepository(self.schedule)
        self.users = FakeUserRepository([self.patient, self.professional])
        self.service = ScheduleService(self.repository, self.users)

    def _schedule_data(self, professional_id=None):
        return AdminScheduleCreate(
            professional_id=professional_id or self.professional_id,
            day_of_week=1,
            start_time=time(9),
            end_time=time(17),
            slot_duration_min=30,
            is_active=True,
        )

    def test_create_schedule_succeeds_for_a_professional(self):
        result = self.service.create_schedule(self._schedule_data())

        self.assertEqual(result.professional_id, self.professional_id)
        self.assertEqual(len(self.repository.created_schedules), 1)

    def test_create_schedule_rejects_missing_or_wrong_role_professional(self):
        for professional_id in (uuid.uuid4(), self.patient_id):
            with self.subTest(professional_id=professional_id):
                with self.assertRaises(AppointmentNotFoundError):
                    self.service.create_schedule(self._schedule_data(professional_id))

    def test_create_schedule_translates_conflict_and_rolls_back(self):
        self.repository.fail_create_schedule = True

        with self.assertRaises(AppointmentConflictError):
            self.service.create_schedule(self._schedule_data())

        self.assertTrue(self.repository.rolled_back)

    def test_update_schedule_allows_partial_data(self):
        result = self.service.update_schedule_as_professional(
            self.professional_id,
            self.professional,
            self.schedule.id,
            ProfessionalScheduleUpdate(end_time=time(18)),
        )

        self.assertEqual(result.end_time, time(18))
        self.assertEqual(result.start_time, time(9))

    def test_update_schedule_rejects_identity_missing_and_foreign_schedule(self):
        with self.assertRaises(AppointmentAccessError):
            self.service.update_schedule_as_professional(
                uuid.uuid4(), self.professional, self.schedule.id, ProfessionalScheduleUpdate()
            )

        with self.assertRaises(AppointmentNotFoundError):
            self.service.update_schedule_as_professional(
                self.professional_id,
                self.professional,
                uuid.uuid4(),
                ProfessionalScheduleUpdate(),
            )

        self.schedule.professional_id = uuid.uuid4()
        with self.assertRaises(AppointmentAccessError):
            self.service.update_schedule_as_professional(
                self.professional_id,
                self.professional,
                self.schedule.id,
                ProfessionalScheduleUpdate(),
            )

    def test_update_schedule_rejects_invalid_resulting_ranges(self):
        with self.assertRaises(AppointmentValidationError):
            self.service.update_schedule_as_professional(
                self.professional_id,
                self.professional,
                self.schedule.id,
                ProfessionalScheduleUpdate(start_time=time(18), end_time=time(17)),
            )

        with self.assertRaises(AppointmentValidationError):
            self.service.update_schedule_as_professional(
                self.professional_id,
                self.professional,
                self.schedule.id,
                ProfessionalScheduleUpdate(start_time=time(18)),
            )

    def test_update_schedule_translates_conflict_and_rolls_back(self):
        self.repository.fail_update_schedule = True

        with self.assertRaises(AppointmentConflictError):
            self.service.update_schedule_as_professional(
                self.professional_id,
                self.professional,
                self.schedule.id,
                ProfessionalScheduleUpdate(end_time=time(18)),
            )

        self.assertTrue(self.repository.rolled_back)

    def test_get_professional_checks_existence_and_role(self):
        self.assertIs(
            self.service._get_professional(self.professional_id), self.professional
        )

        for professional_id in (uuid.uuid4(), self.patient_id):
            with self.subTest(professional_id=professional_id):
                with self.assertRaises(AppointmentNotFoundError):
                    self.service._get_professional(professional_id)


if __name__ == "__main__":
    unittest.main()
