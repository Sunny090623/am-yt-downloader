from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Text
from app.database import Base

class AdminSession(Base):
    __tablename__ = "admin_sessions"

    session_id = Column(String(64), primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
