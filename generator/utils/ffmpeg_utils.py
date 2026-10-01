"""FFmpeg utility functions for audio/video processing, duration probing, and concatenation."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from generator.utils.logger import console, print_error


def check_ffmpeg_installed() -> bool:
    """Checks if ffmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def get_media_duration(file_path: Path) -> float:
    """
    Measures duration of audio or video file in seconds using ffprobe.
    Falls back to mutagen if available.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Media file not found: {file_path}")

    # Try ffprobe first
    if shutil.which("ffprobe"):
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(file_path)
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(result.stdout)
            duration_str = data.get("format", {}).get("duration")
            if duration_str:
                return float(duration_str)
        except Exception:
            pass

    # Fallback to mutagen
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(file_path))
        if audio is not None and audio.info and hasattr(audio.info, "length"):
            return float(audio.info.length)
    except Exception:
        pass

    return 0.0


def sync_audio_and_video(
    video_path: Path,
    audio_path: Optional[Path],
    output_path: Path,
    target_duration: Optional[float] = None
) -> Path:
    """
    Merges a video track and an audio track into a single MP4 file.
    If video duration is shorter than audio, pads the video with the last frame (tpad).
    If audio duration is shorter, pads audio with silence (apad).
    Ensures standard H.264/AAC encoding and 16:9 or 9:16 compatibility.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path or not audio_path.exists():
        # No audio, just normalize video container
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path)
        ]
    else:
        # Get exact durations
        vid_dur = get_media_duration(video_path)
        aud_dur = get_media_duration(audio_path)
        final_dur = target_duration if target_duration else max(vid_dur, aud_dur)

        # Build FFmpeg command with proper video padding / looping last frame if video is shorter
        # or shortest=1 if video is longer
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration=5[v];[1:a]apad=pad_dur=2[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", f"{final_dur + 0.2:.3f}",
            "-movflags", "+faststart",
            str(output_path)
        ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        # Fallback simpler merge
        fallback_cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            *(["-i", str(audio_path)] if audio_path and audio_path.exists() else []),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path)
        ]
        fb_res = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if fb_res.returncode != 0:
            raise RuntimeError(f"FFmpeg sync error: {fb_res.stderr}")

    return output_path


def concatenate_videos(
    video_files: List[Path],
    output_path: Path,
    temp_dir: Path
) -> Path:
    """
    Concatenates multiple video files seamlessly using FFmpeg concat demuxer.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    if not video_files:
        raise ValueError("No video files provided for concatenation.")

    if len(video_files) == 1:
        shutil.copy(video_files[0], output_path)
        return output_path

    # Create concat list file
    concat_list_file = temp_dir / "concat_list.txt"
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for v in video_files:
            # Escape single quotes in filenames for ffmpeg concat
            safe_path = str(v.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_file),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path)
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg concatenation error: {res.stderr}")

    return output_path
