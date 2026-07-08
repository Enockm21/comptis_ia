from fastapi import APIRouter, Depends, HTTPException, status

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
from comptis.interface.api.dependencies import (
    get_password_hasher,
    get_token_service,
    get_user_repository,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    user_repo: SQLAlchemyUserRepository = Depends(get_user_repository),
    hasher: BcryptPasswordHasher = Depends(get_password_hasher),
) -> UserResponse:
    use_case = RegisterUser(user_repo=user_repo, hasher=hasher)
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
    body: LoginRequest,
    user_repo: SQLAlchemyUserRepository = Depends(get_user_repository),
    hasher: BcryptPasswordHasher = Depends(get_password_hasher),
    token_service: JWTTokenService = Depends(get_token_service),
) -> TokenResponse:
    use_case = LoginUser(user_repo=user_repo, hasher=hasher, token_service=token_service)
    try:
        access_token, refresh_token = await use_case.execute(body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email or password"},
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    token_service: JWTTokenService = Depends(get_token_service),
) -> AccessTokenResponse:
    use_case = RefreshToken(token_service=token_service)
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
