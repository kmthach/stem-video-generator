"""Unit tests for FastAPI video endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from db.database import Base, get_db
from db.models import VideoJob, JobStatus
from api.app import app

# Create in-memory SQLite engine for testing with StaticPool
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@patch("api.routes.task_queue.enqueue")
def test_generate_video_endpoint(mock_enqueue):
    """Test POST /api/videos/generate successfully creates a job and enqueues to Redis."""
    mock_enqueue.return_value = True

    payload = {"topic": "How does photosynthesis work?"}
    response = client.post("/api/videos/generate", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["topic"] == "How does photosynthesis work?"
    assert data["status"] == "PENDING"
    assert "id" in data
    assert data["video_path"] is None
    # Ensure removed fields are not present in the response
    assert "total_tokens" not in data
    assert "prompt_tokens" not in data
    assert "candidates_tokens" not in data
    assert "api_calls" not in data
    assert "current_step" not in data
    assert "progress_percent" not in data

    mock_enqueue.assert_called_once_with(job_id=data["id"], topic=data["topic"])


def test_generate_video_empty_topic():
    """Test POST /api/videos/generate with empty topic returns 422/400 validation error."""
    response = client.post("/api/videos/generate", json={"topic": "   "})
    assert response.status_code in (400, 422)


def test_list_videos_endpoint():
    """Test GET /api/videos returns list of requested video jobs."""
    db = TestingSessionLocal()
    job1 = VideoJob(topic="Topic A", status=JobStatus.COMPLETED, progress_percent=100)
    job2 = VideoJob(topic="Topic B", status=JobStatus.PROCESSING, progress_percent=45)
    db.add_all([job1, job2])
    db.commit()
    db.close()

    response = client.get("/api/videos")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    topics = [item["topic"] for item in data]
    assert "Topic A" in topics
    assert "Topic B" in topics
    assert "total_tokens" not in data[0]
    assert "progress_percent" not in data[0]


def test_get_video_by_id_success():
    """Test GET /api/videos/{id} returns job details and video path."""
    db = TestingSessionLocal()
    job = VideoJob(
        topic="What is Quantum Tunneling?",
        status=JobStatus.COMPLETED,
        progress_percent=100,
        current_step="Completed ✓",
        video_path="/path/to/quantum_tunneling.mp4",
        total_duration_sec=95.4,
        total_tokens=18450,
        prompt_tokens=8200,
        candidates_tokens=10250,
        api_calls=7
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    response = client.get(f"/api/videos/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["topic"] == "What is Quantum Tunneling?"
    assert data["status"] == "COMPLETED"
    assert data["video_path"] == "/path/to/quantum_tunneling.mp4"
    assert data["total_duration_sec"] == 95.4
    # Verify excluded fields
    assert "total_tokens" not in data
    assert "prompt_tokens" not in data
    assert "candidates_tokens" not in data
    assert "api_calls" not in data
    assert "current_step" not in data
    assert "progress_percent" not in data


def test_get_video_by_id_relative_path_converts_to_absolute():
    """Test GET /api/videos/{id} converts a relative video path to an absolute path."""
    from pathlib import Path
    db = TestingSessionLocal()
    job = VideoJob(
        topic="Relative Path Test",
        status=JobStatus.COMPLETED,
        video_path="./output/relative_folder/video.mp4"
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    response = client.get(f"/api/videos/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["video_path"] == str(Path("./output/relative_folder/video.mp4").resolve())
    assert Path(data["video_path"]).is_absolute()


def test_get_video_by_id_container_path_translates_to_host_path():
    """Test GET /api/videos/{id} translates container /app/output path to host machine path when HOST_OUTPUT_DIR is set."""
    from generator.config import settings
    original_host_output_dir = settings.host_output_dir
    settings.host_output_dir = "/Users/testuser/project/output"
    try:
        db = TestingSessionLocal()
        job = VideoJob(
            topic="Docker Container Path Test",
            status=JobStatus.COMPLETED,
            video_path="/app/output/c60bba27-6881-4a83-8daa-446bc1394cca/c60bba27-6881-4a83-8daa-446bc1394cca.mp4"
        )
        db.add(job)
        db.commit()
        job_id = job.id
        db.close()

        response = client.get(f"/api/videos/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["video_path"] == "/Users/testuser/project/output/c60bba27-6881-4a83-8daa-446bc1394cca/c60bba27-6881-4a83-8daa-446bc1394cca.mp4"
    finally:
        settings.host_output_dir = original_host_output_dir


def test_get_video_by_id_not_found():
    """Test GET /api/videos/{id} returns 404 for non-existent job."""
    response = client.get("/api/videos/non-existent-uuid")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_health_check():
    """Test GET /health returns status."""
    with patch("task_queue.task_queue.task_queue.ping", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["redis_connected"] is True
        assert data["max_queue_workers"] == 5
