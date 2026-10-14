from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlcoholLog


class AlcoholLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, log: AlcoholLog) -> AlcoholLog:
        self.session.add(log)
        self.session.flush()
        return log

    def latest(self, patient_id: UUID) -> AlcoholLog | None:
        return self.session.scalar(
            select(AlcoholLog)
            .where(AlcoholLog.patient_id == patient_id)
            .order_by(AlcoholLog.date.desc(), AlcoholLog.id.desc())
            .limit(1)
        )

    def list_history(self, patient_id: UUID, cursor: int | None = None, limit: int = 100) -> tuple[list[AlcoholLog], int | None]:
        limit = min(max(limit, 1), 100)
        query = select(AlcoholLog).where(AlcoholLog.patient_id == patient_id)
        if cursor is not None:
            query = query.where(AlcoholLog.id < cursor)
        rows = list(self.session.scalars(query.order_by(AlcoholLog.id.desc()).limit(limit + 1)))
        next_cursor = rows.pop().id if len(rows) > limit else None
        return rows, next_cursor
