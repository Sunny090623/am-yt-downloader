import asyncio
import os
import shutil
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any
from sqlalchemy import select, update
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.task import DownloadTask, TaskStatus, MediaType
from app.core.quota import refund_quota

async def run_cleanup_cycle() -> Dict[str, Any]:
    """
    Scans for expired completed tasks (expires_at <= now),
    deletes physical files, marks them as expired in DB,
    and purges stale temp fragments.
    """
    now = datetime.now(timezone.utc)
    cleaned_tasks = 0
    cleaned_temp_files = 0
    freed_bytes = 0

    async with AsyncSessionLocal() as db:
        # 1. Clean expired completed tasks
        stmt = select(DownloadTask).where(
            DownloadTask.status == TaskStatus.COMPLETED.value,
            DownloadTask.expires_at <= now
        )
        res = await db.execute(stmt)
        expired_tasks = res.scalars().all()

        for task in expired_tasks:
            # Physical directory deletion
            task_dir = settings.STORAGE_DIR / task.user_id / task.id
            if task_dir.exists():
                try:
                    for root, _, files in os.walk(task_dir):
                        for f in files:
                            fp = Path(root) / f
                            freed_bytes += fp.stat().st_size
                    shutil.rmtree(task_dir, ignore_errors=True)
                except Exception:
                    pass
            elif task.file_path and Path(task.file_path).exists():
                try:
                    fp = Path(task.file_path)
                    freed_bytes += fp.stat().st_size
                    fp.unlink(missing_ok=True)
                except Exception:
                    pass

            task.status = TaskStatus.EXPIRED.value
            task.file_path = None
            cleaned_tasks += 1

        await db.commit()

    # 2. Clean orphaned temporary fragments (> 2 hours old)
    if settings.TEMP_DIR.exists():
        cutoff_time = time.time() - (2 * 3600)
        try:
            for item in settings.TEMP_DIR.iterdir():
                try:
                    if item.is_file() and item.stat().st_mtime < cutoff_time:
                        freed_bytes += item.stat().st_size
                        item.unlink(missing_ok=True)
                        cleaned_temp_files += 1
                    elif item.is_dir() and item.stat().st_mtime < cutoff_time:
                        shutil.rmtree(item, ignore_errors=True)
                        cleaned_temp_files += 1
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "cleaned_tasks": cleaned_tasks,
        "cleaned_temp_files": cleaned_temp_files,
        "freed_bytes": freed_bytes
    }

async def recover_orphaned_tasks_on_startup() -> int:
    """
    Finds in-flight tasks from a previous server session,
    marks them as INTERRUPTED, and refunds quota.
    """
    interrupted_count = 0
    active_statuses = [
        TaskStatus.QUEUED.value,
        TaskStatus.FETCHING_INFO.value,
        TaskStatus.DOWNLOADING.value,
        TaskStatus.PROCESSING.value
    ]

    async with AsyncSessionLocal() as db:
        stmt = select(DownloadTask).where(DownloadTask.status.in_(active_statuses))
        res = await db.execute(stmt)
        orphans = res.scalars().all()

        for task in orphans:
            task.status = TaskStatus.INTERRUPTED.value
            task.error_message = "服务重启导致任务中断"
            interrupted_count += 1
            # Refund quota
            try:
                media_type = MediaType(task.media_type)
            except Exception:
                media_type = MediaType.VIDEO
            await refund_quota(db, task.user_id, task.user_id == "admin", media_type)

        await db.commit()

    # Clean any temp files left from prior runs
    if settings.TEMP_DIR.exists():
        try:
            for item in settings.TEMP_DIR.iterdir():
                if item.is_file():
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
        except Exception:
            pass

    return interrupted_count

async def cleanup_background_worker() -> None:
    """Continuous background loop running cleanup cycles."""
    interval_seconds = settings.CLEANUP_INTERVAL_MINUTES * 60
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await run_cleanup_cycle()
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)
