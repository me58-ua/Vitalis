import unittest

from app.ai.onboarding.family_history_parser import (
    FAMILY_HISTORY_PROMPT,
    parse_family_history,
    sanitize_entries,
)


class FamilyHistoryParserTests(unittest.TestCase):
    def test_prompt_is_english_but_requires_spanish_persistence_values(self):
        self.assertIn("Return only JSON", FAMILY_HISTORY_PROMPT)
        self.assertIn("madre|padre|hermano", FAMILY_HISTORY_PROMPT)
        self.assertIn("answer is in Spanish", FAMILY_HISTORY_PROMPT)

    def test_sanitize_entries_applies_closed_values_and_limits(self):
        entries = sanitize_entries(
            [
                {
                    "relationship": "invalid",
                    "category": "invalid",
                    "detail": "x" * 200,
                    "age": 121,
                }
            ]
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].relationship, "otro")
        self.assertEqual(entries[0].category, "otro")
        self.assertEqual(len(entries[0].detail), 150)
        self.assertIsNone(entries[0].age)

    def test_malformed_items_are_dropped_and_only_twenty_are_kept(self):
        raw = [{"relationship": "madre", "category": "diabetes"}] * 21
        raw.insert(3, "malformed")
        result = sanitize_entries(raw)
        self.assertEqual(len(result), 20)

    def test_parser_makes_one_call_and_returns_sanitized_drafts(self):
        calls = []

        def llm(prompt, answer):
            calls.append((prompt, answer))
            return '{"status":"entries","entries":[{"relationship":"padre","category":"cancer","age":55}]}'

        result = parse_family_history("Mi padre tuvo cáncer", llm)
        self.assertEqual(result.status, "entries")
        self.assertEqual(result.entries[0].relationship, "padre")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("perfil", calls[0][0].lower())

    def test_invalid_json_or_llm_error_skips_without_entries(self):
        self.assertEqual(parse_family_history("respuesta", lambda *_: "no-json").status, "invalid")
        self.assertEqual(
            parse_family_history("respuesta", lambda *_: (_ for _ in ()).throw(RuntimeError())).status,
            "invalid",
        )


if __name__ == "__main__":
    unittest.main()
