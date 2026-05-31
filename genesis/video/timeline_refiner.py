"""
Genesis Studio — Timeline refinement: apply trims and balance scene durations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.media.media_manifest import load_media_manifest
from genesis.video.clip_trimmer import suggest_trims_for_manifest, write_trim_decisions
from genesis.video.timeline_models import TimelineClip, VideoTimeline
from genesis.video.trim_models import (
    ClipTrim,
    RefinementStatus,
    SceneTimingDecision,
    TimelineRefinementResult,
)

_TITLE_SEC = 1.0
_END_SEC = 1.5


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _scenes_from_storyboard(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    sp = storyboard.get("shot_plan", {})
    if isinstance(sp, dict):
        return list(sp.get("scenes") or [])
    return list(sp) if isinstance(sp, list) else []


def _caption_count_for_scene(timeline: VideoTimeline, scene_id: str) -> int:
    return sum(1 for c in timeline.captions if c.scene_id == scene_id)


def align_clips_to_scene_durations(
    timeline: VideoTimeline,
    scene_durations: list[float],
) -> list[float]:
    """Return balanced scene durations aligned to narration when possible."""
    scenes = timeline.scenes or []
    if not scenes:
        return scene_durations
    narr_total = 0.0
    if timeline.audio_tracks:
        narr_total = sum(a.duration for a in timeline.audio_tracks if a.duration > 0)
    if narr_total > 0 and scene_durations:
        body = max(narr_total - _TITLE_SEC - _END_SEC, sum(scene_durations))
        scale = body / (sum(scene_durations) or 1.0)
        return [max(2.0, d * scale) for d in scene_durations]
    return scene_durations


def balance_scene_durations(durations: list[float], *, min_sec: float = 2.0, max_sec: float = 12.0) -> list[float]:
    return [max(min_sec, min(max_sec, round(d, 3))) for d in durations]


def apply_trim_decisions_to_timeline(
    timeline: VideoTimeline,
    trims: list[ClipTrim],
) -> VideoTimeline:
    trim_by_scene = {t.scene_id: t for t in trims}
    for clip in timeline.clips:
        if clip.visual_role != "scene":
            continue
        t = trim_by_scene.get(clip.scene_id)
        if not t or clip.media_type not in ("video", "image"):
            continue
        if t.warnings and "unknown" in (t.reason or "").lower():
            clip.warnings = list(clip.warnings) + t.warnings
            continue
        if clip.media_type == "video" and t.end_offset > t.start_offset:
            clip.source_start = t.start_offset
            clip.source_end = t.end_offset
            clip.duration = round(t.duration or (t.end_offset - t.start_offset), 3)
            clip.trim_reason = t.reason
            clip.notes = "trimmed segment"
        elif clip.media_type == "image":
            clip.duration = round(t.duration or clip.duration, 3)
            clip.trim_reason = t.reason or "image hold"
    return timeline


def validate_refined_timeline(timeline: VideoTimeline) -> list[str]:
    warnings: list[str] = []
    for clip in timeline.clips:
        if clip.visual_role != "scene":
            continue
        if clip.media_type == "placeholder":
            warnings.append(f"{clip.scene_id}: placeholder fallback")
        if getattr(clip, "source_start", 0) and getattr(clip, "source_end", 0):
            if clip.source_end <= clip.source_start:
                warnings.append(f"{clip.scene_id}: invalid trim on timeline clip")
        if clip.duration <= 0:
            warnings.append(f"{clip.clip_id}: zero duration")
    if timeline.duration > 120:
        warnings.append("total duration exceeds 120s")
    return warnings


def refine_video_timeline(
    timeline: VideoTimeline,
    *,
    trims: list[ClipTrim] | None = None,
    scene_durations: list[float] | None = None,
) -> TimelineRefinementResult:
    scenes = timeline.scenes or []
    durs = scene_durations or []
    if not durs and scenes:
        from genesis.video.timeline_builder import estimate_scene_durations
        durs = estimate_scene_durations(scenes)
    durs = balance_scene_durations(align_clips_to_scene_durations(timeline, durs))

    if trims:
        apply_trim_decisions_to_timeline(timeline, trims)

    scene_timing: list[SceneTimingDecision] = []
    trim_by_scene = {t.scene_id: t for t in (trims or [])}
    for i, scene in enumerate(scenes):
        sid = scene.get("scene_id", f"scene_{i+1:02d}")
        target = durs[i] if i < len(durs) else 3.0
        t = trim_by_scene.get(sid)
        clip = next((c for c in timeline.clips if c.scene_id == sid), None)
        selected = clip.source_path if clip else ""
        scene_timing.append(SceneTimingDecision(
            scene_id=sid,
            target_duration=target,
            selected_asset=selected,
            trim_start=getattr(clip, "source_start", 0.0) if clip else (t.start_offset if t else 0.0),
            trim_end=getattr(clip, "source_end", 0.0) if clip else (t.end_offset if t else 0.0),
            visual_duration=clip.duration if clip else target,
            narration_duration=0.0,
            caption_count=_caption_count_for_scene(timeline, sid),
            decision_reason=t.reason if t else (clip.notes if clip else "no trim"),
            warnings=list(clip.warnings) if clip else [],
        ))

    total = timeline.duration
    if timeline.clips:
        last = timeline.clips[-1]
        total = last.start_time + last.duration

    warnings = validate_refined_timeline(timeline)
    status = RefinementStatus.COMPLETE if trims else RefinementStatus.PARTIAL
    if any("placeholder" in w for w in warnings):
        status = RefinementStatus.PARTIAL

    return TimelineRefinementResult(
        job_id=timeline.job_id,
        trim_decisions=trims or [],
        scene_timing=scene_timing,
        total_duration=round(total, 3),
        status=status,
        warnings=warnings,
        notes=[f"refined {len(trims or [])} trim(s)"],
    )


def write_timeline_refinement(run_dir: Path, result: TimelineRefinementResult) -> Path:
    path = run_dir / "timeline_refinement.json"
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path


def run_trim_for_job(
    job_id: str,
    *,
    runs_base: Path | None = None,
    repo_root: Path | None = None,
) -> tuple[list[ClipTrim], TimelineRefinementResult | None]:
    repo_root = repo_root or Path(__file__).resolve().parents[2]
    runs_base = runs_base or (repo_root / "assets" / "runs")
    run_dir = runs_base / job_id

    manifest = load_media_manifest(run_dir)
    if not manifest:
        return [], None

    storyboard = _safe_json(run_dir / "storyboard.json")
    scenes = _scenes_from_storyboard(storyboard)
    from genesis.video.timeline_builder import estimate_scene_durations
    durs = estimate_scene_durations(scenes)

    trims = suggest_trims_for_manifest(manifest, scenes, durs)
    write_trim_decisions(run_dir, trims, job_id)

    tl_data = _safe_json(run_dir / "timeline.json")
    if tl_data:
        clips = [
            TimelineClip(**{k: v for k, v in c.items() if k in TimelineClip.__dataclass_fields__})
            for c in tl_data.get("clips", [])
        ]
        timeline = VideoTimeline(
            job_id=job_id,
            clips=clips,
            scenes=scenes,
            duration=tl_data.get("duration", 0),
        )
        result = refine_video_timeline(timeline, trims=trims, scene_durations=durs)
        write_timeline_refinement(run_dir, result)
        timeline.to_json()
        (run_dir / "timeline.json").write_text(timeline.to_json(), encoding="utf-8")
        return trims, result

    return trims, None
