from pathlib import Path
from moviepy import ImageClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx import CrossFadeIn
from .models import Project, Slide
from .config import Config


def _cover_crop_video(clip: VideoFileClip, target_w: int, target_h: int) -> VideoFileClip:
    vw, vh = clip.size
    scale = max(target_w / vw, target_h / vh)
    new_w, new_h = round(vw * scale), round(vh * scale)
    clip = clip.resized((new_w, new_h))
    x1 = (new_w - target_w) // 2
    y1 = (new_h - target_h) // 2
    return clip.cropped(x1=x1, y1=y1, x2=x1 + target_w, y2=y1 + target_h)


def _make_clip(slide: Slide, config: Config):
    if slide.video_path is not None:
        video = VideoFileClip(str(slide.video_path)).without_audio()
        video = _cover_crop_video(video, config.width, config.height)
        video = video.with_fps(config.fps)
        if slide.frame_path is not None:
            overlay = ImageClip(str(slide.frame_path)).with_duration(video.duration)
            return CompositeVideoClip([video, overlay])
        return video
    clip = ImageClip(str(slide.frame_path), duration=slide.phrase.duration or config.slide_duration)
    return clip.with_fps(config.fps)


def assemble_video(project: Project, config: Config, intermediate_path: Path) -> Path:
    clips = []
    for slide in project.slides:
        clips.append(_make_clip(slide, config))

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
