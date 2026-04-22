import os
from typing import Self

from pydantic import BaseModel

class Config(BaseModel):
    # Output
    width: int = 1080
    height: int = 1920
    fps: int = 30

    # Timing
    slide_duration: float = 3.0  # seconds per slide
    transition_duration: float = 0.2

    # Text styling
    font_size: int = 72
    text_color: str = "white"
    text_position: str = "bottom"  # "top", "center", "bottom"
    text_backdrop_color: tuple[int, int, int, int] = (20, 10, 45, 170)  # RGBA deep navy-purple
    # text_backdrop_color: Los primeros 3 valores son RGB y el 4to es la opacidad (0=transparente, 255=sólido):
    # - Más morado: (40, 10, 60, 180)
    # - Más azul: (10, 15, 50, 180)
    # - Más transparente: bajar el 4to valor a 120
    text_backdrop_padding_x: int = 48  # horizontal padding inside backdrop
    text_backdrop_padding_y: int = 44  # vertical padding inside backdrop
    text_edge_margin: int = 490       # distance from the frame top/bottom edges


    # Image generation
    hf_token: str = ""
    hf_model: str = "stabilityai/stable-diffusion-xl-base-1.0"
    image_style_suffix: str = "mystical atmosphere, cinematic lighting, highcontrast, photorealistic, 8k"
    # image_style_suffix: str = "mystical cosmic atmosphere, deep navy and purple tones, starry night sky, ethereal moonlight, celestial symbols, dark moody background, cinematic lighting, highcontrast, photorealistic, 8k"
    # image_style_suffix: str = "cinematic, high quality, vibrant colors, sharp focus"
    # image_style_suffix: str = "dark mystical illustration, deep indigo and violet palette, crescent moon, scattered stars, nebula background, soft glowing light, elegant and spiritual mood, artstation quality"

    # Logo overlay
    logo_max_width: int = 560     # px
    logo_margin: int = 1         # distance from right edge
    logo_margin_y: int = -290       # distance from bottom edge (use negative to push further down/off-screen)
    logo_opacity: float = 0.65    # 0.0 = invisible, 1.0 = fully opaque

    # Video
    video_bitrate: str = "3500k"

    @classmethod
    def from_env(cls) -> Self:
        return cls(hf_token=os.getenv("HF_TOKEN", ""))
