# ==============================================================================
# Ultra-Fast Optimized Multi-Stage Dockerfile for Synology NAS / Linux
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build React Frontend
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

ARG NPM_REGISTRY=""
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry $NPM_REGISTRY; fi

# Cache package dependencies
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund --prefer-offline

COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Fast Local Go Binary Compilation
# ------------------------------------------------------------------------------
FROM golang:1.22-alpine AS go-builder
WORKDIR /app/apple-music-src

ARG GOPROXY="https://proxy.golang.org,direct"
ENV GOPROXY=$GOPROXY

# Copy local source directly (avoids slow git clone over network)
COPY apple-music/ ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /app/bin/apple-music-downloader .

# ------------------------------------------------------------------------------
# Stage 3: Minimal GPAC (MP4Box) Static Compilation
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS gpac-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    zlib1g-dev \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
# Copy local gpac source if provided, or clone minimal depth 1 if missing
COPY gpac/ /tmp/gpac/
RUN if [ ! -f /tmp/gpac/configure ]; then \
        git clone --depth 1 https://github.com/gpac/gpac.git /tmp/gpac; \
    fi && \
    cd /tmp/gpac && \
    ./configure --static-bin --use-zlib=no --strip --disable-x11 --disable-ssl && \
    make -j$(nproc) && \
    make install && \
    (cp bin/gcc/MP4Box /usr/local/bin/MP4Box || cp /usr/local/bin/MP4Box /usr/local/bin/MP4Box || true)

# ------------------------------------------------------------------------------
# Stage 4: Production Runtime (Python 3.11 Slim + FFmpeg + MP4Box + Node.js)
# ------------------------------------------------------------------------------
FROM python:3.11-slim

ARG PIP_INDEX_URL=""
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# 1. Install system utilities and multimedia engines in a single layer (without removed Debian gpac)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# 2. Pre-install backend dependencies with binary wheels (fast download & no compilation)
COPY backend/requirements.txt ./backend/
RUN if [ -n "$PIP_INDEX_URL" ]; then pip config set global.index-url $PIP_INDEX_URL; fi && \
    pip install --prefer-binary -r ./backend/requirements.txt yt-dlp curl-cffi yt-dlp-ejs

# 3. Copy Backend application code
COPY backend/ ./backend/

# 4. Copy compiled Frontend bundle from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 5. Copy pre-compiled Apple Music Downloader binary from Stage 2
COPY --from=go-builder /app/bin/apple-music-downloader /usr/local/bin/apple-music-downloader
RUN chmod +x /usr/local/bin/apple-music-downloader

# 6. Copy pre-compiled MP4Box binary from Stage 3
COPY --from=gpac-builder /usr/local/bin/MP4Box /usr/local/bin/MP4Box
RUN chmod +x /usr/local/bin/MP4Box

# 7. Initialize runtime directories and configuration
RUN mkdir -p /app/apple-music /app/backend/data/logs /app/backend/data/storage/temp
COPY apple-music/config.yaml* /app/apple-music/
RUN if [ ! -f /app/apple-music/config.yaml ] && [ -f /app/apple-music/config.yaml.example ]; then cp /app/apple-music/config.yaml.example /app/apple-music/config.yaml; fi

WORKDIR /app/backend

ENV ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    YTDLP_PATH=yt-dlp \
    FFMPEG_PATH=ffmpeg \
    FFPROBE_PATH=ffprobe \
    GPAC_PATH=MP4Box \
    APPLE_MUSIC_DIR=/app/apple-music \
    APPLE_MUSIC_BINARY=/usr/local/bin/apple-music-downloader \
    DATA_DIR=/app/backend/data \
    STORAGE_DIR=/app/backend/data/storage \
    TEMP_DIR=/app/backend/data/storage/temp \
    DATABASE_URL=sqlite+aiosqlite:////app/backend/data/app.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
