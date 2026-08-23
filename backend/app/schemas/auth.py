from typing import Optional
from pydantic import BaseModel, Field

class QuotaInfo(BaseModel):
    video_limit: int
    video_used: int
    video_remaining: int
    album_limit: int
    album_used: int
    album_remaining: int
    single_limit: int
    single_used: int
    single_remaining: int
    is_unlimited: bool = False

class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, description="Admin password")

class LoginResponse(BaseModel):
    success: bool
    is_admin: bool
    message: str

class AuthStatusResponse(BaseModel):
    is_admin: bool
    user_id: str
    quota: QuotaInfo
