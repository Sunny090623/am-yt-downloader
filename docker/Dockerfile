# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime (Synology NAS / Linux)
FROM python:3.11-slim

# 1. Install system dependencies (FFmpeg, Node.js runtime for YouTube JS challenges, curl, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Pre-install yt-dlp & advanced challenge handlers
RUN pip install --no-cache-dir yt-dlp curl-cffi yt-dlp-ejs

WORKDIR /app

# 3. Install Python backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# 4. Copy Backend application code
COPY backend/ ./backend/

# 5. Copy compiled Frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 6. Ensure default persistent directories exist
RUN mkdir -p /app/backend/data/logs /app/backend/data/storage/temp

WORKDIR /app/backend

ENV ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    YTDLP_PATH=yt-dlp \
    FFMPEG_PATH=ffmpeg \
    FFPROBE_PATH=ffprobe \
    DATA_DIR=/app/backend/data \
    STORAGE_DIR=/app/backend/data/storage \
    TEMP_DIR=/app/backend/data/storage/temp \
    DATABASE_URL=sqlite+aiosqlite:////app/backend/data/app.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
