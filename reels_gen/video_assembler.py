from pathlib import Path
from moviepy import ImageClip, VideoClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx import CrossFadeIn
from .frame_composer import make_image_typewriter_func, make_video_overlay_typewriter_func
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
    duration = slide.phrase.duration or config.slide_duration

    if slide.video_path is not None:
        video = VideoFileClip(str(slide.video_path)).without_audio()
        video = _cover_crop_video(video, config.width, config.height)
        if slide.phrase.duration and slide.phrase.duration < video.duration:
            video = video.subclipped(0, slide.phrase.duration)
        video = video.with_fps(config.fps)
        dur = video.duration

        if config.typewriter_mode:
            make_rgba = make_video_overlay_typewriter_func(slide, config, dur)
            _slot: list = [None, None]  # [last_t, last_rgba] — avoids double PIL render per frame

            def _cached_rgba(t, _s=_slot, _f=make_rgba):
                if _s[0] != t:
                    _s[0], _s[1] = t, _f(t)
                return _s[1]

            overlay = VideoClip(lambda t: _cached_rgba(t)[:, :, :3], duration=dur)
            mask = VideoClip(lambda t: _cached_rgba(t)[:, :, 3] / 255.0, duration=dur, is_mask=True)
            overlay = overlay.with_mask(mask)
            return CompositeVideoClip([video, overlay])

        if slide.frame_path is not None:
            overlay = ImageClip(str(slide.frame_path)).with_duration(dur)
            return CompositeVideoClip([video, overlay])
        return video

    if config.typewriter_mode:
        make_frame = make_image_typewriter_func(slide, config, duration)
        return VideoClip(make_frame, duration=duration).with_fps(config.fps)

    return ImageClip(str(slide.frame_path), duration=duration).with_fps(config.fps)


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
