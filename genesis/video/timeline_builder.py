"""
Genesis Studio — Build VideoTimeline from storyboard + script package.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from genesis.video.caption_timing import generate_caption_cues, validate_caption_cues
from genesis.video.media_resolver import (
    MediaAsset,
    create_placeholder_visuals_if_needed,
    match_assets_to_scenes,
)
from genesis.video.timeline_models import (
    TimelineAudio,
    TimelineClip,
    TimelineStatus,
    VideoTimeline,
)

_DEFAULT_W = 1080
_DEFAULT_H = 1920
_DEFAULT_FPS = 30
_MIN_SCENE_SEC = 2.0
_TITLE_SEC = 1.0
_END_SEC = 1.5


def _parse_resolution(resolution: str) -> tuple[int, int]:
    m = re.match(r"(\d+)x(\d+)", resolution.replace(" ", ""))
    if m:
        return int(m.group(1)), int(m.group(2))
    return _DEFAULT_W, _DEFAULT_H


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def estimate_scene_durations(
    scenes: list[dict[str, Any]],
    *,
    total_duration: float | None = None,
    target_duration: float | None = None,
) -> list[float]:
    """Proportional durations from narration word counts."""
    counts = [max(_word_count(s.get("narration_text", "")), 8) for s in scenes]
    total_words = sum(counts) or len(scenes)
    target = total_duration or target_duration or max(len(scenes) * 4.0, 15.0)
    body = max(target - _TITLE_SEC - _END_SEC, len(scenes) * _MIN_SCENE_SEC)
    durations = [max(_MIN_SCENE_SEC, body * (c / total_words)) for c in counts]
    return durations


def align_narration_to_scenes(
    narration_duration: float,
    scene_durations: list[float],
) -> list[float]:
    """Scale scene durations to fit narration length (excluding title/end padding)."""
    if narration_duration <= 0:
        return scene_durations
    body_target = max(narration_duration - _TITLE_SEC - _END_SEC, len(scene_durations) * _MIN_SCENE_SEC)
    current = sum(scene_durations) or 1.0
    scale = body_target / current
    return [max(_MIN_SCENE_SEC, d * scale) for d in scene_durations]


def _audio_duration_seconds(path: Path) -> float:
    if not path.is_file():
        return 0.0
    try:
        from moviepy import AudioFileClip
        with AudioFileClip(str(path)) as clip:
            return float(clip.duration or 0)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def assign_media_to_timeline(
    scenes: list[dict[str, Any]],
    scene_durations: list[float],
    *,
    asset_map: dict[str, MediaAsset],
    placeholder_plan: Any,
    start_offset: float = _TITLE_SEC,
) -> list[TimelineClip]:
    clips: list[TimelineClip] = []
    t = start_offset
    ph_by_id = {p["scene_id"]: p for p in getattr(placeholder_plan, "placeholders", [])}

    for i, scene in enumerate(scenes):
        sid = scene.get("scene_id", f"scene_{i+1:02d}")
        dur = scene_durations[i] if i < len(scene_durations) else _MIN_SCENE_SEC
        asset = asset_map.get(sid)
        if asset and asset.media_type in ("video", "image"):
            source = asset.path
            media_type = asset.media_type
            notes = "user media"
        else:
            ph = ph_by_id.get(sid, {})
            source = ph.get("planned_path", "")
            media_type = "placeholder"
            notes = "generated placeholder card"

        clips.append(TimelineClip(
            clip_id=f"clip_{sid}",
            scene_id=sid,
            source_path=source,
            media_type=media_type,
            start_time=round(t, 3),
            duration=round(dur, 3),
            visual_role="scene",
            crop_mode="cover",
            caption_text=(scene.get("overlay_text") or "")[:120],
            notes=notes,
        ))
        t += dur
    return clips


def assign_captions_to_timeline(
    timeline: VideoTimeline,
    cues: list[Any],
) -> VideoTimeline:
    timeline.captions = list(cues)
    return timeline


def validate_timeline(timeline: VideoTimeline) -> list[str]:
    warnings: list[str] = []
    if timeline.aspect_ratio != "9:16":
        warnings.append(f"non-vertical aspect ratio: {timeline.aspect_ratio}")
    w, h = _parse_resolution(timeline.resolution)
    if h <= w:
        warnings.append("resolution is not vertical")
    if not timeline.clips:
        warnings.append("timeline has no clips")
    expected_end = 0.0
    for clip in timeline.clips:
        if clip.duration <= 0:
            warnings.append(f"{clip.clip_id}: zero duration")
        if clip.start_time < expected_end - 0.01:
            warnings.append(f"{clip.clip_id}: overlapping start")
        expected_end = clip.start_time + clip.duration
    if timeline.duration and abs(expected_end - timeline.duration) > 2.0:
        warnings.append("timeline duration mismatch vs clip spans")
    warnings.extend(validate_caption_cues(timeline.captions, total_duration=timeline.duration))
    return warnings


def build_video_timeline(
    *,
    job_id: str,
    storyboard: dict[str, Any],
    script_package: dict[str, Any] | None = None,
    overlay_captions: list[dict[str, Any]] | None = None,
    narration_path: str = "",
    media_assets: list[MediaAsset] | None = None,
    run_dir: Path | None = None,
    repo_root: Path | None = None,
    target_platform: str = "tiktok",
    target_duration: float | None = None,
) -> VideoTimeline:
    """Assemble VideoTimeline from run package data."""
    repo_root = repo_root or Path(__file__).resolve().parents[2]
    shot_plan = storyboard.get("shot_plan", {})
    scenes = shot_plan.get("scenes", [])
    if not scenes:
        return VideoTimeline(
            job_id=job_id,
            status=TimelineStatus.PARTIAL,
            warnings=["no storyboard scenes"],
        )

    w, h = _DEFAULT_W, _DEFAULT_H
    narration_dur = 0.0
    audio_tracks: list[TimelineAudio] = []
    if narration_path:
        abs_narr = repo_root / narration_path if not Path(narration_path).is_absolute() else Path(narration_path)
        narration_dur = _audio_duration_seconds(abs_narr)
        if narration_dur > 0:
            audio_tracks.append(TimelineAudio(
                source_path=narration_path,
                start_time=_TITLE_SEC,
                duration=narration_dur,
                audio_role="narration",
            ))

    scene_durs = estimate_scene_durations(scenes, total_duration=narration_dur or target_duration)
    if narration_dur > 0:
        scene_durs = align_narration_to_scenes(narration_dur, scene_durs)

    asset_map = match_assets_to_scenes(scenes, media_assets or [])
    ph_plan = create_placeholder_visuals_if_needed(
        run_dir or (repo_root / "assets" / "runs" / job_id),
        scenes,
        repo_root=repo_root,
    )

    clips: list[TimelineClip] = []

    # Title card
    hook = storyboard.get("primary_hook", "")[:80]
    clips.append(TimelineClip(
        clip_id="clip_title",
        scene_id="title",
        source_path="",
        media_type="title_card",
        start_time=0.0,
        duration=_TITLE_SEC,
        visual_role="title",
        caption_text=hook,
        notes="auto title card",
    ))

    clips.extend(assign_media_to_timeline(
        scenes, scene_durs, asset_map=asset_map, placeholder_plan=ph_plan
    ))

    # End card CTA
    cta = ""
    if script_package:
        opts = script_package.get("cta_options") or []
        if opts:
            cta = str(opts[0].get("text", ""))[:80]
    end_start = clips[-1].start_time + clips[-1].duration if clips else _TITLE_SEC
    clips.append(TimelineClip(
        clip_id="clip_end",
        scene_id="end",
        source_path="",
        media_type="end_card",
        start_time=round(end_start, 3),
        duration=_END_SEC,
        visual_role="cta",
        caption_text=cta,
        notes="auto end card",
    ))

    total_duration = end_start + _END_SEC

    scene_timings: list[tuple[str, str, float, float]] = []
    scene_idx = 0
    for c in clips:
        if c.visual_role != "scene":
            continue
        narr = scenes[scene_idx].get("narration_text", "") if scene_idx < len(scenes) else ""
        scene_timings.append((c.scene_id, narr, c.start_time, c.start_time + c.duration))
        scene_idx += 1

    sections = []
    if script_package:
        ps = script_package.get("primary_script") or {}
        sections = ps.get("sections") or []

    cues = generate_caption_cues(
        scene_timings=scene_timings,
        overlay_captions=overlay_captions,
        script_sections=sections,
    )

    timeline = VideoTimeline(
        job_id=job_id,
        aspect_ratio="9:16",
        resolution=f"{w}x{h}",
        fps=_DEFAULT_FPS,
        duration=round(total_duration, 3),
        clips=clips,
        audio_tracks=audio_tracks,
        captions=cues,
        scenes=scenes,
        status=TimelineStatus.COMPLETE,
        notes=[f"target_platform={target_platform}", f"placeholders={len(ph_plan.placeholders)}"],
    )
    timeline.warnings = validate_timeline(timeline)
    return timeline
