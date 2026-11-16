"""Preguntas fijas del onboarding conversacional 

El LLM interpreta las respuestas, pero nunca redacta las preguntas ni decide
su orden. Los IDs son estables para que el frontend pueda renderizar cada
pregunta y para que el servicio seleccione la siguiente.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Pregunta:
    id: str
    text: str
    block: str
    options: tuple[tuple[str, int], ...] = ()


AUDIT_C_FREQUENCY_OPTIONS: Final[tuple[tuple[str, int], ...]] = (
    ("Nunca", 0),
    ("Una o menos veces al mes / Mensualmente o menos", 1),
    ("De 2 a 4 veces al mes", 2),
    ("De 2 a 3 veces a la semana", 3),
    ("4 o más veces a la semana", 4),
)

AUDIT_C_QUANTITY_OPTIONS: Final[tuple[tuple[str, int], ...]] = (
    ("1 o 2", 0),
    ("3 o 4", 1),
    ("5 o 6", 2),
    ("De 7 a 9", 3),
    ("10 o más", 4),
)

AUDIT_C_BINGE_OPTIONS: Final[tuple[tuple[str, int], ...]] = (
    ("Nunca", 0),
    ("Menos de 1 vez al mes", 1),
    ("Mensualmente", 2),
    ("Semanalmente", 3),
    ("A diario o casi a diario", 4),
)


PREGUNTAS: Final[dict[str, Pregunta]] = {
    "ai_processing_consent": Pregunta(
        id="ai_processing_consent",
        text="¿Aceptas que Vitalis procese tus respuestas mediante inteligencia artificial para organizar tu información de salud?",
        block="consentimiento_ia",
        options=(("Sí, acepto", 1), ("No, no acepto", 0)),
    ),
    "auditc_frequency": Pregunta(
        id="auditc_frequency",
        text="¿Con qué frecuencia consume alguna bebida alcohólica?",
        block="alcohol",
        options=AUDIT_C_FREQUENCY_OPTIONS,
    ),
    "auditc_quantity": Pregunta(
        id="auditc_quantity",
        text="¿Cuántas consumiciones de bebidas alcohólicas suele beber en un día de consumo normal?",
        block="alcohol",
        options=AUDIT_C_QUANTITY_OPTIONS,
    ),
    "auditc_binge": Pregunta(
        id="auditc_binge",
        text="¿Con qué frecuencia toma 6 o más bebidas alcohólicas en un solo día?",
        block="alcohol",
        options=AUDIT_C_BINGE_OPTIONS,
    ),
    "height": Pregunta("height", "¿Cuál es tu altura en centímetros?", "cuerpo"),
    "weight": Pregunta("weight", "¿Cuál es tu peso en kilogramos?", "cuerpo"),
    "blood_type": Pregunta("blood_type", "¿Cuál es tu grupo sanguíneo (A+, A-, B+, B-, AB+, AB-, O+ u O-)? Si no lo sabes, puedes omitir la pregunta.", "cuerpo"),
    "tobacco": Pregunta("tobacco", "¿Cuántos cigarrillos fumas al día?", "habitos"),
    "exercise": Pregunta("exercise", "¿Cuántos minutos dedicas al ejercicio a la semana?", "habitos"),
    "sleep": Pregunta("sleep", "¿Cuántas horas duermes normalmente cada noche?", "habitos"),
    "diet": Pregunta("diet", "¿Cuántas raciones de fruta y verdura consumes al día?", "habitos"),
    "family_history": Pregunta(
        "family_history",
        "¿Tienes antecedentes familiares de alguna enfermedad importante? Puedes indicar el parentesco y la enfermedad, o responder «ninguno» o «no sé».",
        "antecedentes_familiares",
    ),
    "allergies": Pregunta(
        "allergies",
        "¿Tienes alguna alergia? Puedes indicar el nombre y su gravedad, o responder «ninguna».",
        "alergias",
    ),
    "chronic_conditions": Pregunta(
        "chronic_conditions",
        "¿Tienes alguna enfermedad crónica diagnosticada? Puedes indicar cuál o responder «ninguna».",
        "enfermedades_cronicas",
    ),
    "medication": Pregunta(
        "medication",
        "¿Tomas actualmente algún medicamento? Puedes indicar el nombre, la dosis y la frecuencia, o responder «ninguno».",
        "medicacion",
    ),
}


# Explicit order de las preguntas
QUESTION_ORDER: Final[tuple[str, ...]] = (
    "allergies", "chronic_conditions", "medication", "height", "weight", "blood_type",
    "auditc_frequency", "auditc_quantity", "auditc_binge", "tobacco",
    "exercise", "sleep", "diet", "family_history",
)


def get_question(question_id: str) -> Pregunta:
    try:
        return PREGUNTAS[question_id]
    except KeyError as error:
        raise KeyError(f"Pregunta de onboarding desconocida: {question_id}") from error
