import hmac
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from fastapi import Request, Response, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import bcrypt
from app.config import settings
from app.database import get_db
from app.models.session import AdminSession

ANONYMOUS_COOKIE_NAME = "amyt_device_token"
ADMIN_COOKIE_NAME = "amyt_admin_session"

def sign_device_id(device_id: str) -> str:
    """Signs a device_id with HMAC-SHA256."""
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        device_id.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{device_id}.{sig}"

def verify_and_extract_device_id(cookie_value: Optional[str]) -> Optional[str]:
    """Verifies the HMAC signature and extracts the original device_id."""
    if not cookie_value or "." not in cookie_value:
        return None
    try:
        device_id, sig = cookie_value.rsplit(".", 1)
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            device_id.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(sig, expected_sig):
            return device_id
    except Exception:
        pass
    return None

def sign_admin_session(session_id: str) -> str:
    """Signs an admin session_id with HMAC-SHA256."""
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        session_id.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{session_id}.{sig}"

def verify_and_extract_admin_session(cookie_value: Optional[str]) -> Optional[str]:
    """Verifies the HMAC signature and extracts the original session_id."""
    if not cookie_value:
        return None
    if "." in cookie_value:
        try:
            session_id, sig = cookie_value.rsplit(".", 1)
            expected_sig = hmac.new(
                settings.SECRET_KEY.encode("utf-8"),
                session_id.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(sig, expected_sig):
                return session_id
        except Exception:
            pass
        return None
    # Backward compatibility for plain UUID hex during migration
    if len(cookie_value) == 32 and all(c in "0123456789abcdefABCDEF" for c in cookie_value):
        return cookie_value
    return None



def verify_admin_password(plain_password: str) -> bool:
    """Verifies plain password against configured admin password hash."""
    expected_hash = settings.get_admin_password_hash()
    if not expected_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            expected_hash.encode("utf-8")
        )
    except Exception:
        return False

async def create_admin_session_record(db: AsyncSession, request: Request) -> str:
    """Creates a new admin session record in the database valid for 7 days."""
    session_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.ADMIN_SESSION_DAYS)
    
    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client else ""
    
    session_record = AdminSession(
        session_id=session_id,
        created_at=now,
        expires_at=expires_at,
        is_revoked=False,
        user_agent=user_agent[:500] if user_agent else None,
        ip_address=client_ip[:64] if client_ip else None
    )
    db.add(session_record)
    await db.commit()
    return session_id

async def revoke_admin_session_record(db: AsyncSession, session_id: str) -> None:
    """Revokes an admin session in the database."""
    stmt = (
        update(AdminSession)
        .where(AdminSession.session_id == session_id)
        .values(is_revoked=True)
    )
    await db.execute(stmt)
    await db.commit()

async def is_valid_admin_session(db: AsyncSession, session_id: Optional[str]) -> bool:
    """Checks whether the given session_id is a valid, active, unexpired admin session."""
    if not session_id:
        return False
    stmt = select(AdminSession).where(
        AdminSession.session_id == session_id,
        AdminSession.is_revoked == False
    )
    result = await db.execute(stmt)
    session_record = result.scalar_one_or_none()
    if not session_record:
        return False
    
    now = datetime.now(timezone.utc)
    # Ensure timezone aware comparison
    expires_at = session_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at <= now:
        # Mark expired as revoked
        session_record.is_revoked = True
        await db.commit()
        return False
    
    return True

class UserContext:
    def __init__(self, user_id: str, is_admin: bool):
        self.user_id = user_id
        self.is_admin = is_admin

async def get_current_user_context(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> UserContext:
    """
    Resolves the current request user context:
    1. Checks for valid Admin session.
    2. Fallbacks to signed anonymous device cookie (or creates one).
    """
    raw_admin_cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    admin_session_id = verify_and_extract_admin_session(raw_admin_cookie)
    if admin_session_id:
        if await is_valid_admin_session(db, admin_session_id):
            return UserContext(user_id="admin", is_admin=True)

    # Anonymous user
    device_cookie = request.cookies.get(ANONYMOUS_COOKIE_NAME)
    device_id = verify_and_extract_device_id(device_cookie)
    
    if not device_id:
        device_id = uuid.uuid4().hex
        signed_val = sign_device_id(device_id)
        response.set_cookie(
            key=ANONYMOUS_COOKIE_NAME,
            value=signed_val,
            max_age=365 * 24 * 3600,
            httponly=True,
            samesite="lax",
            secure=False # Works over local HTTP (NAS LAN/Windows)
        )
    
    return UserContext(user_id=device_id, is_admin=False)

async def require_admin(
    user_ctx: UserContext = Depends(get_current_user_context)
) -> UserContext:
    """Dependency that requires admin privileges."""
    if not user_ctx.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要管理员权限"
        )
    return user_ctx
