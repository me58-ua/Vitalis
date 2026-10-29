from app.repositories.audit_repository import AuditRepository
from app.schemas.admin_audit import AuditFilters, AuditLogListResponse


class AdminReportingService:
    """Read-only administrative audit queries; audit creation stays in AuditService."""

    def __init__(self, audits: AuditRepository):
        self.audits = audits

    def list_audits(self, filters: AuditFilters, page: int, page_size: int) -> AuditLogListResponse:
        items, total = self.audits.list(filters.model_dump(), (page - 1) * page_size, page_size)
        return AuditLogListResponse(items=items, total=total, page=page, page_size=page_size)
