"""Closed extraction prompts used by the onboarding service.

Instructions are written in English for model consistency. Patient answers
are Spanish, and closed values must use the Spanish persistence contract.
"""

import json
from typing import Any


EXTRACTION_PROMPTS = {
    "alergias": (
        'Return only JSON with {"records":[{"name":"string","severity":"leve|moderada|grave|mortal"}]}. '
        "The patient's answer is in Spanish. Extract only explicit allergies from the current answer. "
        "Use exactly the Spanish enum values shown above. If there is no data, return an empty records array."
    ),
    "enfermedades_cronicas": (
        'Return only JSON with {"records":[{"condition_name":"string","diagnosis_date":"YYYY-MM-DD|null","active":true|false}]}. '
        "The patient's answer is in Spanish. Extract only explicit diagnoses from the current answer."
    ),
    "medicacion": (
        'Return only JSON with {"records":[{"name":"string","dosage":"string","frequency":"string","active":true|false}]}. '
        "The patient's answer is in Spanish. Extract only explicit medication details from the current answer."
    ),
    "habitos": (
        'Return only JSON with {"records":[{"habit_type":"sueno|ejercicio|dieta|tabaco","value":number|null,"unit":"string","date":"YYYY-MM-DD|null"}]}. '
        "The patient's answer is in Spanish. Extract only explicit habits from the current answer. "
        "Use exactly the Spanish habit enum values shown above and do not infer a value."
    ),
    "cuerpo": (
        'Return only JSON with {"height_cm":number|null,"weight_kg":number|null}. '
        "The patient's answer is in Spanish. Extract only explicit height and weight from the current answer."
    ),
    "alcohol": (
        'Return only JSON with {"frequency":0-4,"quantity":0-4|null,"binge":0-4|null}. '
        "The patient's answer is in Spanish. Convert only explicit AUDIT-C answers to 0-4. "
        "If frequency is 0, quantity and binge must be null."
    ),
}


def prompt_for(block: str) -> str:
    try:
        return EXTRACTION_PROMPTS[block]
    except KeyError as error:
        raise ValueError(f"Unknown onboarding extraction block: {block}") from error


def parse_json_object(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        return None
    try:
        result = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None
