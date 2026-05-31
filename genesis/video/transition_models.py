"""Genesis Studio — Transition and beat-timing models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class TransitionStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class TransitionSpec:
    transition_id: str
    transition_type: str
    duration: float
    apply_between_scene_ids: tuple[str, str]
    intensity: float = 0.5
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "transition_type": self.transition_type,
            "duration": self.duration,
            "apply_between_scene_ids": list(self.apply_between_scene_ids),
            "intensity": self.intensity,
            "reason": self.reason,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class BeatTimingResult:
    job_id: str
    audio_path: str
    duration: float
    estimated_bpm: float
    beat_times: list[float]
    confidence: float
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "audio_path": self.audio_path,
            "duration": self.duration,
            "estimated_bpm": self.estimated_bpm,
            "beat_times": self.beat_times,
            "confidence": self.confidence,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class ScenePacingDecision:
    scene_id: str
    original_start: float
    original_duration: float
    adjusted_start: float
    adjusted_duration: float
    nearest_beat: float
    pacing_reason: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "original_start": self.original_start,
            "original_duration": self.original_duration,
            "adjusted_start": self.adjusted_start,
            "adjusted_duration": self.adjusted_duration,
            "nearest_beat": self.nearest_beat,
            "pacing_reason": self.pacing_reason,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class TransitionPlan:
    job_id: str
    preset_name: str
    transitions: list[TransitionSpec]
    beat_timing: BeatTimingResult | None
    pacing_decisions: list[ScenePacingDecision]
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "preset_name": self.preset_name,
            "transitions": [t.to_dict() for t in self.transitions],
            "beat_timing": self.beat_timing.to_dict() if self.beat_timing else None,
            "pacing_decisions": [p.to_dict() for p in self.pacing_decisions],
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
