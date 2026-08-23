import asyncio
import time
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.task import DownloadTask, TaskStatus, ServiceType, MediaType
from app.schemas.task import TaskProgressUpdate
from app.downloaders import get_downloader, MediaMetadata
from app.core.quota import consume_quota, refund_quota, check_quota
from app.core.sse_hub import sse_hub
from app.core.logger import logger

class DownloadTaskManager:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._last_progress_time: Dict[str, float] = {}

    def get_active_count(self) -> int:
        return len([t for t in self._running_tasks.values() if not t.done()])

    async def submit_task(
        self,
        task_id: str,
        user_id: str,
        service_type: ServiceType,
        media_type: MediaType,
        url: str,
        is_admin: bool
    ) -> DownloadTask:
        """
        Validates URL, checks & consumes quota, creates the DB record,
        and launches the background execution.
        """
        downloader = get_downloader(service_type)
        is_valid, sanitized_url, err = downloader.validate_url(url)
        if not is_valid or not sanitized_url:
            raise ValueError(err or "无效的下载链接")

        async with AsyncSessionLocal() as db:
            # 1. Quota Check
            allowed, quota_err = await check_quota(db, user_id, is_admin, media_type)
            if not allowed:
                raise PermissionError(quota_err or "超过今日下载额度限制")

            # 2. Consume Quota upfront
            await consume_quota(db, user_id, is_admin, media_type)

            # 3. Create Task Record in DB
            now = datetime.now(timezone.utc)
            task_record = DownloadTask(
                id=task_id,
                user_id=user_id,
                service_type=service_type.value,
                media_type=media_type.value,
                url=sanitized_url,
                status=TaskStatus.QUEUED.value,
                progress_percent=0.0,
                created_at=now
            )
            db.add(task_record)
            await db.commit()
            await db.refresh(task_record)

        logger.info(f"[TaskManager] 新任务提交成功: ID={task_id}, 用户={user_id}, 服务={service_type.value}, URL={sanitized_url}")

        # 4. Launch async worker
        cancel_event = asyncio.Event()
        self._cancel_events[task_id] = cancel_event
        bg_task = asyncio.create_task(
            self._execute_task_pipeline(task_id, user_id, service_type, media_type, sanitized_url, is_admin, cancel_event)
        )
        self._running_tasks[task_id] = bg_task

        return task_record

    async def cancel_task(self, task_id: str, user_id: str, is_admin: bool) -> bool:
        """Cancels an in-flight or queued task and refunds quota."""
        async with AsyncSessionLocal() as db:
            stmt = select(DownloadTask).where(DownloadTask.id == task_id)
            res = await db.execute(stmt)
            task = res.scalar_one_or_none()
            if not task:
                return False
            if not is_admin and task.user_id != user_id:
                raise PermissionError("无权取消其他用户的任务")

            if task.status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value, TaskStatus.EXPIRED.value):
                return False

            logger.info(f"[TaskManager] 正在取消任务: ID={task_id}, 用户={user_id}")

            if task_id in self._cancel_events:
                self._cancel_events[task_id].set()

            # Update DB immediately if queued or processing
            task.status = TaskStatus.CANCELLED.value
            task.error_message = "用户主动取消任务"
            await db.commit()

            # Refund quota
            await refund_quota(db, task.user_id, is_admin, MediaType(task.media_type))

            # Broadcast update
            await sse_hub.broadcast_task_update(
                task.user_id,
                TaskProgressUpdate(
                    task_id=task.id,
                    status=task.status,
                    progress_percent=task.progress_percent,
                    error_message=task.error_message
                )
            )

        return True

    async def _execute_task_pipeline(
        self,
        task_id: str,
        user_id: str,
        service_type: ServiceType,
        media_type: MediaType,
        url: str,
        is_admin: bool,
        cancel_event: asyncio.Event
    ) -> None:
        downloader = get_downloader(service_type)
        output_dir = settings.STORAGE_DIR / user_id / task_id
        temp_dir = settings.TEMP_DIR / task_id

        try:
            # Stage 1: Fetching Info
            if cancel_event.is_set():
                return

            await self._update_task_db_and_broadcast(
                task_id, user_id,
                status=TaskStatus.FETCHING_INFO.value,
                progress_percent=0.0
            )

            try:
                metadata = await downloader.extract_info(url)
            except NotImplementedError as nie:
                raise nie
            except Exception as e:
                # Metadata extraction non-fatal for download, but nice for UI
                metadata = MediaMetadata(title="YouTube Media")

            await self._update_task_db_and_broadcast(
                task_id, user_id,
                title=metadata.title,
                uploader=metadata.uploader,
                duration=metadata.duration,
                thumbnail_url=metadata.thumbnail_url
            )

            if cancel_event.is_set():
                return

            # Stage 2: Concurrency Queue & Download
            async with self._semaphore:
                if cancel_event.is_set():
                    return

                await self._update_task_db_and_broadcast(
                    task_id, user_id,
                    status=TaskStatus.DOWNLOADING.value,
                    progress_percent=0.0
                )

                async def progress_callback(
                    percent: float,
                    speed: Optional[str],
                    eta: Optional[str],
                    downloaded_bytes: Optional[int],
                    total_bytes: Optional[int]
                ):
                    now_ts = time.time()
                    last_ts = self._last_progress_time.get(task_id, 0)
                    # Throttle progress broadcasts (every 0.3s or if completed/high change)
                    if (now_ts - last_ts >= 0.3) or percent >= 99.0 or percent <= 1.0:
                        self._last_progress_time[task_id] = now_ts
                        await self._update_task_db_and_broadcast(
                            task_id, user_id,
                            status=TaskStatus.DOWNLOADING.value,
                            progress_percent=percent,
                            download_speed=speed,
                            eta=eta,
                            downloaded_bytes=downloaded_bytes,
                            total_bytes=total_bytes
                        )

                # Execute Download
                final_file, final_filename = await downloader.download(
                    task_id=task_id,
                    url=url,
                    output_dir=output_dir,
                    temp_dir=temp_dir,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event
                )

                # Stage 3: Completed
                file_size = final_file.stat().st_size if final_file.exists() else 0
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(hours=settings.FILE_RETENTION_HOURS)

                await self._update_task_db_and_broadcast(
                    task_id, user_id,
                    status=TaskStatus.COMPLETED.value,
                    progress_percent=100.0,
                    download_speed=None,
                    eta=None,
                    file_name=final_filename,
                    file_path=str(final_file),
                    file_size=file_size,
                    completed_at=now,
                    expires_at=expires_at
                )

        except asyncio.CancelledError:
            # Clean up temp
            self._cleanup_dir(temp_dir)
            self._cleanup_dir(output_dir)
            logger.info(f"[Task {task_id}] 任务已成功取消并清理临时目录")
            await self._update_task_db_and_broadcast(
                task_id, user_id,
                status=TaskStatus.CANCELLED.value,
                error_message="下载任务已取消"
            )
            async with AsyncSessionLocal() as db:
                await refund_quota(db, user_id, is_admin, media_type)

        except Exception as e:
            # Clean up temp files
            self._cleanup_dir(temp_dir)
            self._cleanup_dir(output_dir)
            err_text = str(e)
            logger.error(f"[Task {task_id}] 任务执行失败: {err_text}", exc_info=True)
            await self._update_task_db_and_broadcast(
                task_id, user_id,
                status=TaskStatus.FAILED.value,
                error_message=err_text[:400]
            )
            async with AsyncSessionLocal() as db:
                await refund_quota(db, user_id, is_admin, media_type)

        finally:
            self._cancel_events.pop(task_id, None)
            self._running_tasks.pop(task_id, None)
            self._last_progress_time.pop(task_id, None)
            self._cleanup_dir(temp_dir)

    def _cleanup_dir(self, directory: Path):
        if directory.exists():
            try:
                shutil.rmtree(directory, ignore_errors=True)
            except Exception:
                pass

    async def _update_task_db_and_broadcast(self, task_id: str, user_id: str, **kwargs):
        """Updates DB task row and broadcasts an SSE event."""
        async with AsyncSessionLocal() as db:
            stmt = select(DownloadTask).where(DownloadTask.id == task_id)
            res = await db.execute(stmt)
            task = res.scalar_one_or_none()
            if not task:
                return

            for k, v in kwargs.items():
                if hasattr(task, k):
                    setattr(task, k, v)

            await db.commit()
            await db.refresh(task)

            # Broadcast SSE
            update_payload = TaskProgressUpdate(
                task_id=task.id,
                status=task.status,
                progress_percent=task.progress_percent,
                download_speed=task.download_speed,
                eta=task.eta,
                downloaded_bytes=task.downloaded_bytes,
                total_bytes=task.total_bytes,
                error_message=task.error_message,
                title=task.title,
                thumbnail_url=task.thumbnail_url,
                file_name=task.file_name,
                file_size=task.file_size,
                completed_at=task.completed_at,
                expires_at=task.expires_at
            )
            await sse_hub.broadcast_task_update(user_id, update_payload)

task_manager = DownloadTaskManager()
