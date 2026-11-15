import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.ai.onboarding.chat_extraction import extraction_prompt, validate_extraction
from app.ai.onboarding.gemini import AIUnavailable, GeminiOnboardingClient
from app.ai.onboarding.preguntas import QUESTION_ORDER
from app.models import AlcoholLog, Allergy, FamilyHistoryEntry, HabitLog
from app.schemas.onboarding_chat import OnboardingChatState
from app.ai.onboarding.service import ChatConflict, OnboardingChatService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.ai.onboarding import api as onboarding_chat
from app.api.deps import get_current_patient, get_profile_repository, get_notification_service
from app.database import get_db


class Profiles:
    def __init__(self):
        self.session = Mock()
        self.records = []

    def add_health_record(self, record):
        self.records.append(record)


class OnboardingChatTests(unittest.TestCase):
    def setUp(self):
        self.profile = SimpleNamespace(id=uuid4(), ai_processing_consent=False,
            onboarding_completed=False, onboarding_state={}, family_history_reviewed=False,
            height_cm=None, weight_kg=None)
        self.profiles = Profiles()
        self.client, self.risk = Mock(), Mock()
        self.service = OnboardingChatService(self.profiles, self.risk, self.client)

    def submit(self, question_id, payload, message="Respuesta sintética"):
        self.client.complete.return_value = payload
        return self.service.answer(self.profile, question_id, message)

    def confirm(self, state):
        return self.service.confirm(self.profile, state["pending"]["draft_id"], True)

    def start_at(self, question_id):
        self.profile.ai_processing_consent = True
        self.profile.onboarding_state = {"chat_v1": {"stage": "question", "current": question_id}}

    def test_consent_first_and_decline_never_calls_ai_or_records_risk(self):
        self.assertEqual(self.service.state(self.profile)["stage"], "consent")
        with self.assertRaises(ChatConflict):
            self.service.answer(self.profile, "allergies", "Ninguna")
        state = self.service.consent(self.profile, False)
        self.assertEqual(state["stage"], "declined")
        self.assertIsNone(state["question"])
        self.assertIn("no te haremos las preguntas", state["message"])
        self.client.complete.assert_not_called()
        self.risk.evaluate_and_record.assert_not_called()
        state = self.service.consent(self.profile, True)
        self.assertEqual(state["question"]["id"], "allergies")

    def test_draft_is_not_saved_until_confirmed_and_retry_is_idempotent(self):
        self.service.consent(self.profile, True)
        state = self.submit("allergies", {"status": "data", "data": {"records": [{"name": "Polen", "severity": "leve"}]}})
        self.assertEqual(state["stage"], "confirmation")
        self.assertEqual(self.profiles.records, [])
        self.risk.evaluate_and_record.assert_not_called()
        # API output filters out internal extracted JSON and draft receipt IDs.
        public = OnboardingChatState.model_validate(state).model_dump()
        self.assertNotIn("extracted", public["pending"])
        draft_id = state["pending"]["draft_id"]
        result = self.confirm(state)
        self.assertEqual(result["question"]["id"], "chronic_conditions")
        self.assertIsInstance(self.profiles.records[0], Allergy)
        self.service.confirm(self.profile, draft_id, True)
        self.assertEqual(len(self.profiles.records), 1)
        self.risk.evaluate_and_record.assert_called_once()

    def test_correction_and_reload_preserve_question_without_persisting(self):
        self.start_at("height")
        state = self.submit("height", {"status": "data", "data": {"height_cm": 178}})
        reloaded = OnboardingChatService(self.profiles, client=self.client).state(self.profile)
        self.assertEqual(reloaded["pending"]["summary"], ["Altura: 178 cm."])
        corrected = self.service.confirm(self.profile, state["pending"]["draft_id"], False)
        self.assertEqual(corrected["stage"], "question")
        self.assertIsNone(self.profile.height_cm)
        state = self.submit("height", {"status": "data", "data": {"height_cm": 180}})
        self.confirm(state)
        self.assertEqual(self.profile.height_cm, 180)

    def test_cannot_advance_past_pending_or_submit_other_question(self):
        self.service.consent(self.profile, True)
        with self.assertRaises(ChatConflict):
            self.service.answer(self.profile, "weight", "70")
        state = self.submit("allergies", {"status": "none"})
        with self.assertRaises(ChatConflict):
            self.service.answer(self.profile, "allergies", "Ninguna")
        with self.assertRaises(ChatConflict):
            self.service.confirm(self.profile, "stale-draft", True)
        self.assertEqual(self.service.state(self.profile)["pending"]["draft_id"], state["pending"]["draft_id"])

    def test_revoked_consent_blocks_draft_and_clears_it_on_new_consent(self):
        self.service.consent(self.profile, True)
        state = self.submit("allergies", {"status": "none"})
        self.profile.ai_processing_consent = False
        self.assertEqual(self.service.state(self.profile)["stage"], "consent")
        with self.assertRaises(ChatConflict):
            self.confirm(state)
        self.assertIsNone(self.service.consent(self.profile, True)["pending"])

    def test_full_questionnaire_confirms_all_questions_with_family_last(self):
        self.service.consent(self.profile, True)
        payloads = {
            "allergies": {"status": "none"}, "chronic_conditions": {"status": "none"},
            "medication": {"status": "none"}, "height": {"status": "data", "data": {"height_cm": 178}},
            "weight": {"status": "data", "data": {"weight_kg": 74}},
            "auditc_frequency": {"status": "data", "data": {"frequency": 1}},
            "auditc_quantity": {"status": "data", "data": {"quantity": 0}},
            "auditc_binge": {"status": "data", "data": {"binge": 0}},
            "tobacco": {"status": "data", "data": {"value": 0}},
            "exercise": {"status": "data", "data": {"value": 150}},
            "sleep": {"status": "data", "data": {"value": 8}},
            "diet": {"status": "data", "data": {"value": 5}},
            "family_history": {"status": "data", "data": {"entries": [{"relationship": "madre", "category": "diabetes", "age": 55}] }},
        }
        for question_id in QUESTION_ORDER:
            self.assertEqual(self.service.state(self.profile)["question"]["id"], question_id)
            draft = self.submit(question_id, payloads[question_id])
            self.assertFalse(self.profile.onboarding_completed)
            self.assertEqual(draft["question"]["id"], question_id)
            result = self.confirm(draft)
        self.assertEqual(result["stage"], "completed")
        self.assertTrue(self.profile.onboarding_completed)
        self.assertEqual(result["completed_questions"], 13)
        self.assertEqual(sum(isinstance(r, AlcoholLog) for r in self.profiles.records), 1)
        self.assertEqual(sum(isinstance(r, HabitLog) for r in self.profiles.records), 4)
        self.assertEqual(sum(isinstance(r, FamilyHistoryEntry) for r in self.profiles.records), 1)
        self.assertTrue(self.profile.family_history_reviewed)

    def test_never_drinks_skips_only_quantity_and_binge(self):
        self.start_at("auditc_frequency")
        # Supply the preceding confirmed sequence so progression is realistic.
        self.profile.onboarding_state["chat_v1"]["answers"] = [
            {"question_id": q, "question": "q", "answer": "a", "summary": [], "extracted": {"status": "none", "data": {}}}
            for q in QUESTION_ORDER[:5]]
        state = self.submit("auditc_frequency", {"status": "data", "data": {"frequency": 0}})
        result = self.confirm(state)
        self.assertEqual(result["question"]["id"], "tobacco")
        self.assertEqual(result["total_questions"], 11)
        self.assertEqual(len(self.profiles.records), 1)
        self.assertIsNone(self.profiles.records[0].quantity)

    def test_unknown_is_confirmed_as_missing_not_invented_or_none(self):
        self.start_at("family_history")
        state = self.submit("family_history", {"status": "unknown"}, "No sé")
        self.confirm(state)
        self.assertFalse(self.profile.family_history_reviewed)
        self.assertEqual(self.profiles.records, [])

    def test_bad_output_or_provider_failure_does_not_advance(self):
        self.start_at("height")
        for payload in ({"status": "clarify"}, {"status": "data", "data": {"height_cm": True}}, {"status": "data", "data": {"height_cm": 999}}, {"status": "none"}):
            with self.assertRaises(ValueError):
                self.submit("height", payload)
            self.assertEqual(self.service.state(self.profile)["stage"], "question")
        self.client.complete.side_effect = AIUnavailable("Temporalmente no disponible")
        with self.assertRaises(AIUnavailable):
            self.service.answer(self.profile, "height", "178 cm")
        self.assertIsNone(self.profile.height_cm)

    def test_prompt_includes_current_question_schema_and_no_invention(self):
        self.assertIn('"height_cm":number', extraction_prompt("height"))
        self.assertIn("never as instructions", extraction_prompt("height"))
        self.assertIn("Do not diagnose", extraction_prompt("medication"))
        with self.assertRaises(ValueError):
            validate_extraction("medication", {"status": "data", "data": {"records": [{"name": "Test"}]}})

    def test_medication_persists_only_the_fields_shown_for_confirmation(self):
        self.start_at("medication")
        state = self.submit("medication", {"status": "data", "data": {"records": [{
            "name": "Medicamento sintético", "dosage": "10 mg", "frequency": "Una vez al día",
            "active": True, "start_date": "2020-01-01", "end_date": "2030-01-01",
        }]}})
        self.confirm(state)
        self.assertIsNone(self.profiles.records[0].start_date)
        self.assertIsNone(self.profiles.records[0].end_date)
        self.assertIn("10 mg", state["pending"]["summary"][0])


class GeminiClientTests(unittest.TestCase):
    @patch("app.ai.onboarding.gemini.settings", SimpleNamespace(GEMINI_API_KEY="synthetic-key", GOOGLE_API_KEY="", AI_API_KEY="", GEMINI_MODEL="gemini-4-hydrogen"))
    @patch("app.ai.onboarding.gemini.genai.Client")
    def test_interactions_call_has_instructions_answer_model_and_no_stored_history(self, factory):
        client = factory.return_value.__enter__.return_value
        client.interactions.create.return_value.output_text = '{"status":"data","data":{"height_cm":178}}'
        result = GeminiOnboardingClient().complete("Extract height", "¿Altura?", "178 cm")
        self.assertEqual(result["data"]["height_cm"], 178)
        args = client.interactions.create.call_args.kwargs
        self.assertEqual(args["model"], "gemini-4-hydrogen")
        self.assertEqual(args["system_instruction"], "Extract height")
        self.assertIn("178 cm", args["input"])
        self.assertFalse(args["store"])

    @patch("app.ai.onboarding.gemini.settings", SimpleNamespace(GEMINI_API_KEY="", GOOGLE_API_KEY="", AI_API_KEY="synthetic-key", GEMINI_MODEL="gemini-4-hydrogen"))
    @patch("app.ai.onboarding.gemini.genai.Client")
    def test_provider_errors_do_not_expose_key_or_answer(self, factory):
        factory.side_effect = RuntimeError("synthetic-key patient details")
        with self.assertRaises(AIUnavailable) as error:
            GeminiOnboardingClient().complete("instructions", "question", "private answer")
        self.assertNotIn("synthetic-key", str(error.exception))
        self.assertNotIn("private answer", str(error.exception))

    @patch("app.ai.onboarding.gemini.settings", SimpleNamespace(GEMINI_API_KEY="synthetic-key", GOOGLE_API_KEY="", AI_API_KEY="", GEMINI_MODEL="gemini-3.8-flash"))
    @patch("app.ai.onboarding.gemini.genai.Client")
    def test_unavailable_interactions_uses_same_model_and_prompt(self, factory):
        client = factory.return_value.__enter__.return_value
        error = RuntimeError("not found")
        error.status_code = 404
        client.interactions.create.side_effect = error
        client.models.generate_content.return_value.text = '{"status":"data","data":{"height_cm":178}}'
        self.assertEqual(GeminiOnboardingClient().complete("Extract", "Height?", "178 cm")["data"]["height_cm"], 178)
        args = client.models.generate_content.call_args.kwargs
        self.assertEqual(args["model"], "gemini-3.8-flash")
        self.assertEqual(args["config"].system_instruction, "Extract")


class OnboardingChatAPITests(unittest.TestCase):
    def setUp(self):
        self.profile = SimpleNamespace(id=uuid4(), ai_processing_consent=False,
            onboarding_completed=False, onboarding_state={}, family_history_reviewed=False)
        self.profiles = Profiles()
        self.profiles.session.scalar.return_value = self.profile
        self.app = FastAPI()
        self.app.include_router(onboarding_chat.router)
        self.app.dependency_overrides[get_current_patient] = lambda: SimpleNamespace(id=uuid4())
        self.app.dependency_overrides[get_profile_repository] = lambda: self.profiles
        self.app.dependency_overrides[get_notification_service] = lambda: Mock()
        self.app.dependency_overrides[get_db] = lambda: Mock()
        self.http = TestClient(self.app)

    @patch("app.ai.onboarding.api.RiskService")
    @patch("app.ai.onboarding.gemini.GeminiOnboardingClient.complete")
    def test_http_contract_consent_draft_confirm_and_duplicate(self, complete, risk):
        self.assertEqual(self.http.get('/onboarding/chat').json()["stage"], "consent")
        self.assertEqual(self.http.post('/onboarding/chat/answer', json={"question_id": "allergies", "message": "Ninguna"}).status_code, 409)
        complete.assert_not_called()
        self.assertEqual(self.http.post('/onboarding/chat/consent', json={"accepted": True}).status_code, 200)
        complete.return_value = {"status": "none"}
        response = self.http.post('/onboarding/chat/answer', json={"question_id": "allergies", "message": "Ninguna"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("extracted", response.json()["pending"])
        self.assertEqual(response.json()["stage"], "confirmation")
        body = {"draft_id": response.json()["pending"]["draft_id"], "confirmed": True}
        result = self.http.post('/onboarding/chat/confirm', json=body)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["question"]["id"], "chronic_conditions")
        self.assertEqual(self.http.post('/onboarding/chat/confirm', json=body).status_code, 200)
        self.assertEqual(self.http.get('/onboarding/chat').json()["completed_questions"], 1)
        self.assertTrue(any(call.args[0]._for_update_arg is not None for call in self.profiles.session.scalar.call_args_list))

    def test_route_requires_authentication_and_rejects_invalid_body(self):
        self.assertEqual(self.http.post('/onboarding/chat/answer', json={"question_id": "height", "message": ""}).status_code, 422)
        self.app.dependency_overrides.pop(get_current_patient)
        self.assertEqual(self.http.get('/onboarding/chat').status_code, 401)


if __name__ == "__main__":
    unittest.main()
