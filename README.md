# AM-YT-Downloader (MediaHub)

个人专属媒体下载与管理服务。针对 **Windows** 本地开发测试与 **Synology NAS (群晖)** 生产部署进行深度适配与优化。

## 📌 开发计划 (Roadmap)

- [ ] **适配 Apple Music 下载**：接入 Apple Music 下载引擎，支持单曲 (Single) 与专辑 (Album) 独立额度管理、无损音质解析及完整元数据标签写入。

---

## 🌟 核心特性

- **YouTube 高清流式下载**：基于 `yt-dlp`，默认最佳画质音视频自动合并封装，不额外重编码，极速且节省 NAS 性能。
- **真机实时进度 (SSE)**：采用 Server-Sent Events 流式推送百分比、下载速度、预估剩余时间 (ETA) 与状态转换，断网/刷新自动重连。
- **一体化交互界面**：输入链接、下载控制、实时进度与文件保存全部在同一个现代化单页内完成，支持自适应暗色/亮色模式与移动端触控适配。
- **合规匿名配额系统**：通过服务端签名 HttpOnly Cookie 进行设备识别，实现普通用户每日 5 个视频额度限制，任务异常/取消自动返还配额。
- **安全可撤销的管理员会话**：数据库驱动的 7 天有效 Session，支持无限下载与全局任务/存储管控，退出登录立即撤销凭据。
- **24小时物理过期清理**：以 `expires_at = completed_at + 24h` 为准，后台轻量异步协程定时自动删除过期磁盘文件与临时碎片。
- **Apple Music 扩展架构**：统一的 `BaseDownloader` 抽象层，第一阶段保留入口与友好提示，未来接入新平台无需重构核心逻辑。
- **系统级安全隔离**：严禁 Shell 拼接与 `shell=True`，彻底杜绝命令注入；严格校验文件存储路径与文件归属权，抵御路径穿越攻击。

---

## 🛠️ Windows 本地开发与测试指南

### 1. 后端准备与启动

1. 打开 PowerShell 进入后端目录：

   ```powershell
   cd backend
   ```
2. 创建并激活 Python 虚拟环境 (或使用 Conda / Miniforge)：

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. 安装依赖：

   ```powershell
   pip install -r requirements.txt
   pip install -U "yt-dlp[default,curl-cffi]" yt-dlp-ejs
   conda install -c conda-forge deno
   # 或 mamba install -c conda-forge deno
   ```
4. 配置环境变量（可选）：
   如 yt-dlp 或 ffmpeg 位于特定路径，复制根目录下的 `.env.example` 为 `.env` 并填写实际路径：

   ```ini
   YTDLP_PATH=C:\path\to\yt-dlp.exe
   FFMPEG_PATH=C:\path\to\ffmpeg.exe
   ```
5. 启动后端服务：

   ```powershell
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
   ```

   后端 Swagger 接口文档地址：`http://127.0.0.1:8001/docs`
6. 运行自动化测试：

   ```powershell
   pytest tests -v
   ```

---

### 2. 前端准备与启动

1. 打开新的终端窗口进入前端目录：
   ```powershell
   cd frontend
   ```
2. 安装前端依赖：
   ```powershell
   npm install
   ```
3. 启动 Vite 开发服务器：
   ```powershell
   npm run dev
   ```
4. 在浏览器中打开：`http://localhost:5173`

---

## 🐳 Synology NAS (群晖) / Linux 零配置一键部署指南

本项目采用**全自动化多阶段 Docker 镜像构建**，已将 **FFmpeg、Node.js 运行时、yt-dlp、curl-cffi 以及编译好的前端静态资源**全部打包进单一容器内：

- ❌ **无需**在群晖宿主机上手动安装 Conda、Python、FFmpeg 或 yt-dlp；
- ❌ **无需**在宿主机上手动新建文件夹（Docker 会自动挂载并初始化）；
- ❌ **无需**单独部署前端或配置 Nginx 反向代理。

### 🚀 一键启动步骤

1. 将整个项目文件夹复制到群晖 NAS（例如 `/volume1/docker/am-yt-downloader`）或服务器；
2. 在该目录下直接执行一行命令：
   ```bash
   docker compose up -d --build
   ```

   *(或在群晖 **Container Manager -> 项目 (Project)** 中选择该目录并点击“构建并启动”)*；
3. 启动完成后，直接在浏览器中打开：
   ```text
   http://<NAS_IP>:5173
   ```

   即可直接进入功能完整的 MediaHub 网站！无需任何额外配置。

---

## 📁 目录结构

```text
am-yt-downloader/
├── backend/
│   ├── app/
│   │   ├── api/             # 路由层 (Tasks, Download, Auth, Admin)
│   │   ├── core/            # 核心机制 (TaskManager, SSEHub, Quota, Cleanup, URLValidator)
│   │   ├── downloaders/     # 下载引擎抽象 (Base, YouTube, AppleMusic)
│   │   ├── models/          # SQLAlchemy 数据模型 (Task, Usage, Session)
│   │   ├── schemas/         # Pydantic 数据模式
│   │   ├── config.py        # 环境变量与路径配置
│   │   ├── database.py      # SQLite 异步会话
│   │   └── main.py          # FastAPI 主入口与生命周期
│   ├── requirements.txt
│   └── tests/               # 自动化单元测试集
├── frontend/
│   ├── src/
│   │   ├── components/      # UI 组件 (Navbar, TaskCard, Toast, AdminModal)
│   │   ├── pages/           # 页面 (HomePage, YouTubePage, AdminPage)
│   │   ├── services/        # API 与 SSE 客户端
│   │   ├── App.jsx
│   │   └── index.css        # 现代设计系统与主题样式
│   ├── package.json
│   └── vite.config.js
├── docker/
│   └── Dockerfile           # 多阶段 Docker 生产镜像构建
├── docker-compose.yml       # 群晖部署配置
├── CHANGELOG.md             # 变更与实现记录
└── README.md
```
