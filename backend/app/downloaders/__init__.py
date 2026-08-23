from app.models.task import ServiceType
from app.downloaders.base import BaseDownloader, MediaMetadata, ProgressCallback
from app.downloaders.youtube import YouTubeDownloader
from app.downloaders.apple_music import AppleMusicDownloader

def get_downloader(service_type: ServiceType | str) -> BaseDownloader:
    """Returns the corresponding downloader instance based on service type."""
    if isinstance(service_type, str):
        try:
            service_type = ServiceType(service_type.lower())
        except ValueError:
            raise ValueError(f"未知的服务类型: {service_type}")

    if service_type == ServiceType.YOUTUBE:
        return YouTubeDownloader()
    elif service_type == ServiceType.APPLE_MUSIC:
        return AppleMusicDownloader()
    else:
        raise ValueError(f"不支持的服务类型: {service_type}")

__all__ = [
    "BaseDownloader",
    "MediaMetadata",
    "ProgressCallback",
    "YouTubeDownloader",
    "AppleMusicDownloader",
    "get_downloader"
]
