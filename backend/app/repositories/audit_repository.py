from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.models import AuditLog


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        self.session.flush()
        return log

    def list(self, filters: dict, offset: int, limit: int) -> tuple[list[AuditLog], int]:
        conditions = []
        for key, value in filters.items():
            if value is None:
                continue
            if key == "from_date":
                conditions.append(AuditLog.fecha_hora >= value)
            elif key == "to_date":
                conditions.append(AuditLog.fecha_hora <= value)
            else:
                conditions.append(getattr(AuditLog, key) == value)
        total = self.session.scalar(select(func.count()).select_from(AuditLog).where(*conditions)) or 0
        query = select(AuditLog).where(*conditions).order_by(AuditLog.fecha_hora.desc(), AuditLog.id.desc())
        return list(self.session.scalars(query.offset(offset).limit(limit))), total
