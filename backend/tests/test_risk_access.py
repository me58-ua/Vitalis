import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.models import PatientProfile, UserRole
from app.schemas.risk import RiskResult
from app.services.risk_history_service import RiskHistoryAccessError, RiskHistoryService
from app.services.risk_summary_service import RiskSummaryAccessError, RiskSummaryService


class ProfessionalRiskAccessTests(unittest.TestCase):
    def setUp(self):
        self.profile = SimpleNamespace(
            id=uuid4(), user_id=uuid4(), share_health_data=True,
            ai_processing_consent=True,
        )
        self.professional = SimpleNamespace(id=uuid4(), role=UserRole.PROFESSIONAL)
        self.profiles = Mock()
        self.profiles.session.get.return_value = self.profile
        self.appointments = Mock()
        self.appointments.has_shared_appointment.side_effect = (
            lambda patient_id, professional_id:
            patient_id == self.profile.user_id and professional_id == self.professional.id
        )
        self.appointments.health_sharing_scope.side_effect = (
            lambda profile, professional_id: "full"
            if profile.share_health_data and self.appointments.has_shared_appointment(profile.user_id, professional_id)
            else "none"
        )
        self.snapshots = Mock()
        self.snapshots.list_history.return_value = ([], None)
        self.risk = Mock()
        self.risk.evaluate.return_value = [RiskResult(
            model="bmi", status="ok", metric_value=24,
            category="healthy", alert_level="info",
            explanation="", source="", disclaimer="",
        )]

    def summary(self):
        return RiskSummaryService(
            self.risk, self.snapshots, self.profiles, self.appointments
        ).get(self.profile.id, self.professional)

    def history(self):
        return RiskHistoryService(
            self.snapshots, self.profiles, self.appointments
        ).list_for_user(
            self.profile.id, self.professional, "bmi", None, None, None, 50
        )

    def test_summary_checks_user_id_and_queries_risk_by_profile_id(self):
        self.assertEqual(len(self.summary()["results"]), 1)
        self.profiles.session.get.assert_called_once_with(PatientProfile, self.profile.id)
        self.appointments.health_sharing_scope.assert_called_once_with(self.profile, self.professional.id)
        self.risk.evaluate.assert_called_once_with(self.profile.id)
        self.snapshots.list_history.assert_called_once_with(self.profile.id, "bmi", limit=100)

    def test_history_checks_user_id_and_queries_snapshots_by_profile_id(self):
        self.assertEqual(self.history()["snapshots"], [])
        self.profiles.session.get.assert_called_once_with(PatientProfile, self.profile.id)
        self.appointments.health_sharing_scope.assert_called_once_with(self.profile, self.professional.id)
        self.snapshots.list_history.assert_any_call(
            self.profile.id, "bmi", None, None, None, 50
        )

    def test_professional_without_shared_appointment_is_rejected(self):
        self.appointments.has_shared_appointment.side_effect = None
        self.appointments.has_shared_appointment.return_value = False
        with self.assertRaises(RiskSummaryAccessError):
            self.summary()
        with self.assertRaises(RiskHistoryAccessError):
            self.history()
        self.risk.evaluate.assert_not_called()
        self.snapshots.list_history.assert_not_called()

    def test_professional_without_health_sharing_is_rejected(self):
        self.profile.share_health_data = False
        with self.assertRaises(RiskSummaryAccessError):
            self.summary()
        with self.assertRaises(RiskHistoryAccessError):
            self.history()
        self.risk.evaluate.assert_not_called()
        self.snapshots.list_history.assert_not_called()

    def test_basic_sharing_does_not_grant_risk_access(self):
        self.appointments.health_sharing_scope.side_effect = None
        self.appointments.health_sharing_scope.return_value = "basic"
        with self.assertRaises(RiskSummaryAccessError):
            self.summary()
        with self.assertRaises(RiskHistoryAccessError):
            self.history()
        self.risk.evaluate.assert_not_called()
        self.snapshots.list_history.assert_not_called()
