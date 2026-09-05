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
from datetime import datetime

import httpx

from app.config import settings
from app.downloaders.base import BaseDownloader, MediaMetadata, ProgressCallback
from app.core.url_validator import validate_and_sanitize_apple_music_url
from app.core.logger import logger, APPLE_MUSIC_LOG_DIR, APPLE_MUSIC_LOG_FILE
from app.core.token_refresher import token_manager


TRACK_PROGRESS_REGEX = re.compile(r"Track\s+(\d+)\s+of\s+(\d+):", re.IGNORECASE)
PROGRESS_REGEX = re.compile(r"(?:Downloading|Decrypting)\.\.\.\s+([\d\.]+)%?\s*(?:\(([^,\)]+)(?:,\s*([^\)]+))?\))?", re.IGNORECASE)
TRACK_TITLE_REGEX = re.compile(r"^\d{2}\.\s+(.+)$")

QUALITY_REGEX = re.compile(r"(\d+-bit\s*/\s*\d+\s*Hz|\d+\s*Kbps)", re.IGNORECASE)

def kill_proc_tree(pid: int) -> None:
    """Kills a process and all of its spawned child processes across Windows & Linux."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            try:
                os.killpg(os.getpgid(pid), 9)
            except Exception:
                os.kill(pid, 9)
    except Exception:
        pass

class AppleMusicDownloader(BaseDownloader):

    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        is_valid, sanitized_url, _, err = validate_and_sanitize_apple_music_url(url)
        return is_valid, sanitized_url, err

    async def extract_info(self, url: str) -> MediaMetadata:
        """Extracts title, artist, and artwork metadata for Apple Music song or album."""
        is_valid, sanitized_url, media_type, err = validate_and_sanitize_apple_music_url(url)
        if not is_valid or not sanitized_url:
            raise ValueError(err or "无效的 Apple Music URL")

        parsed = urllib.parse.urlparse(sanitized_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        query_params = urllib.parse.parse_qs(parsed.query)

        # Extract storefront (e.g., 'cn', 'jp', 'us', 'gb', 'tw') from URL path
        storefront = None
        if path_parts and len(path_parts[0]) == 2 and path_parts[0].isalpha():
            storefront = path_parts[0].lower()

        # Extract numeric Apple Music ID (track id if ?i= exists, else album id from path)
        lookup_id = None
        if "i" in query_params and query_params["i"] and query_params["i"][0]:
            lookup_id = query_params["i"][0]
        else:
            for seg in reversed(path_parts):
                if seg.isdigit():
                    lookup_id = seg
                    break

        # Determine fallback title from unquoted URL slug
        slug = ""
        for i, part in enumerate(path_parts):
            if part in ("album", "song", "playlist") and i + 1 < len(path_parts):
                next_part = path_parts[i + 1]
                if not next_part.isdigit():
                    slug = urllib.parse.unquote(next_part)
                break

        fallback_title = slug.replace("-", " ").title() if slug else ("Apple Music Album" if media_type == "album" else "Apple Music Single")
        title = fallback_title
        artist = None
        thumbnail = None
        track_count = 1 if media_type == "song" else None

        # 1. Primary: iTunes Lookup API (Accurate official metadata & 3000x3000 Ultra-HD Artwork)
        if lookup_id:
            try:
                lookup_url = f"https://itunes.apple.com/lookup?id={lookup_id}&entity=song"
                if storefront:
                    lookup_url += f"&country={storefront}"
                
                async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                    resp = await client.get(lookup_url)
                    data = resp.json() if resp.status_code == 200 else {}
                    results = data.get("results", [])

                    # If country-specific query returned no results, retry without country (defaults to US catalog)
                    if not results and storefront:
                        resp_fallback = await client.get(f"https://itunes.apple.com/lookup?id={lookup_id}&entity=song")
                        if resp_fallback.status_code == 200:
                            results = resp_fallback.json().get("results", [])

                    if results:
                        item = results[0]
                        if media_type == "song":
                            # Look for track matching ID or use first result
                            track_item = next((r for r in results if str(r.get("trackId")) == str(lookup_id)), item)
                            title = track_item.get("trackName") or track_item.get("collectionName") or title
                            artist = track_item.get("artistName") or artist
                            art_url = track_item.get("artworkUrl100") or track_item.get("artworkUrl60")
                        else:
                            title = item.get("collectionName") or item.get("trackName") or title
                            artist = item.get("artistName") or artist
                            art_url = item.get("artworkUrl100") or item.get("artworkUrl60")
                            if item.get("trackCount"):
                                track_count = int(item["trackCount"])

                        if art_url:
                            thumbnail = re.sub(r"\d+x\d+bb\.(?:jpg|png)", "3000x3000bb.jpg", art_url)
            except Exception as e:
                logger.warning(f"[AppleMusicDownloader] iTunes API 查询失败: {str(e)}")

        # 2. Secondary fallback: Webpage OpenGraph and JSON-LD parsing
        if not artist or not thumbnail or title == fallback_title:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
                }
                async with httpx.AsyncClient(headers=headers, timeout=6.0, follow_redirects=True) as client:
                    resp = await client.get(sanitized_url)
                    if resp.status_code == 200:
                        html_text = resp.text
                        if not thumbnail:
                            og_image_match = re.search(r'<meta\s+(?:property|name)=["\'](?:og:image|twitter:image)["\']\s+content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
                            if og_image_match:
                                thumbnail = og_image_match.group(1).strip()
            except Exception as e:
                logger.debug(f"[AppleMusicDownloader] 网页回退元数据提取异常: {str(e)}")

        logger.info(f"[AppleMusicDownloader] 元数据提取成功: '{title}' (艺术家: {artist}, 类型: {media_type})")

        return MediaMetadata(
            title=title,
            uploader=artist,
            duration=None,
            thumbnail_url=thumbnail,
            is_playlist=(media_type == "album"),
            playlist_count=track_count
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

        # Ensure Apple Music Developer Token is valid and automatically refreshed
        try:
            await token_manager.ensure_valid_token()
        except Exception as e:
            logger.warning(f"[Task {task_id}] Token 检查/刷新警告: {str(e)}")


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

        # Locate newly produced or verified files
        post_files = set(f.resolve() for f in download_base.rglob("*") if f.is_file())
        new_files = [
            f for f in post_files
            if (f not in pre_files) or (f.stat().st_mtime > pre_mtimes.get(f, 0)) or (f.stat().st_mtime >= run_start_ts)
        ]
        
        # 1. Primary: Audio files that were newly written
        audio_files = [f for f in new_files if f.suffix.lower() in (".m4a", ".mp4", ".flac", ".mp3", ".wav")]
        
        # 2. Resilient Fallback: If Go reported "Track already exists locally", pick up all existing audio in download_base
        if not audio_files:
            audio_files = [
                f for f in download_base.rglob("*")
                if f.is_file() and f.suffix.lower() in (".m4a", ".mp4", ".flac", ".mp3", ".wav")
            ]

        if not audio_files:
            logger.error(f"[Task {task_id}] Apple Music 下载完成但未在 {download_base} 找到音频产物")
            raise RuntimeError("Apple Music 下载完成但未能获取到最终音频文件")


        # Find the folder where output was generated
        common_parent = audio_files[0].parent
        album_folder_name = common_parent.name if common_parent.name != "AM-DL downloads" else "Apple_Music_Album"

        # Move all files (audio, lyrics, artwork) in common_parent to task output_dir
        all_moved_files: List[Path] = []
        audio_moved_files: List[Path] = []

        for item in list(common_parent.iterdir()):
            if item.is_file():
                dest = output_dir / item.name
                shutil.move(str(item), str(dest))
                all_moved_files.append(dest)
                if dest.suffix.lower() in (".m4a", ".mp4", ".flac", ".mp3", ".wav"):
                    audio_moved_files.append(dest)

        self._cleanup_empty_dirs(download_base)

        if not audio_moved_files:
            logger.error(f"[Task {task_id}] 移动成品文件失败: {output_dir}")
            raise RuntimeError("下载完成但未生成音频文件，请检查解密服务或授权配置")

        if len(audio_moved_files) == 1 and media_type == "song":
            final_file = audio_moved_files[0]
            logger.info(f"[Task {task_id}] 单曲下载完成: {final_file.name} (大小: {final_file.stat().st_size} 字节)")
            return final_file, final_file.name
        else:
            # Multi-track Album: Package all tracks, artwork & lyrics into semantic zip
            safe_album_name = re.sub(r'[\\/*?:"<>|]', "_", album_folder_name).strip() or "Apple_Music_Album"
            zip_filename = f"{safe_album_name}.zip"
            zip_path = output_dir / zip_filename
            logger.info(f"[Task {task_id}] 正在将专辑 ({len(audio_moved_files)} 首曲目 + 附属文件) 打包为 ZIP: {zip_filename}")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fpath in all_moved_files:
                    if fpath.is_file() and fpath != zip_path:
                        zf.write(fpath, arcname=fpath.name)
            # Remove individual files after archiving
            for fpath in all_moved_files:
                try:
                    if fpath != zip_path:
                        fpath.unlink(missing_ok=True)
                except Exception:
                    pass
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
        loop = asyncio.get_running_loop()
        line_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        task_log_file = APPLE_MUSIC_LOG_DIR / f"{task_id}.log"

        def write_am_log(text: str):
            if not text:
                return
            ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"{ts_str} [Task {task_id}] {text}\n"
            try:
                with open(task_log_file, "a", encoding="utf-8", errors="replace") as f_task:
                    f_task.write(log_line)
            except Exception:
                pass
            try:
                with open(APPLE_MUSIC_LOG_FILE, "a", encoding="utf-8", errors="replace") as f_all:
                    f_all.write(log_line)
            except Exception:
                pass

        write_am_log(f"启动 Apple Music 下载进程: {' '.join(cmd)} (工作目录: {work_dir})")

        current_track_idx = 1
        total_tracks_count = 1
        last_track_percent = 0.0

        async def process_line(line: str):
            nonlocal current_track_idx, total_tracks_count, last_track_percent
            if not line:
                return

            write_am_log(line)

            track_match = TRACK_PROGRESS_REGEX.search(line)
            if track_match:
                current_track_idx = int(track_match.group(1))
                total_tracks_count = max(1, int(track_match.group(2)))
                last_track_percent = 0.0
                calc_overall = ((current_track_idx - 1) * 100.0) / total_tracks_count
                await progress_callback(calc_overall, None, None, None, None)
                logger.info(f"[Task {task_id}] 正在处理曲目 [{current_track_idx}/{total_tracks_count}]")
                return

            prog_match = PROGRESS_REGEX.search(line)
            if prog_match:
                pct_str, bytes_str, speed_str = prog_match.groups()
                try:
                    track_pct = float(pct_str)
                except ValueError:
                    track_pct = last_track_percent

                last_track_percent = track_pct
                overall_percent = ((current_track_idx - 1) * 100.0 + track_pct) / total_tracks_count
                speed = speed_str.strip() if speed_str else None
                await progress_callback(overall_percent, speed, None, None, None)
                return

        use_threaded = False
        async_proc = None

        try:
            async_proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(work_dir),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=4 * 1024 * 1024
            )

        except (NotImplementedError, AttributeError):
            use_threaded = True
        except Exception as e:
            write_am_log(f"启动 Apple Music 进程失败: {str(e)}")
            raise RuntimeError(f"启动 Apple Music 进程失败: {str(e)}")

        if not use_threaded and async_proc:
            async def read_async_stream():
                buffer = ""
                while True:
                    chunk = await async_proc.stdout.read(256)
                    if not chunk:
                        if buffer.strip():
                            await process_line(buffer.strip())
                        break
                    text = chunk.decode("utf-8", errors="replace")
                    buffer += text
                    while "\r" in buffer or "\n" in buffer:
                        idx_r = buffer.find("\r")
                        idx_n = buffer.find("\n")
                        if idx_r != -1 and idx_n != -1:
                            idx = min(idx_r, idx_n)
                        elif idx_r != -1:
                            idx = idx_r
                        else:
                            idx = idx_n
                        line = buffer[:idx].strip()
                        buffer = buffer[idx + 1:]
                        if line:
                            await process_line(line)

            stream_task = asyncio.create_task(read_async_stream())

            while async_proc.returncode is None:
                if cancel_event.is_set():
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
                raise RuntimeError(f"Apple Music 下载失败 (退出码 {async_proc.returncode})")
        else:
            sync_proc = subprocess.Popen(
                cmd,
                cwd=str(work_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            def stdout_reader():
                buffer = ""
                while True:
                    chunk = sync_proc.stdout.read(256)
                    if not chunk:
                        if buffer.strip():
                            loop.call_soon_threadsafe(line_queue.put_nowait, buffer.strip())
                        break
                    text = chunk.decode("utf-8", errors="replace")
                    buffer += text
                    while "\r" in buffer or "\n" in buffer:
                        idx_r = buffer.find("\r")
                        idx_n = buffer.find("\n")
                        if idx_r != -1 and idx_n != -1:
                            idx = min(idx_r, idx_n)
                        elif idx_r != -1:
                            idx = idx_r
                        else:
                            idx = idx_n
                        line = buffer[:idx].strip()
                        buffer = buffer[idx + 1:]
                        if line:
                            loop.call_soon_threadsafe(line_queue.put_nowait, line)
                loop.call_soon_threadsafe(line_queue.put_nowait, None)

            reader_t = threading.Thread(target=stdout_reader, daemon=True)
            reader_t.start()

            while True:
                if cancel_event.is_set():
                    try:
                        kill_proc_tree(sync_proc.pid)
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
                raise RuntimeError(f"Apple Music 下载失败 (退出码 {sync_proc.returncode})")

    def _cleanup_empty_dirs(self, root: Path) -> None:
        """Removes empty directories recursively under root."""
        try:
            for p in sorted(root.rglob("*"), key=lambda x: len(str(x)), reverse=True):
                if p.is_dir() and not any(p.iterdir()):
                    try:
                        p.rmdir()
                    except Exception:
                        pass
        except Exception:
            pass

    def _cleanup_new_files(self, base_dir: Path, before_snapshot: set) -> None:
        """Removes newly created partial files on task cancellation."""
        try:
            current_files = set(base_dir.rglob("*")) if base_dir.exists() else set()
            for new_f in (current_files - before_snapshot):
                if new_f.is_file():
                    try:
                        new_f.unlink(missing_ok=True)
                    except Exception:
                        pass
            self._cleanup_empty_dirs(base_dir)
        except Exception:
            pass

