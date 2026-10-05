import unittest

from app.database import Base
from app.main import app
from app.api import ws_chat
from app.models import PatientProfile, ProfessionalPatient, ProfessionalProfile, User
from app.schemas.profiles import PatientSummaryResponse


class ContractTests(unittest.TestCase):
    def test_profile_tables_and_assignment_table_are_registered(self):
        self.assertTrue(
            {
                "users",
                "patient_profiles",
                "professional_profiles",
                "professional_patient_assignments",
            }.issubset(Base.metadata.tables)
        )
        self.assertNotIn("language_preference", PatientProfile.__table__.columns)
        self.assertTrue(PatientProfile.__table__.c.user_id.unique)
        self.assertTrue(ProfessionalProfile.__table__.c.user_id.unique)
        self.assertEqual(
            set(ProfessionalPatient.__table__.primary_key.columns.keys()),
            {"professional_id", "patient_id"},
        )

    def test_user_profile_relationships_are_one_to_one(self):
        self.assertFalse(User.patient_profile.property.uselist)
        self.assertFalse(User.professional_profile.property.uselist)
        self.assertEqual(User.patient_profile.property.back_populates, "user")
        self.assertEqual(User.professional_profile.property.back_populates, "user")

    def test_patient_summary_excludes_sensitive_and_private_fields(self):
        fields = set(PatientSummaryResponse.model_fields)
        self.assertIn("email", fields)
        self.assertIn("tel", fields)
        self.assertIn("blood_type", fields)
        self.assertIn("allergies_summary", fields)
        self.assertIn("chronic_conditions_summary", fields)
        self.assertNotIn("address", fields)
        self.assertNotIn("password_hash", fields)

    def test_all_branch_endpoint_paths_are_registered(self):
        paths = app.openapi()["paths"]
        expected = {
            "/admin/users",
            "/admin/users/{user_id}",
            "/patients/me/profile",
            "/patients/me",
            "/patients/me/change-password",
            "/professionals/me/profile",
            "/professionals/me",
            "/professionals/me/change-password",
            "/professionals/me/patients",
            "/professionals",
            "/professionals/{professional_id}",
            "/professionals/{professional_id}/appointments/{appointment_id}/prescription",
            "/admin/appointments/{appointment_id}/prescription-authorization",
            "/patients/me/appointments/{appointment_id}/prescription",
            "/professionals/{professional_id}/appointments/history",
            "/professionals/{professional_id}/prescriptions",
            "/appointments/{appointment_id}/chat",
            "/appointments/{appointment_id}/chat/messages",
            "/appointments/{appointment_id}/video/join",
        }
        self.assertTrue(expected.issubset(paths))
        self.assertTrue(
            any(
                getattr(route, "path", None) == "/ws/chat/{appointment_id}"
                for route in ws_chat.router.routes
            )
        )
        self.assertIn("patch", paths["/admin/users/{user_id}"])
        self.assertIn("delete", paths["/admin/users/{user_id}"])
        self.assertIn("get", paths["/professionals"])


if __name__ == "__main__":
    unittest.main()
