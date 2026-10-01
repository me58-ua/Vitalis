from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        self.session.flush()
        return log