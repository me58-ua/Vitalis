from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_audit_repository, get_current_admin
from app.models import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.admin_audit import AuditFilters, AuditListQuery, AuditLogListResponse
from app.services.admin_reporting_service import AdminReportingService

router = APIRouter(prefix="/admin", tags=["admin-audit"])
Admin = Annotated[User, Depends(get_current_admin)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(_: Admin, audits: Audits, query: Annotated[AuditListQuery, Query()], response: Response):
    response.headers["Cache-Control"] = "no-store"
    filters = AuditFilters.model_validate(query.model_dump())
    return AdminReportingService(audits).list_audits(filters, query.page, query.page_size)
