from pathlib import Path
from typing import Optional, Tuple
import asyncio
from app.downloaders.base import BaseDownloader, MediaMetadata, ProgressCallback

class AppleMusicDownloader(BaseDownloader):
    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        return False, None, "Apple Music 下载服务暂未开放"

    async def extract_info(self, url: str) -> MediaMetadata:
        raise NotImplementedError("Apple Music 下载服务暂未开放")

    async def download(
        self,
        task_id: str,
        url: str,
        output_dir: Path,
        temp_dir: Path,
        progress_callback: ProgressCallback,
        cancel_event: asyncio.Event
    ) -> Tuple[Path, str]:
        raise NotImplementedError("Apple Music 下载服务暂未开放")
