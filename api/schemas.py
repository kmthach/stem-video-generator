import os
from typing import Optional
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from generator.config import settings


from generator.utils.path_utils import format_host_path


class VideoGenerateRequest(BaseModel):
    """Request payload for triggering asynchronous video generation."""
    topic: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The STEM topic to explain and animate (e.g. 'What is the difference between ionic and covalent bonding?')"
    )


class VideoJobResponse(BaseModel):
    """Response representation of a video generation job."""
    id: str
    topic: str
    status: str
    video_path: Optional[str] = None
    total_duration_sec: float = 0.0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("video_path", mode="before")
    @classmethod
    def make_video_path_absolute(cls, v):
        if not v:
            return v
        return format_host_path(
            video_path=str(v),
            host_output_dir=settings.host_output_dir,
            container_output_dir=str(settings.default_output_dir.resolve())
        )

