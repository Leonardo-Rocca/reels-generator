from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Phrase:
    text: str
    image_prompt: str | None = None  # custom image prompt; falls back to text if None
    title: str | None = None
    body_position: str | None = None  # overrides config.text_position for this slide
    image_file: str | None = None  # local filename inside assets/images/
    duration: float | None = None  # overrides config.slide_duration for this slide

@dataclass
class Slide:
    phrase: Phrase
    image_path: Path | None = None
    frame_path: Path | None = None

@dataclass
class Project:
    slides: list[Slide]
    output_path: Path
    work_dir: Path = field(default_factory=lambda: Path("./tmp_reels_work"))
