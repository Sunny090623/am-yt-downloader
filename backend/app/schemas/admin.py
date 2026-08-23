from typing import Optional, Dict, Any
from pydantic import BaseModel

class DiskUsageInfo(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    storage_dir_bytes: int
    storage_dir_formatted: str

class SystemStatsResponse(BaseModel):
    environment: str
    uptime_seconds: float
    yt_dlp_version: str
    ffmpeg_available: bool
    disk: DiskUsageInfo
    tasks_summary: Dict[str, int]
    active_downloads: int

class CleanupResponse(BaseModel):
    cleaned_tasks: int
    cleaned_temp_files: int
    freed_bytes: int
    message: str
