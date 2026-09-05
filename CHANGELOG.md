# Changelog - AM-YT-Downloader

All notable changes, bug fixes, and feature additions for this project are documented in this file.

## [v0.2.4] - 2026-09-05

### Fixed
- **跨平台进程管理与运行时崩溃修复**:
  - 新增 `app/core/process_utils.py`，集中实现跨 Windows 与 Linux 的 `resolve_binary()` 和 `kill_proc_tree()`。
  - 彻底修复 `apple_music.py` 中缺失 `sys` 导入导致的取消下载时 `NameError`。
  - 彻底修复 `youtube.py` 中缺失 `os` 导入导致在 POSIX / Docker 环境下取消下载时 `NameError`。
- **任务删除接口依赖缺失修复**:
  - 修复 `routes_tasks.py` 中缺失 `asyncio`、`shutil`、`Path` 与 `logger` 导入导致的删除任务异常。
- **Apple Music 任务元数据丢失修复**:
  - 扩充 `base.py` 中 `MediaMetadata` dataclass，支持 `is_playlist` 与 `playlist_count` 字段，杜绝元数据解析时抛出 `TypeError` 降级而丢失标题、艺术家与封面信息。
- **取消任务配额重复退还修复**:
  - 修复 `task_manager.py` 在取消下载时捕获 `CancelledError` 再次退款的缺陷，确保取消任务仅扣除/退还一次额度。
- **临时文件清理竞态条件消除**:
  - 优化 `cleanup.py`，统一缓存 `item.stat()`，消除并发删除时的二次调用异常。
- **管理员密码内存安全强化**:
  - 修改密码后将 `config.py` 中的 `ADMIN_PASSWORD` 重置为 `None`，仅保留不可逆哈希，消除进程内存明文残留。

### Optimized
- **高并发与内存稳定性强化**:
  - `quota.py`: 捕获并发 `IntegrityError` 并自动回滚重查，保障多用户首次请求的配额幂等性。
  - `routes_auth.py`: 自动修剪登录防爆破记录中的空 IP 与过期条目，防止无感内存增长。
  - `sse_hub.py`: 设置 `asyncio.Queue(maxsize=500)` 上限，配合丢弃机制防止后台冻结客户端耗尽内存。
  - `routes_admin.py`: 提取密码修改数据模型至 `schemas/admin.py` 并规范顶部导入。

## [v0.2.3] - 2026-09-05

### Added
- **多区 Apple Music 动态国家代码 (Storefront) 透传机制**:
  - 在 `apple_music.py` 中自动从分享链接提取 Storefront 地区代码（如 `cn`、`jp`、`us`、`tw`、`gb` 等），向 iTunes Lookup API 透传 `&country={storefront}`，并在单区查询无果时自动全区优雅降级。彻底解决非美区曲目因官方 API 缺失国家代码返回空列表而导致元数据及 3000x3000px 超清封面回退为默认占位符的问题。
- **RFC 6266 标准双格式 Content-Disposition 下载头**:
  - 在 `routes_download.py` 中同时下发兼容 ASCII 的 `filename="fallback.ext"` 与 UTF-8 编码的 `filename*=UTF-8''...` 规范响应头，彻底消除安卓 Chrome 桌面版模式以及原生下载管理器拦截时因无法解析纯 UTF-8 编码头导致的下载中断或文件名丢失。
- **移动端与老旧设备（$\le 480px$）专用响应式布局系统**:
  - **紧凑配额胶囊**: 增加 `.quota-desktop` 与 `.quota-mobile` 策略，大屏显示完整文字（如 `视频: 5/5 | 专辑: 5/5 | 单曲: 10/10`），手机端自动折叠为紧凑徽标（`视:5 · 专:5 · 曲:10`），极窄屏隐藏品牌文字保护导航栏不产生横向溢出。
  - **自适应配置弹窗**: IP 输入框与“测试连接”按钮在窄屏下自动转为自适应纵向排布，按钮全宽居中，彻底消除水平溢出；底部操作按钮弹性适配，取消按钮设置 `white-space: nowrap; flex-shrink: 0;`，杜绝文字垂直折行；为弹窗补充 `scrollbar-width: thin` 纤细滚动条。
  - **管理后台数据表格自适应**: 表格增加 `.table-responsive` 容器与 `min-width: 650px`，支持移动端原生动量水平平滑滑动。

### Fixed
- **任务卡片下载与删除按钮间距及排布优化 (YouTube & Apple Music 通用)**:
  - 显式声明全局 `.task-actions-main` 样式（`display: flex; align-items: center; gap: 0.85rem; flex-wrap: wrap;`），将删除按钮标准化为 `inline-flex`，彻底根除桌面端与移动端下载按钮与删除按钮紧贴甚至无间距粘连的 UI 缺陷。
- **移除 Apple Music 页面冗余的 Wrapper 配置入口**:
  - 移除了 Apple Music 页面标题旁多余的 `[⚙ Wrapper 配置]` 按钮，与全局导航栏齿轮入口归一化，消除界面元素冲突。
- **Apple Music 任务卡片方形封面小屏拉伸变形修复**:
  - 移除了 `@media (max-width: 640px)` 下强制 `.task-thumbnail { width: 100%; height: 140px; }` 的规则，Apple Music 专辑封面固定为精致正方形（`54px x 54px`），采用横向图文排布与 2 行标题弹性截断（`-webkit-line-clamp: 2`）。
- **Apple Music URL 清洗与 iTunes 域名兼容**:
  - `url_validator.py` 补充支持 `itunes.apple.com` 域名并自动规范化，去除尾部多余斜杠并清洗无关跟踪参数，完整保留 `?i=` 单曲参数。
- **自动化测试套件隔离加固**:
  - 在 `test_api.py` 的测试夹具中对 `settings.DATA_DIR` 进行临时目录隔离，杜绝测试修改持久化写入工作区，新增 3 项回归测试，全套 32 项单元测试全部通过。

## [v0.2.2] - 2026-08-30

### Added
- **子进程进程树深度清理机制 (`kill_proc_tree`)**:
  - 在 `youtube.py` 与 `apple_music.py` 中引入跨平台进程树强制终止函数（Windows 使用 `taskkill /F /T`，POSIX 使用 `os.killpg(SIGKILL)`），任务取消或异常时彻底销毁所有派生子进程（`ffmpeg`、`MP4Box`），从根源杜绝孤儿进程与端口占用。
- **Developer Token 内存 TTL 缓存优化**:
  - 在 `token_refresher.py` 中引入 5 分钟内存 TTL 缓存与并发安全锁，避免高频请求重复进行 Base64 解码与磁盘 Regex 扫描，提升 API 响应吞吐。
- **深色/浅色主题偏好持久化记录**:
  - 在前端引入基于 `localStorage` (`amyt_theme`) 的主题偏好同步与系统偏好自动检测，刷新或重启浏览器后始终保留用户选择的主题模式，并在 `index.html` 加入预挂载脚本杜绝首屏白闪（FOUC）。
- **工程规范与安全配置文件补全**:

  - 在 `.gitignore` 中显式补全 `.admin_password`、`.token_cache`、测试覆盖率与编译产物过滤规则，杜绝敏感凭据误提交风险。
  - 全面重构并升级了 `README.md`，更新 Roadmap、核心特性架构、环境变量规范与完整项目目录树。

### Fixed
- **Python 3.14+ 事件循环策略 DeprecationWarning 修复**:
  - 优化 `WindowsProactorEventLoopPolicy` 设置条件，避免在已默认启用 Proactor 的高版本 Python 下抛出弃用警告。

## [v0.2.1] - 2026-08-28


### Added
- **Apple Music 独立日志目录与全量实时日志落盘 (`data/logs/apple_music/`)**:
  - **双轨日志落盘机制**: 在 `backend/data/logs/apple_music/` 目录下为每个下载任务生成独立的 `task_{id}.log`，同时自动汇总写入滚动的 `apple_music.log`，完整记录下载器原生 stdout/stderr（包含音频分片解密、MP4Box 标签处理、网络请求细节）。
  - **管理端日志源切换 UI**: 在管理后台日志查看面板增加 Tab 切换组件，支持在“系统主日志 (`app.log`)”与“Apple Music 引擎日志 (`apple_music.log`)”之间一键切换并实时刷新。
  - **标准输入防挂起保护**: 启动 Apple Music 子进程时显式关闭 `stdin`（重定向为 `DEVNULL`），杜绝因 `fmt.Scanln()` 或交互提示等待回车导致容器后台永久卡死。
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

### Added
- **管理员控制台新增修改密码功能**:
  - 管理后台新增「修改密码」模态框与 `POST /api/admin/change-password` 接口，支持旧密码校验、新密码长度检查与显隐切换。
  - 修改后的密码哈希自动持久化存入 `data/.admin_password`，确保容器重启或升级后新密码依然有效。

### Fixed
- **浅色与深色模式下日志选项卡及交互按钮对比度与悬浮样式全面优化**:
  - 修复了浅色模式下「系统主日志」由于未定义 CSS 变量导致文字与背景同为白色不可见的问题；为两个日志源定制了鲜明高亮的红色/粉色 Pill 徽章与发光阴影。
  - 重构了 `.btn-secondary` 与 `.btn-danger-outline`，修复「修改密码」悬浮时文字发白不可读以及「退出管理」按钮对比度过低发灰的问题，浅色与深色主题无缝自适应。
- **Apple Music 重复下载异常修复（解决 `Track already exists locally` 导致误报未生成音频文件的 Bug）**:

  - 修复了此前重新下载同一歌曲时，Go 底层输出 `Track already exists locally.` 跳过下载，导致 Python 时间戳扫描未能识别到已有音频产物而抛出异常的问题。
  - 现已重构扫描逻辑：若新写入产物为空，自动兜底扫描并提取暂存目录中的全部有效音频产物，正常移入任务存储并清理暂存区。
- **任务卡片专辑封面实时持久化展示修复**:
  - 修复了 SSE 高频推送进度时，未携带缩略图导致前端状态合并意外将解析好的 `thumbnail_url` 覆盖为 `null` 的 Bug。
  - 为 Apple Music 专属定制了高品质方形 `64x64` 专辑封面样式与优雅的加载失败回退。
- **管理后台修改密码弹窗与按钮 UI 风格统一（消除白底突兀感）**:
  - 修复了 `.btn-secondary` 与 `.input-field` 缺失的全局样式，修改密码弹窗与操作按钮完全统一为暗黑毛玻璃极简美学风格。
  - 移除了前台顶部的「⚡ 管理员免限权：无限下载」多余提示。
- **任务删除逻辑加固（删除运行中任务立即自动终止后台进程）**:

  - 修复了此前在任务列表或后台记录直接删除处于 `downloading` / `fetching_info` / `queued` 的任务时未自动停止后台下载的问题。
  - 现在删除任务时会自动触发 `cancel_task` 中断子进程并回收配额，再彻底移除数据库记录与临时文件。
- **默认回退标题由 `YouTube Media` 优化为 `Audio`**:
  - 修复了下载中或解析元数据失败时任务卡片标题默认显示为 `YouTube Media` 的问题，现已统一规范为 `Audio`。
- **Apple Music 专辑 ZIP 语义化命名与全要素归档升级**:

  - 升级了 `apple_music.py` 中的专辑打包逻辑，压缩包采用 `【歌手】专辑名.zip` 语义化安全命名，替代原本的 UUID 任务 ID。
  - 将该专辑目录下的所有音频曲目（`.m4a`/`.flac`）、LRC 歌词与超高清封面图完整打入 ZIP 压缩包，打包后自动清理中间散落文件，仅保留成品 ZIP 供用户一键下载。
- **Apple Music 专辑名称、多语言 Unicode 与 3000px 超清封面元数据提取修复**:

  - 修复了 `url_validator.py` 在清洗 URL 时误将 `%` 及非 ASCII 字符剔除导致歌曲名称乱码（如 `E7A59E...`）以及网页 404 无法获取封面的问题。
  - 在 `AppleMusicDownloader.extract_info` 中深度集成了官方 iTunes Lookup API，毫秒级获取 100% 官方正式名称、艺术家及 **3000x3000px 超清封面大图**。
- **Apple Music 开发者 Token 24小时自动续期与常驻生命周期守护**:
  - 新增 `app/core/token_refresher.py` 模块与 FastAPI `lifespan` 24 小时后台巡检守护任务，实时解析 JWT `exp` 过期时间戳。
  - 当 Token 剩余有效期小于 30 天时，系统自动从 Apple Music Web Player 在线爬取全新 Token 并热更新至 `config.yaml` 与 `.token_cache`，彻底免除 70 天过期的后顾之忧。
- **Apple Music 开发者 Token 抓取兼容性与内置容灾回退**:

  - 在 `utils/ampapi/token.go` 中内置了官方 Web Player 有效 Developer Token。当因网络阻断、CDN TLS 握手异常 (`EOF`) 或页面结构变动导致动态提取失败时，自动无缝回退至内置 Token，保障无论在何种网络环境下均 100% 具备合法 API 访问凭据。
  - 在 `main.go` 中针对致命错误使用 `os.Exit(1)` 退出，杜绝容器静默退出。
- **Apple Music 成品文件移动与收集逻辑修复**:
  - 补齐了 `AppleMusicDownloader` 类中的 `_cleanup_empty_dirs` 与 `_cleanup_new_files` 辅助方法，解决下载解密成功后清理空目录时抛出 `AttributeError` 的问题。
  - 优化了单曲直接交付与专辑打包流。

- **Apple Music 实时流式进度 Carriage-Return (`\r`) 捕获修复**:

  - 修复了 Go 进度条使用回车符 `\r` 刷新进度导致 Python `readline()` 必须等待单曲全量下载完成才返回换行 `\n`，从而导致前端界面在 `16-bit / 44100 Hz` 处长达数十秒无视觉反馈、看似卡死的问题。
  - 重构了流式读取逻辑，同时支持 `\r` 与 `\n` 实时提取分块数据，并支持 `Downloading...` 与 `Decrypting...` 进度和速率的无缝实时推流。
- **管理后台前端 AdminPage 参数解构命名错误修复**:

  - 修复了 `AdminPage.jsx` 组件入参将 `tasks` 误命名为 `allTasks` 导致访问后台时抛出 `TypeError: Cannot read properties of undefined (reading 'length')` 控制台无法打开的 React 崩溃问题。
- **Apple Music 下载器网络死锁与超时机制加固**:
  - 在 `runv2.go` 中将音频流下载接入了 `httputil.Client` 代理客户端，并配置了请求 Context 超时，解决直连 Apple CDN 偶发停滞无限挂起的问题。
  - 为 Wrapper 解密 TCP 握手增加了 `net.DialTimeout("tcp", addr, 15*time.Second)`，彻底杜绝跨设备网络通讯时的死锁阻塞。
  - 移除了 `main.go` 中的 `fmt.Scanln()` 交互回车等待，防止后台容器无输入环境下永久卡死。
- **管理员路由模块缺失 `from typing import Optional` 修复**:
  - 修复了在 `routes_admin.py` 中使用 `Optional[str]` 类型注解但在模块顶部未导入 `Optional` 导致的 `NameError: name 'Optional' is not defined` 容器启动异常，补齐了完整的类型导入。
- **Synology NAS 挂载目录初始化与 Git 目录结构修复**:
  - 创建了 `data/.gitkeep` 与 `storage/.gitkeep`，并在 `.gitignore` 中配置白名单保留规则，解决群晖 DSM Docker 引擎在宿主机目录不存在时抛出 `Bind mount failed: '/volume1/.../data' does not exist` 的错误。


- **Docker 构建缺失 Debian 12 (bookworm) gpac 软件包修复 (方案一)**: 
  - 针对 Debian 12 官方源彻底移除 `gpac` 的问题，在 [docker/Dockerfile](file:///c:/Users/zihan/Desktop/My-Projects/am-yt-downloader/docker/Dockerfile) 中新增了 `gpac-builder` 独立多阶段构建阶段。
  - 使用 `--static-bin --use-zlib=no --disable-x11 --disable-ssl` 静态编译最小化 `MP4Box` 二进制，彻底消除宿主机及容器内 `libGL.so.1` 等图形库缺失报错，通过 `strip` 与直接拷贝 `bin/gcc/MP4Box` 规避 `make install` 对头文件执行 strip 的异常，并将产物注入运行镜像。

- **Docker 构建 Go 编译器版本升级**: 将 `go-builder` 基础镜像从 `golang:1.22-alpine` 升级为 `golang:1.23-alpine`，满足 `apple-music/go.mod` 要求的 `go >= 1.23.1` 编译约束。
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
