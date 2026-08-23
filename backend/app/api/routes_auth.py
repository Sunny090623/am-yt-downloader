from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.schemas.auth import LoginRequest, LoginResponse, AuthStatusResponse
from app.core.auth import (
    verify_admin_password,
    create_admin_session_record,
    revoke_admin_session_record,
    get_current_user_context,
    UserContext,
    ADMIN_COOKIE_NAME
)
from app.core.quota import get_user_quota_info

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login", response_model=LoginResponse)
async def admin_login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Authenticates admin and issues a revocable 7-day session cookie."""
    if not verify_admin_password(req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员密码错误"
        )

    session_id = await create_admin_session_record(db, request)
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=session_id,
        max_age=settings.ADMIN_SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=False
    )

    return LoginResponse(
        success=True,
        is_admin=True,
        message="管理员登录成功"
    )

@router.post("/logout")
async def admin_logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Revokes the current admin session immediately and clears cookie."""
    session_id = request.cookies.get(ADMIN_COOKIE_NAME)
    if session_id:
        await revoke_admin_session_record(db, session_id)

    response.delete_cookie(
        key=ADMIN_COOKIE_NAME,
        httponly=True,
        samesite="lax"
    )

    return {"success": True, "message": "已安全退出登录"}

@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    user_ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves current user role, ID, and daily quota stats."""
    quota = await get_user_quota_info(db, user_ctx.user_id, user_ctx.is_admin)
    return AuthStatusResponse(
        is_admin=user_ctx.is_admin,
        user_id=user_ctx.user_id,
        quota=quota
    )
