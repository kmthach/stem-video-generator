"""Unit tests for Database models and Redis task queue."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base
from db.models import VideoJob, JobStatus
from task_queue.task_queue import TaskQueue

# In-memory DB
engine = create_engine("sqlite:///:memory:")
TestSession = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def test_video_job_model_crud():
    """Test VideoJob model persistence and to_dict method."""
    session = TestSession()
    job = VideoJob(
        topic="How does gravity work?",
        status=JobStatus.PENDING,
        progress_percent=0,
        current_step="Queued"
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    assert job.id is not None
    assert job.topic == "How does gravity work?"
    assert job.status == JobStatus.PENDING

    # Test dictionary serialization
    d = job.to_dict()
    assert d["id"] == job.id
    assert d["topic"] == "How does gravity work?"
    assert d["status"] == "PENDING"
    assert d["progress_percent"] == 0

    # Update job
    job.status = JobStatus.COMPLETED
    job.progress_percent = 100
    job.video_path = "/path/to/gravity.mp4"
    session.commit()
    session.refresh(job)

    assert job.status == JobStatus.COMPLETED
    assert job.video_path == "/path/to/gravity.mp4"
    session.close()


def test_task_queue_enqueue_dequeue():
    """Test TaskQueue enqueue and dequeue operations with mocked Redis client."""
    mock_redis = MagicMock()
    mock_redis.lpush.return_value = 1
    mock_redis.brpop.return_value = ("stem_video_tasks", '{"job_id": "test-uuid-123", "topic": "Photosynthesis"}')
    mock_redis.llen.return_value = 1
    mock_redis.ping.return_value = True

    with patch("redis.from_url", return_value=mock_redis):
        queue = TaskQueue("redis://mock:6379/0")
        
        # Test enqueue
        success = queue.enqueue("test-uuid-123", "Photosynthesis")
        assert success is True
        mock_redis.lpush.assert_called_once()

        # Test dequeue
        task = queue.dequeue(timeout=1)
        assert task == {"job_id": "test-uuid-123", "topic": "Photosynthesis"}

        # Test queue length and ping
        assert queue.get_queue_length() == 1
        assert queue.ping() is True
