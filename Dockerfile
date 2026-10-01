# 1. Pull pre-compiled full-featured FFmpeg & FFprobe from the official FFmpeg image
FROM mwader/static-ffmpeg:latest AS ffmpeg_image

# 2. Main Python 3.11 runtime
FROM python:3.14-slim

# Copy FFmpeg and FFprobe binaries from the FFmpeg image
COPY --from=ffmpeg_image /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg_image /ffprobe /usr/local/bin/ffprobe

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry'

WORKDIR /app

# Install system dependencies needed for Manim (Cairo, Pango) and healthcheck (curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Copy poetry dependency definition files first for layer caching
COPY pyproject.toml poetry.lock* ./

# Install dependencies (without installing root package yet)
RUN poetry install --no-root --no-interaction --no-ansi

# Copy project source code
COPY . .

# Install root project package
RUN poetry install --no-interaction --no-ansi

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start the FastAPI server
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
