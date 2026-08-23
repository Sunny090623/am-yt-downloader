import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.core.auth import (
    sign_device_id,
    verify_and_extract_device_id,
    verify_admin_password,
    create_admin_session_record,
    revoke_admin_session_record,
    is_valid_admin_session
)
from app.config import settings

@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

def test_signed_device_cookie():
    dev_id = "device-uuid-12345"
    signed = sign_device_id(dev_id)
    assert "." in signed

    extracted = verify_and_extract_device_id(signed)
    assert extracted == dev_id

    # Tampered cookie
    tampered = signed + "tampered"
    assert verify_and_extract_device_id(tampered) is None

    # Invalid format
    assert verify_and_extract_device_id("invalid") is None
    assert verify_and_extract_device_id(None) is None

def test_admin_password_verification():
    assert verify_admin_password(settings.ADMIN_PASSWORD) is True
    assert verify_admin_password("wrong_password") is False

@pytest.mark.asyncio
async def test_admin_session_lifecycle(async_db: AsyncSession):
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "TestAgent/1.0"
    mock_request.client.host = "192.168.1.100"

    # Create session
    session_id = await create_admin_session_record(async_db, mock_request)
    assert len(session_id) > 0

    # Validate active
    valid = await is_valid_admin_session(async_db, session_id)
    assert valid is True

    # Revoke session
    await revoke_admin_session_record(async_db, session_id)
    valid_after_revoke = await is_valid_admin_session(async_db, session_id)
    assert valid_after_revoke is False
