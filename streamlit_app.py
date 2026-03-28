"""Reels Studio — Streamlit web UI."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Streamlit Cloud: expose secrets as env vars so Config.from_env() picks them up
if not os.getenv("HF_TOKEN") and "HF_TOKEN" in st.secrets:
    os.environ["HF_TOKEN"] = st.secrets["HF_TOKEN"]

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Reels Studio",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
    <style>
    html, body, [class*="css"]          { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3                          { font-family: 'Cormorant Garamond', serif !important; }
    #MainMenu, footer, header           { visibility: hidden; }
    .block-container                    { padding-top: 2rem; padding-bottom: 5rem; max-width: 720px; }

    .slide-num {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #8886a0;
    }
</style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────

DEFAULT_DURATION: float = 2.8


def _new_slide() -> dict:
    return {
        "id": uuid.uuid4().hex[:8],   # stable key — never changes after creation
        "title": "",
        "body": "",
        "image_file": None,
        "image_bytes": None,
        "duration": DEFAULT_DURATION,
    }


if "slides" not in st.session_state:
    st.session_state.slides = [_new_slide()]
if "video_bytes" not in st.session_state:
    st.session_state.video_bytes = None

slides: list[dict] = st.session_state.slides


def _delete_slide(idx: int) -> None:
    """on_click callback — index is captured at render time via args=(i,)."""
    st.session_state.slides.pop(idx)
    st.session_state.video_bytes = None

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("# Reels *studio*")
st.caption(
    "Build your reel slide by slide — each card is one scene. "
    "Leave **Body** empty to center the title on screen."
)
st.divider()

# ── Slide cards ───────────────────────────────────────────────────────────────

for i, slide in enumerate(slides):
    sid = slide["id"]  # stable ID — widget keys never collide after insert/delete

    with st.container(border=True):

        # Header row: slide number + delete button
        col_num, col_del = st.columns([8, 1])
        with col_num:
            st.markdown(
                f'<p class="slide-num">Slide {i + 1:02d}</p>',
                unsafe_allow_html=True,
            )
        with col_del:
            st.button(
                "✕",
                key=f"del_{sid}",
                disabled=len(slides) == 1,
                help="Delete this slide",
                on_click=_delete_slide,
                args=(i,),
            )

        # Fields — keyed by stable sid so widget state travels with the slide
        slide["title"] = st.text_input(
            "Title",
            value=slide["title"],
            key=f"title_{sid}",
            placeholder="Luna Nueva",
        )
        slide["body"] = st.text_area(
            "Body  *(optional)*",
            value=slide["body"],
            key=f"body_{sid}",
            placeholder="Es tiempo de soltar lo que ya no te pertenece.",
            height=80,
        )

        # Image upload (required)
        uploaded = st.file_uploader(
            "Image",
            type=["png", "jpg", "jpeg"],
            key=f"img_{sid}",
        )
        if uploaded is not None:
            slide["image_bytes"] = uploaded.getvalue()
            slide["image_file"] = uploaded.name
            st.image(slide["image_bytes"], width=200)
        else:
            slide["image_bytes"] = None
            slide["image_file"] = None

        slide["duration"] = st.slider(
            "Duration (seconds)",
            min_value=1.0,
            max_value=8.0,
            step=0.1,
            value=float(slide["duration"]),
            key=f"dur_{sid}",
        )

    st.write("")  # breathing room between cards

# ── Add slide ─────────────────────────────────────────────────────────────────

if st.button("＋  Add slide", use_container_width=True):
    slides.append(_new_slide())
    st.session_state.video_bytes = None
    st.rerun()

st.divider()

# ── Generate ──────────────────────────────────────────────────────────────────

def _build_txt(slides: list[dict]) -> str:
    """Convert slide dicts to the .txt format consumed by _parse_txt()."""
    lines: list[str] = []
    for s in slides:
        title = (s["title"] or "").strip()
        body  = (s["body"]  or "").strip()
        img   = (s["image_file"] or "").strip()

        if body:
            lines.append(f"<title>{title}</title>")
            lines.append(f"<body>{body}</body>")
        else:
            lines.append(f"<title center>{title}</title>")

        if img:
            lines.append(f"<image>{img}</image>")

        lines.append(f"<duration>{float(s['duration'])}</duration>")
        lines.append("")

    return "\n".join(lines)


if st.button("▶  Generate Reel", type="primary", use_container_width=True):

    # Basic validation
    if not all((s["title"] or "").strip() for s in slides):
        st.error("Every slide needs a title.")
        st.stop()

    missing_images = [i + 1 for i, s in enumerate(slides) if not s["image_bytes"]]
    if missing_images:
        st.error(f"Missing image on slide{'s' if len(missing_images) > 1 else ''}: {', '.join(map(str, missing_images))}.")
        st.stop()

    from reels_gen.config import Config
    config = Config.from_env()

    if not config.hf_token:
        st.error(
            "**HF_TOKEN not set.**  \n"
            "Locally: add it to `.env`.  \n"
            "Streamlit Cloud: add it under *Settings → Secrets*."
        )
        st.stop()

    from reels_gen.frame_composer import compose_all
    from reels_gen.image_generator import generate_all
    from reels_gen.input_parser import _parse_txt, build_project
    from reels_gen.output_encoder import encode_for_instagram
    from reels_gen.video_assembler import assemble_video

    # Write uploaded images to a temp directory (assets_images_dir)
    assets_dir = Path(tempfile.mkdtemp(prefix="reels_assets_"))
    for s in slides:
        if s["image_bytes"] and s["image_file"]:
            (assets_dir / s["image_file"]).write_bytes(s["image_bytes"])

    phrases     = _parse_txt(_build_txt(slides))
    output_path = Path(tempfile.mktemp(suffix=".mp4", prefix="reels_out_"))
    project     = build_project(phrases, output_path)
    n           = len(project.slides)

    cache_dir = Path(".reels_cache")
    cache_dir.mkdir(exist_ok=True)
    work_dir  = Path(tempfile.mkdtemp(prefix="reels_work_"))

    try:
        with st.status("Generating reel…", expanded=True) as status:

            st.write(f"**Stage 1 / 4** — Generating images ({n} slide{'s' if n > 1 else ''})…")
            prog1 = st.progress(0.0)

            def _img_cb(done: int, total: int) -> None:
                prog1.progress(done / total)

            generate_all(
                project.slides,
                cache_dir,
                config,
                progress_callback=_img_cb,
                assets_images_dir=assets_dir,
            )

            st.write("**Stage 2 / 4** — Composing frames…")
            prog2 = st.progress(0.0)

            def _frame_cb(done: int, total: int) -> None:
                prog2.progress(done / total)

            compose_all(project.slides, work_dir, config, progress_callback=_frame_cb)

            st.write("**Stage 3 / 4** — Assembling video…")
            intermediate = work_dir / "intermediate.mp4"
            assemble_video(project, config, intermediate)

            st.write("**Stage 4 / 4** — Encoding for Instagram…")
            encode_for_instagram(intermediate, output_path, config)

            status.update(label="✓  Done!", state="complete")

        st.session_state.video_bytes = output_path.read_bytes()

    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")

    finally:
        shutil.rmtree(work_dir,   ignore_errors=True)
        shutil.rmtree(assets_dir, ignore_errors=True)
        output_path.unlink(missing_ok=True)

# ── Download ──────────────────────────────────────────────────────────────────

if st.session_state.video_bytes:
    st.download_button(
        "⬇  Download reel.mp4",
        data=st.session_state.video_bytes,
        file_name="reel.mp4",
        mime="video/mp4",
        use_container_width=True,
    )