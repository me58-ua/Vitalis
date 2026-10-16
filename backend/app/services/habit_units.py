"""Canonical units, conversions, and ranges for habit logs."""

import math


HABIT_UNITS = {
    "sueno": {"canonical": "horas/noche", "accepted": {"horas/noche", "min/noche"}, "maximum": 24},
    "ejercicio": {"canonical": "min/semana", "accepted": {"min/semana", "min/dia"}, "maximum": 2520},
    "dieta": {"canonical": "raciones_fruta_verdura/dia", "accepted": {"raciones_fruta_verdura/dia"}, "maximum": 20},
    "tabaco": {"canonical": "cigarrillos/dia", "accepted": {"cigarrillos/dia"}, "maximum": 100},
}

# Kept as a public mapping for callers that only need the canonical unit.
CANONICAL_UNITS = {habit_type: config["canonical"] for habit_type, config in HABIT_UNITS.items()}


def _habit_value(habit_type) -> str:
    return habit_type.value if hasattr(habit_type, "value") else habit_type


def _config(habit_type) -> tuple[str, dict]:
    value = _habit_value(habit_type)
    try:
        return value, HABIT_UNITS[value]
    except KeyError as error:
        raise ValueError(f"Unknown habit type: {value}") from error


def canonical_unit(habit_type, unit: str) -> str:
    value, config = _config(habit_type)
    if not unit:
        raise ValueError("Unit is required")
    if unit not in config["accepted"]:
        raise ValueError(f"Unit for {value} must be one of {sorted(config['accepted'])}")
    return config["canonical"]


def normalize_habit_value(habit_type, value: float | None, unit: str) -> tuple[float | None, str]:
    """Validate a habit value and return it in its canonical unit."""
    value_name, config = _config(habit_type)
    canonical = canonical_unit(habit_type, unit)
    if value is None:
        return None, canonical
    if not math.isfinite(value):
        raise ValueError(f"Value for {value_name} must be finite")

    converted = value
    if value_name == "ejercicio" and unit == "min/dia":
        converted = value * 7
    elif value_name == "sueno" and unit == "min/noche":
        converted = value / 60

    if converted < 0 or converted > config["maximum"]:
        raise ValueError(f"Value for {value_name} must be between 0 and {config['maximum']}")
    return converted, canonical


def exercise_minutes_per_week(value: float, unit: str) -> float:
    normalized, _ = normalize_habit_value("ejercicio", value, unit)
    assert normalized is not None
    return normalized
