import asyncio
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Tuple
from app.config import settings
from app.downloaders.base import BaseDownloader, MediaMetadata, ProgressCallback
from app.core.url_validator import validate_and_sanitize_youtube_url
from app.core.logger import logger
from app.core.process_utils import resolve_binary, kill_proc_tree

PROGRESS_REGEX = re.compile(r"\[PROGRESS\]:\s*([\d\.]+)%?\|([^|]*)\|([^|]*)\|([^|]*)\|([^|\r\n]*)")
FALLBACK_PERCENT_REGEX = re.compile(r"\[download\]\s+([\d\.]+)%")
FALLBACK_SPEED_REGEX = re.compile(r"at\s+([\d\.]+\s*[kKMGT]?i?B/s)")
FALLBACK_ETA_REGEX = re.compile(r"ETA\s+([\d:]+)")


def get_ytdlp_cmd_base() -> list:
    """Resolves executable path or fallback python module invocation."""
    resolved = resolve_binary(settings.YTDLP_PATH)
    if shutil.which(resolved) or Path(resolved).exists():
        return [resolved]
    try:
        import yt_dlp
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return [resolved]


class YouTubeDownloader(BaseDownloader):

    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        return validate_and_sanitize_youtube_url(url)

    async def extract_info(self, url: str) -> MediaMetadata:
        """Runs yt-dlp -J to extract metadata without downloading."""
        is_valid, sanitized_url, err = self.validate_url(url)
        if not is_valid or not sanitized_url:
            raise ValueError(err or "无效的 YouTube URL")

        cmd = get_ytdlp_cmd_base() + [
            "--dump-single-json",
            "--no-warnings",
            "--no-playlist",
            sanitized_url
        ]

        logger.info(f"[YouTubeDownloader] 正在解析元数据: {sanitized_url} (使用引擎: {' '.join(cmd[:2])})")

        stdout_bytes, stderr_bytes, returncode = await self._run_exec_or_thread(cmd)

        if returncode != 0:
            err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
            logger.warning(f"[YouTubeDownloader] 元数据提取退出码 {returncode}: {err_msg}")
            raise RuntimeError(f"解析视频元信息失败: {err_msg[:300] if err_msg else '未知错误'}")

        try:
            info = json.loads(stdout_bytes.decode("utf-8", errors="replace"))
        except Exception as e:
            logger.error(f"[YouTubeDownloader] JSON 解析失败: {str(e)}")
            raise RuntimeError("无法解析 yt-dlp 返回的 JSON 数据")

        title = info.get("title") or "YouTube Video"
        uploader = info.get("uploader") or info.get("channel")
        duration = info.get("duration")
        thumbnail_url = info.get("thumbnail")

        logger.info(f"[YouTubeDownloader] 元数据解析成功: '{title}' (发布者: {uploader}, 时长: {duration}s)")

        return MediaMetadata(
            title=title,
            uploader=uploader,
            duration=duration,
            thumbnail_url=thumbnail_url
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
        Executes download via yt-dlp subprocess with streaming progress.
        Supports both asyncio subprocess and threaded fallback on Windows.
        """
        is_valid, sanitized_url, err = self.validate_url(url)
        if not is_valid or not sanitized_url:
            raise ValueError(err or "无效的 YouTube URL")

        output_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_exec = resolve_binary(settings.FFMPEG_PATH)

        cmd = get_ytdlp_cmd_base() + [
            "--newline",
            "--no-warnings",
            "--no-playlist",
            "--no-abort-on-error",
            "--retries", "3",
            "--extractor-retries", "3",
            "-f", "bv*[dynamic_range=HDR]+ba/bv*+ba/b",
            "--merge-output-format", "mkv",
            "--ffmpeg-location", ffmpeg_exec,
            "--progress-template", "[PROGRESS]:%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|%(progress.downloaded_bytes)s|%(progress.total_bytes_estimate)s",
            "-P", f"temp:{temp_dir}",
            "-P", f"home:{output_dir}",
            "-o", "%(title).200B.%(ext)s",
            sanitized_url
        ]


        logger.info(f"[Task {task_id}] 开始下载命令: {' '.join(cmd[:6])}... URL: {sanitized_url}")

        await self._run_download_stream(task_id, cmd, progress_callback, cancel_event)

        # Locate completed file in output_dir
        downloaded_files = [f for f in output_dir.iterdir() if f.is_file() and not f.name.endswith((".part", ".ytdl", ".temp"))]
        if not downloaded_files:
            logger.error(f"[Task {task_id}] 输出目录未找到产物文件: {output_dir}")
            raise RuntimeError("下载完成但未能在目标目录找到成品文件")

        # Pick the newest file
        final_file = max(downloaded_files, key=lambda f: f.stat().st_mtime)
        logger.info(f"[Task {task_id}] 下载并合并完成: {final_file.name} (大小: {final_file.stat().st_size} 字节)")
        return final_file, final_file.name

    async def _run_exec_or_thread(self, cmd: list) -> Tuple[bytes, bytes, int]:
        """Runs a subprocess using asyncio or fallback to thread on Windows SelectorEventLoop."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return stdout, stderr, proc.returncode
        except (NotImplementedError, AttributeError):
            # Fallback to synchronous subprocess in thread
            def run_sync():
                p = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                out, err = p.communicate()
                return out, err, p.returncode

            return await asyncio.to_thread(run_sync)
        except FileNotFoundError:
            raise RuntimeError(f"未找到可执行文件: {cmd[0]}")
        except Exception as e:
            raise RuntimeError(f"执行命令失败: {str(e)}")

    async def _run_download_stream(
        self,
        task_id: str,
        cmd: list,
        progress_callback: ProgressCallback,
        cancel_event: asyncio.Event
    ) -> None:
        """Executes download with line-by-line stream parsing, supporting Windows event loops."""
        loop = asyncio.get_running_loop()
        line_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        last_percent = 0.0

        async def process_line(line: str):
            nonlocal last_percent
            if not line:
                return
            match = PROGRESS_REGEX.search(line)
            if match:
                p_str, speed, eta, d_bytes_str, t_bytes_str = match.groups()
                try:
                    percent = float(p_str.replace("%", "").strip())
                except ValueError:
                    percent = last_percent

                last_percent = percent
                speed = speed.strip() if speed.strip() and speed.strip() != "NA" else None
                eta = eta.strip() if eta.strip() and eta.strip() != "NA" else None

                try:
                    d_bytes = int(d_bytes_str) if d_bytes_str and d_bytes_str != "NA" else None
                except ValueError:
                    d_bytes = None

                try:
                    t_bytes = int(t_bytes_str) if t_bytes_str and t_bytes_str != "NA" else None
                except ValueError:
                    t_bytes = None

                await progress_callback(percent, speed, eta, d_bytes, t_bytes)
            else:
                p_match = FALLBACK_PERCENT_REGEX.search(line)
                if p_match:
                    try:
                        percent = float(p_match.group(1))
                        speed_m = FALLBACK_SPEED_REGEX.search(line)
                        eta_m = FALLBACK_ETA_REGEX.search(line)
                        speed = speed_m.group(1) if speed_m else None
                        eta = eta_m.group(1) if eta_m else None
                        await progress_callback(percent, speed, eta, None, None)
                    except Exception:
                        pass

        # Try Async Subprocess first, fallback to Threaded Popen if SelectorEventLoop
        use_threaded = False
        async_proc = None
        sync_proc = None

        try:
            async_proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=4 * 1024 * 1024
            )

        except (NotImplementedError, AttributeError):
            use_threaded = True
        except FileNotFoundError:
            raise RuntimeError(f"未找到 yt-dlp 可执行文件: {cmd[0]}")
        except Exception as e:
            raise RuntimeError(f"启动下载进程失败: {str(e)}")

        if not use_threaded and async_proc:
            # Async Subprocess Mode
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
                    logger.info(f"[Task {task_id}] 收到取消信号，终止子进程 PID {async_proc.pid}")
                    try:
                        kill_proc_tree(async_proc.pid)
                        async_proc.terminate()
                    except Exception:
                        pass
                    stream_task.cancel()
                    raise asyncio.CancelledError("下载任务已取消")

                try:
                    await asyncio.wait_for(asyncio.shield(async_proc.wait()), timeout=0.5)
                except asyncio.TimeoutError:
                    pass

            await stream_task
            _, stderr = await async_proc.communicate()

            if async_proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.error(f"[Task {task_id}] yt-dlp 异常退出 ({async_proc.returncode}):\n{err_msg}")
                raise RuntimeError(f"下载失败 (代码 {async_proc.returncode}): {err_msg[:400] if err_msg else '未知错误'}")

        else:
            # Threaded Popen Mode (Fallback on Windows environments)
            sync_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            def stdout_reader_thread():
                for raw_line in iter(sync_proc.stdout.readline, b''):
                    line_str = raw_line.decode("utf-8", errors="replace").strip()
                    loop.call_soon_threadsafe(line_queue.put_nowait, line_str)
                loop.call_soon_threadsafe(line_queue.put_nowait, None) # Sentinel

            reader_t = threading.Thread(target=stdout_reader_thread, daemon=True)
            reader_t.start()

            # Process queue items asynchronously
            while True:
                if cancel_event.is_set():
                    logger.info(f"[Task {task_id}] 收到取消信号，终止线程子进程 PID {sync_proc.pid}")
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
                stderr_text = sync_proc.stderr.read().decode("utf-8", errors="replace").strip()
                logger.error(f"[Task {task_id}] yt-dlp 异常退出 ({sync_proc.returncode}):\n{stderr_text}")
                raise RuntimeError(f"下载失败 (代码 {sync_proc.returncode}): {stderr_text[:400] if stderr_text else '未知错误'}")
