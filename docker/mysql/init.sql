-- MySQL Schema Initialization for STEM Video Generator

CREATE DATABASE IF NOT EXISTS stem_videos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE stem_videos;

CREATE TABLE IF NOT EXISTS video_jobs (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    topic VARCHAR(500) NOT NULL,
    status ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'PENDING',
    progress_percent INT NOT NULL DEFAULT 0,
    current_step VARCHAR(255) NOT NULL DEFAULT 'Queued',
    video_path VARCHAR(1000) NULL,
    total_duration_sec FLOAT NOT NULL DEFAULT 0.0,
    total_tokens INT NOT NULL DEFAULT 0,
    prompt_tokens INT NOT NULL DEFAULT 0,
    candidates_tokens INT NOT NULL DEFAULT 0,
    api_calls INT NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    INDEX idx_video_jobs_status (status),
    INDEX idx_video_jobs_created_at (created_at),
    INDEX idx_video_jobs_topic (topic)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
