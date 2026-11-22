# Servicio de auditoría: registra acciones relevantes de los usuarios mediante `record`.
from uuid import UUID

from app.models import AuditAction, AuditLog, UserRole
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, audits: AuditRepository | None):
        self.audits = audits

    def record(
        self,
        actor_id: UUID | None,
        actor_role: UserRole | None,
        action: AuditAction,
        entity: str,
        entity_id: UUID | None = None,
        patient_id: UUID | None = None,
    ) -> AuditLog | None:
        """Record a resource action; patient_id always refers to users.id."""
        if self.audits is None:
            return None
        return self.audits.create(
            AuditLog(
                actor_id=actor_id,
                actor_role=actor_role,
                accion=action,
                entidad=entity,
                entidad_id=entity_id,
                patient_id=patient_id,
            )
        )
