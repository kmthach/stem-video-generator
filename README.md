# STEM Video Generator

An AI-powered application that transforms learner STEM topic queries into pedagogical animated videos using **Google Gemini**, **Edge-TTS**, **Manim CE**, and **FFmpeg**.

---

## 🎬 Best Generated Videos

| #   | Learner Query                                                  | Output Video                                                                                                                                                 | Concepts Covered                                                                     |
| --- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| 1   | _"What is the difference between ionic and covalent bonding?"_ | [`best_3_videos/what_is_the_difference_between_ionic_and_covalent_bonding.mp4`](best_3_videos/what_is_the_difference_between_ionic_and_covalent_bonding.mp4) | Electron transfer vs. sharing, lattice formation, molecular bonds, electronegativity |
| 2   | _"Why do atoms form covalent bonds?"_                          | [`best_3_videos/why_do_atoms_form_covalent_bonds__final.mp4`](best_3_videos/why_do_atoms_form_covalent_bonds__final.mp4)                                     | Octet rule, valence electron overlap, potential energy curves, bond stability        |
| 3   | _"How does the pH scale work?"_                                | [`best_3_videos/how_does_ph_scale_work.mp4`](best_3_videos/how_does_ph_scale_work.mp4)                                                                       | Logarithmic scale, $[H^+]$ vs. $[OH^-]$ concentrations, acids, neutrals, and bases   |

---

## 🏗️ Architecture & System Boundaries

```
[ Learner Query ]
       │
       ▼
┌──────────────────┐       Enqueues       ┌──────────────────┐
│   FastAPI API    │ ───────────────────► │  Redis 7 Queue   │
│  (Port: 8000)    │                      └────────┬─────────┘
└────────┬─────────┘                               │ Dequeues (Max 5 Workers)
         │ Writes PENDING                          ▼
         ▼                                ┌──────────────────┐
┌──────────────────┐  Updates State       │ Background Queue │
│   MySQL 8.0 DB   │ ◄─────────────────── │   Worker Pool    │
│  (Metadata/State)│                      └────────┬─────────┘
└──────────────────┘                               │
                                                   ▼
                     ┌──────────────────────────────────────────────────────────┐
                     │                    Pipeline Execution                    │
                     │                                                          │
                     │  1. AI Boundary (Gemini 3.5 Flash)                   │
                     │     • Modular Storyboard Generation                      │
                     │     • Manim Python Code Generation per Scene             │
                     │     • Self-Healing Code Repair on Render Errors          │
                     │                                                          │
                     │  2. Video-Gen Boundary (Edge-TTS, Manim, FFmpeg)         │
                     │     • Neural Voice Narration & Exact Millisecond Timing  │
                     │     • Mathematical Scene Animation Rendering             │
                     │     • Audio-Video Time Stretching / Padding Sync         │
                     │     • Final Multi-Scene Concatenation (MP4)              │
                     └─────────────────────────────┬────────────────────────────┘
                                                   │
                                                   ▼
                                      ┌────────────────────────┐
                                      │  Artifacts / Volume    │
                                      │  (./output/<job-id>/)  │
                                      └────────────────────────┘
```

### 1. Job Lifecycle

1. **Submission**: Client posts a topic prompt to `POST /api/videos/generate` (or runs via CLI).
2. **Persistence**: FastAPI inserts a `VideoJob` record into MySQL with status `PENDING` and pushes `{job_id, topic}` to the Redis task queue.
3. **Worker Processing**: Background worker thread dequeues the job, updates MySQL status to `PROCESSING`, and starts the `VideoGeneratorPipeline`.
4. **Execution**: The pipeline synthesizes voiceover audio, animates scenes with Manim, runs self-healing on any compilation errors, and stitches the final MP4 with FFmpeg.
5. **Completion**: Worker marks status as `COMPLETED` (or `FAILED`), persists token consumption metrics, and formats the cross-platform absolute `video_path`.

### 2. Persistence / Artifact Boundary

- **Relational Metadata (MySQL)**: Stores persistent job records (UUID, query topic, status, duration, error logs, timestamps, and LLM token usage).
- **Filesystem Artifacts (`./output/<job-id>/`)**: Stores media assets (voice narration `.mp3`, raw/synced scene clips `.mp4`, generated Manim scripts `.py`, `storyboard.json`, `pipeline_result.json`, and the final concatenated video).

### 3. AI / Video-Generation Boundary

- **AI Layer (Google Gemini)**: Acts as the pedagogical planner and animator. It creates structured scene breakdowns and writes Manim Python scripts tailored to audio duration budgets. When compilation or runtime errors occur, the self-healing loop sends tracebacks back to Gemini to automatically fix the code.
- **Video-Generation Layer (Edge-TTS, Manim CE, FFmpeg)**: Acts as the deterministic rendering engine. Edge-TTS synthesizes neural narration and calculates exact durations; Manim compiles 2D mathematical vector animations; FFmpeg synchronizes audio/video streams and stitches scenes into a single MP4 video.

---

## 🚀 Quick Start (Zero Config & Zero Dependencies)

> **Note on API Key**: A valid Gemini API key is pre-configured in `docker-compose.yml` purely for testing convenience so you can evaluate the full generation pipeline without hitting free-tier rate limits. I am fully aware of the API key exposure here—please don't worry about it, as this is a temporary disposable key that will be revoked immediately after evaluation.

### Just run:

```bash
docker compose up
```

That's it! This immediately spins up the entire production-ready stack:

- **FastAPI API Server**: `http://localhost:8000` ([Interactive Docs](http://localhost:8000/docs))
- **Background Task Worker**: 5 concurrent worker threads processing video generation jobs
- **MySQL 8.0 Database**: Port `3306` (stores persistent job tracking and token metrics)
- **Redis 7 Task Queue**: Port `6379` (in-memory job queue)

_(All local project files are live-mounted, so code changes take effect immediately)._

---

## 🏃 Optional: Local Host Execution (Without Docker)

If you wish to develop or run directly on your host machine without Docker:

### Prerequisites

- **Python 3.10+**, **Poetry**
- **FFmpeg** (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Linux)
- **Cairo & Pango** (`brew install cairo pango` on macOS, `apt install libcairo2-dev libpango1.0-dev` on Linux)
- Optional: Copy `.env.example` to `.env` if overriding default keys/database settings

```bash
# Install dependencies locally
poetry install

# Run via CLI script
poetry run stem-video --topic "How Neural Networks Learn Backpropagation" --quality medium

# Or start the local API server and queue worker
poetry run stem-video-api     # Terminal 1: FastAPI on http://localhost:8000
poetry run stem-video-worker  # Terminal 2: Background queue worker pool
```

---

## 🌐 API Reference

Interactive API documentation and Swagger UI are available at `http://localhost:8000/docs`.

### 1. Submit Video Generation Job

**`POST /api/videos/generate`**

```bash
curl -X POST http://localhost:8000/api/videos/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "What is the difference between ionic and covalent bonding?"}'
```

**Response (202 Accepted)**:

```json
{
  "id": "c60bba27-6881-4a83-8daa-446bc1394cca",
  "topic": "What is the difference between ionic and covalent bonding?",
  "status": "PENDING",
  "video_path": null,
  "total_duration_sec": 0.0,
  "error_message": null,
  "created_at": "2026-09-21T03:46:13",
  "completed_at": null
}
```

### 2. Track Job Status & Retrieve Absolute Video Path

**`GET /api/videos/{id}`**

```bash
curl http://localhost:8000/api/videos/c60bba27-6881-4a83-8daa-446bc1394cca
```

**Response (200 OK)**:

```json
{
  "id": "c60bba27-6881-4a83-8daa-446bc1394cca",
  "topic": "What is the difference between ionic and covalent bonding?",
  "status": "COMPLETED",
  "video_path": "/Users/heymac/x/stem-video-generator/output/c60bba27-6881-4a83-8daa-446bc1394cca/c60bba27-6881-4a83-8daa-446bc1394cca.mp4",
  "total_duration_sec": 148.267,
  "error_message": null,
  "created_at": "2026-09-21T03:46:13",
  "completed_at": "2026-09-21T03:47:26"
}
```

_(The returned `video_path` is formatted as a valid host absolute path across Windows, macOS, and Linux)._

### 3. List All Jobs

**`GET /api/videos`**

```bash
curl http://localhost:8000/api/videos
```
