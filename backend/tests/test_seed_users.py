import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import MetaData, create_engine, func, select
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import sessionmaker

from app.models import (User, UserRole, PatientProfile, ProfessionalProfile, ProfessionalApprovalStatus,
                        Appointment, AppointmentStatus, AppointmentType, ProfessionalPatient, Allergy, ChronicCondition)
from app.repositories.professional_repository import ProfessionalRepository
from app.services.professional_service import ProfessionalService
from app.repositories.user_repository import UserRepository
from app.scripts.seed_users import DEMO_USERS, SEED_USERS, seed_users
from app.services.auth_service import AuthService


class SeedUsersTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        # SQLite checks seed data and slot selection. PostgreSQL alone enforces
        # its GiST exclusion constraint; remove it only from this metadata copy.
        self.tables = [model.__table__ for model in
                       (User, PatientProfile, ProfessionalProfile, Appointment, ProfessionalPatient, Allergy, ChronicCondition)]
        metadata = MetaData()
        for table in self.tables:
            copy = table.to_metadata(metadata)
            for constraint in list(copy.constraints):
                if isinstance(constraint, ExcludeConstraint):
                    copy.constraints.remove(constraint)
        metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

    def test_three_login_accounts_profiles_and_no_other_records(self):
        self.assertEqual(seed_users(self.sessions, include_demo=False), 3)
        with self.sessions() as db:
            counts = {
                table.name: db.scalar(select(func.count()).select_from(table))
                for table in self.tables
            }
            self.assertEqual(counts.pop("users"), 3)
            self.assertEqual(counts.pop("patient_profiles"), 1)
            self.assertEqual(counts.pop("professional_profiles"), 1)
            self.assertTrue(all(count == 0 for count in counts.values()), counts)
            for seed in SEED_USERS:
                account = AuthService(UserRepository(db)).authenticate(seed.username, seed.password)
                self.assertEqual(account.role, seed.role)
                self.assertTrue(account.is_active)
            patient = db.scalar(select(PatientProfile))
            self.assertEqual(float(patient.height_cm), 165)
            self.assertEqual(float(patient.weight_kg), 62)
            self.assertEqual(patient.birth_date, patient.user.birth_date)
            self.assertEqual(patient.timezone, "Europe/Madrid")
            self.assertFalse(patient.onboarding_completed)
            self.assertFalse(patient.ai_processing_consent)
            self.assertFalse(patient.share_health_data)
            professional = db.scalar(select(ProfessionalProfile))
            self.assertEqual(professional.approval_status, ProfessionalApprovalStatus.APPROVED)
            self.assertEqual(db.get(User, professional.reviewed_by).role, UserRole.ADMIN)

    def test_rerun_preserves_profiles_passwords_and_ids(self):
        seed_users(self.sessions, include_demo=False)
        with self.sessions.begin() as db:
            patient = db.scalar(select(PatientProfile))
            patient.weight_kg = 70
            account = patient.user
            original_id = account.id
            original_hash = account.password_hash
        self.assertEqual(seed_users(self.sessions, include_demo=False), 0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 3)
            account = db.get(User, original_id)
            self.assertEqual(account.password_hash, original_hash)
            self.assertEqual(float(account.patient_profile.weight_kg), 70)

    def test_demo_accounts_bookings_assignments_and_rerun(self):
        now = datetime(2026, 11, 6, 20, tzinfo=timezone.utc)  # Friday; skip weekend.
        self.assertEqual(seed_users(self.sessions, now=now), 26)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(PatientProfile)), 19)
            profiles = list(db.scalars(select(ProfessionalProfile)))
            self.assertEqual(len(profiles), 6)
            self.assertEqual(len({p.specialty for p in profiles}), 6)
            self.assertTrue(all(p.approval_status == ProfessionalApprovalStatus.APPROVED for p in profiles))
            first = db.scalar(select(User).where(User.email == 'professional1@vitalis.local'))
            appointments = list(db.scalars(select(Appointment)))
            self.assertEqual(len(appointments), 64)
            self.assertEqual(sum(a.professional_id == first.id for a in appointments), 39)
            future = [a for a in appointments if a.status != AppointmentStatus.COMPLETED]
            self.assertEqual(len(future), 34)
            historical = [a for a in appointments if a.status == AppointmentStatus.COMPLETED]
            self.assertEqual(len(historical), 30)
            local_now = now.astimezone(ZoneInfo('Europe/Madrid'))
            historical_dates = [a.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Madrid')).date() for a in historical]
            self.assertEqual(sum(day == local_now.date() - timedelta(days=1) for day in historical_dates), 8)
            previous_month = (local_now.date().replace(day=1) - timedelta(days=1)).month
            self.assertEqual(sum(day.month == previous_month for day in historical_dates), 22)
            page = ProfessionalService(ProfessionalRepository(db)).list_my_patients(first.id, None, 1, 20)
            self.assertEqual(page.total, 19)
            self.assertEqual(len(page.patients), 19)
            self.assertTrue(all(p.allergies_summary is None and p.chronic_conditions_summary is None for p in page.patients))
            for item in appointments:
                start = item.start_time.replace(tzinfo=timezone.utc)
                if item.status == AppointmentStatus.COMPLETED:
                    self.assertLess(item.end_time.replace(tzinfo=timezone.utc), now)
                else:
                    self.assertGreater(start, now)
                    self.assertLess(start, now + timedelta(days=20))
                    self.assertLess(start.weekday(), 5)
                self.assertNotIn('sintético', item.appointment_reason)
                self.assertNotIn('desarrollo', item.appointment_reason)
                self.assertEqual(item.end_time - item.start_time, timedelta(minutes=30))
                self.assertEqual(item.type, AppointmentType.VIDEO)
                for other in appointments:
                    if item.id != other.id and (item.professional_id == other.professional_id or item.patient_id == other.patient_id):
                        self.assertFalse(item.start_time < other.end_time and item.end_time > other.start_time)
            assignments = list(db.scalars(select(ProfessionalPatient)))
            self.assertEqual(len(assignments), 34)
            for link in assignments:
                self.assertTrue(any(a.patient_id == link.patient_id and a.professional_id == link.professional_id for a in appointments))
            original = {a.id: (a.start_time, a.room_id, a.status) for a in appointments}
            for seed in DEMO_USERS:
                self.assertEqual(AuthService(UserRepository(db)).authenticate(seed.username, seed.password).name, seed.name)
        self.assertEqual(seed_users(self.sessions, now=now + timedelta(days=1)), 0)
        with self.sessions() as db:
            self.assertEqual(original, {a.id: (a.start_time, a.room_id, a.status) for a in db.scalars(select(Appointment))})
            self.assertEqual(db.scalar(select(func.count()).select_from(ProfessionalPatient)), 34)

    def test_existing_patient_or_professional_booking_moves_new_seed_slot(self):
        now = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        seed_users(self.sessions, include_demo=False)
        with self.sessions.begin() as db:
            patient = db.scalar(select(User).where(User.email == 'patient1@vitalis.local'))
            professional = db.scalar(select(User).where(User.email == 'professional1@vitalis.local'))
            patient_id = patient.id
            db.add(Appointment(patient_id=patient.id, professional_id=professional.id,
                               start_time=datetime(2026, 11, 5, 8, tzinfo=timezone.utc),
                               end_time=datetime(2026, 11, 5, 9, tzinfo=timezone.utc),
                               type=AppointmentType.VIDEO, status=AppointmentStatus.CONFIRMED))
        seed_users(self.sessions, now=now)
        with self.sessions() as db:
            rows = list(db.scalars(select(Appointment).where(Appointment.patient_id == patient_id)))
            self.assertEqual(len(rows), 6)  # Existing + 2 future + 3 historical.
            for item in rows:
                for other in rows:
                    if item.id != other.id:
                        self.assertFalse(item.start_time < other.end_time and item.end_time > other.start_time)

    def test_cancelled_seed_does_not_create_an_assignment_on_rerun(self):
        now = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        seed_users(self.sessions, now=now)
        with self.sessions.begin() as db:
            patient = db.scalar(select(User).where(User.email == 'patient19@vitalis.local'))
            appointment = db.scalar(select(Appointment).where(Appointment.patient_id == patient.id))
            appointment.status = AppointmentStatus.CANCELLED
            pair = (appointment.professional_id, appointment.patient_id)
            db.delete(db.get(ProfessionalPatient, pair))
        seed_users(self.sessions, now=now)
        with self.sessions() as db:
            self.assertIsNone(db.get(ProfessionalPatient, pair))

    def test_naive_seed_time_is_rejected(self):
        with self.assertRaises(ValueError):
            seed_users(self.sessions, now=datetime(2026, 11, 4))

    def test_rerun_upgrades_old_seed_text_without_overwriting_custom_text(self):
        now = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
        seed_users(self.sessions, now=now)
        with self.sessions.begin() as db:
            rows = list(db.scalars(select(Appointment).where(Appointment.status == AppointmentStatus.CONFIRMED).limit(2)))
            legacy_id, edited_id = rows[0].id, rows[1].id
            rows[0].appointment_reason = 'Consulta de seguimiento (datos sintéticos de desarrollo).'
            rows[1].appointment_reason = 'Revisión acordada con el paciente'
            profile = db.scalar(select(ProfessionalProfile))
            profile_id = profile.id
            profile.bio = 'Perfil sintético para desarrollo local de Vitalis.'
        seed_users(self.sessions, now=now)
        with self.sessions() as db:
            self.assertEqual(db.get(Appointment, legacy_id).appointment_reason, 'Consulta de seguimiento')
            self.assertEqual(db.get(Appointment, edited_id).appointment_reason, 'Revisión acordada con el paciente')
            self.assertNotIn('sintético', db.get(ProfessionalProfile, profile_id).bio)

    def test_history_stays_past_on_monday_and_across_year_boundary(self):
        now = datetime(2027, 1, 4, 8, tzinfo=timezone.utc)  # Monday; yesterday is Sunday.
        seed_users(self.sessions, now=now)
        with self.sessions() as db:
            completed = list(db.scalars(select(Appointment).where(Appointment.status == AppointmentStatus.COMPLETED)))
            dates = [a.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Madrid')).date() for a in completed]
            self.assertEqual(sum(day.isoformat() == '2027-01-03' for day in dates), 8)
            self.assertEqual(sum(day.year == 2026 and day.month == 12 for day in dates), 22)


if __name__ == "__main__":
    unittest.main()
