"""FastAPI route handlers for video generation endpoints."""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import VideoJob, JobStatus
from task_queue.task_queue import task_queue
from api.schemas import VideoGenerateRequest, VideoJobResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.post("/generate", response_model=VideoJobResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_video(
    request: VideoGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Submits a new STEM video generation task asynchronously.
    - Creates a job record in MySQL with PENDING status.
    - Enqueues the task to Redis for worker processing (up to 5 parallel workers).
    """
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic must not be empty.")

    # 1. Create database record
    job = VideoJob(
        topic=topic,
        status=JobStatus.PENDING,
        progress_percent=0,
        current_step="Queued in Redis"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 2. Push to Redis queue
    try:
        task_queue.enqueue(job_id=job.id, topic=job.topic)
    except Exception as e:
        logger.error(f"Failed to enqueue task {job.id} to Redis: {e}")
        job.status = JobStatus.FAILED
        job.error_message = f"Failed to push task to Redis queue: {e}"
        db.commit()
        db.refresh(job)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis queue unavailable: {e}"
        )

    return job


@router.get("", response_model=List[VideoJobResponse])
def list_videos(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all requested video generation jobs, ordered by creation time descending.
    """
    jobs = (
        db.query(VideoJob)
        .order_by(VideoJob.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return jobs


@router.get("/{video_id}", response_model=VideoJobResponse)
def get_video_by_id(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves the status, video path, and metadata for a specific video job.
    """
    job = db.query(VideoJob).filter(VideoJob.id == video_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video job with ID '{video_id}' not found."
        )
    return job
