from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from app.api.deps import get_current_user, get_user_repository, get_notification_service, oauth2_scheme
from app.core.rate_limit import password_reset_confirmation_limiter
from app.services.notification_service import NotificationService
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
	ForgotPasswordRequest,
	ResetPasswordRequest,
	TokenResponse,
	UserRegisterRequest,
	UserResponse,
	RefreshTokenRequest,
)
from app.services.password_reset_service import InvalidPasswordResetToken, PasswordResetService
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
	InvalidRefreshTokenError,
	InvalidAccessTokenError,
)
from app.services.email_service import send_welcome_email


router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
	data: UserRegisterRequest,
	users: Annotated[UserRepository, Depends(get_user_repository)],
	background_tasks: BackgroundTasks = None,
	notifications: Annotated[NotificationService, Depends(get_notification_service)] = None,
) -> User:
	try:
		user = AuthService(users, notifications).register_user(data)
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
	service = AuthService(users)
	try:
		user = service.authenticate(form_data.username, form_data.password)
	except (InvalidCredentialsError, InactiveUserError):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="INVALID_CREDENTIALS",
			headers={"WWW-Authenticate": "Bearer"},
		)
	access_token, refresh_token = service.issue_tokens(user)
	return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
	data: RefreshTokenRequest,
	users: Annotated[UserRepository, Depends(get_user_repository)],
) -> TokenResponse:
	try:
		access_token, refresh_token = AuthService(users).refresh_tokens(data.refresh_token)
	except InvalidRefreshTokenError:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="INVALID_REFRESH_TOKEN",
			headers={"WWW-Authenticate": "Bearer"},
		)
	return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
	data: ForgotPasswordRequest,
	request: Request,
	users: Annotated[UserRepository, Depends(get_user_repository)],
	background_tasks: BackgroundTasks,
) -> dict[str, str]:
	client_host = request.client.host if request.client else "unknown"
	reset = PasswordResetService(users).request_reset(data.email, client_host)
	if reset is not None:
		user, token = reset
		email, name = user.email, user.name
		users.session.commit()
		background_tasks.add_task(send_password_reset_email, email, name, token)
	return {"message_code": "PASSWORD_RESET_REQUEST_ACCEPTED"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
	data: ResetPasswordRequest,
	request: Request,
	users: Annotated[UserRepository, Depends(get_user_repository)],
	background_tasks: BackgroundTasks,
) -> None:
	client_host = request.client.host if request.client else "unknown"
	if not password_reset_confirmation_limiter.allow(client_host):
		raise HTTPException(
			status_code=status.HTTP_429_TOO_MANY_REQUESTS,
			detail="PASSWORD_RESET_RATE_LIMITED",
			headers={"Retry-After": str(password_reset_confirmation_limiter.window_seconds)},
		)
	try:
		user = PasswordResetService(users).reset_password(data.token, data.password)
	except InvalidPasswordResetToken as error:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
	email, name = user.email, user.name
	users.session.commit()
	background_tasks.add_task(send_password_changed_email, email, name)


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
	return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
	current_user: Annotated[User, Depends(get_current_user)],
	users: Annotated[UserRepository, Depends(get_user_repository)],
	token: Annotated[str, Depends(oauth2_scheme)],
) -> None:
	"""Close only the login session identified by the bearer token."""
	try:
		AuthService(users).logout(current_user, token)
	except InvalidAccessTokenError as error:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS") from error
