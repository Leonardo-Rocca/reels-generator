import hashlib
import time
from pathlib import Path
from typing import Callable

import httpx

from .config import Config
from .models import Slide

HF_API_URL = "https://router.huggingface.co/hf-inference/models/{model}"

def _prompt_hash(text: str, model: str) -> str:
    return hashlib.md5(f"{model}:{text}".encode()).hexdigest()[:12]

def generate_image(slide: Slide, work_dir: Path, config: Config) -> Path:
    image_prompt = slide.phrase.image_prompt or slide.phrase.text
    prompt = f"{image_prompt}, {config.image_style_suffix}"
    cache_name = f"img_{_prompt_hash(image_prompt, config.hf_model)}.png"
    cache_path = work_dir / cache_name

    if cache_path.exists():
        return cache_path

    url = HF_API_URL.format(model=config.hf_model)
    headers = {"Authorization": f"Bearer {config.hf_token}"}
    payload = {
        "inputs": prompt,
        "parameters": {"num_inference_steps": 25, "guidance_scale": 7.5}
    }

    for attempt in range(3):
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=120.0)
            if response.status_code == 503:  # model loading
                wait = int(response.json().get("estimated_time", 20))
                time.sleep(min(wait, 30))
                continue
            if response.status_code == 402:
                raise RuntimeError(
                    f"Model '{config.hf_model}' requires a paid HuggingFace plan. "
                    "HuggingFace's serverless inference API now charges for image generation models. "
                    "Upgrade your HF plan at huggingface.co/pricing or switch to another provider."
                )
            response.raise_for_status()
            cache_path.write_bytes(response.content)
            return cache_path
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))

    raise RuntimeError(f"Failed to generate image for: {slide.phrase.text}")

ASSETS_IMAGES_DIR = Path(__file__).parent.parent / "assets" / "images"

def generate_all(slides: list[Slide], work_dir: Path, config: Config, progress_callback: Callable[[int, int], None] | None = None) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    for i, slide in enumerate(slides):
        if slide.phrase.image_file:
            local = ASSETS_IMAGES_DIR / slide.phrase.image_file
            if not local.exists():
                raise FileNotFoundError(f"Image not found: {local}")
            slide.image_path = local
        else:
            slide.image_path = generate_image(slide, work_dir, config)
        if progress_callback:
            progress_callback(i + 1, len(slides))
