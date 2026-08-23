from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Callable, Awaitable
import asyncio

@dataclass
class MediaMetadata:
    title: str
    uploader: Optional[str] = None
    duration: Optional[int] = None
    thumbnail_url: Optional[str] = None

# Progress callback type: (percent: float, speed_str: Optional[str], eta_str: Optional[str], downloaded_bytes: Optional[int], total_bytes: Optional[int])
ProgressCallback = Callable[[float, Optional[str], Optional[str], Optional[int], Optional[int]], Awaitable[None]]

class BaseDownloader(ABC):
    @abstractmethod
    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates URL and returns (is_valid, sanitized_url, error_message).
        """
        pass

    @abstractmethod
    async def extract_info(self, url: str) -> MediaMetadata:
        """
        Extracts media metadata without downloading.
        """
        pass

    @abstractmethod
    async def download(
        self,
        task_id: str,
        url: str,
        output_dir: Path,
        temp_dir: Path,
        progress_callback: ProgressCallback,
        cancel_event: asyncio.Event
    ) -> Tuple[Path, str]:
        """
        Executes download and returns (final_file_path, final_filename).
        """
        pass
