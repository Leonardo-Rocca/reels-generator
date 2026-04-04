# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Installation

```bash
pip install -e .          # Install in editable/dev mode
cp .env.example .env      # Then add HF_TOKEN to .env
source .venv/bin/activate
```

Requires Python 3.12+ and `ffmpeg` available as a system binary.

## Running the Tool

```bash
reels-gen --input examples/phrases.txt --output reel.mp4
reels-gen --phrase "Hello world" --phrase "Another phrase" --output test.mp4
reels-gen --input phrases.txt --text-position center --duration 5.0
reels-gen --dry-run --input phrases.txt    # Validate input only
```

## Architecture

The pipeline has 3 sequential stages orchestrated by `cli.py`:

1. **Image generation** (`image_generator.py`) — Calls the HuggingFace Inference API. Results are MD5-hash cached in `.reels_cache/` (keyed on `model:prompt`). If `image_file` is set on a phrase, skips the API and reads from `assets/images/`. Retries with exponential backoff; raises a clean error on 402.

2. **Frame composition** (`frame_composer.py`) — PIL-based: cover-crops images to 1080×1920, draws text blocks with a semi-transparent backdrop sized to the text content. Optionally overlays `assets/logo.png` bottom-right (controlled by `logo_opacity`). Frame filenames are an MD5 hash of the phrase text to avoid collisions.

3. **Video assembly** (`video_assembler.py` → `output_encoder.py`) — MoviePy builds H.264 with crossfade transitions. FFmpeg post-processes to Instagram specs (H.264 high profile level 4.0, maxrate 4000k, `+faststart`).

**Data flow**: `Phrase[]` → `Slide[]` (image_path filled) → `Slide[]` (frame_path filled) → `intermediate.mp4` → `output.mp4`

**Key models** (`models.py`):
- `Phrase`: text, optional title, image_prompt, image_file, body_position, duration
- `Slide`: Phrase + image_path + frame_path (mutated in place by each stage)
- `Project`: slides + output_path

**Config** (`config.py`): Pydantic `Config` loaded via `Config.from_env()`. Tunable fields: `hf_model`, `image_style_suffix`, `text_backdrop_color` (RGBA tuple), `text_backdrop_padding_x/y`, `text_edge_margin`, `logo_opacity`. `HF_TOKEN` is read from `.env`.

## Input File Format (`.txt`)

```
# comment

# Plain phrase (uses text as image prompt)
El silencio también habla.

# Custom image prompt
Todo pasa por algo.
<prompt>a cosmic road into a starry horizon, purple nebula sky</prompt>

# Local image from assets/images/
<title>Luna Nueva</title>
<body>Es tiempo de soltar lo que ya no te pertenece.</body>
<image>moon.png</image>

# Standalone centered text (no separate title block)
<title center>La astrología no te define.</title>
<image>moon.png</image>

# Per-slide duration override
El tiempo es relativo.
<duration>4.0</duration>
```

- `<title>` is drawn at the top; `<body>` at the position set by `--text-position` (default: bottom).
- `<title center|top|bottom>` without a following `<body>` renders a single centered text block at that position.
- `<prompt>` and `<image>` are mutually exclusive.
- `Phrase.duration` overrides `config.slide_duration` for that slide only.

## Assets

- `assets/images/` — local images referenced via `<image>` tags
- `assets/logo.png` — overlaid bottom-right if present (optional)
- `assets/fonts/` — Montserrat Bold (auto-downloaded on first run)
- `.reels_cache/` — persistent image cache (do not delete between runs if you want to resume)

# Token Efficient Rules

1. Think before acting. Read existing files before writing code.
2. Be concise in output but thorough in reasoning.
3. Prefer editing over rewriting whole files.
4. Do not re-read files you have already read unless the file may have changed.
5. Test your code before declaring done.
6. No sycophantic openers or closing fluff.
7. Keep solutions simple and direct.
8. User instructions always override this file.
9. Always answer in spanish