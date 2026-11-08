from sqlalchemy.exc import IntegrityError

from app.models import AuditAction, ProfessionalTimeBlock
from app.services.audit_service import AuditService
from app.services.appointment_service import AppointmentConflictError, AppointmentNotFoundError


class TimeBlockService:
    def __init__(self, blocks, audits=None):
        self.blocks = blocks
        self.audit = AuditService(audits)

    def create(self, user, data):
        try:
            block = self.blocks.create(ProfessionalTimeBlock(professional_id=user.id, **data.model_dump()))
        except IntegrityError as error:
            self.blocks.session.rollback()
            raise AppointmentConflictError("TIME_BLOCK_CONFLICT") from error
        self.audit.record(user.id, user.role, AuditAction.CREATE, "professional_time_block", block.id)
        return block

    def delete(self, user, block_id):
        block = self.blocks.get_owned(user.id, block_id)
        if block is None:
            raise AppointmentNotFoundError("Time block not found")
        self.blocks.delete(block)
        self.audit.record(user.id, user.role, AuditAction.DELETE, "professional_time_block", block_id)
