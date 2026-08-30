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
    GPAC_PATH: str = Field(default="MP4Box", description="Executable path or command for MP4Box (GPAC)")
    APPLE_MUSIC_DIR: Path = Field(
        default_factory=lambda: (Path(__file__).resolve().parent.parent.parent / "apple-music" if (Path(__file__).resolve().parent.parent.parent / "apple-music").exists() else Path("./apple-music")),
        description="Path to apple-music directory containing config.yaml"
    )
    APPLE_MUSIC_BINARY: str = Field(default="apple-music-downloader", description="Path or command for apple-music binary")
    
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

    _cached_admin_hash: Optional[str] = None

    def get_admin_password_hash(self) -> str:
        # 1. Check persistent file in data dir
        pw_file = self.DATA_DIR / ".admin_password"
        if pw_file.exists():
            try:
                stored = pw_file.read_text(encoding="utf-8").strip()
                if stored.startswith("$2"):
                    self._cached_admin_hash = stored
                    return stored
            except Exception:
                pass

        if self.ADMIN_PASSWORD_HASH:
            return self.ADMIN_PASSWORD_HASH
        if self._cached_admin_hash:
            return self._cached_admin_hash
        if self.ADMIN_PASSWORD:
            salt = bcrypt.gensalt()
            self._cached_admin_hash = bcrypt.hashpw(self.ADMIN_PASSWORD.encode("utf-8")[:72], salt).decode("utf-8")
            return self._cached_admin_hash
        return ""

    def update_admin_password(self, new_password: str) -> None:
        """Updates admin password and stores hashed value persistently."""
        salt = bcrypt.gensalt()
        new_hash = bcrypt.hashpw(new_password.encode("utf-8")[:72], salt).decode("utf-8")
        self._cached_admin_hash = new_hash
        self.ADMIN_PASSWORD = new_password
        
        try:
            self.DATA_DIR.mkdir(parents=True, exist_ok=True)
            (self.DATA_DIR / ".admin_password").write_text(new_hash, encoding="utf-8")
        except Exception:
            pass


settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Pre-cache admin password hash
settings.get_admin_password_hash()

# Production Security Sanity Checks
if settings.ENVIRONMENT == "production":
    if settings.SECRET_KEY == "dev-insecure-secret-key-change-in-production-123456789":
        import warnings
        warnings.warn(
            "[SECURITY CRITICAL] SECRET_KEY 正在使用默认不安全密钥！请立即在生产环境 .env 中配置高强度的 SECRET_KEY！",
            RuntimeWarning,
            stacklevel=2
        )
    if settings.ADMIN_PASSWORD == "admin123" and not settings.ADMIN_PASSWORD_HASH:
        import warnings
        warnings.warn(
            "[SECURITY WARNING] ADMIN_PASSWORD 正在使用默认密码 'admin123'！请在生产环境 .env 中修改 ADMIN_PASSWORD 或 ADMIN_PASSWORD_HASH！",
            RuntimeWarning,
            stacklevel=2
        )

