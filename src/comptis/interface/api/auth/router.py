from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)
from comptis.application.auth.use_cases import LoginUser, RefreshToken, RegisterUser
from comptis.infrastructure.auth.jwt import JWTTokenService
from comptis.infrastructure.auth.password import BcryptPasswordHasher
from comptis.infrastructure.db.repositories import SQLAlchemyUserRepository
from comptis.interface.api.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from comptis.interface.api.dependencies import get_db_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest, session: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    use_case = RegisterUser(
        user_repo=SQLAlchemyUserRepository(session),
        hasher=BcryptPasswordHasher(),
    )
    try:
        user = await use_case.execute(body.email, body.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_already_registered", "message": "Email already in use"},
        )
    return UserResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    use_case = LoginUser(
        user_repo=SQLAlchemyUserRepository(session),
        hasher=BcryptPasswordHasher(),
        token_service=JWTTokenService(),
    )
    try:
        access_token, refresh_token = await use_case.execute(body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email or password"},
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest) -> AccessTokenResponse:
    use_case = RefreshToken(token_service=JWTTokenService())
    try:
        access_token = use_case.execute(body.refresh_token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "Token has expired"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token"},
        )
    return AccessTokenResponse(access_token=access_token)
