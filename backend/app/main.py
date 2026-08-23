import sys
import asyncio
import os

# Ensure Windows uses ProactorEventLoop to support asyncio subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.config import settings
from app.database import init_db
from app.core.cleanup import recover_orphaned_tasks_on_startup, cleanup_background_worker
from app.api.routes_tasks import router as tasks_router
from app.api.routes_download import router as download_router
from app.api.routes_auth import router as auth_router
from app.api.routes_admin import router as admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database Tables
    await init_db()
    
    # 2. Recover Orphaned / Interrupted Tasks from previous session
    orphans_cleaned = await recover_orphaned_tasks_on_startup()
    if orphans_cleaned > 0:
        print(f"[Startup] 已重置 {orphans_cleaned} 个上次意外中断的任务状态为 interrupted 并返还额度")

    # 3. Start Background 24h Cleanup Task
    cleanup_task = asyncio.create_task(cleanup_background_worker())
    
    yield
    
    # 4. Graceful Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="AM-YT Downloader API",
    description="Personal Media Downloader Service for Synology NAS and Windows",
    version="0.1.0",
    lifespan=lifespan
)

# CORS Middleware for Vite development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(tasks_router)
app.include_router(download_router)
app.include_router(auth_router)
app.include_router(admin_router)

# Static Files & SPA Fallback (Production / Docker Mode)
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if not FRONTEND_DIST_DIR.exists():
    FRONTEND_DIST_DIR = Path("/app/frontend/dist")

if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        
        file_path = FRONTEND_DIST_DIR / full_path
        if file_path.is_file() and file_path.exists():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
else:
    @app.get("/")
    async def root_dev_info():
        return {
            "service": "AM-YT Downloader Backend API",
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "message": "Frontend dev server running on Vite port (default 5173)"
        }
