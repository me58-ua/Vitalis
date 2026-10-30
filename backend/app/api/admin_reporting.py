from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_audit_repository, get_current_admin, get_user_repository, get_appointment_repository
from app.models import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.admin_audit import AuditFilters, AuditListQuery, AuditLogListResponse
from app.services.admin_reporting_service import AdminReportingService
from app.repositories.user_repository import UserRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.admin_metrics import AdminMonthlyMetricsResponse
from app.services.admin_metrics_service import AdminMetricsService

router = APIRouter(prefix="/admin", tags=["admin-audit"])
Admin = Annotated[User, Depends(get_current_admin)]
Audits = Annotated[AuditRepository, Depends(get_audit_repository)]


@router.get("/metrics/monthly", response_model=AdminMonthlyMetricsResponse)
def monthly_admin_metrics(_: Admin, users: Annotated[UserRepository, Depends(get_user_repository)],
                          appointments: Annotated[AppointmentRepository, Depends(get_appointment_repository)],
                          response: Response, months: int = Query(default=6, ge=2, le=24)):
    response.headers["Cache-Control"] = "no-store"
    return AdminMetricsService(users, appointments).monthly(months)


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(_: Admin, audits: Audits, query: Annotated[AuditListQuery, Query()], response: Response):
    response.headers["Cache-Control"] = "no-store"
    filters = AuditFilters.model_validate(query.model_dump())
    return AdminReportingService(audits).list_audits(filters, query.page, query.page_size)
