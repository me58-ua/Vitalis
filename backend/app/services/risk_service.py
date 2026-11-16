"""Deterministic, explainable risk calculations for the early-risk feature."""

import logging
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Callable, Iterable

from app.repositories.risk_repository import RiskInputs, RiskRepository
from app.repositories.risk_snapshot_repository import RiskSnapshotRepository
from app.models import RiskSnapshot, RiskSnapshotTrigger
from app.services.notification_service import NotificationService
from app.schemas.risk import RiskResult


logger = logging.getLogger(__name__)

OMS_SOURCE = "WHO adult BMI and physical activity guidance: https://www.who.int/"
AUDIT_C_SOURCE = "Bush et al. 1998, AUDIT-C sex-specific thresholds"
TOBACCO_SOURCE = "Vitalis v1 fixed cigarette-consumption bands"
FAMILY_SOURCE = "Vitalis v1 family-history rules"
DISCLAIMER = "This is a screening aid, not a diagnosis or a probability."

BMI_UNDERWEIGHT = 18.5
BMI_HEALTHY_MAX = 24.9
BMI_OVERWEIGHT_MAX = 29.9
AUDIT_C_WOMEN_THRESHOLD = 3
AUDIT_C_MEN_THRESHOLD = 4
SEDENTARY_MINUTES_THRESHOLD = 150


def _insufficient(model: str, missing: list[str], explanation: str, source: str) -> RiskResult:
    return RiskResult(
        model=model,
        status="insufficient_data",
        explanation=explanation,
        missing=missing,
        source=source,
        disclaimer=DISCLAIMER,
    )


def _ok(
    model: str,
    metric_value: float,
    category: str,
    alert_level: str,
    explanation: str,
    source: str,
) -> RiskResult:
    return RiskResult(
        model=model,
        status="ok",
        metric_value=metric_value,
        category=category,
        alert_level=alert_level,
        explanation=explanation,
        source=source,
        disclaimer=DISCLAIMER,
    )


def calc_bmi(
    height_cm: float | None,
    weight_kg: float | None,
    birth_date: date | None,
    today: date | None = None,
) -> RiskResult:
    """Calculate adult BMI from height in centimetres and weight in kilograms.

    BMI is weight_kg divided by height_m squared. The calculation requires a
    birth date proving the patient is at least 18; children are not classified
    with adult WHO thresholds. Missing or invalid measurements are not guessed.
    """
    if height_cm is None or weight_kg is None:
        missing = [key for key, value in (("height_cm", height_cm), ("weight_kg", weight_kg)) if value is None]
        return _insufficient("bmi", missing, "No se puede calcular el BMI porque faltan datos de altura o peso.", OMS_SOURCE)
    if birth_date is None:
        return _insufficient("bmi", ["birth_date"], "Adult age cannot be established.", OMS_SOURCE)
    reference = today or date.today()
    age = reference.year - birth_date.year - ((reference.month, reference.day) < (birth_date.month, birth_date.day))
    if age < 18:
        return _insufficient("bmi", ["adult_age"], "Adult BMI thresholds do not apply before age 18.", OMS_SOURCE)
    if height_cm <= 0 or weight_kg <= 0:
        return _insufficient("bmi", ["valid_measurements"], "Height and weight must be positive.", OMS_SOURCE)
    bmi = float(weight_kg) / (float(height_cm) / 100) ** 2
    if bmi < BMI_UNDERWEIGHT:
        category, alert = "underweight", "info"
    elif bmi <= BMI_HEALTHY_MAX:
        category, alert = "healthy", "info"
    elif bmi <= BMI_OVERWEIGHT_MAX:
        category, alert = "overweight", "elevated"
    else:
        category, alert = "obesity", "high"
    return _ok("bmi", round(bmi, 2), category, alert, "BMI was calculated from the supplied adult measurements.", OMS_SOURCE)


def calc_audit_c(
    frequency: int | None,
    quantity: int | None,
    binge: int | None,
    sex_at_birth: str | None,
) -> RiskResult:
    """Calculate AUDIT-C from three coded answers and sex at birth.

    ``frequency``, ``quantity`` and ``binge`` are the official 0-4 AUDIT-C
    scores. A zero frequency makes the other two scores irrelevant. Sex is
    required because the positive screening threshold is 3 for women and 4
    for men; unknown sex is intentionally insufficient rather than inferred.
    """
    scores = (frequency, quantity, binge)
    if any(score is not None and (isinstance(score, bool) or not 0 <= score <= 4) for score in scores):
        return _insufficient("audit_c", ["valid_scores"], "AUDIT-C answers must use scores from 0 to 4.", AUDIT_C_SOURCE)
    if frequency is None or sex_at_birth is None:
        return _insufficient("audit_c", ["frequency" if frequency is None else "sex_at_birth"], "AUDIT-C score and sex are required.", AUDIT_C_SOURCE)
    if frequency == 0:
        total = 0
    elif quantity is None or binge is None:
        return _insufficient("audit_c", ["quantity" if quantity is None else "binge"], "All AUDIT-C answers are required when frequency is non-zero.", AUDIT_C_SOURCE)
    else:
        total = frequency + quantity + binge
    normalized_sex = sex_at_birth.strip().casefold()
    if normalized_sex in {"mujer", "female", "f", "woman"}:
        threshold = AUDIT_C_WOMEN_THRESHOLD
    elif normalized_sex in {"hombre", "male", "m", "man"}:
        threshold = AUDIT_C_MEN_THRESHOLD
    else:
        return _insufficient("audit_c", ["sex_at_birth"], "The AUDIT-C sex-specific threshold is unavailable.", AUDIT_C_SOURCE)
    category = "positive_screen" if total >= threshold else "lower_screen"
    alert = "elevated" if total >= threshold else "info"
    return _ok("audit_c", float(total), category, alert, f"AUDIT-C total {total}; positive screening threshold for this sex is {threshold}.", AUDIT_C_SOURCE)


def calc_tobacco(logs: Iterable[object]) -> RiskResult:
    """Average cigarettes per day from tobacco logs recorded in the last 30 days.

    Each log must expose ``value`` in the canonical ``cigarrillos/dia`` unit.
    The average prevents one unusually high or low entry from replacing the
    patient's recent history; no logs means insufficient data.
    """
    values = [
        float(log.value)
        for log in logs
        if log.value is not None and getattr(log, "unit", None) == "cigarrillos/dia"
    ]
    if not values:
        return _insufficient("tobacco", ["tobacco_logs"], "At least one recent tobacco record is required.", TOBACCO_SOURCE)
    average = mean(values)
    if average == 0:
        category, alert = "none", "info"
    elif average <= 10:
        category, alert = "low", "elevated"
    elif average <= 20:
        category, alert = "moderate", "elevated"
    else:
        category, alert = "high", "high"
    return _ok("tobacco", round(average, 2), category, alert, "Average recent cigarette consumption was calculated from tobacco logs.", TOBACCO_SOURCE)


def calc_sedentary(logs: Iterable[object]) -> RiskResult:
    """Estimate weekly exercise minutes from at least three recent logs.

    Each log must expose ``value`` in canonical ``min/semana`` units. The
    returned metric is the arithmetic mean of the recent weekly values, so
    irregular entries do not get mistaken for one cumulative month.
    """
    values = [
        float(log.value)
        for log in logs
        if log.value is not None and getattr(log, "unit", None) == "min/semana"
    ]
    if len(values) < 3:
        return _insufficient("sedentary", ["three_exercise_logs"], "At least three recent exercise records are required.", OMS_SOURCE)
    weekly_minutes = mean(values)
    if weekly_minutes >= SEDENTARY_MINUTES_THRESHOLD:
        category, alert = "active", "info"
    elif weekly_minutes >= 75:
        category, alert = "low_activity", "elevated"
    elif weekly_minutes > 0:
        category, alert = "very_low_activity", "high"
    else:
        category, alert = "inactive", "high"
    return _ok("sedentary", round(weekly_minutes, 2), category, alert, "Recent weekly exercise minutes were averaged and compared with the WHO 150-minute threshold.", OMS_SOURCE)


def calc_family_history(
    entries: Iterable[object],
    bmi: float | None = None,
) -> list[RiskResult]:
    """Create one deterministic result per supported hereditary condition.

    Entries provide ``condition_category`` and ``relationship``. First-degree
    relationships (parent, sibling, or child) can reach ``elevated``; other
    relationships are capped at informational severity. Diabetes is elevated
    when a family entry exists and BMI is at least 25, or when it has a
    first-degree relative.
    """
    grouped: dict[str, list[object]] = {}
    for entry in entries:
        category = getattr(entry.condition_category, "value", entry.condition_category)
        if category in {"diabetes", "cancer", "cardiovascular", "huntington"}:
            grouped.setdefault(category, []).append(entry)
        elif category == "otro":
            grouped.setdefault("other", []).append(entry)
    results = []
    for category, category_entries in grouped.items():
        first_degree = any(
            getattr(entry.relationship, "value", entry.relationship)
            in {"madre", "padre", "hermano", "hijo"}
            for entry in category_entries
        )
        model = f"family_{category}"
        alert = "elevated" if first_degree or (category == "diabetes" and bmi is not None and bmi >= 25) else "info"
        explanation = "Family history was grouped from explicitly recorded entries."
        if first_degree:
            explanation += " A first-degree relative warrants discussing a preventive appointment."
        if category == "diabetes" and bmi is not None and bmi >= 25:
            explanation += " Diabetes family history is elevated because BMI is at least 25."
        results.append(_ok(model, float(len(category_entries)), "family_history", alert, explanation, FAMILY_SOURCE))
    return results


Calculator = Callable[..., RiskResult | list[RiskResult]]
CALCULATORS: dict[str, Calculator] = {
    "bmi": calc_bmi,
    "audit_c": calc_audit_c,
    "tobacco": calc_tobacco,
    "sedentary": calc_sedentary,
    "family_history": calc_family_history,
}


def calc_trend(model: str, snapshots: Iterable[object]) -> str:
    """Classify the two most recent snapshots without inferring missing data."""
    if model.startswith("family_"):
        return "insufficient_history"
    ordered = sorted(
        snapshots,
        key=lambda item: getattr(item, "computed_at", date.min),
    )
    if len(ordered) < 2:
        return "insufficient_history"
    previous, current = ordered[-2], ordered[-1]
    if previous.metric_value is None or current.metric_value is None:
        return "insufficient_history"
    previous_value = float(previous.metric_value)
    current_value = float(current.metric_value)
    if model == "bmi":
        def distance(value: float) -> float:
            if value < BMI_UNDERWEIGHT:
                return BMI_UNDERWEIGHT - value
            if value > BMI_HEALTHY_MAX:
                return value - BMI_HEALTHY_MAX
            return 0
        old_distance, new_distance = distance(previous_value), distance(current_value)
        better = new_distance < old_distance
        worse = new_distance > old_distance
    elif model in {"audit_c", "tobacco"}:
        better = current_value < previous_value
        worse = current_value > previous_value
    elif model == "sedentary":
        better = current_value > previous_value
        worse = current_value < previous_value
    else:
        return "insufficient_history"
    if better:
        return "improving"
    if worse:
        return "worsening"
    return "stable"


class RiskService:
    def __init__(
        self,
        repository: RiskRepository,
        snapshots: RiskSnapshotRepository | None = None,
        notifications: NotificationService | None = None,
    ):
        self.repository = repository
        self.snapshots = snapshots
        self.notifications = notifications

    def evaluate(self, patient_id, today: date | None = None) -> list[RiskResult]:
        """Evaluate all available models without writing results to the database."""
        inputs = self.repository.get_inputs(patient_id, today=today)
        if inputs is None or not inputs.profile.ai_processing_consent:
            return []
        results: list[RiskResult] = []
        calls = (
            ("bmi", lambda: CALCULATORS["bmi"](inputs.profile.height_cm, inputs.profile.weight_kg, inputs.profile.birth_date, today)),
            ("audit_c", lambda: CALCULATORS["audit_c"](
                inputs.alcohol_log.frequency if inputs.alcohol_log else None,
                inputs.alcohol_log.quantity if inputs.alcohol_log else None,
                inputs.alcohol_log.binge if inputs.alcohol_log else None,
                inputs.profile.sex_at_birth,
            )),
            ("tobacco", lambda: CALCULATORS["tobacco"](inputs.tobacco_logs)),
            ("sedentary", lambda: CALCULATORS["sedentary"](inputs.exercise_logs)),
        )
        for model, calculate in calls:
            try:
                result = calculate()
                results.extend(result if isinstance(result, list) else [result])
            except (TypeError, ValueError, AttributeError):
                logger.exception("Risk calculator failed for model=%s", model)
        try:
            bmi_result = calc_bmi(
                inputs.profile.height_cm,
                inputs.profile.weight_kg,
                inputs.profile.birth_date,
                today,
            )
            bmi = bmi_result.metric_value if bmi_result.status == "ok" else None
            results.extend(CALCULATORS["family_history"](inputs.family_history, bmi=bmi))
        except (TypeError, ValueError, AttributeError):
            logger.exception("Risk calculator failed for model=family_history")
        return results

    def evaluate_and_record(self, patient_id, trigger: str) -> list[RiskSnapshot]:
        """Evaluate and persist only successful changes in the caller's transaction."""
        if self.snapshots is None:
            raise RuntimeError("RiskSnapshotRepository is required to record risk evaluations")
        try:
            trigger_value = RiskSnapshotTrigger(trigger)
        except ValueError as error:
            raise ValueError("Invalid risk snapshot trigger") from error
        results = self.evaluate(patient_id)
        recorded: list[RiskSnapshot] = []
        for result in results:
            if result.status != "ok":
                continue
            latest = self.snapshots.latest_by_model(patient_id, result.model)
            if latest is not None and (
                float(latest.metric_value) if latest.metric_value is not None else None
            ) == result.metric_value and latest.category == result.category and latest.alert_level == result.alert_level:
                continue
            recorded.append(self.snapshots.create(RiskSnapshot(
                patient_id=patient_id,
                model=result.model,
                metric_value=result.metric_value,
                category=result.category or "",
                alert_level=result.alert_level or "none",
                trigger=trigger_value,
            )))
            if self.notifications is not None and result.alert_level not in {None, "none"}:
                self.notifications.notify_risk(
                    inputs.profile.user_id,
                    result.model,
                    result.alert_level,
                )
        return recorded
