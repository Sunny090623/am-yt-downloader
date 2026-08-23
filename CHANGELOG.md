# Changelog - AM-YT-Downloader

All notable changes, bug fixes, and feature additions for this project are documented in this file.

## [v0.1.0] - 2026-08-23

### Added
- Added **Roadmap (开发计划)** section in `README.md` tracking future Apple Music engine adaptation (Single/Album quota, lossless audio, and metadata tagging).
- Updated Docker / Container Manager host port mapping in `docker-compose.yml` to use port **5173** (`5173:8000`), unifying local dev and NAS production access at port 5173.
- Upgraded `Dockerfile` and `docker-compose.yml` to support **100% Turnkey Zero-Config Deployment**:
  - Automatically installs `ffmpeg`, `nodejs` (JS challenge runtime), and `yt-dlp` / `curl-cffi` / `yt-dlp-ejs` inside the Docker image.
  - Multi-stage build compiles React frontend into single FastAPI static bundle, requiring no Nginx or manual folder creation.
  - Users only need to run `docker compose up -d --build` on Synology NAS or Linux.
- Fixed Admin panel component health check (`yt-dlp` and `ffmpeg` status showing "未安装 / 不可用") by implementing threaded `subprocess.Popen` execution with `shutil.which` binary resolution and exact version flags (`yt-dlp --version` / `yt-dlp -v` and `ffmpeg -version`).
- Temporarily removed subtitle downloading and embedding options to avoid YouTube's aggressive timedtext API rate limits (HTTP 429), focusing purely on HDR video and audio download.
- Removed deprecated `--no-call-home` yt-dlp parameter.
- Added `--no-abort-on-error`, `--retries 3`, and `--extractor-retries 3`.
- Added **Batch Clear-All** feature (`POST /api/tasks/clear-finished`) allowing users to one-click delete all finished, completed, and failed tasks along with their physical files.
- Added reusable **ConfirmModal** component with "以后不再提示 (Don't ask again)" checkbox preference persistence in `localStorage`.
- Added "一键清除" button positioned immediately to the left of the refresh button in the task list title bar.
- Removed `(配额不回退)` text suffix from deletion toasts and replaced with polite confirmation modal dialog.
- Added manual task and file deletion feature (`DELETE /api/tasks/{task_id}`) allowing users to delete downloaded media files from disk and clean task records without refunding daily quota.
- Added trash/delete action button to TaskCard in frontend UI with immediate list refresh.

### Fixed
- Implemented robust **Dual-Mode Subprocess Execution** in `YouTubeDownloader`: uses native `asyncio.create_subprocess_exec` when supported, and automatically falls back to threaded `subprocess.Popen` with async queue line streaming when running under Windows `SelectorEventLoop`, completely eliminating `NotImplementedError`.
- Added `backend/run.py` launcher ensuring `WindowsProactorEventLoopPolicy` is set before Uvicorn initialization.
- Implemented structured file logging (`data/logs/app.log` with `RotatingFileHandler` 10MB/5 backups) and console stream.
- Added cross-platform binary resolution using `shutil.which` for `yt-dlp` and `ffmpeg` to resolve Windows `.exe` path lookup issues.
- Added Admin logs endpoint (`GET /api/admin/logs`) and live log viewer directly in the Admin web dashboard.
- Removed top redundant pill badge (`个人专属媒体下载中心 • 私有 NAS 部署`) from HomePage for cleaner layout.
- Fixed Apple Music card background in light theme by replacing hardcoded dark background with theme-adaptive `var(--bg-card)` and clear badge contrast.
- Changed default backend development port to `8001` and updated Vite proxy to avoid Windows `[WinError 10013]` port 8000 permission conflicts.
- Added `backend/pytest.ini` and `backend/tests/conftest.py` with `pythonpath = .` to resolve `ModuleNotFoundError: No module named 'app'`.
- Replaced deprecated `passlib` bcrypt backend with direct `bcrypt` library (`bcrypt.hashpw` and `bcrypt.checkpw`) to prevent 72-byte truncation crash on Python 3.12+ and bcrypt 4.x/5.x.
- Enhanced structured YouTube URL validator with strict video ID regex sanitization (stripping shell characters, spaces, semicolons) and early non-http/https scheme rejection.
- Upgraded `TaskResponse` schema to Pydantic v2 `model_config = ConfigDict(from_attributes=True)` removing deprecation warnings.

### Added
- **Core Architecture & Engine**:
  - Implemented `BaseDownloader` abstraction layer with `MediaMetadata` and async progress callback.
  - Implemented `YouTubeDownloader` utilizing `asyncio.create_subprocess_exec` for safe CLI process execution without `shell=True`.
  - Configured default format strategy `-f "bestvideo+bestaudio/best"` with automatic FFmpeg merging, avoiding forced recoding.
  - Implemented `AppleMusicDownloader` placeholder that rejects operations cleanly with "暂未开放".
  - Created structured YouTube URL validator supporting `youtube.com`, `youtu.be`, `shorts`, `music.youtube.com`, and stripping tracking parameters.
- **Task Management & Real-time Progress**:
  - Implemented `DownloadTaskManager` with async semaphore concurrency control (default max 2 concurrent downloads).
  - Built `SSEHub` for Server-Sent Events broadcasting real-time download percentages, speeds, ETA, and state transitions.
  - Supported cancel capability terminating child subprocesses cleanly.
- **Storage, Retention & Cleanup**:
  - Implemented exact 24-hour retention based on `expires_at = completed_at + 24h`.
  - Built `cleanup_background_worker` scanning every 15 minutes to delete physical files of expired tasks and clean stale temporary fragments (`.part`, `.ytdl`).
  - Added startup orphan recovery mechanism marking in-flight interrupted tasks as `interrupted`, refunding user quota, and cleaning temp files.
  - Implemented secure file download endpoint (`/api/downloads/{task_id}/file`) verifying ownership and validating resolved file path against storage boundary to prevent path traversal attacks.
- **Authentication & Daily Quotas**:
  - Implemented database-backed `AdminSession` with 7-day expiration and instant server-side revocation on logout.
  - Implemented HMAC-SHA256 signed `device_token` HttpOnly cookie for anonymous user identification.
  - Implemented daily quota counter restricting anonymous users to 5 YouTube videos per day, with automatic refunding on failures/cancellations.
  - Admin bypasses daily quota limitations.
- **Frontend SPA (React + Vite + Modern CSS)**:
  - Designed responsive glassmorphism UI with dark/light theme toggle.
  - Built Home page with interactive YouTube downloader card and disabled Apple Music card with friendly toast feedback.
  - Built single-page YouTube downloader allowing URL input, task submission, live progress bar, speed display, and file save button on one screen.
  - Built Admin management console showing system diagnostics, storage disk usage, active downloads, yt-dlp & ffmpeg statuses, global task table, manual 24h cleanup trigger, and logout.
- **Deployment & Testing**:
  - Created multi-stage `Dockerfile` (Node.js build stage + Python 3.11-slim runtime with FFmpeg & yt-dlp).
  - Created `docker-compose.yml` pre-configured for Synology NAS Container Manager.
  - Created automated test suite covering URL validation, quota limits, HMAC cookies, admin sessions, 24h cleanup, startup recovery, and API security.
