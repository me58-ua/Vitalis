import unittest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, UserRole, PatientProfile, ProfessionalProfile, ProfessionalApprovalStatus
from app.repositories.user_repository import UserRepository
from app.scripts.seed_users import SEED_USERS, seed_users
from app.services.auth_service import AuthService


class SeedUsersTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        # Only the three tables the seeder may write. An accidental clinical
        # insert fails here; PostgreSQL-specific appointment constraints are
        # intentionally outside this SQLite test.
        self.tables = [User.__table__, PatientProfile.__table__, ProfessionalProfile.__table__]
        Base.metadata.create_all(self.engine, tables=self.tables)
        self.sessions = sessionmaker(bind=self.engine)

    def test_three_login_accounts_profiles_and_no_other_records(self):
        self.assertEqual(seed_users(self.sessions), 3)
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
        seed_users(self.sessions)
        with self.sessions.begin() as db:
            patient = db.scalar(select(PatientProfile))
            patient.weight_kg = 70
            account = patient.user
            original_id = account.id
            original_hash = account.password_hash
        self.assertEqual(seed_users(self.sessions), 0)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 3)
            account = db.get(User, original_id)
            self.assertEqual(account.password_hash, original_hash)
            self.assertEqual(float(account.patient_profile.weight_kg), 70)


if __name__ == "__main__":
    unittest.main()
