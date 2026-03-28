# Next Steps: Streamlit UI — Slide Builder

Una UI web local con un editor de slides tipo carrusel, sin exponer el formato `.txt` interno al usuario.

## Archivos a crear/modificar

| Archivo | Acción |
|---|---|
| `app.py` | Crear — UI Streamlit principal |
| `reels_gen/image_generator.py` | Agregar parámetro `assets_images_dir` a `generate_all` |
| `pyproject.toml` | Agregar `streamlit>=1.35.0` a dependencies |

La pipeline existente (`image_generator`, `frame_composer`, `video_assembler`, `output_encoder`) no se toca — se reutiliza igual que en `cli.py`.

## UI layout

```
┌─────────────────────────────────────────────────────┐
│  🎬 Reels Generator                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ◀  Slide 2 / 4  ▶                    [ + Slide ]  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  Título   [___________________________]       │  │
│  │  Body     [___________________________]       │  │
│  │           [___________________________]       │  │
│  │  Imagen   [ Subir imagen (PNG/JPG) ▼ ]       │  │
│  │  Duración [2.5] s                             │  │
│  │                                    [ 🗑 ] │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│              [ ▶ Generar Reel ]                     │
│                                                     │
│  Stage 1/3: Generando imágenes…                     │
│  [████████░░] 3/4                                   │
│                                                     │
│  ✓ Listo → [ ⬇ Descargar reel.mp4 ]               │
└─────────────────────────────────────────────────────┘
```

## Estado en `st.session_state`

```python
# Estructura de cada slide
slide = {
    "title": str,          # requerido
    "body": str,           # opcional — si vacío → <title center>
    "image_file": str,     # nombre del archivo subido, o "" para generar con AI
    "image_bytes": bytes,  # contenido del archivo subido
    "duration": float,     # default: config.slide_duration
}

# Estado global
st.session_state.slides: list[dict]   # lista de slides
st.session_state.current: int         # índice del slide visible
st.session_state.music_bytes: bytes   # MP3 opcional
```

## Navegación del carrusel

- `◀ ▶` cambian `st.session_state.current` (con `st.rerun()`)
- `[ + Slide ]` appends un slide vacío y navega al nuevo
- `[ 🗑 ]` elimina el slide actual (si queda más de 1)
- El slide actual se renderiza completo con sus widgets
- Los otros slides existen en session_state pero no se renderizan

## Conversión a formato interno `.txt`

`_slides_to_txt(slides) -> str` — genera el string que el parser existente consume:

```python
def _slides_to_txt(slides: list[dict]) -> str:
    lines = []
    for s in slides:
        title = s["title"].strip()
        body  = s["body"].strip()
        img   = s["image_file"].strip()

        if img:
            lines.append(f"<image>{img}</image>")

        if body:
            lines.append(f"<title>{title}</title>")
            lines.append(f"<body>{body}</body>")
        else:
            lines.append(f"<title center>{title}</title>")

        lines.append("")   # blank line entre slides
    return "\n".join(lines)
```

Esta función se llama en el botón "Generar", su output se pasa al parser existente (`_parse_txt`), y desde ahí la pipeline sigue igual que en `cli.py`.

## Flujo completo al generar

1. `_slides_to_txt(slides)` → string en formato `.txt`
2. `_parse_txt(content)` (parser existente) → `list[Phrase]`
3. Imágenes subidas se guardan en un `tempfile.mkdtemp()` → `assets_images_dir`
4. `Config.from_env()` con `slide_duration` por slide (o global si todos son iguales)
5. Pipeline normal con callbacks de progreso → `st.progress` + `st.status`
6. Output → `tempfile.mktemp(suffix=".mp4")` → `st.download_button`

## Cambio en `image_generator.py`

`generate_all` necesita aceptar un directorio de imágenes override para las subidas por la UI:

```python
def generate_all(slides, work_dir, config, progress_callback=None, assets_images_dir=None):
    images_dir = assets_images_dir or ASSETS_IMAGES_DIR
    ...
    local = images_dir / slide.phrase.image_file
```

## Duración por slide vs global

- `Config` tiene `slide_duration: float` (default global)
- Cada slide en la UI tiene su propio campo de duración (pre-poblado con el default)
- Al generar, si todos los slides tienen la misma duración → se usa como global en `Config`
- Si hay duraciones mixtas → se necesita pasar por slide (ver si `Phrase` soporta duration o si hay que agregarlo)
- **Decisión pendiente**: ¿agregar `duration` a `Phrase` en `models.py`? Revisar antes de implementar.

## Cómo correrla

```bash
source .venv/bin/activate
streamlit run app.py
# abre http://localhost:8501 en el browser
```