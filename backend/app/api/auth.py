from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from app.api.deps import get_current_user, get_user_repository
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
	ForgotPasswordRequest,
	ResetPasswordRequest,
	TokenResponse,
	UserRegisterRequest,
	UserResponse,
)
from app.services.password_reset_service import InvalidPasswordResetToken, PasswordResetService
from app.core.rate_limit import password_reset_rate_limiter
from app.services.email_service import (
	send_password_changed_email,
	send_password_reset_email,
)
from app.services.auth_service import (
	AuthService,
	EmailAlreadyRegisteredError,
	InactiveUserError,
	InvalidCredentialsError,
	UsernameAlreadyRegisteredError,
)
from app.services.email_service import send_welcome_email


router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
	data: UserRegisterRequest,
	users: Annotated[UserRepository, Depends(get_user_repository)],
	background_tasks: BackgroundTasks = None,
) -> User:
	try:
		user = AuthService(users).register_patient(data)
		if background_tasks is not None:
			background_tasks.add_task(send_welcome_email, user.email, user.name)
		return user
	except (EmailAlreadyRegisteredError, UsernameAlreadyRegisteredError) as error:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=str(error) or "The email or username is already registered",
		)


@router.post("/login", response_model=TokenResponse)
def login(
	form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
	users: Annotated[UserRepository, Depends(get_user_repository)],
) -> TokenResponse:
	try:
		user = AuthService(users).authenticate(form_data.username, form_data.password)
	except (InvalidCredentialsError, InactiveUserError):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Incorrect email or password",
			headers={"WWW-Authenticate": "Bearer"},
		)
	return TokenResponse(access_token=AuthService(users).issue_access_token(user))


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
	data: ForgotPasswordRequest,
	request: Request,
	users: Annotated[UserRepository, Depends(get_user_repository)],
	background_tasks: BackgroundTasks,
) -> dict[str, str]:
	message = "Si el correo está registrado, recibirás instrucciones para restablecer la contraseña."
	client_host = request.client.host if request.client else "unknown"
	allowed_by_ip = password_reset_rate_limiter.allow(f"ip:{client_host}")
	allowed_by_email = password_reset_rate_limiter.allow(f"email:{data.email}")
	if allowed_by_ip and allowed_by_email:
		user = users.get_by_email(data.email)
		if user is not None and user.is_active:
			token = PasswordResetService(users).issue_token(user)
			background_tasks.add_task(send_password_reset_email, user.email, user.name, token)
	return {"message": message}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
	data: ResetPasswordRequest,
	users: Annotated[UserRepository, Depends(get_user_repository)],
	background_tasks: BackgroundTasks,
) -> None:
	try:
		user = PasswordResetService(users).reset_password(data.token, data.password)
	except InvalidPasswordResetToken as error:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
	background_tasks.add_task(send_password_changed_email, user.email, user.name)


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
	return current_user
