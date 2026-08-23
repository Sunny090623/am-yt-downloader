from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import bcrypt

class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development", description="development or production")
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8001, description="Server port")
    
    # Binary Paths (configurable for Windows Miniforge/Conda or Synology NAS)
    YTDLP_PATH: str = Field(default="yt-dlp", description="Executable path or command for yt-dlp")
    FFMPEG_PATH: str = Field(default="ffmpeg", description="Executable path or command for ffmpeg")
    FFPROBE_PATH: str = Field(default="ffprobe", description="Executable path or command for ffprobe")
    
    # Storage & Database paths
    DATA_DIR: Path = Field(default=Path("./data"), description="Base data directory")
    STORAGE_DIR: Path = Field(default=Path("./data/storage"), description="Directory to store downloaded media files")
    TEMP_DIR: Path = Field(default=Path("./data/storage/temp"), description="Directory for temporary/partial download fragments")
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data/app.db", description="Database connection string")
    
    # Security & Sessions
    SECRET_KEY: str = Field(default="dev-insecure-secret-key-change-in-production-123456789", description="Secret key for signing cookies")
    ADMIN_PASSWORD: Optional[str] = Field(default="admin123", description="Initial admin password if hash is not set")
    ADMIN_PASSWORD_HASH: Optional[str] = Field(default=None, description="Bcrypt hash for admin password")
    ADMIN_SESSION_DAYS: int = Field(default=7, description="Admin session duration in days")
    
    # Concurrency & Quota
    MAX_CONCURRENT_DOWNLOADS: int = Field(default=2, description="Max concurrent yt-dlp processes")
    ANONYMOUS_DAILY_VIDEO_LIMIT: int = Field(default=5, description="Daily download limit for anonymous users")
    ANONYMOUS_DAILY_ALBUM_LIMIT: int = Field(default=5, description="Reserved for future Apple Music album quota")
    ANONYMOUS_DAILY_SINGLE_LIMIT: int = Field(default=10, description="Reserved for future Apple Music track quota")
    
    # Retention
    FILE_RETENTION_HOURS: int = Field(default=24, description="Retention duration for completed files in hours")
    CLEANUP_INTERVAL_MINUTES: int = Field(default=15, description="Cleanup worker interval in minutes")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_admin_password_hash(self) -> str:
        if self.ADMIN_PASSWORD_HASH:
            return self.ADMIN_PASSWORD_HASH
        if self.ADMIN_PASSWORD:
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(self.ADMIN_PASSWORD.encode("utf-8")[:72], salt).decode("utf-8")
        return ""

settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
