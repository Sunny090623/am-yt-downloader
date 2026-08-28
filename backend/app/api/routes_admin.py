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
import re
from app.schemas.admin import (
    SystemStatsResponse,
    DiskUsageInfo,
    CleanupResponse,
    AppleMusicConfigResponse,
    UpdateAppleMusicConfigRequest,
    TestWrapperResponse
)

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

import sys

def resolve_binary(binary_name_or_path: str) -> str:
    found = shutil.which(binary_name_or_path)
    if found:
        return found
    
    # Check Python environment directory (Conda / venv / Scripts / bin)
    py_dir = Path(sys.executable).parent
    candidates = [
        py_dir / "Scripts" / f"{binary_name_or_path}.exe",
        py_dir / "Scripts" / binary_name_or_path,
        py_dir / "bin" / binary_name_or_path,
        py_dir / f"{binary_name_or_path}.exe",
        py_dir / binary_name_or_path,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c)
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
            if full_text:
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
            pass

        # Python module fallback for yt-dlp in Conda / venv
        if "yt-dlp" in cmd_path or "ytdlp" in cmd_path:
            try:
                import yt_dlp
                return f"{yt_dlp.version.__version__}"
            except Exception:
                pass
        return None

    res = await asyncio.to_thread(run_sync)
    return res or "未安装 / 不可用"


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """Fetches system diagnostics, storage usage, and component statuses."""
    # 1. Disk usage (execute in worker thread to avoid blocking event loop)
    total, used, free = await asyncio.to_thread(shutil.disk_usage, settings.STORAGE_DIR)
    storage_bytes = await asyncio.to_thread(get_dir_size, settings.STORAGE_DIR)
    
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

    mp4box_ver = await check_binary_version(settings.GPAC_PATH, ["-version"])
    if mp4box_ver == "未安装 / 不可用":
        mp4box_ver = await check_binary_version("MP4Box", ["-version"])
    
    am_avail = (settings.APPLE_MUSIC_DIR / "config.yaml").exists()

    # 3. Tasks summary count
    stmt = select(DownloadTask.status, func.count(DownloadTask.id)).group_by(DownloadTask.status)
    res = await db.execute(stmt)
    summary_dict = {row[0]: row[1] for row in res.all()}

    return SystemStatsResponse(
        environment=settings.ENVIRONMENT,
        uptime_seconds=round(time.time() - SERVER_START_TIME, 1),
        yt_dlp_version=ytdlp_ver,
        ffmpeg_available=ffmpeg_avail,
        mp4box_version=mp4box_ver,
        apple_music_available=am_avail,
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

def read_apple_music_config_from_disk() -> dict:
    """Reads current Apple Music config from disk (config.yaml or fallback to example)."""
    config_file = settings.APPLE_MUSIC_DIR / "config.yaml"
    example_file = settings.APPLE_MUSIC_DIR / "config.yaml.example"
    target_file = config_file if config_file.exists() else (example_file if example_file.exists() else None)
    
    data = {
        "wrapper_ip": "",
        "media_user_token": "",
        "decrypt_m3u8_port": "",
        "get_m3u8_port": "",
        "is_configured": False,
        "has_token": False
    }
    if not target_file or not target_file.exists():
        return data

    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
        
        # Match media-user-token
        token_match = re.search(r'^\s*media-user-token:\s*"(.*?)"', content, re.M)
        if token_match:
            token_val = token_match.group(1).strip()
            if token_val and token_val != "your-media-user-token":
                data["media_user_token"] = token_val
                data["has_token"] = True
                
        # Match decrypt-m3u8-port
        decrypt_match = re.search(r'^\s*decrypt-m3u8-port:\s*"(.*?)"', content, re.M)
        if decrypt_match:
            decrypt_val = decrypt_match.group(1).strip()
            data["decrypt_m3u8_port"] = decrypt_val
            ip_part = decrypt_val.split(":")[0] if ":" in decrypt_val else decrypt_val
            if ip_part and ip_part not in ("127.0.0.1", "localhost"):
                data["wrapper_ip"] = ip_part
                data["is_configured"] = True
            elif ip_part:
                data["wrapper_ip"] = ip_part
                
        # Match get-m3u8-port
        m3u8_match = re.search(r'^\s*get-m3u8-port:\s*"(.*?)"', content, re.M)
        if m3u8_match:
            data["get_m3u8_port"] = m3u8_match.group(1).strip()

    except Exception as e:
        from app.core.logger import logger
        logger.error(f"读取 Apple Music 配置文件失败: {str(e)}")
        
    return data

def update_apple_music_config_on_disk(wrapper_ip: Optional[str], media_user_token: Optional[str]) -> dict:
    """Safely updates wrapper IP ports and media-user-token in config.yaml preserving other fields."""
    config_file = settings.APPLE_MUSIC_DIR / "config.yaml"
    example_file = settings.APPLE_MUSIC_DIR / "config.yaml.example"
    
    if not config_file.exists():
        if example_file.exists():
            shutil.copy(str(example_file), str(config_file))
        else:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text('media-user-token: ""\ndecrypt-m3u8-port: "127.0.0.1:10020"\nget-m3u8-port: "127.0.0.1:20020"\n', encoding="utf-8")

    content = config_file.read_text(encoding="utf-8", errors="replace")
    
    if wrapper_ip is not None:
        clean_ip = wrapper_ip.strip()
        clean_ip = re.sub(r"^https?://", "", clean_ip)
        clean_ip = clean_ip.rstrip("/")
        if ":" in clean_ip:
            clean_ip = clean_ip.split(":")[0]
            
        # Update decrypt-m3u8-port
        if re.search(r'^\s*decrypt-m3u8-port:\s*".*?"', content, re.M):
            content = re.sub(r'^(\s*decrypt-m3u8-port:\s*)".*?"', rf'\g<1>"{clean_ip}:10020"', content, flags=re.M)
        else:
            content += f'\ndecrypt-m3u8-port: "{clean_ip}:10020"\n'
            
        # Update get-m3u8-port
        if re.search(r'^\s*get-m3u8-port:\s*".*?"', content, re.M):
            content = re.sub(r'^(\s*get-m3u8-port:\s*)".*?"', rf'\g<1>"{clean_ip}:20020"', content, flags=re.M)
        else:
            content += f'\nget-m3u8-port: "{clean_ip}:20020"\n'

    if media_user_token is not None:
        clean_token = media_user_token.strip()
        if re.search(r'^\s*media-user-token:\s*".*?"', content, re.M):
            content = re.sub(r'^(\s*media-user-token:\s*)".*?"', rf'\g<1>"{clean_token}"', content, flags=re.M)
        else:
            content = f'media-user-token: "{clean_token}"\n' + content
            
    config_file.write_text(content, encoding="utf-8")
    return read_apple_music_config_from_disk()

@router.get("/settings/apple-music", response_model=AppleMusicConfigResponse)
async def get_apple_music_settings():
    """Retrieves current Apple Music wrapper IP and token configuration from config.yaml."""
    cfg = read_apple_music_config_from_disk()
    return AppleMusicConfigResponse(**cfg)

@router.post("/settings/apple-music", response_model=AppleMusicConfigResponse)
async def save_apple_music_settings(req: UpdateAppleMusicConfigRequest):
    """Updates wrapper IP and user token in apple-music/config.yaml."""
    cfg = update_apple_music_config_on_disk(req.wrapper_ip, req.media_user_token)
    return AppleMusicConfigResponse(**cfg)

@router.post("/settings/apple-music/test", response_model=TestWrapperResponse)
async def test_wrapper_connectivity(req: UpdateAppleMusicConfigRequest):
    """Tests TCP connectivity to the wrapper decrypt port (10020)."""
    ip_to_test = req.wrapper_ip
    if not ip_to_test:
        cfg = read_apple_music_config_from_disk()
        ip_to_test = cfg.get("wrapper_ip")
        
    if not ip_to_test:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未指定 Wrapper 服务端 IP")
        
    clean_ip = ip_to_test.strip()
    clean_ip = re.sub(r"^https?://", "", clean_ip).rstrip("/")
    if ":" in clean_ip:
        clean_ip = clean_ip.split(":")[0]
        
    target_addr = f"{clean_ip}:10020"
    
    try:
        # Attempt TCP connect to 10020
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(clean_ip, 10020),
            timeout=2.5
        )
        writer.close()
        await writer.wait_closed()
        return TestWrapperResponse(
            online=True,
            message=f"连通成功！Wrapper 服务在线 ({target_addr})",
            target=target_addr
        )
    except asyncio.TimeoutError:
        return TestWrapperResponse(
            online=False,
            message=f"连接超时：无法在 2.5 秒内连接到 {target_addr}，请检查 IP、防火墙或 Wrapper 服务是否启动",
            target=target_addr
        )
    except Exception as e:
        return TestWrapperResponse(
            online=False,
            message=f"连接失败：无法连接到 {target_addr} ({str(e)})",
            target=target_addr
        )

