# Changelog - AM-YT-Downloader

All notable changes, bug fixes, and feature additions for this project are documented in this file.

## [v0.2.1] - 2026-08-28

### Added
- **Apple Music 与 Wrapper 服务端前端可视化配置**:
  - **SettingsModal 模态框**: 在导航栏及 Apple Music 页面增加入口，支持直接输入局域网 Wrapper 服务端 IP（如 `192.168.3.154`）与 Apple Music `media-user-token`，支持密码可见性切换。
  - **自动化配置与双向同步**: 打开设置时自动读取并回显现有 `apple-music/config.yaml` 磁盘配置；保存时自动清洗 IP 并精准更新 `decrypt-m3u8-port: "<IP>:10020"` 与 `get-m3u8-port: "<IP>:20020"`，完整保护其他字段与注释。
  - **实时连通性探测 API**: 增加 `POST /api/admin/settings/apple-music/test`，在前端一键测试 10020 端口 TCP 连通性并实时反馈状态。
  - **README 指南**: 完善了通过网页端设置与手动编辑配置文件的详细操作指引。

### Security

- **S1 & S2 (Production Security Checks)**: Added automated startup checks and runtime warnings for default weak `SECRET_KEY` and default `ADMIN_PASSWORD` when running in `ENVIRONMENT=production`.
- **S3 (HMAC Admin Session Cookie)**: Added HMAC-SHA256 signature verification for `amyt_admin_session` cookie (`sign_admin_session` / `verify_and_extract_admin_session`), preventing session ID tampering and matching anonymous device token security standards.
- **S4 (Admin Login Brute-force Protection)**: Added IP-based sliding window rate limiter to `/api/auth/login`, restricting failed attempts to 5 per minute and returning HTTP 429 to mitigate password brute-force attacks.
- **S5 & S6 (URL Sanitization Tightening)**: Enhanced URL path sanitization in `validate_and_sanitize_apple_music_url` to strictly reject directory traversal attempts (`..`), and sanitized fallback query arguments.

### Fixed
- **Docker 构建缺失 Debian 12 (bookworm) gpac 软件包修复 (方案一)**: 
  - 针对 Debian 12 官方源彻底移除 `gpac` 的问题，在 [docker/Dockerfile](file:///c:/Users/zihan/Desktop/My-Projects/am-yt-downloader/docker/Dockerfile) 中新增了 `gpac-builder` 独立多阶段构建阶段。
  - 使用 `--static-bin --use-zlib=no --strip --disable-x11 --disable-ssl` 静态编译最小化 `MP4Box` 二进制，彻底消除宿主机及容器内 `libGL.so.1` 等图形库缺失报错，并将编译产物直接注入运行镜像。
- **Apple Music 下载器缺失 `import time` 修复**: 修复了在 `apple_music.py` 中记录任务起始时间戳 (`time.time()`) 时抛出 `NameError: name 'time' is not defined` 的问题，补充了标准库依赖导入。
- **B1 (Atomic Quota Consumption & TOCTOU Race Fix)**: Implemented atomic `check_and_consume_quota` executing within a single database transaction in `quota.py` and `task_manager.py`, eliminating Time-of-Check to Time-of-Use race conditions under concurrent download submissions.


- **B2 (Apple Music New File Detection)**: Fixed tautology condition (`f.stat().st_mtime > 0`) in `apple_music.py`. Replaced with pre-run snapshot time-mapping (`pre_mtimes`) and strict mtime delta comparison (`f.stat().st_mtime > pre_mtimes.get(f, 0)`), guaranteeing accurate audio output detection.
- **B3 (SSE Push Metadata Classification)**: Added `service_type` and `media_type` to `TaskProgressUpdate` schema and SSE broadcasts, fixing incorrect fallback categorization of newly pushed tasks in `App.jsx`.
- **B4 (YouTube Task List Service Isolation)**: Added `service_type === 'youtube'` filtering in `YouTubePage.jsx`, ensuring YouTube and Apple Music task lists remain strictly separated.
- **B5 & P2 (High-Frequency DB Session Thrashing & SQLite Locking)**: Replaced high-frequency DB writes during downloading streams with in-memory SSE-only broadcast (`_broadcast_progress_only`), reserving SQLite transactions for key state milestones and eliminating `database is locked` lock contention.
- **B6 (Admin Password Hash Caching)**: Pre-calculated and cached bcrypt hash for admin password in `Settings`, eliminating repetitive `bcrypt.gensalt()` CPU overhead on login requests.
- **B7 (Apple Music Cleanup Isolation)**: Safeguarded directory cleanup in `apple_music.py` to prevent accidental deletion of sibling task folders in concurrent runs.
- **B8 (Scoped Clear-Finished Tasks)**: Enhanced `/api/tasks/clear-finished` and frontend `clearFinishedTasks` to support optional `service_type` scoping, ensuring batch cleaning on YouTube/Apple Music pages only clears history for that specific service.
- **yt-dlp 多层级解析与 Conda / venv 深度兼容**:
  - 增强 `resolve_binary`，支持自动探测 Python 环境目录（如 `Scripts/yt-dlp.exe`, `bin/yt-dlp`），解决在 Windows 未激活 Conda 环境直接调用 Python 时 `shutil.which` 返回 None 的问题。
  - 在 `routes_admin.py` 中增加了 Python 模块直接读取 (`import yt_dlp`) 的版本 Fallback 检测。
  - 在 `youtube.py` 中引入 `get_ytdlp_cmd_base`，当独立可执行文件缺失时自动降级为 `python -m yt_dlp` 保证 100% 可用。
- **AdminPage 日志容器自动滚动**:
  - 在 `AdminPage.jsx` 中为实时日志面板 `<pre>` 增加了 `useRef` 与平滑滚动机制，加载或刷新日志时自动滚动到最后一行最新日志。
- **Subprocess Line Buffering Warning**: Removed invalid `bufsize=1` parameter in binary subprocess calls in `apple_music.py` and `youtube.py`, resolving Python 3 `RuntimeWarning`.


### Performance & Docker
- **P1 (SSEHub Lock Contention Reduction)**: Minimized lock duration in `broadcast_task_update` by snapshotting subscriber queues inside the lock and executing `put_nowait` loops outside the lock.
- **P3 & P4 (Async Thread Wrapping for Disk I/O)**: Wrapped synchronous `shutil.disk_usage` and recursive `get_dir_size` in `asyncio.to_thread` in `routes_admin.py`, preventing event-loop stalling on large storage volumes.
- **C1 (Dead Code Cleanup)**: Removed legacy unused `handleAppleMusicClick` in `HomePage.jsx` and cleaned redundant props.
- **C3 (Docker Build Fix)**: Resolved `.dockerignore` conflict with `Dockerfile:73 COPY apple-music/config.yaml` to ensure smooth multi-stage Docker builds.

## [v0.2.0] - 2026-08-28


### Added
- **Apple Music Downloader Integration**:
  - Implemented `AppleMusicDownloader` subclassing `BaseDownloader` in `backend/app/downloaders/apple_music.py`.
  - Added structured URL validator `validate_and_sanitize_apple_music_url` supporting single track (`/song/...`, `?i=...`) and full album (`/album/...`) identification.
  - Zero-configuration mutation design: executes existing validated `config.yaml` within the `apple-music/` working directory without rewriting or touching user configurations.
  - Real-time stdout stream parser for `Track X of Y`, track titles, audio bit-depth/sample-rate, and downloading chunk percent/speed/bytes.
  - Added multi-track automatic ZIP packaging for album downloads, generating `{AlbumName}.zip` with on-the-fly packaging and secure download link.
  - Quota management: distinguishes Single track downloads (10/day) and Album downloads (5/day) with atomic deduction and refund on failure.
  - Frontend: Activated Apple Music card on HomePage and created dedicated `AppleMusicPage.jsx` with real-time SSE progress, quota pills, batch clear-all, and manual delete confirmation.
  - Admin Panel: Added GPAC `MP4Box` version check and Apple Music configuration status in `routes_admin.py` and `AdminPage.jsx`.
  - Multi-stage `Dockerfile`: Stage 1 clones and builds `apple-music-downloader` Go binary from upstream, Stage 2 installs `gpac (MP4Box)` inside the container, achieving zero-dependency deployment on Synology DSM.
  - **Frontend Polish & UX Refinements**:
    - Aligned Apple Music page input layout and header banner to match the YouTube page structure (`download-input-container`, `input-group`, `url-input`).
    - Made Navbar quota indicator context-aware: displays all platform quotas on Home page (`视频: 5/5 | 专辑: 5/5 | 单曲: 10/10`), displays YouTube quota on YouTube page (`视频: 5/5`), and displays Apple Music quota on Apple Music page (`专辑: 5/5 | 单曲: 10/10`).
    - Fixed HomePage Apple Music card hover state: removed `cursor: not-allowed` and dashed border, replaced with smooth hover lift, pink glow shadow, and gradient top border.
    - Updated terminology across UI to `单曲 (Single)` instead of `(Song)`.
    - Enhanced metadata parsing in `apple_music.py` and `task_manager.py` with JSON-LD extraction, OG/Twitter meta filtering, URL slug extraction, and real-time album/track title persistence on completion, eliminating the generic "Apple Music 网页播放器" placeholder.
  - **Docker Build Speed Optimization (From ~30min to ~1-2min)**:
    - Added comprehensive root `.dockerignore` file blocking gigabytes of build context (`data/`, `storage/`, `apple-music/AM-DL*`, `node_modules/`, `.git/`, `.pytest_cache/`) from being sent across memory/disk to the Docker daemon.
    - Optimized Go builder stage in `Dockerfile` to compile from local `apple-music/` source with `GOPROXY` support, eliminating slow international `git clone` delays.
    - Enhanced Python runtime layer with pip `--prefer-binary` pre-built wheels and single-layer caching, avoiding costly wheel compilations on ARM/x86 NAS CPUs.
    - Added optional `NPM_REGISTRY` and `PIP_INDEX_URL` build args for domestic network acceleration.
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
