"""Unit tests for asynchronous queue worker logic."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from db.database import Base
from db.models import VideoJob, JobStatus
from generator.models import PipelineResult, Storyboard, TokenUsage
from task_queue.worker import process_single_job

# Set up testing database
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSession = sessionmaker(bind=test_engine)
Base.metadata.create_all(bind=test_engine)


@patch("task_queue.worker.SessionLocal", side_effect=TestingSession)
@patch("task_queue.worker.VideoGeneratorPipeline")
def test_worker_process_single_job_success(mock_pipeline_cls, mock_session_local):
    """Test worker successfully processes a job, updates DB, records tokens and video path."""
    db = TestingSession()
    job = VideoJob(
        topic="How does DNA replication work?",
        status=JobStatus.PENDING,
        progress_percent=0,
        current_step="Queued"
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    # Mock pipeline execution result
    dummy_video = Path("/tmp/dna_replication.mp4")
    dummy_video.touch(exist_ok=True)
    
    mock_pipeline_instance = MagicMock()
    mock_pipeline_instance.run.return_value = PipelineResult(
        topic="How does DNA replication work?",
        storyboard=Storyboard(
            topic="DNA replication",
            scenes=[]
        ),
        scenes_rendered=[],
        final_video_path=dummy_video,
        total_duration_sec=112.5,
        output_dir=Path("/tmp"),
        is_success=True,
        token_usage=TokenUsage(
            prompt_tokens=5000,
            candidates_tokens=6500,
            total_tokens=11500,
            api_calls=7
        )
    )
    mock_pipeline_cls.return_value = mock_pipeline_instance

    # Run single job processing
    process_single_job(job_id=job_id, topic="How does DNA replication work?")

    # Verify pipeline was called with job_id
    mock_pipeline_instance.run.assert_called_once_with(
        topic="How does DNA replication work?",
        job_id=job_id
    )

    # Verify DB state
    db = TestingSession()
    updated_job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    assert updated_job.status == JobStatus.COMPLETED
    assert updated_job.progress_percent == 100
    assert updated_job.video_path == str(dummy_video.resolve())
    assert updated_job.total_duration_sec == 112.5
    assert updated_job.total_tokens == 11500
    assert updated_job.prompt_tokens == 5000
    assert updated_job.candidates_tokens == 6500
    assert updated_job.completed_at is not None
    db.close()


@patch("task_queue.worker.SessionLocal", side_effect=TestingSession)
@patch("task_queue.worker.VideoGeneratorPipeline")
def test_worker_process_single_job_failure(mock_pipeline_cls, mock_session_local):
    """Test worker handles pipeline failure and records error in DB."""
    db = TestingSession()
    job = VideoJob(
        topic="Faulty Topic",
        status=JobStatus.PENDING,
        progress_percent=0
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    mock_pipeline_instance = MagicMock()
    mock_pipeline_instance.run.side_effect = RuntimeError("Render crash")
    mock_pipeline_cls.return_value = mock_pipeline_instance

    process_single_job(job_id=job_id, topic="Faulty Topic")

    db = TestingSession()
    updated_job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    assert updated_job.status == JobStatus.FAILED
    assert "Render crash" in updated_job.error_message
    db.close()
