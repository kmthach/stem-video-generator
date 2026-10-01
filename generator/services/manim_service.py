"""Manim CE rendering service with intelligent self-healing error recovery loop."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Tuple, Callable
from generator.models import ScenePlan, VideoQuality, AspectRatio, RenderAttempt, SceneRenderResult
from generator.config import QUALITY_CONFIGS, settings
from generator.services.gemini_service import GeminiService
from generator.utils.ffmpeg_utils import get_media_duration
from generator.utils.logger import (
    console,
    print_warning,
    print_success,
    print_error,
)


class ManimService:
    """Orchestrates Manim CE rendering and executes the self-healing repair loop."""

    def __init__(
        self,
        gemini_service: Optional[GeminiService] = None,
        max_retries: Optional[int] = None
    ):
        self.gemini = gemini_service
        self.max_retries = max_retries or settings.max_healing_retries

    @staticmethod
    def _prepare_runnable_code(code: str) -> str:
        """Ensures common color aliases, easing functions, and standard imports exist at the top of the script."""
        shims = (
            "\n# Compatibility shims for colors and rate functions\n"
            "try:\n"
            "    PURE_WHITE = WHITE\n"
            "    PURE_RED = RED\n"
            "    PURE_GREEN = GREEN\n"
            "    PURE_BLUE = BLUE\n"
            "    CYAN = TEAL\n"
            "    MAGENTA = PURPLE\n"
            "    LIGHT_GREY = LIGHT_GRAY\n"
            "    GREY = GRAY\n"
            "    DARK_GREY = DARK_GRAY\n"
            "    # Easing rate function aliases\n"
            "    ease_out_quad = smooth\n"
            "    ease_in_quad = smooth\n"
            "    ease_in_out_quad = smooth\n"
            "    ease_out_cubic = smooth\n"
            "    ease_in_cubic = smooth\n"
            "    ease_in_out_cubic = smooth\n"
            "    ease_out_quart = smooth\n"
            "    ease_in_quart = smooth\n"
            "    ease_in_out_quart = smooth\n"
            "    ease_out_quint = smooth\n"
            "    ease_in_quint = smooth\n"
            "    ease_in_out_quint = smooth\n"
            "    ease_out_sine = smooth\n"
            "    ease_in_sine = smooth\n"
            "    ease_in_out_sine = smooth\n"
            "    ease_out_expo = smooth\n"
            "    ease_in_expo = smooth\n"
            "    ease_in_out_expo = smooth\n"
            "    ease_out_circ = smooth\n"
            "    ease_in_circ = smooth\n"
            "    ease_in_out_circ = smooth\n"
            "    ease_out_back = smooth\n"
            "    ease_in_back = smooth\n"
            "    ease_in_out_back = smooth\n"
            "    ease_out_elastic = smooth\n"
            "    ease_in_elastic = smooth\n"
            "    ease_in_out_elastic = smooth\n"
            "    ease_out_bounce = smooth\n"
            "    ease_in_bounce = smooth\n"
            "    ease_in_out_bounce = smooth\n"
            "    ease_out = smooth\n"
            "    ease_in = smooth\n"
            "    ease_in_out = smooth\n"
            "    easeInOut = smooth\n"
            "    easeOut = smooth\n"
            "    easeIn = smooth\n"
            "    easeInOutQuad = smooth\n"
            "    easeOutQuad = smooth\n"
            "    easeInQuad = smooth\n"
            "    easeInOutCubic = smooth\n"
            "    easeOutCubic = smooth\n"
            "    easeInCubic = smooth\n"
            "except Exception:\n"
            "    pass\n\n"
        )
        # Ensure 'from manim import *' is present at the very top, followed by shims
        clean_code = code.strip()
        if "from manim import *" in clean_code:
            # Place shims immediately after 'from manim import *'
            parts = clean_code.split("from manim import *", 1)
            return f"from manim import *{shims}{parts[1]}"
        else:
            return f"from manim import *{shims}{clean_code}"

    def render_scene_with_self_healing(
        self,
        scene: ScenePlan,
        duration_sec: float,
        output_dir: Path,
        quality: VideoQuality = VideoQuality.LOW,
        aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN,
        initial_code: Optional[str] = None,
        topic: str = "",
        status_callback: Optional[Callable[[str], None]] = None
    ) -> SceneRenderResult:
        """
        Generates and renders Manim code for a scene.
        If rendering fails, activates the self-healing loop to auto-fix code via Gemini.
        """
        scene_dir = output_dir / f"scene_{scene.scene_number:02d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        code_file = scene_dir / f"scene_{scene.scene_number:02d}.py"
        class_name = f"Scene{scene.scene_number}"

        # 1. Generate initial code if not provided
        current_code = initial_code
        if not current_code:
            if status_callback:
                status_callback("Writing code with Gemini...")
            if not self.gemini:
                raise ValueError("GeminiService is required to generate code.")
            current_code = self.gemini.generate_manim_code(
                scene=scene,
                duration_sec=duration_sec,
                aspect_ratio=aspect_ratio,
                topic=topic
            )

        attempts_history: List[RenderAttempt] = []

        # 2. Self-healing loop
        for attempt_idx in range(1, self.max_retries + 2):
            runnable_code = self._prepare_runnable_code(current_code)
            code_file.write_text(runnable_code, encoding="utf-8")
            
            if status_callback:
                status_callback(f"Rendering Manim (Attempt {attempt_idx}/{self.max_retries + 1})...")

            start_t = time.time()
            success, video_path, error_log = self._execute_manim_render(
                code_path=code_file,
                class_name=class_name,
                output_dir=scene_dir,
                quality=quality,
                aspect_ratio=aspect_ratio
            )
            render_elapsed = time.time() - start_t

            attempt = RenderAttempt(
                attempt_number=attempt_idx,
                code=current_code,
                success=success,
                error_message=error_log if not success else None,
                output_video_path=video_path if success else None,
                render_duration_sec=render_elapsed
            )
            attempts_history.append(attempt)

            if success and video_path and video_path.exists():
                actual_dur = get_media_duration(video_path)
                if status_callback:
                    status_callback(f"Rendered ({actual_dur:.1f}s)")
                return SceneRenderResult(
                    scene_number=scene.scene_number,
                    scene_title=scene.scene_title,
                    scene_class_name=class_name,
                    code_path=code_file,
                    raw_video_path=video_path,
                    target_duration_sec=duration_sec,
                    actual_duration_sec=actual_dur,
                    attempts=attempt_idx,
                    is_success=True
                )

            # If failed and more retries remain, invoke Gemini self-healing
            if attempt_idx <= self.max_retries:
                if status_callback:
                    status_callback(f"Repairing with Gemini (Attempt {attempt_idx})...")
                if not self.gemini:
                    raise RuntimeError(f"Manim render failed: {error_log}")

                try:
                    repaired_code = self.gemini.repair_manim_code(
                        scene=scene,
                        duration_sec=duration_sec,
                        failed_code=current_code,
                        error_message=error_log or "Unknown render error",
                        attempt=attempt_idx,
                        aspect_ratio=aspect_ratio
                    )
                    current_code = repaired_code
                except Exception as repair_err:
                    print_error(f"Self-healing agent failed during repair request: {repair_err}")
            else:
                if status_callback:
                    status_callback("Render failed after retries")
                print_error(f"Scene {scene.scene_number} failed after {self.max_retries + 1} attempts.")

        # If all attempts exhausted
        last_error = attempts_history[-1].error_message if attempts_history else "Unknown error"
        return SceneRenderResult(
            scene_number=scene.scene_number,
            scene_title=scene.scene_title,
            scene_class_name=class_name,
            code_path=code_file,
            raw_video_path=Path(""),
            target_duration_sec=duration_sec,
            actual_duration_sec=0.0,
            attempts=len(attempts_history),
            is_success=False,
            error_log=last_error
        )

    def _execute_manim_render(
        self,
        code_path: Path,
        class_name: str,
        output_dir: Path,
        quality: VideoQuality,
        aspect_ratio: AspectRatio
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        Executes Manim CLI command via subprocess.
        """
        quality_cfg = QUALITY_CONFIGS.get(quality, QUALITY_CONFIGS[VideoQuality.LOW])
        manim_flag = quality_cfg["manim_flag"]

        output_filename = f"{class_name}.mp4"
        media_dir = output_dir.resolve() / "manim_media"
        abs_code_path = code_path.resolve()

        cmd = [
            "manim",
            manim_flag,
            "--media_dir", str(media_dir),
            "-o", output_filename,
            str(abs_code_path),
            class_name
        ]

        # Handle vertical aspect ratio
        if aspect_ratio == AspectRatio.VERTICAL:
            # Swap width and height for vertical video (e.g. 720x1280 or 1080x1920)
            pw = quality_cfg["pixel_height"]
            ph = quality_cfg["pixel_width"]
            cmd.extend(["-r", f"{pw},{ph}"])

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(output_dir.resolve())
            )

            if result.returncode == 0:
                # Find output video in media dir
                expected_video = self._find_rendered_video(media_dir, output_filename)
                if expected_video and expected_video.exists():
                    # Move to clean location in output_dir
                    clean_video = output_dir.resolve() / f"scene_{class_name}_raw.mp4"
                    shutil.copy(expected_video, clean_video)
                    return True, clean_video, None
                else:
                    return False, None, f"Video file not found in {media_dir} despite returncode 0."
            else:
                combined_err = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                return False, None, combined_err
        except Exception as e:
            return False, None, str(e)

    def _find_rendered_video(self, media_dir: Path, target_filename: str) -> Optional[Path]:
        """Recursively locates the produced MP4 file in Manim's media directory."""
        if not media_dir.exists():
            return None
        for p in media_dir.rglob("*.mp4"):
            if "partial_movie_files" not in str(p):
                return p
        return None
