"""Safe, database-free family history extraction."""

from dataclasses import dataclass
import json
from typing import Any

from app.models import FamilyRelationship, HereditaryConditions

FAMILY_CATEGORY_VALUES = '|'.join(condition.value for condition in HereditaryConditions)
FAMILY_EXTRACTION_RULES = (
    'Record relatives diseases as family medical history even when not confirmed hereditary. '
    'Never add them to the patient personal diagnoses. Never infer a genetic disorder or risk level from family history alone. '
    'Map ictus/derrame cerebral to stroke, hipertension/tension alta to hypertension, colesterol alto to high_cholesterol, '
    'fibrosis quistica to cystic_fibrosis, anemia falciforme/drepanocitosis to sickle_cell_disease. '
    'Use familial_hypercholesterolemia ONLY when that specific diagnosis is explicitly reported; ordinary high cholesterol is not enough. '
    'Preserve separate entries for multiple relatives with the same condition. '
    'The answer may be in any language. Translate every free-text field into natural Spanish while preserving the meaning: '
    'the reported disease or subtype in detail, the specific relative in relative_detail, and additional reported facts in notes. '
    'For example, maternal grandpa is abuelo materno, paternal grandma is abuela paterna, '
    'stomach cancer is cáncer de estómago, and high cholesterol is colesterol alto. '
    'Preserve sex and the maternal or paternal side when stated. Translate ambiguous wording faithfully without inventing a diagnosis. '
    'Keep category and relationship identifiers exactly as listed, regardless of the answer language. '
    'Use null for unknown age; missing age must never block a record. Do not invent facts.'
)


FAMILY_HISTORY_PROMPT = (
    'Return only JSON with {"status":"entries|none|unknown",'
    '"entries":[{"relationship":"madre|padre|hermano|hijo|abuelo|tio|otro",'
    f'"category":"{FAMILY_CATEGORY_VALUES}",'
    '"detail":"string|null","age":0-120|null,"relative_detail":"string|null","notes":"string|null"}]}. '
    "Use exactly the enum identifiers shown in the schema. "
    "Interpret only the current answer. Do not infer diseases, relationships, or ages. " + FAMILY_EXTRACTION_RULES
)


@dataclass(frozen=True)
class FamilyHistoryDraft:
    relationship: str
    category: str
    detail: str | None
    age: int | None
    relative_detail: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class FamilyHistoryParseResult:
    status: str
    entries: list[FamilyHistoryDraft]


def _value(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def sanitize_entries(raw: Any) -> list[FamilyHistoryDraft]:
    if not isinstance(raw, list):
        return []
    relationships = {item.value for item in FamilyRelationship}
    categories = {item.value for item in HereditaryConditions}
    result = []
    for item in raw:
        if len(result) >= 20:
            break
        if not isinstance(item, dict):
            continue
        relationship = item.get("relationship")
        category = item.get("category")
        if not isinstance(relationship, str) or not isinstance(category, str):
            continue
        relationship = relationship if relationship in relationships else "otro"
        category = category if category in categories else "otro"
        detail = item.get("detail")
        if detail is not None and not isinstance(detail, str):
            detail = None
        detail = detail[:150] if detail else None
        age = item.get("age")
        if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 120:
            age = None
        relative_detail = item.get('relative_detail')
        notes = item.get('notes')
        result.append(FamilyHistoryDraft(relationship, category, detail, age,
            relative_detail[:100] if isinstance(relative_detail, str) else None,
            notes[:500] if isinstance(notes, str) else None))
    return result


def parse_family_history(answer: str, llm_client) -> FamilyHistoryParseResult:
    """Make one LLM call and sanitize its closed JSON response."""
    try:
        if hasattr(llm_client, "complete"):
            response = llm_client.complete(FAMILY_HISTORY_PROMPT, answer)
        else:
            response = llm_client(FAMILY_HISTORY_PROMPT, answer)
        payload = _value(response)
        if not isinstance(payload, dict):
            return FamilyHistoryParseResult("invalid", [])
        status = payload.get("status")
        if status not in {"entries", "none", "unknown"}:
            return FamilyHistoryParseResult("invalid", [])
        entries = sanitize_entries(payload.get("entries", []))
        return FamilyHistoryParseResult(status, entries)
    except (OSError, TypeError, ValueError, RuntimeError):
        return FamilyHistoryParseResult("invalid", [])
