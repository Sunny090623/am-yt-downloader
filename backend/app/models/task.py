from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, BigInteger
from app.database import Base

class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    FETCHING_INFO = "fetching_info"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    EXPIRED = "expired"

class ServiceType(str, enum.Enum):
    YOUTUBE = "youtube"
    APPLE_MUSIC = "apple_music"

class MediaType(str, enum.Enum):
    VIDEO = "video"
    ALBUM = "album"
    SINGLE = "single"

class DownloadTask(Base):
    __tablename__ = "download_tasks"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    service_type = Column(String(32), nullable=False, default=ServiceType.YOUTUBE.value)
    media_type = Column(String(32), nullable=False, default=MediaType.VIDEO.value)
    url = Column(Text, nullable=False)
    
    title = Column(String(512), nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    uploader = Column(String(256), nullable=True)
    duration = Column(Integer, nullable=True) # Duration in seconds
    
    status = Column(String(32), nullable=False, default=TaskStatus.QUEUED.value, index=True)
    progress_percent = Column(Float, default=0.0)
    download_speed = Column(String(64), nullable=True)
    eta = Column(String(64), nullable=True)
    total_bytes = Column(BigInteger, nullable=True)
    downloaded_bytes = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    
    file_name = Column(String(512), nullable=True)
    file_path = Column(Text, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
