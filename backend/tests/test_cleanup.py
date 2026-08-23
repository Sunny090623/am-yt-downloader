import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import patch
from app.database import Base
from app.models.task import DownloadTask, TaskStatus, MediaType
from app.core.cleanup import run_cleanup_cycle, recover_orphaned_tasks_on_startup
from app.config import settings

@pytest.fixture
async def setup_cleanup_db(tmp_path):
    storage_dir = tmp_path / "storage"
    temp_dir = tmp_path / "temp"
    storage_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(settings, "STORAGE_DIR", storage_dir), \
         patch.object(settings, "TEMP_DIR", temp_dir):
        
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        Session = async_sessionmaker(engine, expire_on_commit=False)
        with patch("app.core.cleanup.AsyncSessionLocal", Session):
            yield Session, storage_dir, temp_dir

@pytest.mark.asyncio
async def test_24h_completed_cleanup(setup_cleanup_db):
    Session, storage_dir, _ = setup_cleanup_db
    now = datetime.now(timezone.utc)

    async with Session() as db:
        # Task 1: Expired (completed 25h ago, expires_at 1h ago)
        t1_dir = storage_dir / "user1" / "task1"
        t1_dir.mkdir(parents=True, exist_ok=True)
        t1_file = t1_dir / "video.mp4"
        t1_file.write_text("dummy video data")

        task1 = DownloadTask(
            id="task1",
            user_id="user1",
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=111",
            status=TaskStatus.COMPLETED.value,
            file_name="video.mp4",
            file_path=str(t1_file),
            file_size=16,
            created_at=now - timedelta(hours=26),
            completed_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1) # EXPIRED
        )

        # Task 2: Active (completed 2h ago, expires_at in 22h)
        t2_dir = storage_dir / "user1" / "task2"
        t2_dir.mkdir(parents=True, exist_ok=True)
        t2_file = t2_dir / "video2.mp4"
        t2_file.write_text("active video data")

        task2 = DownloadTask(
            id="task2",
            user_id="user1",
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=222",
            status=TaskStatus.COMPLETED.value,
            file_name="video2.mp4",
            file_path=str(t2_file),
            file_size=17,
            created_at=now - timedelta(hours=3),
            completed_at=now - timedelta(hours=2),
            expires_at=now + timedelta(hours=22) # NOT EXPIRED
        )

        db.add_all([task1, task2])
        await db.commit()

    # Run cleanup
    res = await run_cleanup_cycle()
    assert res["cleaned_tasks"] == 1
    assert res["freed_bytes"] == 16

    # Verify task1 file deleted and status set to expired
    assert not t1_file.exists()
    assert not t1_dir.exists()
    assert t2_file.exists()

    async with Session() as db:
        t1 = await db.get(DownloadTask, "task1")
        t2 = await db.get(DownloadTask, "task2")
        assert t1.status == TaskStatus.EXPIRED.value
        assert t2.status == TaskStatus.COMPLETED.value

@pytest.mark.asyncio
async def test_startup_orphan_recovery(setup_cleanup_db):
    Session, _, temp_dir = setup_cleanup_db
    now = datetime.now(timezone.utc)

    # Create dummy temp file
    temp_file = temp_dir / "fragment.part"
    temp_file.write_text("fragment")

    async with Session() as db:
        task_orphan = DownloadTask(
            id="orphan1",
            user_id="user1",
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=333",
            status=TaskStatus.DOWNLOADING.value,
            created_at=now
        )
        db.add(task_orphan)
        await db.commit()

    # Run recovery
    interrupted_count = await recover_orphaned_tasks_on_startup()
    assert interrupted_count == 1

    # Verify status changed and temp file cleaned
    assert not temp_file.exists()
    async with Session() as db:
        t = await db.get(DownloadTask, "orphan1")
        assert t.status == TaskStatus.INTERRUPTED.value
        assert "服务重启" in t.error_message
