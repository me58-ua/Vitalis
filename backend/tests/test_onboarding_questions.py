import unittest

from app.ai.onboarding.preguntas import (
    AUDIT_C_BINGE_OPTIONS,
    AUDIT_C_FREQUENCY_OPTIONS,
    AUDIT_C_QUANTITY_OPTIONS,
    PREGUNTAS,
    get_question,
)


class OnboardingQuestionTests(unittest.TestCase):
    def test_consent_is_the_first_question(self):
        self.assertEqual(next(iter(PREGUNTAS)), "ai_processing_consent")

    def test_catalogue_contains_fixed_questions_for_all_blocks(self):
        expected_ids = {
            "ai_processing_consent",
            "auditc_frequency",
            "auditc_quantity",
            "auditc_binge",
            "height",
            "weight",
            "tobacco",
            "exercise",
            "sleep",
            "diet",
            "family_history",
            "allergies",
            "chronic_conditions",
            "medication",
        }
        self.assertEqual(set(PREGUNTAS), expected_ids)

    def test_audit_c_has_five_options_scored_zero_to_four(self):
        for options in (
            AUDIT_C_FREQUENCY_OPTIONS,
            AUDIT_C_QUANTITY_OPTIONS,
            AUDIT_C_BINGE_OPTIONS,
        ):
            self.assertEqual(len(options), 5)
            self.assertEqual([score for _, score in options], [0, 1, 2, 3, 4])

    def test_question_lookup_is_spanish_and_rejects_unknown_ids(self):
        self.assertEqual(get_question("height").text, PREGUNTAS["height"].text)
        with self.assertRaises(KeyError):
            get_question("not_a_question")


if __name__ == "__main__":
    unittest.main()
