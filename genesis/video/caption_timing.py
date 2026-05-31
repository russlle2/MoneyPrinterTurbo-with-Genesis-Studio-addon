"""
Genesis Studio — Caption cue generation for vertical draft renders.
"""

from __future__ import annotations

import re
from typing import Any

from genesis.video.timeline_models import CaptionCue, TimelineStatus

_MAX_CAPTION_CHARS = 72
_MIN_CUE_DURATION = 1.2


def split_caption_text(text: str, *, max_len: int = _MAX_CAPTION_CHARS) -> list[str]:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    if len(t) <= max_len:
        return [t]
    parts: list[str] = []
    words = t.split()
    chunk: list[str] = []
    for w in words:
        trial = " ".join(chunk + [w])
        if len(trial) > max_len and chunk:
            parts.append(" ".join(chunk))
            chunk = [w]
        else:
            chunk.append(w)
    if chunk:
        parts.append(" ".join(chunk))
    return parts[:3]


def estimate_caption_timing(
    text: str,
    start: float,
    end: float,
) -> list[tuple[str, float, float]]:
    """Split long text into timed sub-cues within [start, end]."""
    spans = split_caption_text(text)
    if not spans:
        return []
    total = max(end - start, _MIN_CUE_DURATION)
    if len(spans) == 1:
        return [(spans[0], start, end)]
    slot = total / len(spans)
    out: list[tuple[str, float, float]] = []
    t = start
    for i, line in enumerate(spans):
        e = end if i == len(spans) - 1 else min(end, t + slot)
        out.append((line, t, max(e, t + _MIN_CUE_DURATION)))
        t = e
    return out


def generate_caption_cues(
    *,
    scene_timings: list[tuple[str, str, float, float]],
    overlay_captions: list[dict[str, Any]] | None = None,
    script_sections: list[dict[str, Any]] | None = None,
) -> list[CaptionCue]:
    """
    Build caption cues from overlay captions or script sections aligned to scene timings.

    scene_timings: (scene_id, narration_text, start, end)
    """
    cues: list[CaptionCue] = []
    overlay_by_idx: dict[int, dict[str, Any]] = {}
    if overlay_captions:
        for i, cap in enumerate(overlay_captions):
            overlay_by_idx[i] = cap

    for i, (scene_id, narration, start, end) in enumerate(scene_timings):
        text = ""
        if i in overlay_by_idx:
            text = str(overlay_by_idx[i].get("text", "") or "").strip()
        if not text and narration:
            text = narration.strip()[:_MAX_CAPTION_CHARS]
        if not text and script_sections and i < len(script_sections):
            text = str(script_sections[i].get("text", ""))[:_MAX_CAPTION_CHARS]

        if not text:
            continue

        for j, (line, s, e) in enumerate(estimate_caption_timing(text, start, end)):
            warnings: list[str] = []
            if len(line) > _MAX_CAPTION_CHARS:
                warnings.append("caption trimmed for readability")
            cues.append(CaptionCue(
                cue_id=f"cue_{scene_id}_{j+1:02d}",
                scene_id=scene_id,
                text=line,
                start_time=round(s, 3),
                end_time=round(e, 3),
                placement="bottom_safe",
                style="default",
                warnings=warnings,
            ))
    return cues


def validate_caption_cues(cues: list[CaptionCue], *, total_duration: float) -> list[str]:
    warnings: list[str] = []
    for cue in cues:
        if len(cue.text) > _MAX_CAPTION_CHARS:
            warnings.append(f"{cue.cue_id}: text too long")
        if cue.end_time <= cue.start_time:
            warnings.append(f"{cue.cue_id}: invalid timing")
        if cue.end_time > total_duration + 0.5:
            warnings.append(f"{cue.cue_id}: extends past timeline")
    return warnings


def caption_timing_to_dict(cues: list[CaptionCue], job_id: str) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": TimelineStatus.COMPLETE if cues else TimelineStatus.PARTIAL,
        "cues": [c.to_dict() for c in cues],
        "safe_area": {"placement": "bottom_safe", "margin_pct": 12},
    }
