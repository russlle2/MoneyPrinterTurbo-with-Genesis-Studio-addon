"""Genesis Studio — Transition plan and scene pacing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.video.beat_timing import (
    analyze_audio_beats,
    choose_cut_points_near_beats,
    validate_beat_timing,
)
from genesis.video.transition_models import (
    BeatTimingResult,
    ScenePacingDecision,
    TransitionPlan,
    TransitionSpec,
    TransitionStatus,
)
from genesis.video.transition_presets import (
    TransitionPreset,
    resolve_transition_preset,
)
from genesis.video.timeline_models import VideoTimeline

MIN_SCENE_DURATION = 1.2
MIN_CAPTION_DURATION = 1.0
MAX_PACING_SHIFT = 0.15


def choose_transition_for_scene_pair(
    preset: TransitionPreset,
    scene_a_id: str,
    scene_b_id: str,
    *,
    index: int,
    transition_duration: float | None = None,
) -> TransitionSpec:
    dur = transition_duration if transition_duration is not None else preset.default_duration
    ttype = preset.default_transition_type
    if ttype in ("quick_zoom", "slide_soft", "card_punch"):
        notes = ["may fall back to crossfade or cut in renderer"]
    else:
        notes = []
    return TransitionSpec(
        transition_id=f"tr_{index:03d}",
        transition_type=ttype,
        duration=dur,
        apply_between_scene_ids=(scene_a_id, scene_b_id),
        intensity=preset.intensity,
        reason=f"preset={preset.name}",
        notes=notes,
    )


def align_scene_boundaries_to_beats(
    timeline: VideoTimeline,
    beat_timing: BeatTimingResult | None,
    *,
    beat_sync_enabled: bool = True,
) -> list[ScenePacingDecision]:
    decisions: list[ScenePacingDecision] = []
    scene_clips = [c for c in timeline.clips if c.visual_role == "scene" or c.media_type not in ("title_card", "end_card")]
    if not scene_clips:
        scene_clips = [c for c in timeline.clips if c.media_type not in ("title_card", "end_card")]

    end_times = [c.start_time + c.duration for c in scene_clips]
    adjusted_ends = end_times
    if beat_sync_enabled and beat_timing and beat_timing.beat_times:
        adjusted_ends = choose_cut_points_near_beats(end_times, beat_timing.beat_times, max_shift=MAX_PACING_SHIFT)

    for clip, adj_end in zip(scene_clips, adjusted_ends):
        orig_dur = clip.duration
        new_dur = max(MIN_SCENE_DURATION, adj_end - clip.start_time)
        if new_dur < MIN_CAPTION_DURATION:
            new_dur = orig_dur
        nearest = 0.0
        if beat_timing and beat_timing.beat_times:
            nearest = min(beat_timing.beat_times, key=lambda b: abs(b - adj_end))
        reason = "beat-aligned" if abs(new_dur - orig_dur) > 0.01 else "unchanged"
        warnings: list[str] = []
        if new_dur < MIN_CAPTION_DURATION:
            warnings.append("caption duration too short — kept original")
            new_dur = orig_dur
        decisions.append(ScenePacingDecision(
            scene_id=clip.scene_id,
            original_start=clip.start_time,
            original_duration=orig_dur,
            adjusted_start=clip.start_time,
            adjusted_duration=new_dur,
            nearest_beat=nearest,
            pacing_reason=reason,
            warnings=warnings,
        ))
    return decisions


def adjust_scene_pacing(
    timeline: VideoTimeline,
    decisions: list[ScenePacingDecision],
) -> list[str]:
    """Apply soft pacing adjustments to timeline clips; returns warnings."""
    warnings: list[str] = []
    by_scene = {d.scene_id: d for d in decisions}
    cursor = 0.0
    for clip in timeline.clips:
        dec = by_scene.get(clip.scene_id)
        if dec and abs(dec.adjusted_duration - dec.original_duration) <= MAX_PACING_SHIFT + 0.01:
            if dec.adjusted_duration >= MIN_SCENE_DURATION:
                clip.duration = dec.adjusted_duration
            else:
                warnings.append(f"{clip.scene_id}: duration clamped")
        clip.start_time = cursor
        cursor += clip.duration
    timeline.duration = cursor
    return warnings


def validate_transition_plan(plan: TransitionPlan) -> list[str]:
    warnings: list[str] = plan.warnings[:]
    for dec in plan.pacing_decisions:
        if dec.adjusted_duration <= 0:
            warnings.append(f"{dec.scene_id}: negative duration")
        if dec.adjusted_duration < MIN_CAPTION_DURATION:
            warnings.append(f"{dec.scene_id}: very short scene for captions")
    for tr in plan.transitions:
        if tr.duration < 0:
            warnings.append(f"{tr.transition_id}: negative transition duration")
        if tr.transition_type not in (
            "cut", "crossfade", "fade_to_black", "quick_zoom", "slide_soft", "card_punch",
        ):
            warnings.append(f"{tr.transition_id}: unknown transition type {tr.transition_type}")
    if plan.beat_timing:
        warnings.extend(validate_beat_timing(plan.beat_timing))
    return list(dict.fromkeys(warnings))


def build_transition_plan(
    timeline: VideoTimeline,
    *,
    preset_name: str = "auto",
    brand_preset: str = "clean_creator",
    content_format: str = "",
    beat_sync_enabled: bool = True,
    music_audio_path: str = "",
    narration_audio_path: str = "",
    repo_root: Path | None = None,
    transition_duration: float | None = None,
) -> TransitionPlan:
    repo_root = repo_root or Path(__file__).resolve().parents[2]
    preset = resolve_transition_preset(
        preset_name, brand_preset=brand_preset, content_format=content_format,
    )

    beat: BeatTimingResult | None = None
    if beat_sync_enabled and music_audio_path:
        beat = analyze_audio_beats(
            timeline.job_id,
            music_audio_path,
            repo_root=repo_root,
            is_music=True,
            target_duration=timeline.duration,
        )
    elif beat_sync_enabled and not music_audio_path:
        beat = BeatTimingResult(
            job_id=timeline.job_id,
            audio_path="",
            duration=timeline.duration,
            estimated_bpm=0.0,
            beat_times=[],
            confidence=0.0,
            status=TransitionStatus.SKIPPED,
            notes=["no music bed — narration pacing used"],
        )

    pacing = align_scene_boundaries_to_beats(
        timeline, beat, beat_sync_enabled=beat_sync_enabled,
    )

    scene_ids = [c.scene_id for c in timeline.clips if c.media_type not in ("title_card", "end_card")]
    transitions: list[TransitionSpec] = []
    for i in range(len(scene_ids) - 1):
        transitions.append(choose_transition_for_scene_pair(
            preset, scene_ids[i], scene_ids[i + 1],
            index=i,
            transition_duration=transition_duration,
        ))

    plan = TransitionPlan(
        job_id=timeline.job_id,
        preset_name=preset.name,
        transitions=transitions,
        beat_timing=beat,
        pacing_decisions=pacing,
        status=TransitionStatus.COMPLETE,
        notes=[f"preset={preset.name}", f"transitions={len(transitions)}"],
    )
    plan.warnings = validate_transition_plan(plan)
    if plan.warnings:
        plan.status = TransitionStatus.PARTIAL
    return plan


def write_transition_plan(run_dir: Path, plan: TransitionPlan) -> Path:
    path = run_dir / "transition_plan.json"
    path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    return path


def write_beat_timing(run_dir: Path, beat: BeatTimingResult) -> Path:
    path = run_dir / "beat_timing.json"
    path.write_text(json.dumps(beat.to_dict(), indent=2), encoding="utf-8")
    return path
