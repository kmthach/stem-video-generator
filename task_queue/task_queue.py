"""Redis task queue client for enqueuing and managing asynchronous video generation jobs."""

import json
import logging
from typing import Optional, Dict, Any
import redis
from generator.config import settings

logger = logging.getLogger(__name__)

QUEUE_NAME = "stem_video_tasks"


class TaskQueue:
    """Redis-based task queue client."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self.client = redis.from_url(self.redis_url, decode_responses=True)

    def enqueue(self, job_id: str, topic: str) -> bool:
        """Pushes a video generation task onto the Redis queue."""
        payload = json.dumps({"job_id": job_id, "topic": topic})
        try:
            self.client.lpush(QUEUE_NAME, payload)
            logger.info(f"Enqueued job {job_id} for topic '{topic}' onto {QUEUE_NAME}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id} to Redis: {e}")
            raise

    def dequeue(self, timeout: int = 2) -> Optional[Dict[str, Any]]:
        """Blocks for up to timeout seconds waiting to dequeue a task."""
        try:
            item = self.client.brpop(QUEUE_NAME, timeout=timeout)
            if item:
                _, payload_str = item
                return json.loads(payload_str)
            return None
        except redis.ConnectionError as ce:
            logger.warning(f"Redis connection error during dequeue: {ce}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during dequeue: {e}")
            return None

    def get_queue_length(self) -> int:
        """Returns the number of pending tasks in the queue."""
        try:
            return self.client.llen(QUEUE_NAME)
        except Exception:
            return 0

    def ping(self) -> bool:
        """Checks if Redis server is reachable."""
        try:
            return bool(self.client.ping())
        except Exception:
            return False


# Global task queue instance
task_queue = TaskQueue()
