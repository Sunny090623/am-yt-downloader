# AM-YT-Downloader (MediaHub)

个人专属媒体下载与管理服务。针对 **Windows** 本地开发测试与 **Synology NAS (群晖)** 生产部署进行深度适配与极致性能优化。

## ⚠️ 免责声明 / Disclaimer

本工具仅供学习交流与个人合法订阅内容的本地备份归档使用。
使用者需自行承担因违反目标平台服务条款（Terms of Service）或相关版权法律所产生的全部法律责任，作者不对任何滥用行为承担责任。

---

## 📌 开发计划 (Roadmap)

- [x] **适配 Apple Music 下载**：接入 Apple Music 下载引擎，支持单曲 (Single) 与专辑 (Album) 独立额度管理、无损音质解析及完整元数据标签写入。
- [x] **Docker 镜像构建性能优化**：引入全量 `.dockerignore` 上下文拦截、本地 Go 源码编译加速、Pip pre-built wheels 预拉取及多阶段层级复用，构建耗时大幅降低。
- [x] **修复 `docker compose up -d --build` 一键构建**：内置全套编译环境，实现零配置秒级构建启动。
- [ ] 适配 `apple-music-downloader` 中更多可选参数（如杜比全景声、MV 提取等）。
- [ ] 重构页面，减少 AI 感。

---

## 🌟 核心功能

- **YouTube 高清下载**：基于 `yt-dlp`，支持最高 HDR/4K 视频画质与音频提取，默认最佳音画流自动封装合并，无需二次转码。
- **Apple Music 原声下载**：集成 `apple-music-downloader`，支持单曲（M4A）与整张专辑一键打包（ZIP），自动嵌入官方正式元数据与 3000x3000px 超清封面。
- **全端自适应交互界面**：现代化单页应用，支持暗黑/浅色主题自由切换，深度适配桌面端、平板及移动端设备触控。
- **匿名配额与权限管控**：内置每日下载额度限制（普通用户 5 视频 / 5 专辑 / 10 单曲，失败/取消自动返还），支持管理员免限权、控制台在线配置与全局管理。

---

## ⚠️ 已知问题

* None🎆🎆🎆

---

## 🛠️ Windows 本地开发与测试指南

注意：请参考 [apple-music-downloader](https://github.com/zhaarey/apple-music-downloader) 以及 [wrapper](https://github.com/WorldObservationLog/wrapper) 提前安装必要依赖。

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
   ```
4. 配置环境变量（可选）：
   复制根目录下的 `.env.example` 为 `.env` 并填写实际路径：
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

本项目采用**全自动化多阶段 Docker 镜像构建**，已将 **FFmpeg、Node.js 运行时、yt-dlp、curl-cffi、Apple Music 引擎以及编译好的前端静态资源**全部打包进单一容器内：

- ❌ **无需**在群晖宿主机上手动安装 Conda、Python、FFmpeg 或 yt-dlp；
- ❌ **无需**在宿主机上手动新建文件夹（Docker 会自动挂载并初始化）；
- ❌ **无需**单独部署前端或配置 Nginx 反向代理。

### 🚀 一键启动步骤

1. 将整个项目文件夹复制到群晖 NAS 或 Linux 服务器；
2. 在该目录下直接执行一行命令：
   ```bash
   docker compose up -d --build
   ```
   *(或在群晖 **Container Manager -> 项目 (Project)** 中选择该目录并点击“构建并启动”)*；
3. 启动完成后，直接在浏览器中打开：
   ```text
   http://<NAS_IP>:5173
   ```

---

## 🎵 Apple Music 与 Wrapper 服务端配置

Apple Music 下载依赖于局域网内运行的 Apple Music Wrapper 解密服务。系统支持两种便捷的配置方式：

### 方式一：网页端可视化一键配置（推荐）

1. 打开网页端，点击右上角 **管理员登录**（默认初始密码：`admin123`，可在管理后台或 `.env` 中修改）；
2. 点击导航栏右上角的 **⚙️ 设置** 按钮打开配置面板；
3. 输入你的 Wrapper 服务所在设备 IP（例如 `192.168.3.154`）和 Apple Music `media-user-token`；
4. 点击 **“测试连接”** 即刻验证端口连通性，确认后点击 **“保存并应用配置”**，系统会自动格式化并安全写入 `apple-music/config.yaml`。

### 方式二：手动编辑配置文件

1. 将 `apple-music/config.yaml.example` 复制为 `apple-music/config.yaml`（若尚不存在）；
2. 打开 `apple-music/config.yaml`，根据实际情况修改如下字段，例如：
   ```yaml
   media-user-token: "你的-media-user-token"   # 获取 AAC-LC 与歌词所需凭据 (可选)
   decrypt-m3u8-port: "192.168.3.154:10020" # Wrapper 解密端口
   get-m3u8-port: "192.168.3.154:20020"     # Wrapper m3u8 获取端口
   ```
3. 网页端每次打开或刷新均会自动读取 `config.yaml` 的最新配置，无需重启服务。

---

## ⚙️ 技术与架构特性

- **多区 Storefront 智能透传**：根据 Apple Music 链接自动匹配所属地区国家代码（如 `cn`、`jp`、`us`、`tw` 等），透传至官方 iTunes Lookup API，无视地域限制获取 100% 正式元数据与 3000x3000px 原盘大图。
- **跨端下载规范兼容 (RFC 6266)**：严格下发 `filename` 与 `filename*=UTF-8''` 双格式响应头，完美兼容 PC、移动端及 Android Chrome 桌面模式拦截。
- **真机实时进度流 (SSE)**：采用 Server-Sent Events 流式推送百分比、曲目分步进度（如 `Track 1 of 6`）、实时下载速度与预估剩余时间 (ETA)，断网/刷新自动重连。
- **全端自适应响应式设计**：深度适配桌面端、平板、主流手机以及 iPhone SE 等老旧机型（$\le 480px$），包含自适应配额胶囊、防折叠按钮与平滑水平滚动表格。
- **Developer Token 自动续期守护**：内置 JWT 解析与 24h 异步巡检协程，Token 剩余有效期低于 30 天时自动在线获取最新凭据并热更新，免除过期烦恼。
- **跨平台进程树安全销毁**：采用 `taskkill /F /T` (Windows) 与 `os.killpg` (POSIX) 深度清理派生子进程树（`ffmpeg`、`MP4Box`），杜绝任务取消后的僵尸进程。
- **24小时物理文件过期清理**：以 `expires_at = completed_at + 24h` 为基准，后台轻量异步协程定时自动扫描清理过期磁盘文件与临时碎片。
- **系统级安全隔离**：严禁 Shell 拼接与 `shell=True`，彻底杜绝命令注入；严格校验文件存储路径与设备凭据归属权，抵御路径穿越攻击。

---

## 🤝 引用

* [Wrapper](https://github.com/WorldObservationLog/wrapper)
* [apple-music-downloader](https://github.com/zhaarey/apple-music-downloader)
* [yt-dlp](https://github.com/yt-dlp/yt-dlp)

---

## 📁 目录结构

```text
am-yt-downloader/
├── apple-music/             # Apple Music Go 下载引擎源码与配置
│   ├── utils/               # ampapi, decrypt, alac, lyrics 工具库
│   ├── config.yaml.example  # 配置文件样例
│   └── main.go              # Go 下载器入口
├── backend/
│   ├── app/
│   │   ├── api/             # 路由层 (Tasks, Download, Auth, Admin)
│   │   ├── core/            # 核心机制 (TaskManager, SSEHub, Quota, Cleanup, TokenRefresher, URLValidator)
│   │   ├── downloaders/     # 下载引擎抽象 (Base, YouTube, AppleMusic)
│   │   ├── models/          # SQLAlchemy 数据模型 (Task, Usage, Session)
│   │   ├── schemas/         # Pydantic 数据模式
│   │   ├── config.py        # 环境变量与路径配置
│   │   ├── database.py      # SQLite 异步会话
│   │   └── main.py          # FastAPI 主入口与生命周期
│   ├── requirements.txt
│   └── tests/               # 自动化单元测试集 (32 项测试全部通过)
├── frontend/
│   ├── src/
│   │   ├── components/      # UI 组件 (Navbar, TaskCard, Toast, AdminModal, SettingsModal)
│   │   ├── pages/           # 页面 (HomePage, YouTubePage, AppleMusicPage, AdminPage)
│   │   ├── services/        # API 与 SSE 客户端
│   │   ├── App.jsx
│   │   └── index.css        # 现代暗黑/浅色毛玻璃设计系统
│   ├── package.json
│   └── vite.config.js
├── Dockerfile               # 全自动化多阶段 Docker 生产镜像构建
├── docker-compose.yml       # 群晖部署配置
├── CHANGELOG.md             # 变更与实现记录
└── README.md
```

