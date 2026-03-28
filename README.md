# reels-gen

Generate Instagram Reels from text phrases using AI-generated images. Each phrase becomes a slide with an AI-generated background, styled text overlay, and crossfade transitions — encoded to Instagram specs.

## Requirements

- Python 3.12+
- `ffmpeg` available as a system binary
- A [HuggingFace](https://huggingface.co) account with API access

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # then add your HF_TOKEN
```

## Usage

```bash
source .venv/bin/activate
python -m reels_gen.cli --input examples/moons.txt --output reel4.mp4 



 source .venv/bin/activate
 streamlit run app.py
 # abre http://localhost:8501 en el browser



# From a phrases file
reels-gen --input examples/phrases.txt --output reel.mp4

# Inline phrases
reels-gen --phrase "El silencio también habla." --phrase "Todo pasa por algo." --output reel.mp4

# With background music and custom slide duration
reels-gen --input phrases.txt --music bg.mp3 --duration 5.0 --output reel.mp4

# Control text position
reels-gen --input phrases.txt --text-position center --output reel.mp4

# Validate input without generating
reels-gen --dry-run --input phrases.txt
```

### Options

| Option | Default | Description |
|---|---|---|
| `--input FILE` | — | Text file with phrases |
| `--phrase TEXT` | — | Inline phrase (repeatable) |
| `--output FILE` | `output.mp4` | Output video path |
| `--music FILE` | — | Background audio (loops if shorter than video) |
| `--duration FLOAT` | from config | Seconds per slide |
| `--text-position` | `bottom` | `top`, `center`, or `bottom` |
| `--token TEXT` | from `.env` | HuggingFace API token |
| `--model TEXT` | from config | HuggingFace model ID |
| `--dry-run` | — | Validate input only, no generation |

## Input File Format

```
# Lines starting with # are comments. Blank lines are ignored.

# Plain phrase — text is used as both the slide text and image prompt
El silencio también habla.

# Custom image prompt
Todo pasa por algo.
<prompt>a cosmic road into a starry horizon, purple nebula sky</prompt>

# Custom slide duration (overrides global --duration)
Esta slide dura más.
<duration>6.0</duration>

# Title + body layout (title at top, body at bottom)
<title>Luna Nueva</title>
<body>Es tiempo de soltar lo que ya no te pertenece.</body>
<image>moon.png</image>

# Standalone centered text using a local image
<title center>La astrología no te define.</title>
<image>moon.png</image>

# Combining prompt and duration
Confía en el proceso.
<prompt>golden light through forest trees, ethereal mist</prompt>
<duration>4.0</duration>
```

**Tag rules:**
- `<title>` is drawn at the top; `<body>` at the position set by `--text-position`
- `<title top|center|bottom>` without `<body>` renders a single centered text block at that position
- `<prompt>` and `<image>` are mutually exclusive — `<image>` skips API generation entirely
- `<duration>` can be combined with `<prompt>` or `<image>`

## Assets

| Path | Description |
|---|---|
| `assets/images/` | Local images referenced via `<image>` tags |
| `assets/fonts/` | Montserrat Bold (auto-downloaded on first run) |
| `assets/logo.png` | Watermark logo — overlaid bottom-right on every frame |
| `.reels_cache/` | Persistent image cache — preserves generated images across runs |

## Configuration

Defaults live in `reels_gen/config.py` and can be edited directly:

```python
slide_duration: float = 2.5       # seconds per slide
transition_duration: float = 0.2  # crossfade duration
font_size: int = 72
text_position: str = "bottom"     # "top", "center", "bottom"
text_backdrop_color: tuple = (20, 10, 45, 170)  # RGBA

# Logo overlay
logo_max_width: int = 360         # px
logo_margin: int = 60             # distance from right/bottom edges
logo_opacity: float = 0.65        # 0.0 = invisible, 1.0 = fully opaque

# Image generation
hf_model: str = "stabilityai/stable-diffusion-xl-base-1.0"
image_style_suffix: str = "mystical atmosphere, cinematic lighting, ..."
```

## Pipeline

```
phrases.txt → Phrase[] → Slide[] → Slide[] → intermediate.mp4 → output.mp4
                         images    frames     MoviePy            FFmpeg
```

1. **Image generation** — HuggingFace Inference API, MD5-hash cached in `.reels_cache/`. Uses local file if `<image>` tag is set.
2. **Frame composition** — PIL cover-crops images to 1080×1920, draws text with semi-transparent backdrop, overlays logo.
3. **Video assembly** — MoviePy builds H.264 with crossfade transitions and optional looping audio at 0.4× volume.
4. **Encoding** — FFmpeg post-processes to Instagram specs: H.264 high profile level 4.0, maxrate 4000k, `+faststart`.