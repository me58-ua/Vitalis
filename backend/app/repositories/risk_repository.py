from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlcoholLog, FamilyHistoryEntry, HabitLog, PatientProfile


@dataclass(frozen=True)
class RiskInputs:
    profile: PatientProfile
    alcohol_log: AlcoholLog | None
    tobacco_logs: list[HabitLog]
    exercise_logs: list[HabitLog]
    family_history: list[FamilyHistoryEntry]


class RiskRepository:
    """Read-only loader for the inputs consumed by the deterministic calculators."""

    def __init__(self, session: Session):
        self.session = session

    def get_inputs(self, patient_id: UUID, today: date | None = None) -> RiskInputs | None:
        profile = self.session.get(PatientProfile, patient_id)
        if profile is None:
            return None
        cutoff = (today or date.today()) - timedelta(days=30)
        alcohol_log = self.session.scalar(
            select(AlcoholLog)
            .where(AlcoholLog.patient_id == patient_id)
            .order_by(AlcoholLog.date.desc(), AlcoholLog.id.desc())
            .limit(1)
        )
        habits = list(
            self.session.scalars(
                select(HabitLog)
                .where(
                    HabitLog.patient_id == patient_id,
                    HabitLog.date >= cutoff,
                    HabitLog.habit_type.in_(("tabaco", "ejercicio")),
                )
                .order_by(HabitLog.date, HabitLog.id)
            )
        )
        family_history = list(
            self.session.scalars(
                select(FamilyHistoryEntry)
                .where(FamilyHistoryEntry.patient_id == patient_id)
                .order_by(FamilyHistoryEntry.recorded_date, FamilyHistoryEntry.id)
            )
        )
        return RiskInputs(
            profile=profile,
            alcohol_log=alcohol_log,
            tobacco_logs=[log for log in habits if log.habit_type.value == "tabaco"],
            exercise_logs=[log for log in habits if log.habit_type.value == "ejercicio"],
            family_history=family_history,
        )
