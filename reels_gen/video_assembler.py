from pathlib import Path
from moviepy import ImageClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx import CrossFadeIn
from .models import Project
from .config import Config

def assemble_video(project: Project, config: Config, intermediate_path: Path) -> Path:
    clips = []
    for slide in project.slides:
        clip = ImageClip(str(slide.frame_path), duration=slide.phrase.duration or config.slide_duration)
        clip = clip.with_fps(config.fps)
        clips.append(clip)

    # Crossfade transitions
    if len(clips) > 1 and config.transition_duration > 0:
        final_clips = [clips[0]]
        for clip in clips[1:]:
            clip = clip.with_start(final_clips[-1].end - config.transition_duration)
            clip = clip.with_effects([CrossFadeIn(config.transition_duration)])
            final_clips.append(clip)
        video = CompositeVideoClip(final_clips)
    else:
        video = concatenate_videoclips(clips)

    video.write_videofile(
        str(intermediate_path),
        fps=config.fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    return intermediate_path
