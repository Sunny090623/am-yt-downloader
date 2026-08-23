from datetime import date
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models.usage import DailyUsage
from app.models.task import MediaType
from app.schemas.auth import QuotaInfo

async def get_or_create_daily_usage(db: AsyncSession, user_id: str, today: Optional[date] = None) -> DailyUsage:
    """Fetches or creates the DailyUsage record for a user today."""
    if today is None:
        today = date.today()
    
    stmt = select(DailyUsage).where(
        DailyUsage.user_id == user_id,
        DailyUsage.date == today
    )
    result = await db.execute(stmt)
    usage = result.scalar_one_or_none()
    
    if not usage:
        usage = DailyUsage(
            user_id=user_id,
            date=today,
            video_count=0,
            album_count=0,
            single_count=0
        )
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
        
    return usage

async def check_quota(
    db: AsyncSession,
    user_id: str,
    is_admin: bool,
    media_type: MediaType = MediaType.VIDEO
) -> Tuple[bool, Optional[str]]:
    """Checks if the user has remaining quota today."""
    if is_admin:
        return True, None
    
    usage = await get_or_create_daily_usage(db, user_id)
    
    if media_type == MediaType.VIDEO:
        if usage.video_count >= settings.ANONYMOUS_DAILY_VIDEO_LIMIT:
            return False, f"今日视频下载额度已用完 (上限 {settings.ANONYMOUS_DAILY_VIDEO_LIMIT} 个/天)"
    elif media_type == MediaType.ALBUM:
        if usage.album_count >= settings.ANONYMOUS_DAILY_ALBUM_LIMIT:
            return False, f"今日专辑下载额度已用完 (上限 {settings.ANONYMOUS_DAILY_ALBUM_LIMIT} 张/天)"
    elif media_type == MediaType.SINGLE:
        if usage.single_count >= settings.ANONYMOUS_DAILY_SINGLE_LIMIT:
            return False, f"今日单曲下载额度已用完 (上限 {settings.ANONYMOUS_DAILY_SINGLE_LIMIT} 首/天)"
            
    return True, None

async def consume_quota(
    db: AsyncSession,
    user_id: str,
    is_admin: bool,
    media_type: MediaType = MediaType.VIDEO
) -> bool:
    """Atomically consumes 1 unit of daily quota if available."""
    if is_admin:
        return True
    
    usage = await get_or_create_daily_usage(db, user_id)
    
    if media_type == MediaType.VIDEO:
        if usage.video_count >= settings.ANONYMOUS_DAILY_VIDEO_LIMIT:
            return False
        usage.video_count += 1
    elif media_type == MediaType.ALBUM:
        if usage.album_count >= settings.ANONYMOUS_DAILY_ALBUM_LIMIT:
            return False
        usage.album_count += 1
    elif media_type == MediaType.SINGLE:
        if usage.single_count >= settings.ANONYMOUS_DAILY_SINGLE_LIMIT:
            return False
        usage.single_count += 1
        
    await db.commit()
    return True

async def refund_quota(
    db: AsyncSession,
    user_id: str,
    is_admin: bool,
    media_type: MediaType = MediaType.VIDEO
) -> None:
    """Refunds 1 unit of quota if a task failed or was cancelled."""
    if is_admin:
        return
        
    usage = await get_or_create_daily_usage(db, user_id)
    
    if media_type == MediaType.VIDEO and usage.video_count > 0:
        usage.video_count -= 1
    elif media_type == MediaType.ALBUM and usage.album_count > 0:
        usage.album_count -= 1
    elif media_type == MediaType.SINGLE and usage.single_count > 0:
        usage.single_count -= 1
        
    await db.commit()

async def get_user_quota_info(db: AsyncSession, user_id: str, is_admin: bool) -> QuotaInfo:
    """Retrieves full quota details for the user."""
    if is_admin:
        return QuotaInfo(
            video_limit=settings.ANONYMOUS_DAILY_VIDEO_LIMIT,
            video_used=0,
            video_remaining=999999,
            album_limit=settings.ANONYMOUS_DAILY_ALBUM_LIMIT,
            album_used=0,
            album_remaining=999999,
            single_limit=settings.ANONYMOUS_DAILY_SINGLE_LIMIT,
            single_used=0,
            single_remaining=999999,
            is_unlimited=True
        )
        
    usage = await get_or_create_daily_usage(db, user_id)
    v_rem = max(0, settings.ANONYMOUS_DAILY_VIDEO_LIMIT - usage.video_count)
    a_rem = max(0, settings.ANONYMOUS_DAILY_ALBUM_LIMIT - usage.album_count)
    s_rem = max(0, settings.ANONYMOUS_DAILY_SINGLE_LIMIT - usage.single_count)
    
    return QuotaInfo(
        video_limit=settings.ANONYMOUS_DAILY_VIDEO_LIMIT,
        video_used=usage.video_count,
        video_remaining=v_rem,
        album_limit=settings.ANONYMOUS_DAILY_ALBUM_LIMIT,
        album_used=usage.album_count,
        album_remaining=a_rem,
        single_limit=settings.ANONYMOUS_DAILY_SINGLE_LIMIT,
        single_used=usage.single_count,
        single_remaining=s_rem,
        is_unlimited=False
    )
