"""SQLAlchemy models for video generation jobs."""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Enum
from db.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def utc_now():
    return datetime.now(timezone.utc)


class VideoJob(Base):
    """Represents an asynchronous STEM video generation job."""
    __tablename__ = "video_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic = Column(String(500), nullable=False, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    progress_percent = Column(Integer, default=0, nullable=False)
    current_step = Column(String(255), default="Queued", nullable=False)
    
    # Output metadata
    video_path = Column(String(1000), nullable=True)
    total_duration_sec = Column(Float, default=0.0, nullable=False)
    
    # Token consumption metrics
    total_tokens = Column(Integer, default=0, nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    candidates_tokens = Column(Integer, default=0, nullable=False)
    api_calls = Column(Integer, default=0, nullable=False)
    
    # Error logging
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """Converts model instance to dictionary representation."""
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status.value if isinstance(self.status, JobStatus) else self.status,
            "progress_percent": self.progress_percent,
            "current_step": self.current_step,
            "video_path": self.video_path,
            "total_duration_sec": self.total_duration_sec,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "candidates_tokens": self.candidates_tokens,
            "api_calls": self.api_calls,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
