"""Canonical units accepted for risk-relevant habit logs."""

CANONICAL_UNITS = {
    "tabaco": "cigarrillos/dia",
    "ejercicio": "min/semana",
}


def canonical_unit(habit_type, unit: str) -> str:
    value = habit_type.value if hasattr(habit_type, "value") else habit_type
    expected = CANONICAL_UNITS.get(value)
    accepted = {expected}
    if value == "ejercicio":
        accepted.add("min/dia")
    if expected is not None and unit not in accepted:
        raise ValueError(f"Unit for {value} must be {expected}")
    if not unit:
        raise ValueError("Unit is required")
    return unit


def exercise_minutes_per_week(value: float, unit: str) -> float:
    if unit == "min/semana":
        return value
    if unit == "min/dia":
        return value * 7
    raise ValueError("Unknown exercise unit")
