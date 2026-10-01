import logging
from typing import Optional
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

# Silence verbose third-party info logs that disrupt rich live progress bars
for noisy_logger in ["google", "google.genai", "urllib3", "httpcore", "httpx", "manim"]:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "bold magenta",
    "accent": "bold deep_sky_blue1",
    "muted": "dim white",
})

console = Console(theme=custom_theme)


def print_banner():
    """Prints a styled banner for the STEM Video Generator."""
    title_text = "[bold deep_sky_blue1]🎬 STEM Video Generator[/bold deep_sky_blue1]\n" \
                 "[dim cyan]AI-Powered Educational Video Pipeline[/dim cyan]\n" \
                 "[dim white]Gemini • Edge-TTS • Manim CE • Self-Healing Loop • FFmpeg[/dim white]"
    console.print(Panel(title_text, border_style="cyan", expand=False))


def print_step(step_number: int, total_steps: int, title: str, description: Optional[str] = None):
    """Prints a styled step indicator."""
    msg = f"[bold accent]Step {step_number}/{total_steps}:[/bold accent] [bold white]{title}[/bold white]"
    if description:
        msg += f"\n[dim white]{description}[/dim white]"
    console.print(Panel(msg, border_style="blue", expand=False))


def print_storyboard(storyboard_data):
    """Renders a structured storyboard in a Rich table."""
    table = Table(title=f"📐 Storyboard: {storyboard_data.topic}", border_style="cyan", show_header=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Title", style="bold white", width=24)
    table.add_column("Narration / Script", style="dim white")
    table.add_column("Visual Concept", style="italic deep_sky_blue1")

    for scene in storyboard_data.scenes:
        formulas = f" [LaTeX: {', '.join(scene.visuals.math_formulas)}]" if scene.visuals.math_formulas else ""
        table.add_row(
            str(scene.scene_number),
            scene.scene_title,
            scene.narration,
            f"{scene.visuals.description}{formulas}"
        )
    console.print(table)


def print_error(msg: str):
    """Prints an error message."""
    console.print(f"[bold red]❌ Error:[/bold red] {msg}")


def print_render_error(scene_number: int, attempt: int, error_log: str):
    """Prints Manim render errors and tracebacks in a formatted panel."""
    error_snippet = error_log.strip()
    # Limit length if gigantic, but keep the critical traceback lines
    if len(error_snippet) > 2000:
        error_snippet = error_snippet[-2000:]

    panel = Panel(
        f"[bold red]Traceback / Compiler Output:[/bold red]\n[white]{error_snippet}[/white]",
        title=f"[bold yellow]⚠️ Manim Render Error - Scene {scene_number} (Attempt #{attempt})[/bold yellow]",
        border_style="red",
        expand=False
    )
    console.print(panel)


def print_success(msg: str):
    """Prints a success message."""
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_warning(msg: str):
    """Prints a warning message."""
    console.print(f"[bold yellow]⚠️  Warning:[/bold yellow] {msg}")
