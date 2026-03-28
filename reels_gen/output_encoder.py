import subprocess
from pathlib import Path
from .config import Config

def encode_for_instagram(input_path: Path, output_path: Path, config: Config) -> Path:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"scale={config.width}:{config.height},fps={config.fps}",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.0",
        "-pix_fmt", "yuv420p",
        "-b:v", config.video_bitrate,
        "-maxrate", "4000k",
        "-bufsize", "8000k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-movflags", "+faststart",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg encoding failed:\n{result.stderr}")
    return output_path
