"""
Genesis Studio — Clip trim and timeline refinement dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class RefinementStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ClipTrim:
    asset_id: str
    source_path: str
    scene_id: str
    start_offset: float
    end_offset: float
    duration: float
    reason: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source_path": self.source_path,
            "scene_id": self.scene_id,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "duration": self.duration,
            "reason": self.reason,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class SceneTimingDecision:
    scene_id: str
    target_duration: float
    selected_asset: str
    trim_start: float
    trim_end: float
    visual_duration: float
    narration_duration: float
    caption_count: int
    decision_reason: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "target_duration": self.target_duration,
            "selected_asset": self.selected_asset,
            "trim_start": self.trim_start,
            "trim_end": self.trim_end,
            "visual_duration": self.visual_duration,
            "narration_duration": self.narration_duration,
            "caption_count": self.caption_count,
            "decision_reason": self.decision_reason,
            "warnings": self.warnings,
        }


@dataclass
class TimelineRefinementResult:
    job_id: str
    trim_decisions: list[ClipTrim]
    scene_timing: list[SceneTimingDecision]
    total_duration: float
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "trim_decisions": [t.to_dict() for t in self.trim_decisions],
            "scene_timing": [s.to_dict() for s in self.scene_timing],
            "total_duration": self.total_duration,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
