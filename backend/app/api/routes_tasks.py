import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.config import settings
from app.models.task import DownloadTask, TaskStatus, ServiceType, MediaType
from app.schemas.task import CreateTaskRequest, TaskResponse, TaskListResponse
from app.core.auth import get_current_user_context, UserContext
from app.core.task_manager import task_manager
from app.core.sse_hub import sse_hub

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

def to_task_response(task: DownloadTask) -> TaskResponse:
    download_url = None
    if task.status == TaskStatus.COMPLETED.value and task.file_path:
        download_url = f"/api/downloads/{task.id}/file"

    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        service_type=task.service_type,
        media_type=task.media_type,
        url=task.url,
        title=task.title,
        thumbnail_url=task.thumbnail_url,
        uploader=task.uploader,
        duration=task.duration,
        status=task.status,
        progress_percent=task.progress_percent,
        download_speed=task.download_speed,
        eta=task.eta,
        total_bytes=task.total_bytes,
        downloaded_bytes=task.downloaded_bytes,
        error_message=task.error_message,
        file_name=task.file_name,
        file_size=task.file_size,
        download_url=download_url,
        created_at=task.created_at,
        completed_at=task.completed_at,
        expires_at=task.expires_at
    )

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_download_task(
    req: CreateTaskRequest,
    user_ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """Submits a new media download task."""
    if req.service_type == ServiceType.APPLE_MUSIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apple Music 下载服务暂未开放"
        )

    task_id = uuid.uuid4().hex
    try:
        task = await task_manager.submit_task(
            task_id=task_id,
            user_id=user_ctx.user_id,
            service_type=req.service_type,
            media_type=MediaType.VIDEO,
            url=req.url,
            is_admin=user_ctx.is_admin
        )
        return to_task_response(task)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"提交任务失败: {str(e)}")

@router.get("", response_model=TaskListResponse)
async def list_download_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    user_ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """Lists download tasks. Admin can see all, normal user sees only their own."""
    stmt = select(DownloadTask).order_by(desc(DownloadTask.created_at)).limit(limit)
    if not user_ctx.is_admin:
        stmt = stmt.where(DownloadTask.user_id == user_ctx.user_id)

    res = await db.execute(stmt)
    tasks = res.scalars().all()

    return TaskListResponse(
        tasks=[to_task_response(t) for t in tasks],
        total=len(tasks)
    )

@router.get("/events")
async def sse_task_events(
    user_ctx: UserContext = Depends(get_current_user_context)
):
    """Subscribes to Server-Sent Events stream for live progress updates."""
    _, event_gen = await sse_hub.subscribe(user_ctx.user_id, user_ctx.is_admin)
    return StreamingResponse(
        event_gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # For Nginx / Synology reverse proxy
        }
    )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_details(
    task_id: str,
    user_ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves single task state."""
    stmt = select(DownloadTask).where(DownloadTask.id == task_id)
    res = await db.execute(stmt)
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if not user_ctx.is_admin and task.user_id != user_ctx.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该任务")

    return to_task_response(task)

@router.post("/{task_id}/cancel")
async def cancel_download_task(
    task_id: str,
    user_ctx: UserContext = Depends(get_current_user_context)
):
    """Cancels a pending or running task."""
    try:
        success = await task_manager.cancel_task(task_id, user_ctx.user_id, user_ctx.is_admin)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务无法取消或已结束")
        return {"success": True, "message": "任务已成功取消"}
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))

@router.delete("/{task_id}")
async def user_delete_task(
    task_id: str,
    user_ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually deletes a task record and its physical files.
    NOTE: Quota will NOT be refunded.
    """
    import shutil
    from pathlib import Path
    from app.core.logger import logger

    stmt = select(DownloadTask).where(DownloadTask.id == task_id)
    res = await db.execute(stmt)
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if not user_ctx.is_admin and task.user_id != user_ctx.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该任务")

    if task.status in (TaskStatus.DOWNLOADING.value, TaskStatus.FETCHING_INFO.value, TaskStatus.PROCESSING.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="正在下载中的任务请先点击取消后再删除")

    # Delete physical folder / files
    task_dir = settings.STORAGE_DIR / task.user_id / task.id
    if task_dir.exists():
        shutil.rmtree(task_dir, ignore_errors=True)
    elif task.file_path and Path(task.file_path).exists():
        try:
            Path(task.file_path).unlink(missing_ok=True)
        except Exception:
            pass

    # Delete task record from database (quota is strictly NOT refunded)
    await db.delete(task)
    await db.commit()

    logger.info(f"[TasksAPI] 用户 {user_ctx.user_id} 手动删除了任务 {task_id} 及其文件 (配额不回退)")
    return {"success": True, "message": "任务及已下载文件已彻底删除"}

@router.post("/clear-finished")
async def clear_finished_tasks(
    user_ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Clears all finished (completed, failed, cancelled, interrupted, expired) tasks and files for current user.
    Quota is strictly NOT refunded for completed downloads.
    """
    import shutil
    from pathlib import Path
    from app.core.logger import logger

    finished_statuses = [
        TaskStatus.COMPLETED.value,
        TaskStatus.FAILED.value,
        TaskStatus.CANCELLED.value,
        TaskStatus.INTERRUPTED.value,
        TaskStatus.EXPIRED.value
    ]

    stmt = select(DownloadTask).where(
        DownloadTask.status.in_(finished_statuses)
    )
    if not user_ctx.is_admin:
        stmt = stmt.where(DownloadTask.user_id == user_ctx.user_id)

    res = await db.execute(stmt)
    tasks_to_clear = res.scalars().all()

    cleared_count = 0
    for task in tasks_to_clear:
        # Delete physical folder / files
        task_dir = settings.STORAGE_DIR / task.user_id / task.id
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)
        elif task.file_path and Path(task.file_path).exists():
            try:
                Path(task.file_path).unlink(missing_ok=True)
            except Exception:
                pass

        await db.delete(task)
        cleared_count += 1

    await db.commit()
    logger.info(f"[TasksAPI] 用户 {user_ctx.user_id} 一键清除了 {cleared_count} 个已完成/历史任务及文件")

    return {
        "success": True,
        "cleared_count": cleared_count,
        "message": f"已一键清除 {cleared_count} 个历史任务及对应文件"
    }
