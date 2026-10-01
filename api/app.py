"""FastAPI application initialization and server runner."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from generator.config import settings
from db.database import init_db
from api.routes import router as videos_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown events."""
    logger.info("FastAPI service starting up...")
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Could not initialize database tables at startup: {e}")
    yield
    logger.info("FastAPI service shutting down...")


app = FastAPI(
    title="STEM Video Generator API",
    description="Asynchronous API for transforming STEM topics into pedagogical animations using Gemini, Edge-TTS, Manim CE, and FFmpeg.",
    version="0.2.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount video endpoints
app.include_router(videos_router)


@app.get("/health", tags=["Health"])
def health_check():
    """Healthcheck endpoint for monitoring."""
    from task_queue.task_queue import task_queue
    redis_ok = task_queue.ping()
    return {
        "status": "healthy",
        "redis_connected": redis_ok,
        "max_queue_workers": settings.max_queue_workers
    }


def start():
    """Entrypoint for running the FastAPI web server."""
    uvicorn.run(
        "api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False
    )


if __name__ == "__main__":
    start()
