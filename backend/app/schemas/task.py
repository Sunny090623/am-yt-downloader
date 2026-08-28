from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.models.task import TaskStatus, ServiceType, MediaType

class CreateTaskRequest(BaseModel):
    url: str = Field(..., description="YouTube URL to download")
    service_type: ServiceType = Field(default=ServiceType.YOUTUBE, description="Media service type")

class TaskResponse(BaseModel):
    id: str
    user_id: str
    service_type: str
    media_type: str
    url: str
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    uploader: Optional[str] = None
    duration: Optional[int] = None
    
    status: str
    progress_percent: float = 0.0
    download_speed: Optional[str] = None
    eta: Optional[str] = None
    total_bytes: Optional[int] = None
    downloaded_bytes: Optional[int] = None
    error_message: Optional[str] = None
    
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    download_url: Optional[str] = None
    
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int

class TaskProgressUpdate(BaseModel):
    task_id: str
    status: str
    progress_percent: float
    service_type: Optional[str] = None
    media_type: Optional[str] = None
    download_speed: Optional[str] = None
    eta: Optional[str] = None
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    error_message: Optional[str] = None
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

