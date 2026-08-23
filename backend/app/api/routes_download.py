import urllib.parse
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_db
from app.models.task import DownloadTask, TaskStatus
from app.core.auth import get_current_user_context, UserContext

router = APIRouter(prefix="/api/downloads", tags=["Downloads"])

@router.get("/{task_id}/file")
async def download_task_file(
    task_id: str,
    user_ctx: UserContext = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Secure file download endpoint with path traversal defense and ownership checks.
    """
    stmt = select(DownloadTask).where(DownloadTask.id == task_id)
    res = await db.execute(stmt)
    task = res.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # Ownership check
    if not user_ctx.is_admin and task.user_id != user_ctx.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权下载该文件")

    if task.status != TaskStatus.COMPLETED.value or not task.file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件尚未准备就绪或已过期")

    # Path Traversal Verification
    target_file = Path(task.file_path).resolve()
    base_storage = settings.STORAGE_DIR.resolve()

    try:
        target_file.relative_to(base_storage)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="非法的文件访问路径")

    if not target_file.is_file() or not target_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物理文件已丢失或已过期删除")

    # Safe filename encoding
    filename = task.file_name or target_file.name
    encoded_filename = urllib.parse.quote(filename)

    return FileResponse(
        path=target_file,
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Cache-Control": "no-cache"
        }
    )
