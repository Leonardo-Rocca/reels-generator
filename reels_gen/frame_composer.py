import hashlib
import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np
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

def _draw_text_block(img: Image.Image, lines: list[str], font: ImageFont.FreeTypeFont, text_y: int, config: Config, keep_alpha: bool = False) -> Image.Image:
    """Draw a backdrop sized to the text content, then draw the text lines over it."""
    draw = ImageDraw.Draw(img)
    px, py = config.text_backdrop_padding_x, config.text_backdrop_padding_y
    line_height = font.size + 16

    max_line_w = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
    total_h = len(lines) * line_height

    backdrop_x0 = (config.width - max_line_w) // 2 - px
    backdrop_x1 = (config.width + max_line_w) // 2 + px
    backdrop_y0 = text_y - py
    backdrop_y1 = text_y + total_h + py

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([backdrop_x0, backdrop_y0, backdrop_x1, backdrop_y1], fill=config.text_backdrop_color)
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    if not keep_alpha:
        img = img.convert("RGB")

    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        lw = draw.textbbox((0, 0), line, font=font)[2]
        x = (config.width - lw) // 2
        draw.text((x, text_y + i * line_height), line, font=font, fill=config.text_color)

    return img

def _partial_lines(full_lines: list[str], n: int) -> list[str]:
    """Return the first n characters distributed across pre-wrapped lines."""
    result: list[str] = []
    remaining = n
    for line in full_lines:
        if remaining <= 0:
            break
        if remaining >= len(line):
            result.append(line)
            remaining -= len(line)
        else:
            result.append(line[:remaining])
            remaining = 0
    return result


def _apply_logo(img: Image.Image, config: Config) -> Image.Image:
    if not LOGO_PATH.exists():
        return img
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
    was_rgb = img.mode == "RGB"
    base = img.convert("RGBA")
    base.paste(logo, (x, y), mask=logo)
    return base.convert("RGB") if was_rgb else base


def _compose_video_overlay(slide: Slide, work_dir: Path, config: Config) -> Path | None:
    """For video slides: produce a transparent PNG with text + logo overlay, or None if nothing to draw."""
    text = (slide.phrase.text or "").strip()
    title = (slide.phrase.title or "").strip()
    has_logo = LOGO_PATH.exists()
    if not text and not title and not has_logo:
        slide.frame_path = None
        return None

    font = ensure_font(config.font_size)
    max_text_width = config.width - (config.text_backdrop_padding_x + 60) * 2
    img = Image.new("RGBA", (config.width, config.height), (0, 0, 0, 0))

    if text:
        lines = wrap_text(text, font, max_text_width)
        line_height = config.font_size + 16
        total_h = len(lines) * line_height
        position = slide.phrase.body_position or config.text_position
        if position == "bottom":
            text_y = config.height - total_h - config.text_backdrop_padding_y * 2 - config.text_edge_margin
        elif position == "center":
            text_y = (config.height - total_h) // 2
        else:
            text_y = config.text_edge_margin
        if lines:
            img = _draw_text_block(img, lines, font, text_y, config, keep_alpha=True)

    if title:
        title_font = ensure_font(config.font_size)
        title_lines = wrap_text(title, title_font, max_text_width)
        img = _draw_text_block(img, title_lines, title_font, config.text_edge_margin, config, keep_alpha=True)

    if has_logo:
        img = _apply_logo(img, config)

    slide_hash = hashlib.md5(f"overlay|{text}|{title}|{slide.video_path}".encode()).hexdigest()[:8]
    out_path = work_dir / f"overlay_{slide_hash}.png"
    img.save(out_path)
    slide.frame_path = out_path
    return out_path


def compose_frame(slide: Slide, work_dir: Path, config: Config) -> Path | None:
    if slide.video_path is not None:
        return _compose_video_overlay(slide, work_dir, config)
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

    img = _apply_logo(img, config)

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


_CHARS_PER_SECOND = 30.0  # constant typing speed
_REVEAL_FRACTION = 0.4    # fallback: if constant speed is too slow to fit, accelerate to finish here


def _typewriter_layout(slide: Slide, config: Config):
    """Return (full_lines, full_title_lines, text_y, title_chars, body_chars, total_chars, font).

    title types first, then body — both animate character by character.
    """
    font = ensure_font(config.font_size)
    max_text_width = config.width - (config.text_backdrop_padding_x + 60) * 2

    body = (slide.phrase.text or "").strip()
    title = (slide.phrase.title or "").strip()

    full_lines = wrap_text(body, font, max_text_width) if body else []
    full_title_lines = wrap_text(title, font, max_text_width) if title else []
    title_chars = sum(len(l) for l in full_title_lines)
    body_chars = sum(len(l) for l in full_lines)
    total_chars = title_chars + body_chars

    position = slide.phrase.body_position or config.text_position
    line_height = config.font_size + 16
    total_h = len(full_lines) * line_height
    if position == "bottom":
        text_y = config.height - total_h - config.text_backdrop_padding_y * 2 - config.text_edge_margin
    elif position == "center":
        text_y = (config.height - total_h) // 2
    else:
        text_y = config.text_edge_margin

    return full_lines, full_title_lines, text_y, title_chars, body_chars, total_chars, font


def _apply_typewriter(img: Image.Image, n: int, full_lines, full_title_lines, text_y: int,
                      title_chars: int, font, config: Config, keep_alpha: bool = False) -> Image.Image:
    """Draw title + body with n total characters revealed (title first, then body)."""
    n_title = min(n, title_chars)
    n_body = max(0, n - title_chars)

    if full_title_lines and n_title > 0:
        partial_title = _partial_lines(full_title_lines, n_title)
        if partial_title:
            img = _draw_text_block(img, partial_title, font, config.text_edge_margin, config, keep_alpha=keep_alpha)

    if full_lines and n_body > 0:
        partial_body = _partial_lines(full_lines, n_body)
        if partial_body:
            img = _draw_text_block(img, partial_body, font, text_y, config, keep_alpha=keep_alpha)

    return img


def make_image_typewriter_func(slide: Slide, config: Config, duration: float) -> Callable[[float], np.ndarray]:
    """Return make_frame(t) → RGB numpy array for a typewriter effect on an image slide."""
    base_img = cover_crop(Image.open(slide.image_path).convert("RGB"), config.width, config.height)
    base_img = _apply_logo(base_img, config)

    full_lines, full_title_lines, text_y, title_chars, _, total_chars, font = _typewriter_layout(slide, config)
    speed = max(_CHARS_PER_SECOND, total_chars / (duration * _REVEAL_FRACTION)) if total_chars > 0 else 1.0

    def make_frame(t: float) -> np.ndarray:
        n = min(int(t * speed), total_chars)
        img = _apply_typewriter(base_img.copy(), n, full_lines, full_title_lines, text_y, title_chars, font, config)
        return np.array(img)

    return make_frame


def make_video_overlay_typewriter_func(slide: Slide, config: Config, duration: float) -> Callable[[float], np.ndarray]:
    """Return make_rgba_frame(t) → RGBA numpy array for typewriter overlay on a video slide."""
    full_lines, full_title_lines, text_y, title_chars, _, total_chars, font = _typewriter_layout(slide, config)
    speed = max(_CHARS_PER_SECOND, total_chars / (duration * _REVEAL_FRACTION)) if total_chars > 0 else 1.0

    static_base = _apply_logo(Image.new("RGBA", (config.width, config.height), (0, 0, 0, 0)), config)

    def make_rgba_frame(t: float) -> np.ndarray:
        n = min(int(t * speed), total_chars)
        img = _apply_typewriter(static_base.copy(), n, full_lines, full_title_lines, text_y, title_chars, font, config, keep_alpha=True)
        return np.array(img)

    return make_rgba_frame
