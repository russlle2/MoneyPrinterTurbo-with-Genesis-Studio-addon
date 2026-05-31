"""
Genesis Studio — Clip trim suggestions from media manifest and scene targets.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from genesis.media.media_models import MediaAsset, MediaManifest
from genesis.video.trim_models import ClipTrim, RefinementStatus

_BEGIN_ROLES = frozenset({"hook", "intro", "opening", "start", "pattern"})
_END_ROLES = frozenset({"cta", "outro", "end", "final", "result", "conclusion"})
_MIDDLE_ROLES = frozenset({"demo", "process", "demonstration", "tutorial", "walk_talk", "broll"})

_BEGIN_KW = ("hook", "intro", "opening", "start", "pattern")
_END_KW = ("cta", "outro", "end", "final", "result", "proof", "screenshot")
_MIDDLE_KW = ("demo", "process", "howto", "tutorial", "broll", "walk")


def _filename_role_bias(filename: str) -> str:
    stem = re.sub(r"[_\-\s\.]+", " ", Path(filename).stem).lower()
    if any(k in stem for k in _BEGIN_KW):
        return "begin"
    if any(k in stem for k in _END_KW):
        return "end"
    if any(k in stem for k in _MIDDLE_KW):
        return "middle"
    return "center"


def _section_bias(section_name: str, shot_type: str = "") -> str:
    s = (section_name or "").lower()
    st = (shot_type or "").lower()
    if any(k in s for k in ("hook", "intro", "interrupt", "opening")):
        return "begin"
    if any(k in s for k in ("cta", "outro", "end", "close")):
        return "end"
    if any(k in s for k in ("demo", "proof", "solution", "process")):
        return "middle"
    if st in ("product_closeup", "demonstration"):
        return "middle"
    return "center"


def estimate_best_trim_window(
    source_duration: float,
    target_duration: float,
    *,
    bias: str = "center",
) -> tuple[float, float, str]:
    if source_duration <= 0:
        return 0.0, 0.0, "unknown source duration"
    if target_duration <= 0:
        target_duration = source_duration
    if source_duration <= target_duration + 0.05:
        return 0.0, source_duration, "full clip (shorter than target)"

    excess = source_duration - target_duration
    if bias == "begin":
        start = 0.0
    elif bias == "end":
        start = max(0.0, source_duration - target_duration)
    elif bias == "middle":
        start = excess / 2.0
    else:
        start = excess / 2.0
    end = min(source_duration, start + target_duration)
    start = max(0.0, end - target_duration)
    return round(start, 3), round(end, 3), f"trim bias={bias}"


def validate_trim(start: float, end: float, source_duration: float) -> list[str]:
    warnings: list[str] = []
    if start < 0:
        warnings.append("negative start_offset")
    if end <= start:
        warnings.append("end_offset must exceed start_offset")
    if source_duration > 0 and end > source_duration + 0.01:
        warnings.append("end_offset exceeds source duration")
    return warnings


def suggest_clip_trim(
    asset: MediaAsset,
    scene_id: str,
    target_duration: float,
    *,
    section_name: str = "",
    shot_type: str = "",
) -> ClipTrim:
    src_dur = float(asset.duration_seconds or 0.0)
    bias = _filename_role_bias(asset.filename)
    sec_bias = _section_bias(section_name, shot_type)
    if sec_bias != "center":
        bias = sec_bias

    warnings: list[str] = []
    if src_dur <= 0:
        warnings.append("source duration unknown; renderer may use full file or fallback")
        return ClipTrim(
            asset_id=asset.asset_id,
            source_path=asset.stored_path,
            scene_id=scene_id,
            start_offset=0.0,
            end_offset=0.0,
            duration=target_duration,
            reason="duration unknown",
            confidence=0.3,
            warnings=warnings,
        )

    start, end, reason = estimate_best_trim_window(src_dur, target_duration, bias=bias)
    trim_warns = validate_trim(start, end, src_dur)
    warnings.extend(trim_warns)
    use_dur = end - start if end > start else min(src_dur, target_duration)

    return ClipTrim(
        asset_id=asset.asset_id,
        source_path=asset.stored_path,
        scene_id=scene_id,
        start_offset=start,
        end_offset=end,
        duration=round(use_dur, 3),
        reason=reason,
        confidence=0.85 if not warnings else 0.5,
        warnings=warnings,
    )


def suggest_trims_for_manifest(
    manifest: MediaManifest,
    scenes: list[dict[str, Any]],
    scene_durations: list[float],
) -> list[ClipTrim]:
    asset_by_path = {a.stored_path: a for a in manifest.assets}
    match_by_scene = {m.scene_id: m for m in manifest.scene_matches}
    trims: list[ClipTrim] = []

    for i, scene in enumerate(scenes):
        sid = scene.get("scene_id", f"scene_{i+1:02d}")
        target = scene_durations[i] if i < len(scene_durations) else 3.0
        sm = match_by_scene.get(sid)
        if not sm or sm.fallback_needed or not sm.selected_assets:
            continue
        path = sm.selected_assets[0]
        asset = asset_by_path.get(path)
        if not asset:
            basename = Path(path).name
            asset = next((a for a in manifest.assets if a.filename == basename), None)
        if not asset or asset.media_type not in ("video", "image"):
            continue
        if asset.media_type == "image":
            trims.append(ClipTrim(
                asset_id=asset.asset_id,
                source_path=asset.stored_path,
                scene_id=sid,
                start_offset=0.0,
                end_offset=0.0,
                duration=target,
                reason="image hold",
                confidence=0.9,
            ))
            continue
        trims.append(suggest_clip_trim(
            asset, sid, target,
            section_name=scene.get("section_name", ""),
            shot_type=scene.get("shot_type", ""),
        ))
    return trims


def write_trim_decisions(run_dir: Path, trims: list[ClipTrim], job_id: str) -> Path:
    doc = {
        "job_id": job_id,
        "trim_decisions": [t.to_dict() for t in trims],
        "status": RefinementStatus.COMPLETE if trims else RefinementStatus.SKIPPED,
    }
    path = run_dir / "trim_decisions.json"
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path
