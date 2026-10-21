import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.risk_service import (
    calc_audit_c,
    calc_bmi,
    calc_family_history,
    calc_sedentary,
    calc_tobacco,
    RiskService,
)


class RiskCalculatorTests(unittest.TestCase):
    def test_bmi_requires_adult_and_uses_metric_inputs(self):
        result = calc_bmi(170, 70, date(1990, 1, 1), today=date(2026, 1, 1))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.category, "healthy")
        self.assertAlmostEqual(result.metric_value, 24.22, places=2)

        minor = calc_bmi(170, 70, date(2010, 1, 1), today=date(2026, 1, 1))
        self.assertEqual(minor.status, "insufficient_data")

    def test_audit_c_uses_sex_specific_thresholds(self):
        woman = calc_audit_c(1, 1, 1, "mujer")
        man = calc_audit_c(1, 1, 1, "hombre")
        self.assertEqual(woman.category, "positive_screen")
        self.assertEqual(man.category, "lower_screen")

        zero_frequency = calc_audit_c(0, None, None, "hombre")
        self.assertEqual(zero_frequency.metric_value, 0)

    def test_tobacco_averages_recent_values(self):
        logs = [
            SimpleNamespace(value=5, unit="cigarrillos/dia"),
            SimpleNamespace(value=15, unit="cigarrillos/dia"),
        ]
        result = calc_tobacco(logs)
        self.assertEqual(result.metric_value, 10)
        self.assertEqual(result.category, "low")

    def test_sedentary_requires_three_records_and_uses_weekly_minutes(self):
        insufficient = calc_sedentary([
            SimpleNamespace(value=150, unit="min/semana"),
            SimpleNamespace(value=150, unit="min/semana"),
        ])
        self.assertEqual(insufficient.status, "insufficient_data")
        result = calc_sedentary([SimpleNamespace(value=150, unit="min/semana")] * 3)
        self.assertEqual(result.category, "active")

    def test_family_history_applies_first_degree_and_bmi_rule(self):
        entry = SimpleNamespace(condition_category="diabetes", relationship="otro")
        result = calc_family_history([entry], bmi=25)
        self.assertEqual(result[0].model, "family_diabetes")
        self.assertEqual(result[0].alert_level, "elevated")

    def test_service_returns_nothing_without_ai_consent_and_continues_after_failure(self):
        profile = SimpleNamespace(
            ai_processing_consent=True,
            height_cm=170,
            weight_kg=70,
            birth_date=date(1990, 1, 1),
            sex_at_birth="mujer",
        )
        repository = Mock()
        repository.get_inputs.return_value = SimpleNamespace(
            profile=profile,
            alcohol_log=None,
            tobacco_logs=[],
            exercise_logs=[],
            family_history=[],
        )
        results = RiskService(repository).evaluate(
            "patient-id", today=date(2026, 1, 1)
        )
        self.assertTrue(any(result.model == "bmi" for result in results))
        self.assertTrue(any(result.model == "tobacco" for result in results))


if __name__ == "__main__":
    unittest.main()
