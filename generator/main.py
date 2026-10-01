"""Main entry point and CLI for the STEM Video Generator."""

import sys
import asyncio
from pathlib import Path
from typing import Optional
import typer
from rich.table import Table

# Add project root to path if running script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.models import VideoQuality, AspectRatio
from generator.config import settings, POPULAR_VOICES
from generator.pipeline import VideoGeneratorPipeline
from generator.services.gemini_service import GeminiService
from generator.services.tts_service import TTSService
from generator.utils.logger import console, print_banner, print_error, print_storyboard, print_success

app = typer.Typer(
    name="stem-video",
    help="AI-powered STEM Video Generator using Gemini, Edge-TTS, Manim CE, and FFmpeg.",
    add_completion=False,
    invoke_without_command=True
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    topic: Optional[str] = typer.Option(
        None,
        "--topic", "-t",
        help="The STEM topic to explain and animate."
    ),
    quality: VideoQuality = typer.Option(
        VideoQuality.LOW,
        "--quality", "-q",
        help="Video render quality."
    ),
    voice: Optional[str] = typer.Option(
        None,
        "--voice", "-v",
        help="Edge-TTS neural voice name."
    ),
    aspect_ratio: AspectRatio = typer.Option(
        AspectRatio.WIDESCREEN,
        "--aspect-ratio", "-a",
        help="Aspect ratio (16:9 landscape or 9:16 vertical shorts)."
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir", "-o",
        help="Directory to save generated outputs."
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="Google Gemini model name (e.g. gemini-2.5-flash)."
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries", "-r",
        help="Max auto-repair iterations for Manim render failures.",
        min=0, max=10
    ),
    max_workers: int = typer.Option(
        10,
        "--max-workers", "-w",
        help="Maximum parallel workers for scene generation and rendering (1-10).",
        min=1, max=10
    ),
    skip_audio: bool = typer.Option(
        False,
        "--skip-audio",
        help="Skip TTS audio narration generation."
    ),
    job_id: Optional[str] = typer.Option(
        None,
        "--job-id",
        help="Optional job identifier to name the output folder and video file."
    ),
):
    """
    Generate an educational STEM video for any topic prompt.
    """
    # If a subcommand (like 'storyboard' or 'list-voices') was invoked, let it handle the execution
    if ctx.invoked_subcommand is not None:
        return

    # Check if topic is provided either as option or positional fallback
    if not topic:
        # Check if there are positional arguments in sys.argv
        args = [a for a in sys.argv[1:] if not a.startswith("-")]
        if args and not args[0] in ["storyboard", "list-voices"]:
            topic = args[0]

    if not topic:
        console.print("[bold red]Error:[/bold red] Missing required parameter '--topic' / topic argument.")
        console.print("\n[dim]Usage examples:[/dim]")
        console.print("  python generator/main.py --topic \"Pythagorean Theorem\"")
        console.print("  python generator/main.py \"Fourier Transform\" --quality high --max-workers 10")
        console.print("  python generator/main.py list-voices\n")
        raise typer.Exit(code=1)

    try:
        pipeline = VideoGeneratorPipeline(
            model=model,
            voice=voice,
            quality=quality,
            aspect_ratio=aspect_ratio,
            max_retries=max_retries,
            max_workers=max_workers,
            output_dir=output_dir,
            skip_audio=skip_audio
        )

        result = pipeline.run(
            topic=topic,
            job_id=job_id
        )

        if not result.is_success:
            raise typer.Exit(code=1)

    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)


@app.command("storyboard")
def generate_storyboard_only(
    topic: str = typer.Option(
        ...,
        "--topic", "-t",
        prompt="Enter STEM topic",
        help="The STEM topic to create a storyboard for."
    ),
    aspect_ratio: AspectRatio = typer.Option(
        AspectRatio.WIDESCREEN,
        "--aspect-ratio", "-a",
        help="Aspect ratio (16:9 or 9:16)."
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="File path to save the storyboard JSON."
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="Google Gemini model name."
    )
):
    """
    Generate and view only the pedagogical storyboard for a topic.
    """
    print_banner()
    try:
        gemini = GeminiService(model_name=model)
        with console.status(f"[cyan]Generating storyboard for '{topic}'...[/cyan]"):
            sb = gemini.generate_storyboard(
                topic=topic,
                aspect_ratio=aspect_ratio
            )

        print_storyboard(sb)

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(sb.model_dump_json(indent=2), encoding="utf-8")
            print_success(f"Storyboard saved to {output}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(code=1)


@app.command("list-voices")
def list_voices(
    filter_locale: Optional[str] = typer.Option(
        "en-US",
        "--locale", "-l",
        help="Filter voices by locale (e.g. 'en-US', 'en-GB', 'all')."
    )
):
    """
    List available neural text-to-speech voices from Edge-TTS.
    """
    print_banner()
    console.print(f"[cyan]🔍 Searching neural voices (filter: {filter_locale})...[/cyan]\n")

    try:
        locale_param = None if filter_locale == "all" else filter_locale
        voices = asyncio.run(TTSService.list_available_voices(filter_locale=locale_param))

        table = Table(title="🎙️ Available Edge-TTS Neural Voices", border_style="cyan")
        table.add_column("Voice Name (ShortName)", style="bold green")
        table.add_column("Locale", style="dim white")
        table.add_column("Gender", style="yellow")
        table.add_column("Friendly Name", style="dim white")

        for v in voices:
            table.add_row(v["ShortName"], v["Locale"], v["Gender"], v["FriendlyName"])

        console.print(table)
    except Exception as e:
        print_error(f"Failed to retrieve voices: {e}")
        raise typer.Exit(code=1)


def cli():
    """Entrypoint function for poetry script."""
    app()


if __name__ == "__main__":
    app()
