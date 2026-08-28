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
    mp4box_version: Optional[str] = None
    apple_music_available: bool = True
    disk: DiskUsageInfo
    tasks_summary: Dict[str, int]
    active_downloads: int

class CleanupResponse(BaseModel):
    cleaned_tasks: int
    cleaned_temp_files: int
    freed_bytes: int
    message: str

class AppleMusicConfigResponse(BaseModel):
    wrapper_ip: Optional[str] = None
    media_user_token: Optional[str] = None
    decrypt_m3u8_port: Optional[str] = None
    get_m3u8_port: Optional[str] = None
    is_configured: bool = False
    has_token: bool = False

class UpdateAppleMusicConfigRequest(BaseModel):
    wrapper_ip: Optional[str] = None
    media_user_token: Optional[str] = None

class TestWrapperResponse(BaseModel):
    online: bool
    message: str
    target: str

