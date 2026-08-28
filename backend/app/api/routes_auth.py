from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.schemas.auth import LoginRequest, LoginResponse, AuthStatusResponse
import time
from collections import defaultdict
from app.core.auth import (
    verify_admin_password,
    create_admin_session_record,
    revoke_admin_session_record,
    get_current_user_context,
    UserContext,
    ADMIN_COOKIE_NAME,
    sign_admin_session,
    verify_and_extract_admin_session
)
from app.core.quota import get_user_quota_info

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# In-memory IP-based rate limiter for login brute-force defense
_FAILED_LOGINS: dict[str, list[float]] = defaultdict(list)
_MAX_FAILURES = 5
_WINDOW_SECONDS = 60.0

@router.post("/login", response_model=LoginResponse)
async def admin_login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Authenticates admin with brute-force rate limiting and issues a signed session cookie."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Clean expired failure timestamps
    attempts = [ts for ts in _FAILED_LOGINS[client_ip] if now - ts < _WINDOW_SECONDS]
    _FAILED_LOGINS[client_ip] = attempts
    
    if len(attempts) >= _MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试失败过于频繁，请等待 1 分钟后再试"
        )

    if not verify_admin_password(req.password):
        _FAILED_LOGINS[client_ip].append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员密码错误"
        )

    # Clear failure records on success
    _FAILED_LOGINS.pop(client_ip, None)

    session_id = await create_admin_session_record(db, request)
    signed_cookie_val = sign_admin_session(session_id)
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=signed_cookie_val,
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
    raw_cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    session_id = verify_and_extract_admin_session(raw_cookie)
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
