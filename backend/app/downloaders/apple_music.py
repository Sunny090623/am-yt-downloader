import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from typing import Optional, Tuple, List
from app.config import settings
from app.downloaders.base import BaseDownloader, MediaMetadata, ProgressCallback
from app.core.url_validator import validate_and_sanitize_apple_music_url
from app.core.logger import logger

TRACK_PROGRESS_REGEX = re.compile(r"Track\s+(\d+)\s+of\s+(\d+):", re.IGNORECASE)
DOWNLOADING_PROGRESS_REGEX = re.compile(r"Downloading\.\.\.\s+([\d\.]+)%?\s*(?:\(([^,\)]+)(?:,\s*([^\)]+))?\))?", re.IGNORECASE)
TRACK_TITLE_REGEX = re.compile(r"^\d{2}\.\s+(.+)$")
QUALITY_REGEX = re.compile(r"(\d+-bit\s*/\s*\d+\s*Hz|\d+\s*Kbps)", re.IGNORECASE)

class AppleMusicDownloader(BaseDownloader):
    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        is_valid, sanitized_url, _, err = validate_and_sanitize_apple_music_url(url)
        return is_valid, sanitized_url, err

    async def extract_info(self, url: str) -> MediaMetadata:
        """Extracts title, artist, and artwork metadata for Apple Music song or album."""
        is_valid, sanitized_url, media_type, err = validate_and_sanitize_apple_music_url(url)
        if not is_valid or not sanitized_url:
            raise ValueError(err or "无效的 Apple Music URL")

        # Extract storefront and slug from path
        parsed = urllib.parse.urlparse(sanitized_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        
        # Determine fallback title from URL slug
        slug = ""
        for i, part in enumerate(path_parts):
            if part in ("album", "song", "playlist") and i + 1 < len(path_parts):
                next_part = path_parts[i + 1]
                if not next_part.isdigit():
                    slug = next_part
                break

        fallback_title = slug.replace("-", " ").title() if slug else ("Apple Music Album" if media_type == "album" else "Apple Music Single")
        title = fallback_title
        artist = None
        thumbnail = None

        # Fetch webpage metadata via lightweight HTTP request
        try:
            req = urllib.request.Request(
                sanitized_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )
            html_bytes = await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=5.0).read())
            html_text = html_bytes.decode("utf-8", errors="replace")

            # 1. Try JSON-LD schema first
            json_ld_matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([^<]+)</script>', html_text, re.IGNORECASE)
            for raw_json in json_ld_matches:
                try:
                    data = json.loads(raw_json.strip())
                    if isinstance(data, dict):
                        if "name" in data and data["name"]:
                            title = data["name"].strip()
                        if "byArtist" in data:
                            if isinstance(data["byArtist"], dict) and "name" in data["byArtist"]:
                                artist = data["byArtist"]["name"].strip()
                            elif isinstance(data["byArtist"], list) and len(data["byArtist"]) > 0 and "name" in data["byArtist"][0]:
                                artist = data["byArtist"][0]["name"].strip()
                        if "image" in data and data["image"]:
                            thumbnail = data["image"] if isinstance(data["image"], str) else data["image"].get("url")
                        if title and title != fallback_title:
                            break
                except Exception:
                    pass

            # 2. Try OpenGraph / Twitter meta tags
            if not title or title in ("Apple Music 网页播放器", "Apple Music Web Player", "Apple Music", "Apple Music", fallback_title):
                og_title_match = re.search(r'<meta\s+(?:property|name)=["\'](?:og:title|twitter:title|apple:title)["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
                if og_title_match:
                    raw_title = og_title_match.group(1).replace("\u200e", "").replace("\u200f", "").replace(" on Apple Music", "").replace(" on Apple Music", "").strip()
                    if raw_title and raw_title not in ("Apple Music 网页播放器", "Apple Music Web Player", "Apple Music", "Apple Music"):
                        if " by " in raw_title:
                            parts = raw_title.split(" by ", 1)
                            title = parts[0].strip(' "“')
                            if not artist:
                                artist = parts[1].strip()
                        elif " - " in raw_title:
                            parts = raw_title.split(" - ", 1)
                            title = parts[0].strip()
                            if not artist:
                                artist = parts[1].strip()
                        else:
                            title = raw_title

            og_image_match = re.search(r'<meta\s+(?:property|name)=["\'](?:og:image|twitter:image)["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
            if og_image_match and not thumbnail:
                thumbnail = og_image_match.group(1).strip()
        except Exception as e:
            logger.warning(f"[AppleMusicDownloader] 抓取网页元数据失败，使用基础信息: {str(e)}")

        # Ensure title is never the generic web player string
        if not title or title in ("Apple Music 网页播放器", "Apple Music Web Player", "Apple Music", "Apple Music"):
            title = fallback_title

        logger.info(f"[AppleMusicDownloader] 元数据提取成功: '{title}' (艺术家: {artist}, 类型: {media_type})")

        return MediaMetadata(
            title=title,
            uploader=artist,
            duration=None,
            thumbnail_url=thumbnail
        )

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
        Executes apple-music-downloader Go CLI process, parses live stream,
        moves downloaded tracks to isolated output_dir, and archives albums as zip.
        """
        is_valid, sanitized_url, media_type, err = validate_and_sanitize_apple_music_url(url)
        if not is_valid or not sanitized_url:
            raise ValueError(err or "无效的 Apple Music URL")

        output_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Working directory where config.yaml resides
        work_dir = settings.APPLE_MUSIC_DIR
        if not work_dir.exists():
            raise RuntimeError(f"未找到 Apple Music 工作目录: {work_dir}")

        # Resolve binary executable
        binary_path = None
        for candidate in (
            work_dir / "apple-music-downloader.exe",
            work_dir / "apple-music-downloader",
            work_dir / "main.exe",
            work_dir / "main"
        ):
            if candidate.exists() and candidate.is_file():
                binary_path = candidate
                break

        if not binary_path:
            system_bin = shutil.which(settings.APPLE_MUSIC_BINARY)
            if system_bin:
                binary_path = Path(system_bin)

        if binary_path:
            cmd = [str(binary_path)]
        else:
            go_bin = shutil.which("go")
            if not go_bin:
                raise RuntimeError("未找到 Go 运行时或预编译的 apple-music-downloader 可执行文件，请在 PATH 中配置 Go 或编译二进制。")
            cmd = [go_bin, "run", "main.go"]

        if media_type == "song":
            cmd.append("--song")
        cmd.append(sanitized_url)

        logger.info(f"[Task {task_id}] 启动 Apple Music 下载: {' '.join(cmd)} (工作目录: {work_dir})")

        # Snapshot modification times of files in AM-DL downloads before run
        download_base = work_dir / "AM-DL downloads"
        download_base.mkdir(parents=True, exist_ok=True)
        pre_files = set(f.resolve() for f in download_base.rglob("*") if f.is_file())
        pre_mtimes = {f: f.stat().st_mtime for f in pre_files}
        run_start_ts = time.time() - 2.0

        await self._run_am_download_stream(task_id, cmd, work_dir, progress_callback, cancel_event)

        # Locate newly produced files
        post_files = set(f.resolve() for f in download_base.rglob("*") if f.is_file())
        new_files = [
            f for f in post_files
            if (f not in pre_files) or (f.stat().st_mtime > pre_mtimes.get(f, 0)) or (f.stat().st_mtime >= run_start_ts)
        ]
        
        # Filter for audio files
        audio_files = [f for f in new_files if f.suffix.lower() in (".m4a", ".mp4", ".flac", ".mp3", ".wav")]
        if not audio_files:
            # Fallback: scan all audio files modified since run_start_ts in download_base
            audio_files = [
                f for f in download_base.rglob("*")
                if f.is_file() and f.suffix.lower() in (".m4a", ".mp4", ".flac", ".mp3", ".wav") and f.stat().st_mtime >= run_start_ts
            ]

        if not audio_files:
            logger.error(f"[Task {task_id}] Apple Music 下载完成但未在 {download_base} 找到音频产物")
            raise RuntimeError("Apple Music 下载完成但未能获取到最终音频文件")

        # Find the common parent folder of the new files
        common_parent = audio_files[0].parent

        # Move all files (audio, lrc, cover) in common_parent to task output_dir
        moved_audio_files: List[Path] = []
        for item in list(common_parent.iterdir()):
            if item.is_file():
                dest = output_dir / item.name
                shutil.move(str(item), str(dest))
                if dest.suffix.lower() in (".m4a", ".mp4", ".flac", ".mp3", ".wav"):
                    moved_audio_files.append(dest)

        # Clean empty leftover directory in download_base if it is a subfolder
        try:
            if common_parent != download_base and common_parent.exists() and not any(common_parent.iterdir()):
                common_parent.rmdir()
                if common_parent.parent != download_base and common_parent.parent.exists() and not any(common_parent.parent.iterdir()):
                    common_parent.parent.rmdir()
        except Exception:
            pass

        if not moved_audio_files:
            raise RuntimeError("移动成品文件至存储目录失败")


        # Delivery logic: Single track vs Multi-track Album
        if len(moved_audio_files) == 1 and media_type == "song":
            final_file = moved_audio_files[0]
            logger.info(f"[Task {task_id}] 单曲下载完成: {final_file.name} (大小: {final_file.stat().st_size} 字节)")
            return final_file, final_file.name
        else:
            # Multi-track Album: Package into .zip archive
            album_name = common_parent.name if common_parent.name != "AM-DL downloads" else "Apple_Music_Album"
            zip_filename = f"{album_name}.zip"
            zip_path = output_dir / zip_filename

            logger.info(f"[Task {task_id}] 正在将专辑 ({len(moved_audio_files)} 首) 打包为 ZIP: {zip_filename}")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
                for file_to_zip in output_dir.iterdir():
                    if file_to_zip.is_file() and file_to_zip.name != zip_filename:
                        zip_out.write(file_to_zip, arcname=file_to_zip.name)

            logger.info(f"[Task {task_id}] 专辑打包完成: {zip_filename} (大小: {zip_path.stat().st_size} 字节)")
            return zip_path, zip_filename

    async def _run_am_download_stream(
        self,
        task_id: str,
        cmd: list,
        work_dir: Path,
        progress_callback: ProgressCallback,
        cancel_event: asyncio.Event
    ) -> None:
        """Executes Apple Music Downloader subprocess, parsing stdout/stderr lines."""
        loop = asyncio.get_running_loop()
        line_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        current_track_idx = 1
        total_tracks_count = 1
        last_track_percent = 0.0

        async def process_line(line: str):
            nonlocal current_track_idx, total_tracks_count, last_track_percent
            if not line:
                return

            # Match Track X of Y
            track_match = TRACK_PROGRESS_REGEX.search(line)
            if track_match:
                current_track_idx = int(track_match.group(1))
                total_tracks_count = max(1, int(track_match.group(2)))
                last_track_percent = 0.0
                calc_overall = ((current_track_idx - 1) * 100.0) / total_tracks_count
                await progress_callback(calc_overall, None, None, None, None)
                logger.info(f"[Task {task_id}] 正在处理曲目 [{current_track_idx}/{total_tracks_count}]")
                return

            # Match Downloading... XX% (XX/XX MB, XX MB/s)
            dl_match = DOWNLOADING_PROGRESS_REGEX.search(line)
            if dl_match:
                pct_str, bytes_str, speed_str = dl_match.groups()
                try:
                    track_pct = float(pct_str)
                except ValueError:
                    track_pct = last_track_percent

                last_track_percent = track_pct
                overall_percent = ((current_track_idx - 1) * 100.0 + track_pct) / total_tracks_count
                speed = speed_str.strip() if speed_str else None
                await progress_callback(overall_percent, speed, None, None, None)
                return

        # Subprocess Execution with Threaded Fallback
        use_threaded = False
        async_proc = None
        sync_proc = None

        try:
            async_proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
        except (NotImplementedError, AttributeError):
            use_threaded = True
        except FileNotFoundError:
            raise RuntimeError(f"未找到可执行命令: {cmd[0]}")
        except Exception as e:
            raise RuntimeError(f"启动 Apple Music 进程失败: {str(e)}")

        if not use_threaded and async_proc:
            async def read_async_stream():
                while True:
                    line_bytes = await async_proc.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    await process_line(line)

            stream_task = asyncio.create_task(read_async_stream())

            while async_proc.returncode is None:
                if cancel_event.is_set():
                    logger.info(f"[Task {task_id}] 收到取消信号，终止 Apple Music 进程 PID {async_proc.pid}")
                    try:
                        async_proc.terminate()
                        await asyncio.sleep(0.5)
                        if async_proc.returncode is None:
                            async_proc.kill()
                    except Exception:
                        pass
                    stream_task.cancel()
                    raise asyncio.CancelledError("下载任务已取消")

                try:
                    await asyncio.wait_for(asyncio.shield(async_proc.wait()), timeout=0.5)
                except asyncio.TimeoutError:
                    pass

            await stream_task
            if async_proc.returncode != 0:
                logger.error(f"[Task {task_id}] Apple Music 异常退出 ({async_proc.returncode})")
                raise RuntimeError(f"Apple Music 下载失败 (退出码 {async_proc.returncode})")

        else:
            # Threaded Mode for Windows Selector loop
            sync_proc = subprocess.Popen(
                cmd,
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )


            def stdout_reader():
                for raw_line in iter(sync_proc.stdout.readline, b''):
                    line_str = raw_line.decode("utf-8", errors="replace").strip()
                    loop.call_soon_threadsafe(line_queue.put_nowait, line_str)
                loop.call_soon_threadsafe(line_queue.put_nowait, None)

            reader_t = threading.Thread(target=stdout_reader, daemon=True)
            reader_t.start()

            while True:
                if cancel_event.is_set():
                    logger.info(f"[Task {task_id}] 收到取消信号，终止线程子进程 PID {sync_proc.pid}")
                    try:
                        sync_proc.terminate()
                    except Exception:
                        pass
                    raise asyncio.CancelledError("下载任务已取消")

                try:
                    line = await asyncio.wait_for(line_queue.get(), timeout=0.5)
                    if line is None:
                        break
                    await process_line(line)
                except asyncio.TimeoutError:
                    if sync_proc.poll() is not None and line_queue.empty():
                        break

            reader_t.join(timeout=2.0)
            sync_proc.wait()

            if sync_proc.returncode != 0:
                logger.error(f"[Task {task_id}] Apple Music 进程异常退出 ({sync_proc.returncode})")
                raise RuntimeError(f"Apple Music 下载失败 (退出码 {sync_proc.returncode})")
