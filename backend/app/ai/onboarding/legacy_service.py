"""Legacy onboarding compatibility, retained for existing service callers."""
import json
from datetime import date, datetime, timezone
from urllib.request import Request, urlopen

from app.ai.onboarding.family_history_parser import FamilyHistoryParseResult, parse_family_history
from app.ai.onboarding.preguntas import PREGUNTAS
from app.ai.onboarding.prompts import parse_json_object, prompt_for
from app.config import settings
from app.models import AlcoholLog, Allergy, ChronicCondition, HabitLog, Medication
from app.services.habit_units import normalize_habit_value


class LegacyOnboardingMixin:
    def save_onboarding_message(
        self, profile, block: str, message: str, question_id: str | None = None
    ):
        if question_id == "ai_processing_consent" or block == "consentimiento_ia":
            return self._save_consent(profile, message)
        # Legacy in-memory profiles may not expose the consent field yet; keep
        # the provider fallback behavior for those objects. Persisted profiles
        # always have an explicit consent value.
        if getattr(profile, "ai_processing_consent", None) is False:
            self.skip(profile)
            return True, False, "AI_CONSENT_REQUIRED"
        if block not in self.blocks:
            raise ValueError("Invalid onboarding block")

        extracted = self._extract(message, block)
        saved = False
        risk_trigger = None
        if block == "cuerpo" and isinstance(extracted, dict):
            self._save_body(profile, extracted)
            saved = True
            risk_trigger = "body_change"
        elif block == "alcohol" and isinstance(extracted, dict):
            extracted = self._merge_audit_c_answer(profile, extracted)
            if self._audit_c_complete(extracted):
                self._save_alcohol(profile, extracted)
                profile.onboarding_state = {
                    key: value
                    for key, value in (getattr(profile, "onboarding_state", {}) or {}).items()
                    if key != "audit_c"
                }
                saved = True
                risk_trigger = "habit_change"
        elif block == "antecedentes_familiares":
            if isinstance(extracted, FamilyHistoryParseResult):
                profile.onboarding_state = {
                    **getattr(profile, "onboarding_state", {}),
                    "family_history": {
                        "status": extracted.status,
                        "entries": [
                            {
                                "relationship": entry.relationship,
                                "category": entry.category,
                                "detail": entry.detail,
                                "age": entry.age,
                                "relative_detail": entry.relative_detail,
                                "notes": entry.notes,
                            }
                            for entry in extracted.entries
                        ],
                    },
                }
                self.profiles.session.flush()
                if extracted.status == "none":
                    profile.family_history_reviewed = True
                    self._record_risk(profile.id, "family_change")
                saved = extracted.status == "none"
        else:
            model = {
                "alergias": Allergy,
                "enfermedades_cronicas": ChronicCondition,
                "medicacion": Medication,
                "habitos": HabitLog,
            }.get(block)
            if model is not None:
                for item in extracted if isinstance(extracted, list) else []:
                    try:
                        if block == "habitos":
                            item = self._normalize_habit(item)
                        self.profiles.add_health_record(model(patient_id=profile.id, **item))
                        saved = True
                        if block == "habitos" and item["habit_type"] in {"tabaco", "ejercicio"}:
                            risk_trigger = "habit_change"
                    except (KeyError, TypeError, ValueError):
                        continue
        if saved:
            if risk_trigger is not None:
                self._record_risk(profile.id, risk_trigger)

        completed = self._is_last_question(question_id, block)
        profile.onboarding_state = {
            **(getattr(profile, "onboarding_state", {}) or {}),
            "last_question_id": question_id or block,
        }
        profile.onboarding_completed = completed
        self.profiles.session.flush()
        return completed, saved, self._next_question(question_id, block, completed, extracted)

    def confirm_family_history(self, profile, user, confirmed: bool) -> bool:
        state = getattr(profile, "onboarding_state", {}) or {}
        pending = state.get("family_history")
        if not isinstance(pending, dict) or pending.get("status") != "entries":
            raise ValueError("No family history entries await confirmation")
        if confirmed:
            if self.family_history_service is None:
                raise ValueError("Family history service is unavailable")
            for entry in pending.get("entries", []):
                from app.models import FamilyRelationship, HereditaryConditions

                self.family_history_service.create_from_onboarding(
                    user,
                    FamilyRelationship(entry["relationship"]),
                    HereditaryConditions(entry["category"]),
                    entry.get("detail"),
                    entry.get("age"),
                    relative_detail=entry.get('relative_detail'),
                    notes=entry.get('notes'),
                )
            profile.family_history_reviewed = True
            self._record_risk(profile.id, "family_change")
        else:
            profile.family_history_reviewed = False
        profile.onboarding_state = {key: value for key, value in state.items() if key != "family_history"}
        self.profiles.session.flush()
        return confirmed

    def skip(self, profile):
        profile.onboarding_completed = True
        self.profiles.session.flush()
        return True

    def resume(self, profile) -> bool:
        resumed, _, _, _ = self.resume_state(profile)
        return resumed

    def resume_state(self, profile) -> tuple[bool, str | None, str | None, bool]:
        if getattr(profile, "ai_processing_consent", False) is False:
            profile.onboarding_completed = True
            self.profiles.session.flush()
            return False, "AI_CONSENT_REQUIRED", None, False
        profile.onboarding_completed = False
        self.profiles.session.flush()
        state = getattr(profile, "onboarding_state", {}) or {}
        last_question_id = state.get("last_question_id")
        pending_family = isinstance(state.get("family_history"), dict) and state["family_history"].get("status") == "entries"
        if pending_family:
            next_question = "family_history_confirmation"
        elif last_question_id in PREGUNTAS:
            next_question = self._next_question(
                last_question_id,
                PREGUNTAS[last_question_id].block,
                False,
                state.get("audit_c", {}),
            )
        else:
            next_question = "allergies"
        return True, next_question, last_question_id, pending_family

    def _extract(self, message: str, block: str):
        if block == "antecedentes_familiares":
            if self.llm_client is None:
                return []
            return parse_family_history(message, self.llm_client)
        if self.llm_client is not None:
            response = self.llm_client.complete(prompt_for(block), message)
            payload = parse_json_object(response)
        elif settings.AI_API_URL:
            request = Request(
                settings.AI_API_URL,
                data=json.dumps({"prompt": prompt_for(block), "answer": message}).encode(),
                headers={
                    "Content-Type": "application/json",
                    **({"Authorization": "******"} if settings.AI_API_KEY else {}),
                },
                method="POST",
            )
            with urlopen(request, timeout=8) as response:
                payload = parse_json_object(response.read().decode())
        else:
            return []
        if payload is None:
            return []
        if block in {"cuerpo", "alcohol"}:
            return payload
        records = payload.get("records")
        return records if isinstance(records, list) else []

    def _save_consent(self, profile, message: str):
        answer = message.strip().casefold()
        accepted = answer in {"sí", "si", "sí, acepto", "si, acepto", "1", "true"}
        profile.ai_processing_consent = accepted
        profile.ai_processing_consent_at = datetime.now(timezone.utc)
        profile.onboarding_state = {
            **(getattr(profile, "onboarding_state", {}) or {}),
            "consent_answered": True,
        }
        profile.onboarding_completed = not accepted
        self.profiles.session.flush()
        return profile.onboarding_completed, True, (
            "AI_CONSENT_REQUIRED" if not accepted else "allergies"
        )

    def _record_risk(self, patient_id, trigger):
        if self.risk_service is not None:
            self.risk_service.evaluate_and_record(patient_id, trigger=trigger)

    @staticmethod
    def _normalize_habit(item):
        value, unit = normalize_habit_value(
            item["habit_type"], item.get("value"), item["unit"]
        )
        return {
            "habit_type": item["habit_type"],
            "value": value,
            "unit": unit,
            "date": date.fromisoformat(item["date"]) if item.get("date") else date.today(),
        }

    @staticmethod
    def _save_body(profile, payload):
        height = payload.get("height_cm")
        weight = payload.get("weight_kg")
        if height is not None and not 100 <= height <= 250:
            raise ValueError("height_cm is outside the allowed range")
        if weight is not None and not 25 <= weight <= 400:
            raise ValueError("weight_kg is outside the allowed range")
        if height is not None:
            profile.height_cm = height
        if weight is not None:
            profile.weight_kg = weight

    def _save_alcohol(self, profile, payload):
        frequency = payload.get("frequency")
        quantity = payload.get("quantity")
        binge = payload.get("binge")
        if not isinstance(frequency, int) or not 0 <= frequency <= 4:
            raise ValueError("frequency must be between 0 and 4")
        if frequency == 0:
            quantity = binge = None
        elif any(
            not isinstance(value, int) or not 0 <= value <= 4
            for value in (quantity, binge)
        ):
            raise ValueError("quantity and binge must be between 0 and 4")
        self.profiles.add_health_record(
            AlcoholLog(
                patient_id=profile.id,
                frequency=frequency,
                quantity=quantity,
                binge=binge,
                date=date.today(),
            )
        )

    @staticmethod
    def _audit_c_complete(payload):
        return (
            isinstance(payload.get("frequency"), int)
            and 0 <= payload["frequency"] <= 4
            and (
                payload["frequency"] == 0
                or (
                    isinstance(payload.get("quantity"), int)
                    and isinstance(payload.get("binge"), int)
                )
            )
        )

    @staticmethod
    def _merge_audit_c_answer(profile, payload):
        state = getattr(profile, "onboarding_state", {}) or {}
        previous = state.get("audit_c", {})
        merged = {
            key: value
            for key, value in {**previous, **payload}.items()
            if key in {"frequency", "quantity", "binge"} and value is not None
        }
        if merged.get("frequency") == 0:
            merged["quantity"] = None
            merged["binge"] = None
        profile.onboarding_state = {
            **state,
            "audit_c": merged,
        }
        return {**payload, **merged}

    @staticmethod
    def _is_last_question(question_id, block):
        if question_id in PREGUNTAS:
            return list(PREGUNTAS).index(question_id) == len(PREGUNTAS) - 1
        return block == "habitos"

    def _next_question(self, question_id: str | None, block: str, completed: bool, extracted) -> str:
        if completed:
            return "ONBOARDING_COMPLETED"
        if question_id in PREGUNTAS:
            ids = list(PREGUNTAS)
            index = ids.index(question_id)
            if question_id == "auditc_frequency" and isinstance(extracted, dict):
                if extracted.get("frequency") == 0:
                    return "tobacco"
            if index + 1 < len(ids):
                return ids[index + 1]
        return {
            "alergias": "ONBOARDING_NEXT_CHRONIC_CONDITION",
            "enfermedades_cronicas": "ONBOARDING_NEXT_MEDICATION",
            "medicacion": "ONBOARDING_NEXT_HABIT",
            "cuerpo": "auditc_frequency",
            "alcohol": "tobacco",
            "habitos": "ONBOARDING_NEXT_OTHER",
            "antecedentes_familiares": "ONBOARDING_COMPLETED",
        }[block]
