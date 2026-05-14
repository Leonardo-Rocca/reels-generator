"""Reels Studio — Streamlit web UI."""

from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

# ── Backdrop colour palette ───────────────────────────────────────────────────

BACKDROP_PALETTE: dict[str, tuple[int, int, int]] = {
    "#130e2d": (20, 10, 45),
    "#231F20": (35, 31, 32),
    "#264F5E": (38, 79, 94),
    "#7A5C3A": (122, 92, 58),
    "#4D7D7D": (77, 125, 125),
    "#1B1817": (27, 24, 23),
    "#474A8C": (71, 74, 140),
    "#F5E6D3": (245, 230, 211),
    "#FBF3F6": (251, 243, 246),
    "#D1CAAE": (209, 202, 174),
    "#E5AF6E": (229, 175, 110),
    "#F6F0E7": (246, 240, 231),
}
BACKDROP_ALPHA = 170


def _text_color_for_bg(r: int, g: int, b: int) -> str:
    """Return 'white' or 'black' based on perceived luminance (ITU-R BT.601)."""
    return "black" if (r * 299 + g * 587 + b * 114) / 1000 > 128 else "white"


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

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

DEFAULT_DURATION: float = 3.0


def _new_slide() -> dict:
    return {
        "id": uuid.uuid4().hex[:8],   # stable key — never changes after creation
        "title": "",
        "body": "",
        "image_file": None,
        "image_bytes": None,
        "video_file": None,
        "video_path": None,      # path to temp file on disk (never stored as bytes)
        "video_duration": None,
        "media_type": "imagen",  # "imagen" | "video" — persisted here, not in widget state
        "duration": DEFAULT_DURATION,
    }


if "slides" not in st.session_state:
    st.session_state.slides = [_new_slide()]
if "video_bytes" not in st.session_state:
    st.session_state.video_bytes = None
if "backdrop_color_key" not in st.session_state:
    st.session_state.backdrop_color_key = next(iter(BACKDROP_PALETTE))
if "draft_uploader_key" not in st.session_state:
    st.session_state.draft_uploader_key = 0
if "draft_saved" not in st.session_state:
    st.session_state.draft_saved = False

slides: list[dict] = st.session_state.slides


def _delete_slide(idx: int) -> None:
    """on_click callback — index is captured at render time via args=(i,)."""
    slide = st.session_state.slides[idx]
    _unlink_video(slide)
    st.session_state.slides.pop(idx)
    st.session_state.video_bytes = None


def _unlink_video(slide: dict) -> None:
    p = slide.get("video_path")
    if p:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass


def _session_to_draft() -> bytes:
    """Serialize current session state to JSON bytes for local download."""
    slides_data = []
    for s in st.session_state.slides:
        img_b64 = base64.b64encode(s["image_bytes"]).decode() if s["image_bytes"] else None
        _vp = s.get("video_path")
        vid_b64 = base64.b64encode(Path(_vp).read_bytes()).decode() if _vp and Path(_vp).exists() else None
        slides_data.append({
            "id": s["id"],
            "title": s["title"],
            "body": s["body"],
            "image_file": s["image_file"],
            "image_b64": img_b64,
            "video_file": s.get("video_file"),
            "video_b64": vid_b64,
            "video_duration": s.get("video_duration"),
            "media_type": s.get("media_type", "imagen"),
            "duration": s["duration"],
        })
    draft = {
        "version": 1,
        "backdrop_color_key": st.session_state.backdrop_color_key,
        "slides": slides_data,
    }
    return json.dumps(draft, ensure_ascii=False, indent=2).encode()


def _load_draft(raw: bytes) -> str | None:
    """Restore session state from draft JSON bytes. Returns error message or None."""
    try:
        draft = json.loads(raw)
    except json.JSONDecodeError:
        return "El archivo no es un JSON válido."

    if draft.get("version") != 1:
        return "Versión de borrador no soportada."

    # Clean up temp files from current slides before replacing
    for _old in st.session_state.slides:
        _unlink_video(_old)

    slides = []
    for s in draft.get("slides", []):
        img_bytes = base64.b64decode(s["image_b64"]) if s.get("image_b64") else None
        new_id = s.get("id") or uuid.uuid4().hex[:8]
        _vdur = float(s["video_duration"]) if s.get("video_duration") else None
        _vpath = None
        if s.get("video_b64") and s.get("video_file"):
            _tmp = tempfile.NamedTemporaryFile(suffix=Path(s["video_file"]).suffix, delete=False)
            _tmp.write(base64.b64decode(s["video_b64"]))
            _tmp.close()
            _vpath = _tmp.name
        _mtype = s.get("media_type", "video" if _vpath else "imagen")
        slides.append({
            "id": new_id,
            "title": s.get("title", ""),
            "body": s.get("body", ""),
            "image_file": s.get("image_file"),
            "image_bytes": img_bytes,
            "video_file": s.get("video_file"),
            "video_path": _vpath,
            "video_duration": _vdur,
            "media_type": _mtype,
            "duration": float(s.get("duration", DEFAULT_DURATION)),
        })
        if _vdur:
            st.session_state[f"dur_{new_id}"] = float(s.get("duration", _vdur))

    if not slides:
        return "El borrador no contiene slides."

    st.session_state.slides = slides
    color_key = draft.get("backdrop_color_key")
    if color_key in BACKDROP_PALETTE:
        st.session_state.backdrop_color_key = color_key
    st.session_state.video_bytes = None
    return None


# ── Header ────────────────────────────────────────────────────────────────────

if st.session_state.pop("_show_draft_toast", False):
    st.toast("Borrador cargado", icon="✅")

st.markdown("# Reels *studio*")
st.caption(
    "Build your reel slide by slide — each card is one scene. "
    "Leave **Body** empty to center the title. Leave both empty for an image-only slide."
)
st.divider()

# ── Draft: save / load ────────────────────────────────────────────────────────

with st.expander("Descargar/Cargar Borrador", expanded=True):
    _col_save, _col_load = st.columns(2)

    with _col_save:
        with st.container(border=True):
            if st.download_button(
                "⬇  Guardar borrador",
                data=_session_to_draft(),
                file_name="borrador.json",
                mime="application/json",
                use_container_width=True,
            ):
                st.session_state.draft_saved = True
            st.caption("Descarga el borrador para retomarlo después.")

    with _col_load:
        st.markdown(
            "<style>"
            "[data-testid='stColumn']:has(.draft-uploader-wrap)"
            " [data-testid='stFileUploaderDropzone'] button span { display:none; }"
            "[data-testid='stColumn']:has(.draft-uploader-wrap)"
            " [data-testid='stFileUploaderDropzone'] button::after { content:'⬆ Cargar borrador'; }"
            "[data-testid='stColumn']:has(.draft-uploader-wrap)"
            " [data-testid='stElementContainer']:has(.draft-uploader-wrap)"
            " { display:none !important; }"
            "</style>"
            '<div class="draft-uploader-wrap"></div>',
            unsafe_allow_html=True,
        )
        _uploaded_draft = st.file_uploader(
            "⬆ Cargar borrador",
            type=["json"],
            key=f"draft_uploader_{st.session_state.draft_uploader_key}",
            label_visibility="collapsed",
            help="Carga un borrador previamente guardado.",
        )
        if _uploaded_draft is not None:
            _err = _load_draft(_uploaded_draft.getvalue())
            if _err:
                st.error(_err)
            else:
                st.session_state.draft_uploader_key += 1
                st.session_state._show_draft_toast = True
                st.session_state.draft_saved = True
                st.rerun()

st.divider()

# ── Style settings ────────────────────────────────────────────────────────────

st.caption("COLOR DEL FONDO DEL TEXTO")

_palette_items = list(BACKDROP_PALETTE.items())
_mid = (len(_palette_items) + 1) // 2
for _row_items in (_palette_items[:_mid], _palette_items[_mid:]):
    _swatch_cols = st.columns(len(_row_items))
    for _col, (_name, (_r, _g, _b)) in zip(_swatch_cols, _row_items):
        _selected = st.session_state.backdrop_color_key == _name
        _text = _text_color_for_bg(_r, _g, _b)
        _border = "2px solid #6c63ff" if _selected else "2px solid transparent"
        _cls = _name.replace("#", "hex")
        with _col:
            st.markdown(
                f"<style>:has(.sw-{_cls}) + * button{{"
                f"background:rgb({_r},{_g},{_b}) !important;"
                f"color:{_text} !important;"
                f"border:{_border} !important;"
                f"border-radius:6px !important;height:40px;"
                f"}}</style>"
                f'<div class="sw-{_cls}"></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                _name,
                key=f"sw_{_name}",
                help=_name,
                use_container_width=True,
            ):
                st.session_state.backdrop_color_key = _name
                st.session_state.backdrop_custom_color = _name
                st.rerun()

_picker_col, _picker_label_col = st.columns([1, 8])
with _picker_col:
    _custom_val = st.color_picker(
        "Personalizado",
        value=st.session_state.backdrop_color_key
              if st.session_state.backdrop_color_key.startswith("#") and len(st.session_state.backdrop_color_key) == 7
              else "#130e2d",
        key="backdrop_custom_color",
        label_visibility="collapsed",
    )
with _picker_label_col:
    st.caption("Color personalizado (hex)")
if _custom_val != st.session_state.backdrop_color_key:
    st.session_state.backdrop_color_key = _custom_val
    st.rerun()

st.divider()

# ── Text animation mode ───────────────────────────────────────────────────────

st.caption("ANIMACIÓN DE TEXTO")
st.radio(
    "Animación de texto",
    options=["Texto estático", "Texto animado  ✦"],
    key="text_mode",
    horizontal=True,
    label_visibility="collapsed",
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
            "Title (optional)",
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

        # Media type toggle.
        # slide["media_type"] is the persistent source of truth (lives in session_state.slides).
        # Widget session state can be cleared by st.rerun() — we re-seed it from the slide
        # dict ONLY when it's missing (i.e. after a rerun cleared it), never overwriting a
        # legitimate user interaction.
        _prev_media = slide.get("media_type", "imagen")
        _mt_key = f"media_type_{sid}"
        if _mt_key in st.session_state:
            # Capture any user interaction that happened this rerun
            slide["media_type"] = st.session_state[_mt_key]
        # Re-seed so the widget shows the right value even if cleared by rerun
        st.session_state[_mt_key] = slide.get("media_type", "imagen")
        media_type = st.radio(
            "Tipo de media",
            options=["imagen", "video"],
            key=_mt_key,
            horizontal=True,
            label_visibility="collapsed",
        )
        slide["media_type"] = media_type

        if media_type == "imagen":
            if _prev_media == "video":
                # User explicitly switched away — clean up temp file
                _unlink_video(slide)
                slide["video_path"] = None
                slide["video_file"] = None
                slide["video_duration"] = None
            uploaded = st.file_uploader(
                "Imagen",
                type=["png", "jpg", "jpeg"],
                key=f"img_{sid}",
            )
            if uploaded is not None:
                slide["image_bytes"] = uploaded.getvalue()
                slide["image_file"] = uploaded.name
            if slide["image_bytes"]:
                st.image(slide["image_bytes"], width=200)
            elif uploaded is None:
                slide["image_bytes"] = None
                slide["image_file"] = None
        else:
            slide["image_bytes"] = None
            slide["image_file"] = None
            uploaded_vid = st.file_uploader(
                "Video",
                type=["mp4", "mov", "avi", "webm"],
                key=f"vid_{sid}",
            )
            if uploaded_vid is not None:
                if slide.get("video_file") != uploaded_vid.name:
                    # New file — write to temp and read duration
                    _unlink_video(slide)
                    _tmp = tempfile.NamedTemporaryFile(
                        suffix=Path(uploaded_vid.name).suffix, delete=False
                    )
                    try:
                        _tmp.write(uploaded_vid.getvalue())
                        _tmp.close()
                        from moviepy import VideoFileClip as _VFC
                        _vc = _VFC(_tmp.name)
                        _vdur = round(_vc.duration, 1)
                        _vc.close()
                    except Exception:
                        _vdur = None
                    slide["video_path"] = _tmp.name
                    slide["video_file"] = uploaded_vid.name
                    slide["video_duration"] = _vdur
                    slide["duration"] = _vdur or DEFAULT_DURATION
                    st.session_state[f"dur_{sid}"] = slide["duration"]
            if slide.get("video_path") and Path(slide["video_path"]).exists():
                with open(slide["video_path"], "rb") as _f:
                    st.video(_f)

        if media_type == "video":
            _vdur = slide.get("video_duration")
            if _vdur and _vdur > 1.0:
                _dur_key = f"dur_{sid}"
                if _dur_key in st.session_state:
                    st.session_state[_dur_key] = min(float(st.session_state[_dur_key]), _vdur)
                slide["duration"] = st.slider(
                    "Duración (segundos)",
                    min_value=1.0,
                    max_value=float(_vdur),
                    step=0.1,
                    value=min(float(slide["duration"]), float(_vdur)),
                    key=_dur_key,
                    help="Trunca el video desde el final",
                )
            elif _vdur:
                st.caption(f"Duración: {_vdur:.1f}s")
            else:
                st.caption("Duración: definida por el video")
        else:
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
    st.session_state.draft_saved = False
    st.rerun()

st.divider()

# ── Generate ──────────────────────────────────────────────────────────────────

if st.button("▶  Generate Reel", type="primary", use_container_width=True):

    # Basic validation
    missing_media = [
        i + 1 for i, s in enumerate(slides)
        if not s.get("video_path") and not s["image_bytes"]
    ]
    if missing_media:
        st.error(f"Falta imagen o video en slide{'s' if len(missing_media) > 1 else ''}: {', '.join(map(str, missing_media))}.")
        st.stop()

    from reels_gen.config import Config
    config = Config.from_env()
    _color_key = st.session_state.get("backdrop_color_key", next(iter(BACKDROP_PALETTE)))
    _bg = BACKDROP_PALETTE.get(_color_key) or _hex_to_rgb(_color_key)
    config.text_backdrop_color = (*_bg, BACKDROP_ALPHA)
    config.text_color = _text_color_for_bg(*_bg)
    config.typewriter_mode = st.session_state.get("text_mode", "Texto estático") != "Texto estático"

    if not config.hf_token:
        st.error(
            "**HF_TOKEN not set.**  \n"
            "Locally: add it to `.env`.  \n"
            "Streamlit Cloud: add it under *Settings → Secrets*."
        )
        st.stop()

    from reels_gen.frame_composer import compose_all
    from reels_gen.image_generator import generate_all
    from reels_gen.models import Phrase, Slide as SlideModel, Project
    from reels_gen.output_encoder import encode_for_instagram
    from reels_gen.video_assembler import assemble_video

    # Write uploaded images/videos to a temp directory (assets_dir)
    assets_dir = Path(tempfile.mkdtemp(prefix="reels_assets_"))
    for s in slides:
        if s["image_bytes"] and s["image_file"]:
            (assets_dir / s["image_file"]).write_bytes(s["image_bytes"])
        if s.get("video_path") and s.get("video_file") and Path(s["video_path"]).exists():
            shutil.copy(s["video_path"], assets_dir / s["video_file"])

    # Build Phrase/Slide objects directly
    slide_objs = []
    for s in slides:
        title = (s["title"] or "").strip() or None
        body  = (s["body"]  or "").strip()
        if s.get("video_file"):
            phrase = Phrase(text=body, title=title, video_file=s["video_file"], duration=float(s["duration"]))
        elif title and body:
            phrase = Phrase(text=body, title=title, image_file=s["image_file"], duration=float(s["duration"]))
        elif body:
            phrase = Phrase(text=body, image_file=s["image_file"], duration=float(s["duration"]))
        else:
            phrase = Phrase(text=title or "", body_position="center", image_file=s["image_file"], duration=float(s["duration"]))
        slide_objs.append(SlideModel(phrase=phrase))

    output_path = Path(tempfile.mktemp(suffix=".mp4", prefix="reels_out_"))
    project     = Project(slides=slide_objs, output_path=output_path)
    n = len(project.slides)

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

# ── Unsaved-changes guard ─────────────────────────────────────────────────────

import streamlit.components.v1 as components  # noqa: E402

_slides_now = st.session_state.slides
_has_content = len(_slides_now) > 1 or bool(
    _slides_now
    and (_slides_now[0]["title"] or _slides_now[0]["body"] or _slides_now[0]["image_bytes"] or _slides_now[0].get("video_path"))
)
_is_dirty = (
    _has_content
    and not st.session_state.video_bytes
    and not st.session_state.draft_saved
)

components.html(
    f"""
    <script>
    (function() {{
        if ({'true' if _is_dirty else 'false'}) {{
            window.parent.onbeforeunload = function (e) {{
                e.preventDefault();
                return e.returnValue = '';
            }};
        }} else {{
            window.parent.onbeforeunload = null;
        }}
    }})();
    </script>
    """,
    height=0,
)