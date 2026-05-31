"""Genesis Studio — Thumbnail selection models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ThumbnailStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ThumbnailCandidate:
    candidate_id: str
    source_path: str
    source_type: str          # manual | generated | video_frame | placeholder
    timestamp_seconds: float
    score: float
    reason: str
    width: int
    height: int
    aspect_ratio: str
    selected: bool = False
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_path": self.source_path,
            "source_type": self.source_type,
            "timestamp_seconds": self.timestamp_seconds,
            "score": self.score,
            "reason": self.reason,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "selected": self.selected,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class ThumbnailSelectionResult:
    job_id: str
    selected_thumbnail_path: str
    candidates: list[ThumbnailCandidate]
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "selected_thumbnail_path": self.selected_thumbnail_path,
            "candidates": [c.to_dict() for c in self.candidates],
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class ThumbnailExportResult:
    job_id: str
    platform: str
    output_path: str
    source_path: str
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "platform": self.platform,
            "output_path": self.output_path,
            "source_path": self.source_path,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
