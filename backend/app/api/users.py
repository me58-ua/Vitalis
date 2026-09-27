from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_admin, get_professional_repository, get_user_repository
from app.models import ProfessionalApprovalStatus, User, UserRole
from app.repositories.professional_repository import ProfessionalRepository
from app.schemas.profiles import ProfessionalProfileResponse
from app.schemas.professional_approval import ProfessionalRejectionRequest
from app.services.professional_approval_service import ProfessionalApprovalError, ProfessionalApprovalService
from app.repositories.user_repository import UserRepository
from app.schemas.users import (
	AdminUserCreate,
	AdminUserListResponse,
	AdminUserResponse,
	AdminUserUpdate,
)
from app.services.admin_user_service import (
	AdminUserConflictError,
	AdminUserDeleteConflictError,
	AdminUserNotFoundError,
	AdminUserService,
)


router = APIRouter(prefix="/admin/users", tags=["admin-users"])
professional_approval_router = APIRouter(prefix="/admin/professionals", tags=["admin-professionals"])
AdminUser = Annotated[User, Depends(get_current_admin)]
Users = Annotated[UserRepository, Depends(get_user_repository)]
Professionals = Annotated[ProfessionalRepository, Depends(get_professional_repository)]


@professional_approval_router.get("/pending", response_model=list[ProfessionalProfileResponse])
def list_pending_professionals(_: AdminUser, professionals: Professionals):
	return ProfessionalApprovalService(professionals, None).list_pending()


@professional_approval_router.post("/{professional_id}/approve", response_model=ProfessionalProfileResponse)
def approve_professional(
	professional_id: UUID,
	admin: AdminUser,
	professionals: Professionals,
	users: Users,
):
	try:
		return ProfessionalApprovalService(professionals, users).decide(
			professional_id, admin, ProfessionalApprovalStatus.APPROVED
		)
	except ProfessionalApprovalError as error:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@professional_approval_router.post("/{professional_id}/reject", response_model=ProfessionalProfileResponse)
def reject_professional(
	professional_id: UUID,
	data: ProfessionalRejectionRequest,
	admin: AdminUser,
	professionals: Professionals,
	users: Users,
):
	try:
		return ProfessionalApprovalService(professionals, users).decide(
			professional_id,
			admin,
			ProfessionalApprovalStatus.REJECTED,
			data.reason,
		)
	except ProfessionalApprovalError as error:
		status_code = status.HTTP_400_BAD_REQUEST if "reason" in str(error).lower() else status.HTTP_404_NOT_FOUND
		raise HTTPException(status_code=status_code, detail=str(error)) from error


def parse_role(value: str | None) -> UserRole | None:
	if value is None:
		return None
	try:
		return UserRole(value.lower())
	except ValueError as error:
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail="role must be PATIENT, PROFESSIONAL, or ADMIN",
		) from error


@router.get("", response_model=AdminUserListResponse)
def list_users(
	_: AdminUser,
	users: Users,
	role: str | None = Query(default=None),
	search: str | None = Query(default=None, max_length=100),
	page: int = Query(default=1, ge=1),
	page_size: int = Query(default=20, ge=1, le=100),
) -> AdminUserListResponse:
	records, total = AdminUserService(users).list(
		role=parse_role(role),
		search=search,
		offset=(page - 1) * page_size,
		limit=page_size,
	)
	return AdminUserListResponse(users=records, total=total, page=page, page_size=page_size)


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(data: AdminUserCreate, _: AdminUser, users: Users) -> User:
	try:
		return AdminUserService(users).create(data)
	except AdminUserConflictError as error:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{user_id}", response_model=AdminUserResponse)
def get_user(user_id: UUID, _: AdminUser, users: Users) -> User:
	try:
		return AdminUserService(users).get(user_id)
	except AdminUserNotFoundError as error:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/{user_id}", response_model=AdminUserResponse)
def update_user(user_id: UUID, data: AdminUserUpdate, _: AdminUser, users: Users) -> User:
	try:
		service = AdminUserService(users)
		return service.update(service.get(user_id), data)
	except AdminUserNotFoundError as error:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
	except AdminUserConflictError as error:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, _: AdminUser, users: Users) -> None:
	try:
		AdminUserService(users).delete(user_id)
	except AdminUserNotFoundError as error:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
	except AdminUserDeleteConflictError as error:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
