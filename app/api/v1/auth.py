from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.middleware.rate_limit import rate_limit
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    MembershipSummary,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user and their first tenant",
    dependencies=[Depends(rate_limit("register", per_minute=3))],
)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user, _tenant = await auth_service.register_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        tenant_name=payload.tenant_name,
    )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive an access/refresh token pair",
    dependencies=[Depends(rate_limit("login", per_minute=5))],
)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip, ua = _client_meta(request)
    _user, access_token, refresh_token, expires_in = await auth_service.authenticate(
        db, email=payload.email, password=payload.password, ip_address=ip, user_agent=ua
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate a refresh token for a new access token")
async def refresh(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip, ua = _client_meta(request)
    access_token, refresh_token, expires_in = await auth_service.refresh_tokens(
        db, refresh_token=payload.refresh_token, ip_address=ip, user_agent=ua
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token")
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, refresh_token=payload.refresh_token)


@router.get("/me", response_model=MeResponse, summary="Get the current user and their tenant memberships")
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    memberships = await auth_service.get_memberships(db, user_id=current_user.id)
    return MeResponse(
        user=UserOut.model_validate(current_user),
        memberships=[MembershipSummary(**m) for m in memberships],
    )


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset email",
    dependencies=[Depends(rate_limit("forgot_password", per_minute=3))],
)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.request_password_reset(db, email=payload.email)
    return {"message": "If an account exists for this email, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, summary="Reset password using a valid token")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, token=payload.token, new_password=payload.new_password)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT, summary="Verify email using a valid token")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.verify_email(db, token=payload.token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Resend the email verification link",
    dependencies=[Depends(rate_limit("resend_verification", per_minute=3))],
)
async def resend_verification(payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.resend_verification(db, email=payload.email)
    return {"message": "If an account exists for this email, a verification link has been sent."}
