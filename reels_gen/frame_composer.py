import hashlib
import urllib.request
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from .config import Config
from .models import Slide

FONT_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "fonts"
LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"

def ensure_font(size: int) -> ImageFont.FreeTypeFont:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    font_path = ASSETS_DIR / "Montserrat-Bold.ttf"
    if not font_path.exists():
        urllib.request.urlretrieve(FONT_URL, font_path)
    return ImageFont.truetype(str(font_path), size)

def cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if img_ratio > target_ratio:
        new_h = target_h
        new_w = int(img_ratio * new_h)
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def _draw_text_block(img: Image.Image, lines: list[str], font: ImageFont.FreeTypeFont, text_y: int, config: Config) -> Image.Image:
    """Draw a backdrop sized to the text content, then draw the text lines over it."""
    draw = ImageDraw.Draw(img)
    px, py = config.text_backdrop_padding_x, config.text_backdrop_padding_y
    line_height = font.size + 16

    # Measure widest line
    max_line_w = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
    total_h = len(lines) * line_height

    backdrop_x0 = (config.width - max_line_w) // 2 - px
    backdrop_x1 = (config.width + max_line_w) // 2 + px
    backdrop_y0 = text_y - py
    backdrop_y1 = text_y + total_h + py

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([backdrop_x0, backdrop_y0, backdrop_x1, backdrop_y1], fill=config.text_backdrop_color)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        lw = draw.textbbox((0, 0), line, font=font)[2]
        x = (config.width - lw) // 2
        draw.text((x, text_y + i * line_height), line, font=font, fill=config.text_color)

    return img

def compose_frame(slide: Slide, work_dir: Path, config: Config) -> Path:
    if slide.image_path is None:
        raise ValueError(f"Slide has no image_path: {slide.phrase.text}")
    img = Image.open(slide.image_path).convert("RGB")
    img = cover_crop(img, config.width, config.height)

    font = ensure_font(config.font_size)
    max_text_width = config.width - (config.text_backdrop_padding_x + 60) * 2
    lines = wrap_text(slide.phrase.text, font, max_text_width)

    line_height = config.font_size + 16
    total_text_height = len(lines) * line_height

    position = slide.phrase.body_position or config.text_position
    if position == "bottom":
        text_y = config.height - total_text_height - config.text_backdrop_padding_y * 2 - config.text_edge_margin
    elif position == "center":
        text_y = (config.height - total_text_height) // 2
    else:  # top
        text_y = config.text_edge_margin

    if lines:
        img = _draw_text_block(img, lines, font, text_y, config)

    # Draw title at top if present
    if slide.phrase.title:
        title_font = ensure_font(config.font_size)
        title_lines = wrap_text(slide.phrase.title, title_font, max_text_width)
        img = _draw_text_block(img, title_lines, title_font, config.text_edge_margin, config)

    # Overlay logo bottom-right
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        scale = config.logo_max_width / logo.width
        logo = logo.resize(
            (config.logo_max_width, int(logo.height * scale)),
            Image.Resampling.LANCZOS,
        )
        r, g, b, a = logo.split()
        a = a.point(lambda v: int(v * config.logo_opacity))
        logo.putalpha(a)
        x = config.width - logo.width - config.logo_margin
        y = config.height - logo.height - config.logo_margin_y
        base = img.convert("RGBA")
        base.paste(logo, (x, y), mask=logo)
        img = base.convert("RGB")

    slide_hash = hashlib.md5(f"{slide.phrase.text}|{slide.image_path}".encode()).hexdigest()[:8]
    out_path = work_dir / f"frame_{slide_hash}.png"
    img.save(out_path)
    slide.frame_path = out_path
    return out_path

def compose_all(slides: list[Slide], work_dir: Path, config: Config, progress_callback: Callable[[int, int], None] | None = None) -> None:
    for i, slide in enumerate(slides):
        compose_frame(slide, work_dir, config)
        if progress_callback:
            progress_callback(i + 1, len(slides))
