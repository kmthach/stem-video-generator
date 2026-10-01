"""Configuration settings and constants for the STEM Video Generator."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from generator.models import VideoQuality, AspectRatio

# Automatically load .env file if available
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""
    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", ""),
        description="Google Gemini API key"
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        description="Default Gemini model to use"
    )
    default_voice: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_VOICE", "en-US-ChristopherNeural"),
        description="Default Edge-TTS neural voice"
    )
    default_quality: VideoQuality = Field(
        default=VideoQuality.LOW,
        description="Default video quality"
    )
    default_aspect_ratio: AspectRatio = Field(
        default=AspectRatio.WIDESCREEN,
        description="Default aspect ratio"
    )
    default_output_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "./output")),
        description="Default output directory"
    )
    host_output_dir: Optional[str] = Field(
        default_factory=lambda: os.getenv("HOST_OUTPUT_DIR", None),
        description="Host machine output directory mapping for container environments"
    )
    max_healing_retries: int = Field(
        default_factory=lambda: int(os.getenv("MAX_HEALING_RETRIES", "3")),
        description="Max code auto-repair iterations per scene"
    )
    max_workers: int = Field(
        default_factory=lambda: int(os.getenv("MAX_WORKERS", "10")),
        description="Max parallel workers for scene generation and rendering"
    )
    # MySQL Database Settings
    mysql_host: str = Field(
        default_factory=lambda: os.getenv("MYSQL_HOST", "localhost"),
        description="MySQL database host"
    )
    mysql_port: int = Field(
        default_factory=lambda: int(os.getenv("MYSQL_PORT", "3306")),
        description="MySQL database port"
    )
    mysql_user: str = Field(
        default_factory=lambda: os.getenv("MYSQL_USER", "stem_user"),
        description="MySQL database username"
    )
    mysql_password: str = Field(
        default_factory=lambda: os.getenv("MYSQL_PASSWORD", "stem_password"),
        description="MySQL database password"
    )
    mysql_db: str = Field(
        default_factory=lambda: os.getenv("MYSQL_DATABASE", "stem_videos"),
        description="MySQL database name"
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"mysql+pymysql://{os.getenv('MYSQL_USER', 'stem_user')}:{os.getenv('MYSQL_PASSWORD', 'stem_password')}@{os.getenv('MYSQL_HOST', 'localhost')}:{os.getenv('MYSQL_PORT', '3306')}/{os.getenv('MYSQL_DATABASE', 'stem_videos')}?charset=utf8mb4"
        ),
        description="SQLAlchemy database connection URL"
    )
    # Redis Task Queue Settings
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="Redis connection URL for task queue"
    )
    max_queue_workers: int = Field(
        default_factory=lambda: int(os.getenv("MAX_QUEUE_WORKERS", "5")),
        description="Maximum concurrent video generation workers in task queue (default: 5)"
    )
    # API Server Settings
    api_host: str = Field(
        default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"),
        description="FastAPI host address"
    )
    api_port: int = Field(
        default_factory=lambda: int(os.getenv("API_PORT", "8000")),
        description="FastAPI port"
    )

    model_config = {"extra": "ignore"}


settings = Settings()

# Quality mapping to Manim flags and resolutions
QUALITY_CONFIGS: Dict[VideoQuality, Dict[str, Any]] = {
    VideoQuality.LOW: {
        "manim_flag": "-ql",
        "pixel_width": 854,
        "pixel_height": 480,
        "fps": 30,
        "name": "480p",
    },
    VideoQuality.MEDIUM: {
        "manim_flag": "-qm",
        "pixel_width": 1280,
        "pixel_height": 720,
        "fps": 30,
        "name": "720p",
    },
    VideoQuality.HIGH: {
        "manim_flag": "-qh",
        "pixel_width": 1920,
        "pixel_height": 1080,
        "fps": 60,
        "name": "1080p",
    },
    VideoQuality.FOUR_K: {
        "manim_flag": "-qk",
        "pixel_width": 3840,
        "pixel_height": 2160,
        "fps": 60,
        "name": "4k (2160p)",
    },
}

# Popular Edge-TTS voices
POPULAR_VOICES = [
    {"name": "en-US-ChristopherNeural", "gender": "Male", "description": "Engaging, authoritative American male voice (ideal for STEM)"},
    {"name": "en-US-JennyNeural", "gender": "Female", "description": "Natural, clear American female voice"},
    {"name": "en-US-GuyNeural", "gender": "Male", "description": "Casual, friendly American male voice"},
    {"name": "en-US-AriaNeural", "gender": "Female", "description": "Dynamic, expressive American female voice"},
    {"name": "en-GB-SoniaNeural", "gender": "Female", "description": "Polished British English female voice"},
    {"name": "en-GB-RyanNeural", "gender": "Male", "description": "Deep British English male voice"},
    {"name": "en-AU-WilliamNeural", "gender": "Male", "description": "Clear Australian English male voice"},
]
