import pytest
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.models.task import MediaType
from app.core.quota import check_quota, consume_quota, refund_quota, get_user_quota_info
from app.config import settings

@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

@pytest.mark.asyncio
async def test_quota_consumption_and_limits(async_db: AsyncSession):
    user_id = "test_device_001"

    # Initial check: 5 available
    info = await get_user_quota_info(async_db, user_id, is_admin=False)
    assert info.video_remaining == 5
    assert info.video_used == 0

    # Consume 5 times
    for i in range(5):
        allowed, err = await check_quota(async_db, user_id, is_admin=False, media_type=MediaType.VIDEO)
        assert allowed is True
        assert err is None
        consumed = await consume_quota(async_db, user_id, is_admin=False, media_type=MediaType.VIDEO)
        assert consumed is True

    # 6th attempt should be blocked
    allowed, err = await check_quota(async_db, user_id, is_admin=False, media_type=MediaType.VIDEO)
    assert allowed is False
    assert "今日视频下载额度已用完" in err
    consumed = await consume_quota(async_db, user_id, is_admin=False, media_type=MediaType.VIDEO)
    assert consumed is False

    # Refund 1
    await refund_quota(async_db, user_id, is_admin=False, media_type=MediaType.VIDEO)
    info = await get_user_quota_info(async_db, user_id, is_admin=False)
    assert info.video_remaining == 1
    assert info.video_used == 4

@pytest.mark.asyncio
async def test_admin_unlimited_quota(async_db: AsyncSession):
    admin_id = "admin"
    for _ in range(10):
        allowed, err = await check_quota(async_db, admin_id, is_admin=True, media_type=MediaType.VIDEO)
        assert allowed is True
        consumed = await consume_quota(async_db, admin_id, is_admin=True, media_type=MediaType.VIDEO)
        assert consumed is True

    info = await get_user_quota_info(async_db, admin_id, is_admin=True)
    assert info.is_unlimited is True
