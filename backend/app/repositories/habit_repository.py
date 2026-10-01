from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HabitLog, HabitType


class HabitRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_filtered(
        self,
        patient_id: UUID,
        habit_type: HabitType | None,
        search: str | None,
        start_date: date | None,
        end_date: date | None,
        offset: int,
        limit: int,
    ) -> tuple[list[HabitLog], int]:
        filters = self._filters(patient_id, habit_type, search, start_date, end_date)
        query = select(HabitLog).where(*filters).order_by(HabitLog.date.asc(), HabitLog.id.asc()).offset(offset).limit(limit)
        count_query = select(func.count()).select_from(HabitLog).where(*filters)
        return list(self.session.scalars(query)), self.session.scalar(count_query) or 0

    def aggregate(
        self,
        patient_id: UUID,
        habit_type: HabitType | None,
        search: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[dict]:
        filters = self._filters(patient_id, habit_type, search, start_date, end_date)
        rows = self.session.execute(
            select(
                HabitLog.habit_type,
                func.count(HabitLog.id),
                func.count(HabitLog.value),
                func.sum(HabitLog.value),
                func.avg(HabitLog.value),
                func.min(HabitLog.value),
                func.max(HabitLog.value),
            )
            .where(*filters)
            .group_by(HabitLog.habit_type)
            .order_by(HabitLog.habit_type)
        ).all()
        return [
            {
                "habit_type": row[0],
                "count": row[1],
                "numeric_count": row[2],
                "sum": row[3],
                "average": row[4],
                "minimum": row[5],
                "maximum": row[6],
            }
            for row in rows
        ]

    @staticmethod
    def _filters(patient_id, habit_type, search, start_date, end_date):
        filters = [HabitLog.patient_id == patient_id]
        if habit_type is not None:
            filters.append(HabitLog.habit_type == habit_type)
        if search:
            filters.append(HabitLog.unit.ilike(f"%{search}%"))
        if start_date is not None:
            filters.append(HabitLog.date >= start_date)
        if end_date is not None:
            filters.append(HabitLog.date <= end_date)
        return filters