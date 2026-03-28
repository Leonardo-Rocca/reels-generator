import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from dotenv import load_dotenv
import shutil

load_dotenv()

console = Console()

@click.command()
@click.option("--input", "input_file", type=click.Path(exists=True, path_type=Path), help="Text file with phrases (one per line)")
@click.option("--phrase", "phrases", multiple=True, help="Inline phrase (repeatable)")
@click.option("--output", "output_path", type=click.Path(path_type=Path), default="output.mp4", show_default=True)
@click.option("--duration", default=None, type=float, help="Seconds per slide (default: from config)")
@click.option("--text-position", type=click.Choice(["top", "center", "bottom"]), default="bottom", show_default=True)
@click.option("--token", "hf_token", default=None, help="Hugging Face token (or set HF_TOKEN env var)")
@click.option("--model", "hf_model", default=None, help="HuggingFace model ID for image generation")
@click.option("--dry-run", is_flag=True, help="Validate input without generating")
def main(input_file, phrases, output_path, duration, text_position, hf_token, hf_model, dry_run):
    """Generate Instagram Reels from text phrases using AI-generated images."""
    from .config import Config
    from .models import Phrase
    from .input_parser import parse_file, parse_phrases, build_project
    from .image_generator import generate_all
    from .frame_composer import compose_all
    from .video_assembler import assemble_video
    from .output_encoder import encode_for_instagram
    import tempfile

    # Load config
    config = Config.from_env()
    if duration is not None:
        config.slide_duration = duration
    config.text_position = text_position
    if hf_token:
        config.hf_token = hf_token
    if hf_model:
        config.hf_model = hf_model

    if not config.hf_token:
        console.print("[red]Error:[/red] Hugging Face token required. Set HF_TOKEN in .env or use --token")
        raise click.Abort()

    # Parse input
    all_phrases: list[Phrase] = []
    if input_file:
        all_phrases.extend(parse_file(input_file))
    if phrases:
        all_phrases.extend(parse_phrases(list(phrases)))

    if not all_phrases:
        console.print("[red]Error:[/red] No phrases provided. Use --input FILE or --phrase TEXT")
        raise click.Abort()

    console.print(Panel(f"[bold]Reels Generator[/bold]\n{len(all_phrases)} slides → {output_path}", expand=False))

    if dry_run:
        console.print(f"\n[green]Dry run OK.[/green] {len(all_phrases)} phrases:")
        for i, p in enumerate(all_phrases, 1):
            console.print(f"  {i}. {p.text}")
        return

    project = build_project(all_phrases, output_path)
    cache_dir = Path(".reels_cache")
    cache_dir.mkdir(exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="reels_"))

    try:
        # Stage 1: Generate images
        console.print("\n[bold cyan]Stage 1/3:[/bold cyan] Generating images...")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Generating...", total=len(project.slides))
            def img_progress(done: int, total: int) -> None:
                progress.update(task, completed=done)
            generate_all(project.slides, cache_dir, config, progress_callback=img_progress)

        # Stage 2: Compose frames
        console.print("\n[bold cyan]Stage 2/3:[/bold cyan] Composing frames...")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
            task = progress.add_task("Composing...", total=len(project.slides))
            def frame_progress(done: int, total: int) -> None:
                progress.update(task, completed=done)
            compose_all(project.slides, work_dir, config, progress_callback=frame_progress)

        # Stage 3: Assemble video
        console.print("\n[bold cyan]Stage 3/3:[/bold cyan] Assembling video...")
        intermediate = work_dir / "intermediate.mp4"
        assemble_video(project, config, intermediate)

        # Final encode
        console.print("\n[bold cyan]Encoding:[/bold cyan] Final Instagram-spec encoding...")
        encode_for_instagram(intermediate, output_path, config)

        console.print(f"\n[bold green]Done![/bold green] Video saved to: [cyan]{output_path}[/cyan]")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
