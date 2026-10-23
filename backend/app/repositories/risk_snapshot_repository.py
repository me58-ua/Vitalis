from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RiskSnapshot


class RiskSnapshotRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, snapshot: RiskSnapshot) -> RiskSnapshot:
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def latest_by_model(self, patient_id: UUID, model: str) -> RiskSnapshot | None:
        return self.session.scalar(
            select(RiskSnapshot)
            .where(RiskSnapshot.patient_id == patient_id, RiskSnapshot.model == model)
            .order_by(RiskSnapshot.computed_at.desc(), RiskSnapshot.id.desc())
            .limit(1)
        )

    def list_history(
        self, patient_id: UUID, model: str | None = None, from_date: datetime | None = None,
        to_date: datetime | None = None, cursor: str | None = None, limit: int = 100,
    ) -> tuple[list[RiskSnapshot], str | None]:
        limit = min(max(limit, 1), 100)
        query = select(RiskSnapshot).where(RiskSnapshot.patient_id == patient_id)
        if model is not None:
            query = query.where(RiskSnapshot.model == model)
        if from_date is not None:
            query = query.where(RiskSnapshot.computed_at >= from_date)
        if to_date is not None:
            query = query.where(RiskSnapshot.computed_at <= to_date)
        if cursor:
            try:
                cursor_date, cursor_id = cursor.split("|", 1)
                cursor_dt = datetime.fromisoformat(cursor_date)
                query = query.where(
                    (RiskSnapshot.computed_at < cursor_dt)
                    | ((RiskSnapshot.computed_at == cursor_dt) & (RiskSnapshot.id < UUID(cursor_id)))
                )
            except (ValueError, TypeError) as error:
                raise ValueError("Invalid risk history cursor") from error
        rows = list(self.session.scalars(
            query.order_by(RiskSnapshot.computed_at.desc(), RiskSnapshot.id.desc()).limit(limit + 1)
        ))
        next_cursor = None
        if len(rows) > limit:
            last = rows.pop()
            next_cursor = f"{last.computed_at.isoformat()}|{last.id}"
        return rows, next_cursor
