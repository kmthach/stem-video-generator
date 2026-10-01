"""Asynchronous queue worker service for processing video generation jobs from Redis."""

import time
import signal
import threading
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from generator.config import settings
from db.database import SessionLocal, init_db
from db.models import VideoJob, JobStatus
from task_queue.task_queue import task_queue
from generator.pipeline import VideoGeneratorPipeline
from generator.utils.logger import console
from generator.utils.path_utils import format_host_path

# Set up logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("worker")

stop_requested = threading.Event()


def utc_now():
    return datetime.now(timezone.utc)


def handle_shutdown_signal(signum, frame):
    """Graceful shutdown signal handler."""
    logger.info("Shutdown signal received. Stopping worker pool gracefully...")
    stop_requested.set()


def process_single_job(job_id: str, topic: str):
    """Executes video generation pipeline for a single job and updates MySQL state."""
    logger.info(f"Worker started processing Job [{job_id}] Topic: '{topic}'")
    db = SessionLocal()
    try:
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if not job:
            logger.error(f"Job [{job_id}] not found in database. Skipping.")
            return

        # 1. Update status to PROCESSING
        job.status = JobStatus.PROCESSING
        job.progress_percent = 5
        job.current_step = "Initializing storyboard and neural voice synthesis..."
        job.updated_at = utc_now()
        db.commit()

        # Initialize pipeline
        pipeline = VideoGeneratorPipeline(
            quality=settings.default_quality,
            aspect_ratio=settings.default_aspect_ratio,
            max_workers=settings.max_workers
        )

        # 2. Execute pipeline with job_id so output folder and video are named by job id
        result = pipeline.run(topic=topic, job_id=job_id)

        # 3. Handle outcome
        db.refresh(job)
        if result.is_success and result.final_video_path and result.final_video_path.exists():
            job.status = JobStatus.COMPLETED
            job.progress_percent = 100
            job.video_path = format_host_path(
                video_path=str(result.final_video_path.resolve()),
                host_output_dir=settings.host_output_dir,
                container_output_dir=str(settings.default_output_dir.resolve())
            )
            job.total_duration_sec = result.total_duration_sec
            
            # Record token usage
            if result.token_usage:
                job.total_tokens = result.token_usage.total_tokens
                job.prompt_tokens = result.token_usage.prompt_tokens
                job.candidates_tokens = result.token_usage.candidates_tokens
                job.api_calls = result.token_usage.api_calls

            job.completed_at = utc_now()
            job.updated_at = utc_now()
            db.commit()
            logger.info(f"Job [{job_id}] completed successfully. Output: {job.video_path} (Tokens: {job.total_tokens})")
        else:
            job.status = JobStatus.FAILED
            job.current_step = "Failed ✗"
            job.error_message = result.error_summary or "Video generation pipeline failed."
            job.completed_at = utc_now()
            job.updated_at = utc_now()
            db.commit()
            logger.error(f"Job [{job_id}] failed: {job.error_message}")

    except Exception as e:
        logger.exception(f"Unexpected error while processing Job [{job_id}]: {e}")
        try:
            db.refresh(job)
            job.status = JobStatus.FAILED
            job.current_step = "Failed with exception"
            job.error_message = str(e)
            job.completed_at = utc_now()
            job.updated_at = utc_now()
            db.commit()
        except Exception as db_err:
            logger.error(f"Failed to record failure in DB for Job [{job_id}]: {db_err}")
    finally:
        db.close()


def worker_loop(worker_id: int):
    """Continuous worker loop polling tasks from Redis."""
    logger.info(f"Worker thread #{worker_id} started (listening to Redis queue).")
    while not stop_requested.is_set():
        try:
            task_data = task_queue.dequeue(timeout=2)
            if task_data:
                job_id = task_data.get("job_id")
                topic = task_data.get("topic")
                if job_id and topic:
                    process_single_job(job_id, topic)
        except Exception as e:
            logger.error(f"Worker #{worker_id} loop encountered error: {e}")
            time.sleep(1)


def start(max_workers: int = None):
    """Starts the Redis queue worker pool with configured concurrency (default: 5)."""
    concurrency = max_workers or settings.max_queue_workers
    concurrency = min(max(1, concurrency), 5)

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    console.print(f"[bold cyan]🚀 Starting STEM Video Queue Worker Pool[/bold cyan]")
    console.print(f"[dim]Redis Queue:[/dim] [underline]{settings.redis_url}[/underline]")
    console.print(f"[dim]Database:[/dim] [underline]{settings.database_url}[/underline]")
    console.print(f"[dim]Concurrent Workers:[/dim] [bold yellow]{concurrency}[/bold yellow]\n")

    # Initialize DB tables
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Could not connect to database on startup: {e}. Worker will retry on task execution.")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for w_id in range(1, concurrency + 1):
            executor.submit(worker_loop, w_id)

        try:
            while not stop_requested.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            stop_requested.set()

    logger.info("Worker pool has stopped.")


if __name__ == "__main__":
    start()
