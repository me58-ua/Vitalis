"""Safe, database-free family history extraction."""

from dataclasses import dataclass
import json
from typing import Any

from app.models import FamilyRelationship, HereditaryConditions


FAMILY_HISTORY_PROMPT = (
    'Return only JSON with {"status":"entries|none|unknown",'
    '"entries":[{"relationship":"madre|padre|hermano|hijo|abuelo|tio|otro",'
    '"category":"diabetes|cancer|cardiovascular|huntington|otro",'
    '"detail":"string|null","age":0-120|null}]}. '
    "The patient's answer is in Spanish. Use exactly the Spanish enum values shown in the schema. "
    "Interpret only the current answer. Do not infer diseases, relationships, or ages."
)


@dataclass(frozen=True)
class FamilyHistoryDraft:
    relationship: str
    category: str
    detail: str | None
    age: int | None


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
        result.append(FamilyHistoryDraft(relationship, category, detail, age))
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
