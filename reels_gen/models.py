from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Phrase:
    text: str
    image_prompt: str | None = None  # custom image prompt; falls back to text if None
    title: str | None = None
    body_position: str | None = None  # overrides config.text_position for this slide
    image_file: str | None = None  # local filename inside assets/images/
    video_file: str | None = None  # local video filename; mutually exclusive with image_file
    duration: float | None = None  # overrides config.slide_duration for this slide

@dataclass
class Slide:
    phrase: Phrase
    image_path: Path | None = None
    video_path: Path | None = None  # set when phrase.video_file is used
    frame_path: Path | None = None  # for video slides: transparent text overlay PNG (or None)

@dataclass
class Project:
    slides: list[Slide]
    output_path: Path
    work_dir: Path = field(default_factory=lambda: Path("./tmp_reels_work"))
