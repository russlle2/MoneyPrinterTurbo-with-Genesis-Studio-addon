"""
Genesis Studio — Review/export dataclass models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ReviewStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    FAILED = "failed"


@dataclass
class RunSummary:
    job_id: str
    run_dir: str
    created_at: str
    idea: str
    content_format: str
    platforms: list[str]
    status: str
    has_script: bool
    has_narration: bool
    has_metadata: bool
    has_storyboard: bool
    has_timeline: bool
    has_draft_video: bool
    draft_video_path: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_dir": self.run_dir,
            "created_at": self.created_at,
            "idea": self.idea,
            "content_format": self.content_format,
            "platforms": self.platforms,
            "status": self.status,
            "has_script": self.has_script,
            "has_narration": self.has_narration,
            "has_metadata": self.has_metadata,
            "has_storyboard": self.has_storyboard,
            "has_timeline": self.has_timeline,
            "has_draft_video": self.has_draft_video,
            "draft_video_path": self.draft_video_path,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class ReviewAsset:
    asset_type: str
    path: str
    exists: bool
    size_bytes: int
    modified_at: str
    notes: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_type": self.asset_type,
            "path": self.path,
            "exists": self.exists,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
            "notes": self.notes,
            "warnings": self.warnings,
        }


@dataclass
class ReviewPackage:
    job_id: str
    run_summary: RunSummary
    script_preview: str
    metadata_preview: str
    storyboard_preview: str
    video_preview_path: str
    assets: list[ReviewAsset]
    warnings: list[str] = field(default_factory=list)
    status: str = ReviewStatus.COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_summary": self.run_summary.to_dict(),
            "script_preview": self.script_preview,
            "metadata_preview": self.metadata_preview,
            "storyboard_preview": self.storyboard_preview,
            "video_preview_path": self.video_preview_path,
            "assets": [a.to_dict() for a in self.assets],
            "warnings": self.warnings,
            "status": self.status,
        }


@dataclass
class ExportPackage:
    job_id: str
    export_dir: str
    included_files: list[str]
    platform: str
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "export_dir": self.export_dir,
            "included_files": self.included_files,
            "platform": self.platform,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
