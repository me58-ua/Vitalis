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

OMS_SOURCE = "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight"
AUDIT_C_SOURCE = "https://www.hepatitis.va.gov/pdf/auditC-card.pdf"
TOBACCO_SOURCE = "https://www.who.int/news-room/fact-sheets/detail/tobacco"
FAMILY_SOURCE = "https://www.cdc.gov/family-health-history/family-health-history-and-you/family-health-history-and-adults.html"
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
    elif bmi < 25:
        category, alert = "healthy", "info"
    elif bmi < 30:
        category, alert = "overweight", "elevated"
    else:
        category, alert = "obesity", "high"
    meanings = {
        "underweight": "Está por debajo de 18,5, en el intervalo de bajo peso. Conviene revisar tu alimentación y posibles causas con un profesional.",
        "healthy": "Está entre 18,5 y menos de 25, el intervalo de referencia habitual en adultos. Mantener hábitos saludables ayuda a cuidar tu salud.",
        "overweight": "Está entre 25 y menos de 30, en el intervalo de sobrepeso. Puede asociarse con mayor riesgo de diabetes tipo 2 y enfermedad cardiovascular. Una consulta puede ayudarte a valorar otros factores y acordar hábitos adecuados.",
        "obesity": "Es igual o superior a 30, en el intervalo de obesidad. Se asocia con mayor riesgo de diabetes tipo 2 y enfermedad cardiovascular. Te recomendamos pedir cita para una valoración y un plan personalizado.",
    }
    explanation = f"El IMC relaciona el peso con la altura al cuadrado. Tu resultado es {bmi:.2f} kg/m². " + meanings[category]
    explanation += " Es orientativo: no distingue músculo de grasa ni determina por sí solo tu estado de salud."
    return _ok("bmi", round(bmi, 2), category, alert, explanation, OMS_SOURCE)


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
    explanation = f"AUDIT-C resume la frecuencia, cantidad y episodios de consumo elevado de alcohol. Tu puntuación es {total} de 12; el umbral de cribado aplicado es {threshold} (3 para mujeres y 4 para hombres). "
    explanation += (
        "Alcanzas o superas ese umbral: conviene pedir cita para revisar el consumo y cómo reducir posibles daños, como problemas hepáticos y cardiovasculares. Un cribado positivo no diagnostica dependencia."
        if total >= threshold else
        "Estás por debajo del umbral de cribado. Esto no significa que el consumo esté libre de riesgo; cuanto menos alcohol, menor exposición a sus daños."
    )
    return _ok("audit_c", float(total), category, alert, explanation, AUDIT_C_SOURCE)


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
    explanation = f"Tus registros recientes indican una media de {average:g} cigarrillos al día. "
    if average == 0:
        explanation += "No consta consumo de cigarrillos en estos registros. Mantenerte sin fumar y evitar el humo ajeno protege tu salud; este dato no evalúa otros productos de tabaco ni el consumo pasado."
    else:
        band = "hasta 10" if average <= 10 else "más de 10 y hasta 20" if average <= 20 else "más de 20"
        explanation += f"Estás en la franja de {band} cigarrillos al día usada por Vitalis para organizar el consumo, no para calcular una probabilidad de enfermedad. Incluso fumar poco aumenta el riesgo de cáncer, enfermedad cardiovascular y problemas respiratorios; no hay un nivel seguro. Pide cita si quieres apoyo para dejar de fumar."
    return _ok("tobacco", round(average, 2), category, alert, explanation, TOBACCO_SOURCE)


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
    explanation = f"Tus registros indican una media de {weekly_minutes:g} minutos de ejercicio por semana. La referencia para adultos es de 150 a 300 minutos de actividad moderada, o de 75 a 150 de actividad vigorosa, o una combinación equivalente. "
    explanation += "La actividad física ayuda a reducir el riesgo cardiovascular y de diabetes tipo 2. Estos registros no indican intensidad ni tiempo sentado, por lo que no permiten confirmar si cumples toda la recomendación. Si necesitas aumentar tu actividad, acuerda un plan gradual adaptado a tu salud."
    return _ok("sedentary", round(weekly_minutes, 2), category, alert, explanation, "https://www.who.int/news-room/fact-sheets/detail/physical-activity")


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
        relatives = {"madre": "madre", "padre": "padre", "hermano": "hermano/a", "hijo": "hijo/a", "abuelo": "abuelo/a", "tio": "tío/a", "otro": "otro familiar"}
        relationships = sorted({relatives.get(getattr(e.relationship, "value", e.relationship), "familiar") for e in category_entries})
        explanation = "Has registrado este antecedente en: " + ", ".join(relationships) + ". "
        source = FAMILY_SOURCE
        if category == "huntington":
            explanation += "Huntington es una enfermedad hereditaria que puede afectar al movimiento, el pensamiento y el estado de ánimo. Te recomendamos pedir cita para revisar el árbol familiar y valorar asesoramiento genético antes de decidir sobre pruebas. Tener un familiar afectado no confirma que hayas heredado la alteración ni permite calcular aquí tu probabilidad individual."
            source = "https://medlineplus.gov/genetics/condition/huntingtons-disease/"
        elif category == "cancer":
            colorectal = any(any(word in (getattr(e, "detail", None) or "").casefold() for word in ("colon", "colón", "colorrectal", "recto")) for e in category_entries)
            if colorectal:
                explanation += "El antecedente de cáncer de colon o recto puede influir en el riesgo familiar, aunque muchos casos no son hereditarios. Pide cita para revisar el parentesco, la edad al diagnóstico y otros casos, y valorar si necesitas un cribado distinto o asesoramiento genético. Este registro no demuestra un síndrome hereditario."
                source = "https://www.cdc.gov/colorectal-cancer-hereditary/about/index.html"
            else:
                explanation += "Algunos cánceres tienen un componente hereditario, pero un antecedente no demuestra que sea tu caso. Pide cita para revisar el tipo de cáncer, el parentesco, la edad al diagnóstico y otros casos para orientar la prevención y valorar asesoramiento genético."
                source = "https://www.cdc.gov/cancer/risk-factors/family-health-history.html"
        elif category == "diabetes":
            explanation += "La diabetes altera la regulación de la glucosa en sangre. Los antecedentes familiares pueden reflejar factores genéticos y hábitos compartidos, especialmente en la diabetes tipo 2. Conviene pedir cita para revisar qué tipo de diabetes tuvo tu familiar, tus factores personales y si necesitas controles de glucosa; el antecedente no significa que tengas diabetes."
            source = "https://www.niddk.nih.gov/health-information/diabetes/overview/what-is-diabetes/type-2-diabetes"
        elif category == "cardiovascular":
            explanation += "Las enfermedades cardiovasculares afectan al corazón o a los vasos sanguíneos. Los antecedentes familiares pueden aumentar el riesgo, especialmente cuando aparecen a edades tempranas, y pueden combinar factores hereditarios y hábitos compartidos. Pide cita para revisar el diagnóstico familiar, la edad de aparición, la presión arterial y el colesterol, y decidir qué controles necesitas. Este antecedente no demuestra que tengas una enfermedad cardiovascular."
            source = "https://www.cdc.gov/heart-disease-family-history/about/"
        else:
            explanation += "El antecedente se ha clasificado como otra enfermedad. Sin un diagnóstico concreto no podemos describir su mecanismo de herencia ni sus consecuencias. Pide cita y comparte el nombre de la enfermedad, el parentesco y la edad al diagnóstico para valorar si necesitas prevención o asesoramiento genético; este registro no establece un riesgo hereditario por sí solo."
        if first_degree:
            explanation += " Se trata de un familiar de primer grado, un dato importante en la valoración."
        if category == "diabetes" and bmi is not None and bmi >= 25:
            explanation += " Además, tu IMC es igual o superior a 25, otro factor que conviene revisar."
        results.append(_ok(model, float(len(category_entries)), "family_history", alert, explanation, source))
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
                inputs = self.repository.get_inputs(patient_id)
                if inputs is not None:
                    self.notifications.notify_risk(
                        inputs.profile.user_id,
                        result.model,
                        result.alert_level,
                    )
        return recorded
