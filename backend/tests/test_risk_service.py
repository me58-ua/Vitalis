import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.risk_service import (
    calc_audit_c,
    calc_bmi,
    calc_family_history,
    calc_sedentary,
    calc_sleep,
    calc_tobacco,
    calc_trend,
    RiskService,
)
from app.schemas.risk import RiskResult
from app.repositories.risk_repository import RiskRepository
from app.models import HereditaryConditions, FamilyRelationship


class RiskCalculatorTests(unittest.TestCase):
    def test_one_usual_sleep_answer_is_enough_for_the_adult_screen(self):
        session = Mock()
        session.get.return_value = SimpleNamespace(
            ai_processing_consent=True, birth_date=date(1990, 1, 1),
            height_cm=None, weight_kg=None, sex_at_birth=None, onboarding_state={},
        )
        session.scalar.side_effect = [None, SimpleNamespace(value=360, unit="min/noche")]
        session.scalars.side_effect = [[], []]
        results = RiskService(RiskRepository(session)).evaluate("patient-id", today=date(2026, 1, 1))
        sleep = next(result for result in results if result.model == "sleep")
        self.assertEqual((sleep.metric_value, sleep.category, sleep.alert_level), (6, "short_sleep", "elevated"))
        self.assertIn("diabetes tipo 2", sleep.explanation)

    def test_sleep_threshold_and_missing_data(self):
        log = SimpleNamespace(value=7, unit="horas/noche")
        today = date(2026, 1, 1)
        self.assertEqual(calc_sleep(log, date(1990, 1, 1), today).alert_level, "none")
        self.assertEqual(calc_sleep(log, date(2010, 1, 1), today).missing, ["adult_age"])
        self.assertEqual(calc_sleep(None, date(1990, 1, 1), today).missing, ["usual_sleep_hours"])

    def test_every_hereditary_enum_has_explanation_and_authoritative_source(self):
        expected = {
            'diabetes': ('glucosa', 'www.niddk.nih.gov'),
            'cancer': ('cáncer', 'www.cdc.gov'),
            'cardiovascular': ('corazón', 'www.cdc.gov'),
            'huntington': ('Huntington', 'medlineplus.gov'),
            'otro': ('Sin un diagnóstico concreto', 'www.cdc.gov'),
            'hypertension': ('presión arterial', 'www.cdc.gov'),
            'high_cholesterol': ('colesterol', 'www.cdc.gov'),
            'stroke': ('ictus', 'www.cdc.gov'),
            'osteoporosis': ('huesos', 'www.niams.nih.gov'),
            'cystic_fibrosis': ('fibrosis quística', 'medlineplus.gov'),
            'sickle_cell_disease': ('hemoglobina', 'medlineplus.gov'),
            'familial_hypercholesterolemia': ('LDL', 'www.cdc.gov'),
        }
        self.assertEqual(set(expected), {condition.value for condition in HereditaryConditions})
        for condition in HereditaryConditions:
            with self.subTest(condition=condition):
                result, = calc_family_history([SimpleNamespace(
                    condition_category=condition, relationship=FamilyRelationship.GRANDPARENT, detail=None,
                )])
                text, domain = expected[condition.value]
                self.assertIn(text, result.explanation)
                self.assertIn('cita', result.explanation)
                self.assertTrue(result.source.startswith('https://' + domain + '/'))
                self.assertEqual(result.status, 'ok')

    def test_bmi_thresholds_do_not_classify_values_below_25_or_30_too_early(self):
        for bmi, category in ((18.49, 'underweight'), (18.5, 'healthy'), (24.95, 'healthy'), (25, 'overweight'), (29.95, 'overweight'), (30, 'obesity')):
            with self.subTest(bmi=bmi):
                result = calc_bmi(200, bmi * 4, date(1990, 1, 1))
                self.assertEqual(result.category, category)
                self.assertIn('IMC', result.explanation)
                self.assertIn('orientativo', result.explanation)
        self.assertIn('pedir cita', calc_bmi(200, 120, date(1990, 1, 1)).explanation)

    def test_alcohol_explanations_follow_the_applied_threshold(self):
        positive = calc_audit_c(1, 1, 1, 'mujer')
        lower = calc_audit_c(1, 1, 1, 'hombre')
        self.assertIn('umbral de cribado aplicado es 3', positive.explanation)
        self.assertIn('no diagnostica dependencia', positive.explanation)
        self.assertIn('por debajo', lower.explanation)
        self.assertIn('no significa', lower.explanation)

    def test_tobacco_explains_consumption_bands_without_claiming_safe_consumption(self):
        for value, band in ((1, 'hasta 10'), (10, 'hasta 10'), (11, 'más de 10 y hasta 20'), (20, 'más de 10 y hasta 20'), (21, 'más de 20')):
            result = calc_tobacco([SimpleNamespace(value=value, unit='cigarrillos/dia')])
            self.assertIn(band, result.explanation)
            self.assertIn('no hay un nivel seguro', result.explanation)
        self.assertIn('No consta consumo', calc_tobacco([SimpleNamespace(value=0, unit='cigarrillos/dia')]).explanation)

    def test_grandparent_huntington_and_uncle_colon_cancer_have_actionable_explanations(self):
        results = calc_family_history([
            SimpleNamespace(condition_category='huntington', relationship='abuelo', detail=None),
            SimpleNamespace(condition_category='cancer', relationship='tio', detail='cáncer de colon'),
        ])
        self.assertEqual({r.model for r in results}, {'family_huntington', 'family_cancer'})
        huntington, cancer = results
        self.assertIn('hereditaria', huntington.explanation)
        self.assertIn('asesoramiento genético', huntington.explanation)
        self.assertIn('no confirma', huntington.explanation)
        self.assertIn('abuelo/a', huntington.explanation)
        self.assertIn('colon', cancer.explanation)
        self.assertIn('cribado', cancer.explanation)
        self.assertIn('tío/a', cancer.explanation)
        self.assertTrue(all(r.source.startswith('https://') for r in results))

    def test_partial_confirmed_alcohol_scores_override_an_old_complete_log(self):
        session = Mock()
        profile = SimpleNamespace(id='patient', onboarding_state={'alcohol_current': {'frequency': 2, 'quantity': None, 'binge': None}})
        session.get.return_value = profile
        session.scalar.return_value = SimpleNamespace(frequency=0, quantity=None, binge=None)
        session.scalars.side_effect = [[], []]
        inputs = RiskRepository(session).get_inputs(profile.id)
        result = calc_audit_c(inputs.alcohol_log.frequency, inputs.alcohol_log.quantity, inputs.alcohol_log.binge, 'hombre')
        self.assertEqual(result.status, 'insufficient_data')
        self.assertIsNone(result.metric_value)
        self.assertEqual(inputs.alcohol_log.frequency, 2)
    def test_bmi_missing_measurements_do_not_produce_a_numeric_value(self):
        for height, weight, missing in ((None, 70, ['height_cm']), (170, None, ['weight_kg']), (None, None, ['height_cm', 'weight_kg'])):
            result = calc_bmi(height, weight, date(1990, 1, 1))
            self.assertEqual(result.status, 'insufficient_data')
            self.assertIsNone(result.metric_value)
            self.assertEqual(result.missing, missing)
            self.assertIn('No se puede calcular el BMI', result.explanation)

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

    def test_family_history_does_not_score_risk_from_relative_or_bmi(self):
        entry = SimpleNamespace(condition_category="diabetes", relationship="otro")
        result = calc_family_history([entry], bmi=25)
        self.assertEqual(result[0].model, "family_diabetes")
        self.assertEqual(result[0].alert_level, "info")
        first_degree = calc_family_history([SimpleNamespace(condition_category='stroke', relationship='padre')])
        self.assertEqual(first_degree[0].alert_level, 'info')

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
            sleep_log=None,
        )
        results = RiskService(repository).evaluate(
            "patient-id", today=date(2026, 1, 1)
        )
        self.assertTrue(any(result.model == "bmi" for result in results))
        self.assertTrue(any(result.model == "tobacco" for result in results))

    def test_trend_uses_model_direction_and_requires_history(self):
        now = datetime.now(timezone.utc)
        snapshots = [
            SimpleNamespace(computed_at=now - timedelta(days=1), metric_value=30),
            SimpleNamespace(computed_at=now, metric_value=25),
        ]
        self.assertEqual(calc_trend("bmi", snapshots), "improving")
        self.assertEqual(calc_trend("family_diabetes", snapshots), "insufficient_history")
        self.assertEqual(calc_trend("tobacco", snapshots[:1]), "insufficient_history")

    def test_evaluate_and_record_skips_insufficient_and_duplicate_results(self):
        repository = Mock()
        snapshots = Mock()
        snapshots.latest_by_model.return_value = SimpleNamespace(
            metric_value=24.22, category="healthy", alert_level="info"
        )
        service = RiskService(repository, snapshots)
        service.evaluate = Mock(return_value=[RiskResult(
            model="bmi", status="ok", metric_value=24.22, category="healthy",
            alert_level="info", explanation="", source="", disclaimer="",
        )])
        recorded = service.evaluate_and_record("patient-id", "onboarding")
        self.assertEqual(recorded, [])
        snapshots.create.assert_not_called()

    def test_evaluate_and_record_notifies_the_patient_user(self):
        repository = Mock()
        repository.get_inputs.return_value = SimpleNamespace(profile=SimpleNamespace(
            user_id="user-id", ai_processing_consent=True,
            height_cm=170, weight_kg=70, birth_date=date(1990, 1, 1),
            sex_at_birth="mujer",
        ), alcohol_log=None, tobacco_logs=[], exercise_logs=[], family_history=[], sleep_log=None)
        snapshots = Mock()
        snapshots.latest_by_model.return_value = None
        notifications = Mock()

        recorded = RiskService(repository, snapshots, notifications).evaluate_and_record(
            "patient-id", "onboarding"
        )

        self.assertEqual(len(recorded), 1)
        snapshot = snapshots.create.call_args.args[0]
        self.assertEqual(snapshot.patient_id, "patient-id")
        self.assertEqual(snapshot.model, "bmi")
        notifications.notify_risk.assert_called_once_with("user-id", "bmi", "info")


if __name__ == "__main__":
    unittest.main()
