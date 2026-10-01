"""Video processing service for audio-video synchronization and multi-scene assembly."""

from pathlib import Path
from typing import List, Optional
from generator.models import SceneRenderResult
from generator.utils.ffmpeg_utils import sync_audio_and_video, concatenate_videos, get_media_duration
from generator.utils.logger import console, print_success, print_error


class VideoService:
    """Manages scene synchronization and final educational video concatenation."""

    def sync_scene(
        self,
        scene_result: SceneRenderResult,
        audio_path: Optional[Path],
        output_dir: Path
    ) -> SceneRenderResult:
        """
        Synchronizes a rendered Manim video clip with its neural narration audio.
        """
        if not scene_result.is_success or not scene_result.raw_video_path.exists():
            return scene_result

        synced_path = output_dir / f"scene_{scene_result.scene_number:02d}_synced.mp4"

        try:
            synced_video = sync_audio_and_video(
                video_path=scene_result.raw_video_path,
                audio_path=audio_path,
                output_path=synced_path,
                target_duration=scene_result.target_duration_sec
            )
            scene_result.synced_video_path = synced_video
            scene_result.audio_path = audio_path
            scene_result.actual_duration_sec = get_media_duration(synced_video)
            return scene_result
        except Exception as e:
            print_error(f"Failed to sync audio and video for Scene {scene_result.scene_number}: {e}")
            scene_result.synced_video_path = scene_result.raw_video_path
            return scene_result

    def assemble_final_video(
        self,
        scene_results: List[SceneRenderResult],
        output_path: Path,
        temp_dir: Path
    ) -> Path:
        """
        Concatenates all synchronized scene clips into the final video file.
        """
        valid_clips: List[Path] = []
        for s in scene_results:
            if s.synced_video_path and s.synced_video_path.exists():
                valid_clips.append(s.synced_video_path)
            elif s.raw_video_path and s.raw_video_path.exists():
                valid_clips.append(s.raw_video_path)

        if not valid_clips:
            raise ValueError("No rendered scene video clips available to assemble.")

        final_video = concatenate_videos(
            video_files=valid_clips,
            output_path=output_path,
            temp_dir=temp_dir
        )
        return final_video
