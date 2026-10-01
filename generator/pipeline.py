"""Master pipeline orchestrating the end-to-end STEM video generation workflow."""

import json
import re
from pathlib import Path
from typing import Optional, List
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
)

from generator.models import (
    Storyboard,
    ScenePlan,
    VideoQuality,
    AspectRatio,
    SceneRenderResult,
    PipelineResult,
)
from generator.config import settings
from generator.services.gemini_service import GeminiService
from generator.services.tts_service import TTSService
from generator.services.manim_service import ManimService
from generator.services.video_service import VideoService
from generator.utils.ffmpeg_utils import check_ffmpeg_installed, get_media_duration
from generator.utils.logger import (
    console,
    print_banner,
    print_step,
    print_storyboard,
    print_success,
    print_error,
    print_warning,
)


from concurrent.futures import ThreadPoolExecutor, as_completed

class VideoGeneratorPipeline:
    """End-to-end pipeline runner for generating STEM animated videos."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        quality: VideoQuality = VideoQuality.LOW,
        aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN,
        max_retries: int = 3,
        max_workers: int = 10,
        output_dir: Optional[Path] = None,
        skip_audio: bool = False
    ):
        self.quality = quality
        self.aspect_ratio = aspect_ratio
        self.skip_audio = skip_audio
        self.max_workers = min(max(1, max_workers), 10)
        self.output_base = output_dir or settings.default_output_dir

        # Initialize services
        self.gemini = GeminiService(api_key=api_key, model_name=model)
        self.tts = TTSService(voice=voice)
        self.manim = ManimService(gemini_service=self.gemini, max_retries=max_retries)
        self.video = VideoService()


    def _generate_audio_for_scene(self, scene: ScenePlan, audio_dir: Path):
        """Worker helper for synthesizing scene audio in parallel."""
        if self.skip_audio:
            return scene.scene_number, None

        audio_res = self.tts.generate_scene_audio(
            scene_number=scene.scene_number,
            narration=scene.narration,
            output_dir=audio_dir
        )
        return scene.scene_number, audio_res

    def _process_single_scene(
        self,
        scene: ScenePlan,
        audio_info,
        scenes_dir: Path,
        topic: str,
        progress_callback: Optional[callable] = None
    ) -> SceneRenderResult:
        """
        Worker helper for generating code, rendering with self-healing, and syncing AV for a single scene.
        """
        target_dur = audio_info.duration_sec if audio_info else scene.estimated_duration_sec

        def status_updater(msg: str):
            if progress_callback:
                progress_callback(msg)

        # 1. Render scene with self-healing loop
        render_res = self.manim.render_scene_with_self_healing(
            scene=scene,
            duration_sec=target_dur,
            output_dir=scenes_dir,
            quality=self.quality,
            aspect_ratio=self.aspect_ratio,
            topic=topic,
            status_callback=status_updater
        )

        # 2. Sync audio with scene video immediately
        if render_res.is_success:
            status_updater("Syncing audio/video...")
            audio_file = audio_info.audio_path if audio_info else None
            render_res = self.video.sync_scene(
                scene_result=render_res,
                audio_path=audio_file,
                output_dir=scenes_dir
            )
            status_updater("Completed ✓")
        else:
            status_updater("Failed ✗")

        return render_res

    def run(
        self,
        topic: str,
        target_audience: str = "High School & Undergraduate STEM Students",
        job_id: Optional[str] = None
    ) -> PipelineResult:
        """
        Executes the full video generation pipeline for a given topic.
        """
        if not check_ffmpeg_installed():
            raise RuntimeError(
                "FFmpeg is not installed or not found in system PATH. "
                "Please install FFmpeg (e.g. 'brew install ffmpeg') before running."
            )

        # Determine folder name and output directory by job_id if provided, else topic slug
        if job_id:
            folder_name = str(job_id).strip()
            final_video_name = f"{folder_name}.mp4"
        else:
            folder_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", topic.strip().lower())[:40]
            final_video_name = f"{folder_name}_final.mp4"

        project_dir = (self.output_base / folder_name).resolve()
        project_dir.mkdir(parents=True, exist_ok=True)

        audio_dir = project_dir / "audio"
        scenes_dir = project_dir / "scenes"
        temp_dir = project_dir / "temp"

        print_banner()
        console.print(f"[bold cyan]🎯 Topic:[/bold cyan] [bold white]{topic}[/bold white]")
        console.print(f"[dim]📁 Project Output:[/dim] [underline]{project_dir}[/underline]")
        console.print(f"[dim]⚡ Max Workers:[/dim] [bold yellow]{self.max_workers}[/bold yellow]\n")

        # =========================================================================
        # STEP 1: Storyboard Generation
        # =========================================================================
        print_step(1, 4, "Pedagogical Storyboarding", "Generating structured modular storyboard with Gemini...")

        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold cyan]{task.description}"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Decomposing topic into bite-sized visual scenes...", total=None)
            storyboard = self.gemini.generate_storyboard(
                topic=topic,
                target_audience=target_audience,
                aspect_ratio=self.aspect_ratio
            )
            progress.update(task, completed=True)

        # Save storyboard JSON
        storyboard_file = project_dir / "storyboard.json"
        storyboard_file.write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")
        print_storyboard(storyboard)
        print_success(f"Storyboard ({len(storyboard.scenes)} scenes) saved to {storyboard_file}\n")

        # =========================================================================
        # STEP 2: Parallel Neural Audio Synthesis (Edge-TTS)
        # =========================================================================
        print_step(2, 4, "Neural Audio Synthesis (Edge-TTS)", "Generating voiceovers in parallel and measuring exact timing budgets...")

        scene_audios = {}
        effective_workers = max(1, min(self.max_workers, len(storyboard.scenes)))

        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console
        ) as audio_progress:
            audio_task = audio_progress.add_task("Synthesizing voiceovers...", total=len(storyboard.scenes))
            with ThreadPoolExecutor(max_workers=effective_workers) as audio_pool:
                futures = [audio_pool.submit(self._generate_audio_for_scene, scene, audio_dir) for scene in storyboard.scenes]
                for fut in as_completed(futures):
                    scene_num, audio_res = fut.result()
                    scene_audios[scene_num] = audio_res
                    audio_progress.advance(audio_task, 1)

        console.print("")

        # =========================================================================
        # STEP 3: Parallel Manim Generation, Self-Healing Render & AV Sync
        # =========================================================================
        print_step(
            3, 4,
            f"Parallel Scene Rendering ({effective_workers} workers)",
            "Generating Manim animations, executing self-healing render loop, and syncing AV per scene..."
        )

        rendered_scenes: List[SceneRenderResult] = []
        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold cyan]Scene {task.fields[scene_num]}[/bold cyan] [dim]({task.fields[title]})[/dim]:"),
            BarColumn(bar_width=20),
            TextColumn("[bold yellow]{task.fields[status]}[/bold yellow]"),
            TimeElapsedColumn(),
            console=console
        ) as scene_progress:
            # Initialize tasks for all scenes
            task_ids = {}
            for scene in storyboard.scenes:
                tid = scene_progress.add_task(
                    "",
                    total=100,
                    scene_num=scene.scene_number,
                    title=scene.scene_title[:22],
                    status="Queued"
                )
                task_ids[scene.scene_number] = tid

            def make_scene_callback(s_num: int):
                tid = task_ids[s_num]
                def _cb(status_text: str):
                    pct = 20 if "Writing" in status_text else (50 if "Rendering" in status_text else (85 if "Syncing" in status_text else (100 if "Completed" in status_text else 30)))
                    scene_progress.update(tid, completed=pct, status=status_text)
                return _cb

            with ThreadPoolExecutor(max_workers=effective_workers) as scene_pool:
                scene_futures = [
                    scene_pool.submit(
                        self._process_single_scene,
                        scene=scene,
                        audio_info=scene_audios.get(scene.scene_number),
                        scenes_dir=scenes_dir,
                        topic=topic,
                        progress_callback=make_scene_callback(scene.scene_number)
                    )
                    for scene in storyboard.scenes
                ]
                for fut in as_completed(scene_futures):
                    res = fut.result()
                    rendered_scenes.append(res)

        # Sort rendered scenes by scene_number to preserve sequence
        rendered_scenes.sort(key=lambda s: s.scene_number)

        # Check if any scene failed completely
        failed_scenes = [s for s in rendered_scenes if not s.is_success]
        if failed_scenes:
            print_error(f"{len(failed_scenes)} scene(s) failed rendering after exhausting all self-healing retries:")
            for fs in failed_scenes:
                console.print(f"[bold red]  • Scene {fs.scene_number} ({fs.scene_title}):[/bold red] {fs.error_log}")

        # =========================================================================
        # STEP 4: Final Video Assembly & Concatenation
        # =========================================================================
        print_step(4, 4, "Final Video Assembly", "Concatenating synchronized scenes with FFmpeg...")

        final_video_path = (project_dir / final_video_name).resolve()
        try:
            with Progress(
                SpinnerColumn(spinner_name="dots"),
                TextColumn("[bold cyan]Assembling final MP4 video with FFmpeg..."),
                TimeElapsedColumn(),
                console=console
            ) as assemble_progress:
                assemble_task = assemble_progress.add_task("Assembling", total=None)
                assembled_path = self.video.assemble_final_video(
                    scene_results=rendered_scenes,
                    output_path=final_video_path,
                    temp_dir=temp_dir
                )
                assemble_progress.update(assemble_task, completed=True)
            if assembled_path:
                assembled_path = assembled_path.resolve()
            total_dur = get_media_duration(assembled_path)
            is_success = True
            err_msg = None
        except Exception as e:
            print_error(f"Failed to assemble final video: {e}")
            assembled_path = None
            total_dur = 0.0
            is_success = False
            err_msg = str(e)

        token_usage = self.gemini.get_token_usage()

        # Summary metadata
        result = PipelineResult(
            topic=topic,
            storyboard=storyboard,
            scenes_rendered=rendered_scenes,
            final_video_path=assembled_path.resolve() if assembled_path else None,
            total_duration_sec=total_dur,
            output_dir=project_dir.resolve(),
            is_success=is_success,
            error_summary=err_msg,
            token_usage=token_usage
        )

        metadata_file = project_dir / "pipeline_result.json"
        metadata_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        if is_success and assembled_path:
            console.print("\n" + "=" * 60)
            console.print(f"[bold green]🎉 Video Generation Complete![/bold green]")
            console.print(f"[bold white]📹 Output Video:[/bold white] [bold cyan]{assembled_path.resolve()}[/bold cyan]")
            console.print(f"[bold white]⏱️  Total Runtime:[/bold white] [bold yellow]{total_dur:.1f}s[/bold yellow]")
            if token_usage and token_usage.total_tokens > 0:
                console.print(f"[bold white]🪙 Tokens Consumed:[/bold white] [bold yellow]{token_usage.total_tokens:,}[/bold yellow] tokens [dim]({token_usage.api_calls} API calls • {token_usage.prompt_tokens:,} in / {token_usage.candidates_tokens:,} out)[/dim]")
            console.print("=" * 60 + "\n")

        return result
