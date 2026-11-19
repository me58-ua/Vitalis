import unittest
import uuid
from types import SimpleNamespace

from fastapi import HTTPException

from app.api.professionals import get_professional, list_my_patients, list_professionals
from app.models import UserRole


class FakeProfessionalRepository:
    def __init__(self):
        self.captured = {}
        self.patient_records = []
        self.professional_records = []
        self.detail = None

    def list_patients(self, **kwargs):
        self.captured["patients"] = kwargs
        return self.patient_records, len(self.patient_records)

    def list_professionals(self, **kwargs):
        self.captured["professionals"] = kwargs
        return self.professional_records, len(self.professional_records)

    def get_professional(self, professional_id):
        self.captured["detail_id"] = professional_id
        return self.detail


class ProfessionalListingTests(unittest.TestCase):
    def setUp(self):
        self.professional = SimpleNamespace(id=uuid.uuid4(), role=UserRole.PROFESSIONAL)
        self.patient = SimpleNamespace(
            id=uuid.uuid4(),
            name="Assigned Patient",
            username="assigned_patient",
            email="patient@example.com",
            tel="+34123456789",
            gender="female",
        )
        self.patient_profile = SimpleNamespace(
            blood_type="O+",
            allergies=[SimpleNamespace(name="Penicillin")],
            chronic_conditions=[SimpleNamespace(condition_name="Asthma")],
            share_health_data=True,
            address="Private address",
        )
        self.professional_user = SimpleNamespace(id=uuid.uuid4(), name="Dr. Garcia")
        self.professional_profile = SimpleNamespace(
            specialty="Cardiology",
            bio="Heart specialist",
            practice_address="Clinic address",
            practice_phone="+34910000000",
            is_accepting_new_patients=True,
            default_consultation_duration_minutes=30,
            telehealth_enabled=True,
            license_number="COL-12345",
        )
        self.repository = FakeProfessionalRepository()

    def test_patient_list_is_paginated_and_contains_requested_safe_fields(self):
        self.repository.patient_records = [(self.patient, self.patient_profile)]
        response = list_my_patients(
            self.professional,
            self.repository,
            search="assigned",
            page=2,
            page_size=5,
        )

        self.assertEqual(response.total, 1)
        self.assertEqual(response.page, 2)
        self.assertEqual(response.page_size, 5)
        patient = response.patients[0]
        self.assertEqual(patient.email, "patient@example.com")
        self.assertEqual(patient.tel, "+34123456789")
        self.assertEqual(patient.blood_type, "O+")
        self.assertEqual(patient.allergies_summary, "Penicillin")
        self.assertEqual(patient.chronic_conditions_summary, "Asthma")
        self.assertNotIn("address", patient.model_dump())
        self.assertNotIn("password_hash", patient.model_dump())
        self.assertEqual(self.repository.captured["patients"]["offset"], 5)
        self.assertEqual(self.repository.captured["patients"]["limit"], 5)

    def test_patient_summaries_respect_health_sharing_consent(self):
        self.patient_profile.share_health_data = False
        self.repository.patient_records = [(self.patient, self.patient_profile)]
        response = list_my_patients(self.professional, self.repository, search=None, page=1, page_size=20)
        self.assertIsNone(response.patients[0].allergies_summary)
        self.assertIsNone(response.patients[0].chronic_conditions_summary)

    def test_patient_without_health_records_returns_null_summaries(self):
        self.patient_profile.allergies = []
        self.patient_profile.chronic_conditions = []
        self.repository.patient_records = [(self.patient, self.patient_profile)]
        response = list_my_patients(self.professional, self.repository, search=None, page=1, page_size=20)
        self.assertIsNone(response.patients[0].allergies_summary)
        self.assertIsNone(response.patients[0].chronic_conditions_summary)

    def test_public_professional_list_passes_all_filters_and_pagination(self):
        self.repository.professional_records = [(self.professional_user, self.professional_profile)]
        response = list_professionals(
            self.repository,
            name="Garcia",
            specialty="Cardio",
            is_accepting_new_patients=True,
            telehealth_enabled=True,
            page=3,
            page_size=10,
            appointment_type="video",
        )

        self.assertEqual(response.total, 1)
        self.assertEqual(response.professionals[0].name, "Dr. Garcia")
        self.assertEqual(response.professionals[0].specialty, "Cardiology")
        filters = self.repository.captured["professionals"]
        self.assertEqual(filters["name"], "Garcia")
        self.assertEqual(filters["specialty"], "Cardio")
        self.assertTrue(filters["is_accepting_new_patients"])
        self.assertTrue(filters["telehealth_enabled"])
        self.assertEqual(filters["appointment_type"], "video")
        self.assertEqual(filters["offset"], 20)
        self.assertEqual(filters["limit"], 10)

    def test_public_professional_detail_returns_safe_profile(self):
        self.repository.detail = (self.professional_user, self.professional_profile)
        response = get_professional(self.professional_user.id, self.repository)

        self.assertEqual(response.id, self.professional_user.id)
        self.assertEqual(response.practice_phone, "+34910000000")
        self.assertNotIn("email", response.model_dump())
        self.assertNotIn("password_hash", response.model_dump())

    def test_public_professional_detail_returns_404_when_missing(self):
        with self.assertRaises(HTTPException) as error:
            get_professional(uuid.uuid4(), self.repository)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
