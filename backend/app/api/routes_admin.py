import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.config import settings
from app.database import get_db
from app.models.task import DownloadTask, TaskStatus
from app.schemas.admin import SystemStatsResponse, DiskUsageInfo, CleanupResponse
from app.core.auth import require_admin, UserContext
from app.core.task_manager import task_manager
from app.core.cleanup import run_cleanup_cycle

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_admin)])

SERVER_START_TIME = time.time()

def format_bytes(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def get_dir_size(path: Path) -> int:
    total = 0
    if path.exists():
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except Exception:
                    pass
    return total

def resolve_binary(binary_name_or_path: str) -> str:
    found = shutil.which(binary_name_or_path)
    if found:
        return found
    return binary_name_or_path

async def check_binary_version(cmd_path: str, args: list) -> str:
    import subprocess
    executable = resolve_binary(cmd_path)
    cmd = [executable] + args

    def run_sync():
        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = p.communicate(timeout=4)
            full_text = (out + "\n" + err).strip()
            if not full_text:
                return None
            lines = [l.strip() for l in full_text.splitlines() if l.strip()]
            for l in lines:
                if "yt-dlp version" in l:
                    return l.replace("[debug] ", "").strip()
                if l.startswith("ffmpeg version") or l.startswith("ffprobe version"):
                    return l.split(" Copyright")[0].strip()
                if "version" in l.lower() or (len(l) < 30 and ("." in l or "-" in l)):
                    return l
            return lines[0] if lines else None
        except Exception:
            return None

    res = await asyncio.to_thread(run_sync)
    return res or "未安装 / 不可用"

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """Fetches system diagnostics, storage usage, and component statuses."""
    # 1. Disk usage
    total, used, free = shutil.disk_usage(settings.STORAGE_DIR)
    storage_bytes = get_dir_size(settings.STORAGE_DIR)
    
    disk_info = DiskUsageInfo(
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        storage_dir_bytes=storage_bytes,
        storage_dir_formatted=format_bytes(storage_bytes)
    )

    # 2. Binary checks using exact flags
    ytdlp_ver = await check_binary_version(settings.YTDLP_PATH, ["--version"])
    if ytdlp_ver == "未安装 / 不可用":
        ytdlp_ver = await check_binary_version(settings.YTDLP_PATH, ["-v"])

    ffmpeg_ver = await check_binary_version(settings.FFMPEG_PATH, ["-version"])
    ffmpeg_avail = ffmpeg_ver != "未安装 / 不可用"

    # 3. Tasks summary count
    stmt = select(DownloadTask.status, func.count(DownloadTask.id)).group_by(DownloadTask.status)
    res = await db.execute(stmt)
    summary_dict = {row[0]: row[1] for row in res.all()}

    return SystemStatsResponse(
        environment=settings.ENVIRONMENT,
        uptime_seconds=round(time.time() - SERVER_START_TIME, 1),
        yt_dlp_version=ytdlp_ver,
        ffmpeg_available=ffmpeg_avail,
        disk=disk_info,
        tasks_summary=summary_dict,
        active_downloads=task_manager.get_active_count()
    )

@router.post("/cleanup", response_model=CleanupResponse)
async def manual_cleanup():
    """Manually triggers an immediate cleanup cycle."""
    res = await run_cleanup_cycle()
    return CleanupResponse(
        cleaned_tasks=res["cleaned_tasks"],
        cleaned_temp_files=res["cleaned_temp_files"],
        freed_bytes=res["freed_bytes"],
        message=f"清理完成: 清理了 {res['cleaned_tasks']} 个过期任务，释放空间 {format_bytes(res['freed_bytes'])}"
    )

@router.delete("/tasks/{task_id}")
async def admin_delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Admin hard delete of a task record and its physical storage folder."""
    stmt = select(DownloadTask).where(DownloadTask.id == task_id)
    res = await db.execute(stmt)
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # Delete physical dir
    task_dir = settings.STORAGE_DIR / task.user_id / task.id
    if task_dir.exists():
        shutil.rmtree(task_dir, ignore_errors=True)

    await db.delete(task)
    await db.commit()

    return {"success": True, "message": f"任务 {task_id} 及其文件已彻底删除"}

@router.get("/logs")
async def get_system_logs(lines: int = 150):
    """Fetches recent runtime logs from data/logs/app.log."""
    from app.core.logger import LOG_FILE
    if not LOG_FILE.exists():
        return {"logs": "日志文件尚未生成或暂无日志记录"}
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {"logs": "".join(recent_lines)}
    except Exception as e:
        return {"logs": f"读取日志文件失败: {str(e)}"}
