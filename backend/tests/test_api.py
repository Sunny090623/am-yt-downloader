import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db
from app.models.task import DownloadTask, TaskStatus
from app.config import settings

@pytest.fixture
async def app_test_client(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with patch.object(settings, "STORAGE_DIR", storage_dir), \
         patch("app.core.task_manager.AsyncSessionLocal", TestSession), \
         patch("app.database.AsyncSessionLocal", TestSession):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, TestSession, storage_dir

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_api_auth_status_and_cookie_generation(app_test_client):
    client, _, _ = app_test_client
    resp = await client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_admin"] is False
    assert data["quota"]["video_limit"] == 5
    assert data["quota"]["video_remaining"] == 5
    # Check that device cookie was issued
    assert "amyt_device_token" in resp.cookies

@pytest.mark.asyncio
async def test_api_create_apple_music_album_submission(app_test_client):
    client, _, _ = app_test_client
    resp = await client.post("/api/tasks", json={
        "url": "https://music.apple.com/us/album/whenever-you-need-somebody-2022-remaster/1624945511",
        "service_type": "apple_music"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["service_type"] == "apple_music"
    assert data["media_type"] == "album"

    # Verify quota updated
    auth_resp = await client.get("/api/auth/status")
    auth_data = auth_resp.json()
    assert auth_data["quota"]["album_used"] == 1
    assert auth_data["quota"]["album_remaining"] == 4

@pytest.mark.asyncio
async def test_api_create_apple_music_song_submission(app_test_client):
    client, _, _ = app_test_client
    resp = await client.post("/api/tasks", json={
        "url": "https://music.apple.com/us/song/you-move-me-2022-remaster/1624945520",
        "service_type": "apple_music"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["service_type"] == "apple_music"
    assert data["media_type"] == "single"

    # Verify quota updated
    auth_resp = await client.get("/api/auth/status")
    auth_data = auth_resp.json()
    assert auth_data["quota"]["single_used"] == 1
    assert auth_data["quota"]["single_remaining"] == 9

@pytest.mark.asyncio
async def test_api_reject_invalid_youtube_url(app_test_client):
    client, _, _ = app_test_client
    resp = await client.post("/api/tasks", json={
        "url": "https://bilibili.com/video/BV123",
        "service_type": "youtube"
    })
    assert resp.status_code == 400
    assert "不支持的域名" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_api_admin_login_and_logout(app_test_client):
    client, _, _ = app_test_client

    # Wrong password
    resp = await client.post("/api/auth/login", json={"password": "wrongpassword"})
    assert resp.status_code == 401

    # Correct password
    resp = await client.post("/api/auth/login", json={"password": settings.ADMIN_PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True
    assert "amyt_admin_session" in resp.cookies

    # Check status with session cookie
    resp = await client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True
    assert resp.json()["quota"]["is_unlimited"] is True

    # Logout
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200

    # Status back to anonymous
    resp = await client.get("/api/auth/status")
    assert resp.json()["is_admin"] is False

@pytest.mark.asyncio
async def test_api_download_path_traversal_prevention(app_test_client):
    client, TestSession, storage_dir = app_test_client

    # Insert a task pointing outside storage_dir
    async with TestSession() as db:
        evil_task = DownloadTask(
            id="evil_task_1",
            user_id="anonymous_1",
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=123",
            status=TaskStatus.COMPLETED.value,
            file_name="secret.txt",
            file_path="C:/Windows/win.ini", # Attempt path traversal
            file_size=100
        )
        db.add(evil_task)
        await db.commit()

    resp = await client.get("/api/downloads/evil_task_1/file")
    # Anonymous user doesn't own this task -> 403
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_manual_delete_task_without_quota_refund(app_test_client):
    client, TestSession, storage_dir = app_test_client

    # 1. Establish anonymous user session & consume 1 quota
    status_resp = await client.get("/api/auth/status")
    user_id = status_resp.json()["user_id"]
    assert status_resp.json()["quota"]["video_remaining"] == 5

    # 2. Create physical task file
    task_dir = storage_dir / user_id / "task_to_del_123"
    task_dir.mkdir(parents=True, exist_ok=True)
    video_file = task_dir / "test_video.mp4"
    video_file.write_text("video binary data")

    # 3. Insert task into DB and consume 1 quota in daily_usage
    from app.core.quota import consume_quota
    from app.models.task import MediaType
    async with TestSession() as db:
        await consume_quota(db, user_id, False, MediaType.VIDEO)
        task = DownloadTask(
            id="task_to_del_123",
            user_id=user_id,
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=abc12345678",
            status=TaskStatus.COMPLETED.value,
            file_name="test_video.mp4",
            file_path=str(video_file),
            file_size=17
        )
        db.add(task)
        await db.commit()

    # 4. Check quota remaining is 4
    status_resp = await client.get("/api/auth/status")
    assert status_resp.json()["quota"]["video_remaining"] == 4

    # 5. Call DELETE /api/tasks/{task_id}
    del_resp = await client.delete("/api/tasks/task_to_del_123")
    assert del_resp.status_code == 200

    # 6. Verify physical directory deleted
    assert not task_dir.exists()
    assert not video_file.exists()

    # 7. CRITICAL VERIFICATION: Quota remains consumed (still 4, NOT 5)
    status_resp = await client.get("/api/auth/status")
    assert status_resp.json()["quota"]["video_remaining"] == 4
    assert status_resp.json()["quota"]["video_used"] == 1

@pytest.mark.asyncio
async def test_api_clear_finished_tasks(app_test_client):
    client, TestSession, storage_dir = app_test_client

    status_resp = await client.get("/api/auth/status")
    user_id = status_resp.json()["user_id"]

    async with TestSession() as db:
        # Finished task
        t1 = DownloadTask(
            id="clear_task_1",
            user_id=user_id,
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=111",
            status=TaskStatus.COMPLETED.value
        )
        # Active downloading task (should NOT be cleared)
        t2 = DownloadTask(
            id="active_task_2",
            user_id=user_id,
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=222",
            status=TaskStatus.DOWNLOADING.value
        )
        db.add_all([t1, t2])
        await db.commit()

    resp = await client.post("/api/tasks/clear-finished")
    assert resp.status_code == 200
    assert resp.json()["cleared_count"] == 1

    # Verify t1 deleted, t2 remains
    async with TestSession() as db:
        assert await db.get(DownloadTask, "clear_task_1") is None
        assert await db.get(DownloadTask, "active_task_2") is not None

@pytest.mark.asyncio
async def test_api_admin_change_password(app_test_client):
    client, TestSession, storage_dir = app_test_client

    # 1. Login as Admin
    login_resp = await client.post("/api/auth/login", json={"password": settings.ADMIN_PASSWORD})
    assert login_resp.status_code == 200

    # 2. Reject wrong current password
    fail_resp = await client.post("/api/admin/change-password", json={
        "current_password": "wrongpassword",
        "new_password": "newsecretpassword123"
    })
    assert fail_resp.status_code == 400

    # 3. Change password successfully
    ok_resp = await client.post("/api/admin/change-password", json={
        "current_password": settings.ADMIN_PASSWORD,
        "new_password": "newsecretpassword123"
    })
    assert ok_resp.status_code == 200
    assert ok_resp.json()["success"] is True

    # 4. Verify login with new password works
    new_login_resp = await client.post("/api/auth/login", json={"password": "newsecretpassword123"})
    assert new_login_resp.status_code == 200
    assert new_login_resp.json()["is_admin"] is True

    # Restore default password for test isolation
    settings.update_admin_password("admin123")

@pytest.mark.asyncio
async def test_api_delete_active_task_aborts_and_cleans(app_test_client):
    client, TestSession, storage_dir = app_test_client

    status_resp = await client.get("/api/auth/status")
    user_id = status_resp.json()["user_id"]

    # Create an active task
    async with TestSession() as db:
        active_t = DownloadTask(
            id="active_del_task_999",
            user_id=user_id,
            service_type="youtube",
            media_type="video",
            url="https://www.youtube.com/watch?v=running123",
            status=TaskStatus.DOWNLOADING.value
        )
        db.add(active_t)
        await db.commit()

    # Create dummy folder
    task_dir = storage_dir / user_id / "active_del_task_999"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "partial.m4a").write_text("partial data")

    # Delete active task directly
    del_resp = await client.delete("/api/tasks/active_del_task_999")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # DB record and folder should be removed
    async with TestSession() as db:
        assert await db.get(DownloadTask, "active_del_task_999") is None
    assert not task_dir.exists()

