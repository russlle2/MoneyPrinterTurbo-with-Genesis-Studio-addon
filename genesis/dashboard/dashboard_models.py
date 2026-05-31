"""Genesis Studio — Dashboard data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DashboardStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class DashboardRunCard:
    job_id: str
    idea: str
    template: str
    status: str
    primary_platform: str
    brand_preset: str
    run_dir: str
    draft_video_path: str
    thumbnail_path: str
    review_html_path: str
    export_dir: str
    has_media_manifest: bool
    matched_scene_count: int
    total_scene_count: int
    placeholder_scene_count: int
    has_audio_mix: bool
    has_export: bool
    transition_preset: str = ""
    beat_sync_status: str = ""
    missing_scene_count: int = 0
    generated_visual_count: int = 0
    manual_import_count: int = 0
    validation_warning_count: int = 0
    readiness_label: str = ""
    quality_score: int = 0
    quality_badge: str = ""
    warnings: list[str] = field(default_factory=list)
    suggested_commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "idea": self.idea,
            "template": self.template,
            "status": self.status,
            "primary_platform": self.primary_platform,
            "brand_preset": self.brand_preset,
            "run_dir": self.run_dir,
            "draft_video_path": self.draft_video_path,
            "thumbnail_path": self.thumbnail_path,
            "review_html_path": self.review_html_path,
            "export_dir": self.export_dir,
            "has_media_manifest": self.has_media_manifest,
            "matched_scene_count": self.matched_scene_count,
            "total_scene_count": self.total_scene_count,
            "placeholder_scene_count": self.placeholder_scene_count,
            "has_audio_mix": self.has_audio_mix,
            "has_export": self.has_export,
            "transition_preset": self.transition_preset,
            "beat_sync_status": self.beat_sync_status,
            "missing_scene_count": self.missing_scene_count,
            "generated_visual_count": self.generated_visual_count,
            "manual_import_count": self.manual_import_count,
            "validation_warning_count": self.validation_warning_count,
            "readiness_label": self.readiness_label,
            "quality_score": self.quality_score,
            "quality_badge": self.quality_badge,
            "warnings": self.warnings,
            "suggested_commands": self.suggested_commands,
            "notes": self.notes,
        }


@dataclass
class DashboardSummary:
    generated_at: str
    total_runs: int
    complete_runs: int
    partial_runs: int
    failed_runs: int
    missing_video_runs: int
    ready_to_export_runs: int
    runs_with_placeholders: int
    runs: list[DashboardRunCard]
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_runs": self.total_runs,
            "complete_runs": self.complete_runs,
            "partial_runs": self.partial_runs,
            "failed_runs": self.failed_runs,
            "missing_video_runs": self.missing_video_runs,
            "ready_to_export_runs": self.ready_to_export_runs,
            "runs_with_placeholders": self.runs_with_placeholders,
            "runs": [r.to_dict() for r in self.runs],
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class DashboardBuildResult:
    output_path: str
    thumbnail_dir: str
    cards: list[DashboardRunCard]
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": self.output_path,
            "thumbnail_dir": self.thumbnail_dir,
            "cards": [c.to_dict() for c in self.cards],
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
