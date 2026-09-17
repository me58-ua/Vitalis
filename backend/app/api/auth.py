from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.api.deps import get_current_user, get_user_repository
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserRegisterRequest, UserResponse
from app.services.auth_service import (
	AuthService,
	EmailAlreadyRegisteredError,
	InactiveUserError,
	InvalidCredentialsError,
	UsernameAlreadyRegisteredError,
)


router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
	data: UserRegisterRequest,
	users: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
	try:
		return AuthService(users).register_patient(data)
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


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
	return current_user
