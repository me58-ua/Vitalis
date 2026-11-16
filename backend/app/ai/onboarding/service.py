"""Server-owned questionnaire with a durable draft/confirm boundary."""
from datetime import date, datetime, timezone
from uuid import uuid4

from app.ai.onboarding.chat_extraction import ALCOHOL, HABITS, validate_extraction, extraction_prompt
from app.ai.onboarding.gemini import GeminiOnboardingClient
from app.ai.onboarding.preguntas import PREGUNTAS, QUESTION_ORDER
from app.models import AlcoholLog, Allergy, ChronicCondition, FamilyHistoryEntry, HabitLog, Medication
from app.services.habit_units import CANONICAL_UNITS


NO_CONSENT = "Sin tu consentimiento no podemos utilizar tu información para evaluar riesgos de salud. Por eso no te haremos las preguntas. Puedes volver cuando quieras y dar tu consentimiento."


class ChatConflict(ValueError):
    pass


class OnboardingChatService:
    def __init__(self, profiles, risk_service=None, client=None):
        self.profiles = profiles
        self.risk_service = risk_service
        self.client = client or GeminiOnboardingClient()

    @staticmethod
    def _chat(profile):
        return (profile.onboarding_state or {}).get("chat_v1", {})

    def _store(self, profile, chat):
        profile.onboarding_state = {**(profile.onboarding_state or {}), "chat_v1": chat}
        self.profiles.session.flush()

    def state(self, profile):
        chat = self._chat(profile)
        answers = chat.get("answers", [])
        # A consent withdrawn through account settings also blocks a saved draft.
        stage = chat.get("stage", "consent")
        if stage not in {"consent", "declined"} and not profile.ai_processing_consent:
            stage = "consent"
        pending = chat.get("pending") if stage == "confirmation" else None
        question_id = chat.get("current")
        question = PREGUNTAS.get(question_id) if stage in {"question", "confirmation"} else None
        return {
            "stage": stage,
            "question": {"id": question.id, "text": question.text, "block": question.block,
                         "options": [label for label, _ in question.options]} if question else None,
            "pending": pending,
            "confirmed_answers": [{k: v for k, v in a.items() if k != "extracted"} for a in answers],
            "completed_questions": len(answers) + len(chat.get("manual_skipped", [])),
            "total_questions": len(QUESTION_ORDER) - len(chat.get("skipped", [])),
            "message": NO_CONSENT if stage == "declined" else None,
            "skipped_questions": chat.get("manual_skipped", []),
            "auto_skipped_questions": chat.get("skipped", []),
            "is_update": chat.get("is_update", False),
        }

    @staticmethod
    def declarations(chat):
        return {**{a['question_id']: a.get('extracted', {}).get('status', 'unknown') for a in chat.get('answers', [])},
                **chat.get('declarations', {})}

    def restart(self, profile):
        chat = self._chat(profile)
        if chat.get('stage') in {'question', 'confirmation'}:
            return self.state(profile)
        self._store(profile, {'stage': 'question' if profile.ai_processing_consent else 'consent',
            'current': QUESTION_ORDER[0], 'answers': [], 'manual_skipped': [], 'skipped': [],
            'declarations': self.declarations(chat), 'is_update': chat.get('stage') == 'completed' or chat.get('is_update', False)})
        profile.onboarding_completed = False
        self.profiles.session.flush()
        return self.state(profile)

    def _advance(self, profile, chat):
        done = {a['question_id'] for a in chat.get('answers', [])} | set(chat.get('manual_skipped', [])) | set(chat.get('skipped', []))
        next_id = next((q for q in QUESTION_ORDER if q not in done), None)
        profile.onboarding_completed = next_id is None
        self._store(profile, {**chat, 'pending': None, 'current': next_id,
                              'stage': 'completed' if next_id is None else 'question'})
        return self.state(profile)

    def skip(self, profile, question_id):
        chat = self._chat(profile)
        if not profile.ai_processing_consent:
            raise ChatConflict('Primero da tu consentimiento para continuar.')
        if question_id in chat.get('manual_skipped', []):
            return self.state(profile)
        if chat.get('stage') != 'question' or chat.get('current') != question_id:
            raise ChatConflict('La pregunta ha cambiado. Actualiza la conversación.')
        # Workflow metadata only: no extraction, clinical writes, or risk evaluation.
        return self._advance(profile, {**chat, 'manual_skipped': [*chat.get('manual_skipped', []), question_id]})

    def consent(self, profile, accepted):
        chat = self._chat(profile)
        if chat.get("stage") not in {None, "consent", "declined"} and profile.ai_processing_consent:
            raise ChatConflict("El consentimiento ya está registrado. Continúa con la pregunta actual.")
        profile.ai_processing_consent = accepted
        profile.ai_processing_consent_at = datetime.now(timezone.utc)
        profile.onboarding_completed = not accepted
        # Preserve confirmed progress when consent is given again; discard any old draft.
        chat = {**chat, "stage": "question" if accepted else "declined", "pending": None,
                "current": chat.get("current") or QUESTION_ORDER[0]}
        if accepted and len(chat.get("answers", [])) + len(chat.get("manual_skipped", [])) + len(chat.get("skipped", [])) == len(QUESTION_ORDER):
            chat["stage"] = "completed"
            profile.onboarding_completed = True
        self._store(profile, chat)
        return self.state(profile)

    def answer(self, profile, question_id, message):
        chat = self._chat(profile)
        if not profile.ai_processing_consent or chat.get("stage") != "question":
            raise ChatConflict("Primero da tu consentimiento o confirma la respuesta pendiente.")
        if question_id != chat.get("current"):
            raise ChatConflict("La pregunta ha cambiado. Actualiza la conversación.")
        message = message.strip()
        if not message:
            raise ValueError("Escribe tu respuesta en un único mensaje.")
        payload = self.client.complete(extraction_prompt(question_id), PREGUNTAS[question_id].text, message)
        try:
            extracted, summary = validate_extraction(question_id, payload)
        except (KeyError, TypeError, ValueError):
            raise ValueError("No he podido interpretar todos los datos. Responde en un único mensaje con las unidades y detalles solicitados. Si no lo sabes, escribe «no sé». Para alergias, indica la gravedad; para medicamentos, la dosis y la frecuencia.") from None
        draft = {"draft_id": str(uuid4()), "question_id": question_id,
                 "question": PREGUNTAS[question_id].text, "answer": message,
                 "summary": summary, "extracted": extracted}
        if chat.get('is_update') and question_id in {'allergies', 'chronic_conditions', 'medication', 'family_history'} and extracted['status'] != 'unknown':
            draft['summary'] = [*summary, 'Este resumen sustituirá los datos anteriores de este apartado. Incluye todos los datos que quieras conservar.']
        if extracted['status'] == 'unknown':
            draft['summary'] = ['No has indicado un dato nuevo. Se mantienen los datos anteriores; si no había datos, seguirán sin registrar.']
        self._store(profile, {**chat, "stage": "confirmation", "pending": draft})
        return self.state(profile)

    def confirm(self, profile, draft_id, confirmed):
        chat = self._chat(profile)
        draft = chat.get("pending")
        if not profile.ai_processing_consent:
            raise ChatConflict("Se necesita tu consentimiento antes de guardar datos.")
        # A retried confirmation is harmless, including after the next draft exists.
        if any(a.get("draft_id") == draft_id for a in chat.get("answers", [])):
            return self.state(profile)
        if chat.get("stage") != "confirmation" or not draft or draft.get("draft_id") != draft_id:
            raise ChatConflict("Esta confirmación ya no está pendiente. Actualiza la conversación.")
        if not confirmed:
            self._store(profile, {**chat, "stage": "question", "pending": None})
            return self.state(profile)
        question_id = draft["question_id"]
        self._persist(profile, question_id, draft["extracted"], chat)
        answers = [*chat.get("answers", []), draft]
        skipped = list(chat.get("skipped", []))
        # An explicit zero skips only the two dependent alcohol questions.
        if question_id == "auditc_frequency" and draft["extracted"]["data"].get("frequency") == 0:
            skipped = ["auditc_quantity", "auditc_binge"]
        declarations = self.declarations(chat)
        if draft['extracted']['status'] != 'unknown' or question_id not in declarations:
            declarations[question_id] = draft['extracted']['status']
        self._advance(profile, {**chat, "answers": answers, "skipped": skipped, 'declarations': declarations})
        if self.risk_service is not None:
            # All derived assessments see confirmed values only.
            self.risk_service.evaluate_and_record(profile.id, trigger="onboarding")
        return self.state(profile)

    def _persist(self, profile, question_id, extracted, chat):
        status, data = extracted["status"], extracted["data"]
        if status == 'unknown':
            return
        if question_id == "family_history":
            profile.family_history_reviewed = True
        list_model = {'allergies': Allergy, 'chronic_conditions': ChronicCondition, 'medication': Medication, 'family_history': FamilyHistoryEntry}.get(question_id)
        if list_model is not None and status == 'none':
            self.profiles.replace_health_records(list_model, profile.id, [])
        if status != "data":
            return
        if question_id in {"height", "weight", "blood_type"}:
            for key, value in data.items():
                setattr(profile, key, value)
        elif question_id in HABITS:
            habit = HABITS[question_id]
            self.profiles.add_health_record(HabitLog(patient_id=profile.id, habit_type=habit,
                value=data["value"], unit=CANONICAL_UNITS[habit], date=date.today()))
        elif question_id in ALCOHOL:
            existing = self.profiles.list_alcohol_logs(profile.id)
            latest = existing[0] if existing else None
            values = {key: getattr(latest, key, None) for key in ('frequency', 'quantity', 'binge')}
            values.update((profile.onboarding_state or {}).get('alcohol_current', {}))
            for answer in [*chat.get("answers", []), {"question_id": question_id, "extracted": extracted}]:
                if answer["question_id"] in ALCOHOL:
                    values.update(answer["extracted"]["data"])
            if values.get('frequency') == 0:
                values['quantity'] = values['binge'] = None
            profile.onboarding_state = {**(profile.onboarding_state or {}), 'alcohol_current': values}
            if values.get("frequency") == 0 or all(values.get(k) is not None for k in ("frequency", "quantity", "binge")):
                self.profiles.add_health_record(AlcoholLog(patient_id=profile.id, date=date.today(),
                    frequency=values["frequency"], quantity=values.get("quantity"), binge=values.get("binge")))
        elif question_id == "family_history":
            records = []
            for entry in data["entries"]:
                records.append(FamilyHistoryEntry(patient_id=profile.id,
                    relationship=entry["relationship"], condition_category=entry["category"],
                    detail=entry["detail"], age_at_diagnosis=entry["age"], recorded_date=date.today()))
            self.profiles.replace_health_records(FamilyHistoryEntry, profile.id, records)
        else:
            model = {"allergies": Allergy, "chronic_conditions": ChronicCondition, "medication": Medication}[question_id]
            records = []
            for item in data["records"]:
                values = dict(item)
                if values.get("diagnosis_date"):
                    values["diagnosis_date"] = date.fromisoformat(values["diagnosis_date"])
                records.append(model(patient_id=profile.id, **values))
            self.profiles.replace_health_records(model, profile.id, records)
