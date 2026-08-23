from datetime import date
from sqlalchemy import Column, Integer, String, Date, UniqueConstraint
from app.database import Base

class DailyUsage(Base):
    __tablename__ = "daily_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    date = Column(Date, default=date.today, nullable=False, index=True)
    
    video_count = Column(Integer, default=0, nullable=False)
    album_count = Column(Integer, default=0, nullable=False)
    single_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date"),
    )
