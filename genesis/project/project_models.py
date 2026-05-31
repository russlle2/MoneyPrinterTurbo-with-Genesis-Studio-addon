"""Genesis Studio — Project history and batch run models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ProjectStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class ProjectRunRecord:
    job_id: str
    idea: str
    template: str
    primary_platform: str
    platforms: list[str]
    brand_preset: str
    status: str
    run_dir: str
    draft_video_path: str
    export_dir: str
    review_html_path: str
    created_at: str
    updated_at: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "idea": self.idea,
            "template": self.template,
            "primary_platform": self.primary_platform,
            "platforms": self.platforms,
            "brand_preset": self.brand_preset,
            "status": self.status,
            "run_dir": self.run_dir,
            "draft_video_path": self.draft_video_path,
            "export_dir": self.export_dir,
            "review_html_path": self.review_html_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class ProjectIndex:
    index_path: str
    runs: list[ProjectRunRecord]
    last_updated: str
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index_path": self.index_path,
            "runs": [r.to_dict() for r in self.runs],
            "last_updated": self.last_updated,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class BatchRunItem:
    idea: str
    job_id: str = ""
    template: str = "affiliate_product"
    platform: str = "tiktok"
    brand: str = ""
    media_path: str = ""
    music_path: str = ""
    export_enabled: bool = False
    narration_enabled: bool = True
    render_enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)
    status: str = ProjectStatus.PENDING
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "idea": self.idea,
            "job_id": self.job_id,
            "template": self.template,
            "platform": self.platform,
            "brand": self.brand,
            "media_path": self.media_path,
            "music_path": self.music_path,
            "export_enabled": self.export_enabled,
            "narration_enabled": self.narration_enabled,
            "render_enabled": self.render_enabled,
            "options": self.options,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class BatchRunResult:
    batch_id: str
    status: str
    items: list[BatchRunItem]
    completed: int
    partial: int
    failed: int
    skipped: int
    output_path: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "items": [i.to_dict() for i in self.items],
            "completed": self.completed,
            "partial": self.partial,
            "failed": self.failed,
            "skipped": self.skipped,
            "output_path": self.output_path,
            "warnings": self.warnings,
            "notes": self.notes,
        }
