"""
Genesis Studio — Media ingestion dataclass models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MediaStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class MediaAsset:
    asset_id: str
    source_path: str
    stored_path: str
    filename: str
    media_type: str          # video / image / audio / unknown
    extension: str
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    aspect_ratio: str
    orientation: str         # vertical / horizontal / square / unknown
    tags: list[str] = field(default_factory=list)
    inferred_role: str = ""  # product_closeup / broll / demonstration / etc.
    scene_match: str = ""    # matched scene_id
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source_path": self.source_path,
            "stored_path": self.stored_path,
            "filename": self.filename,
            "media_type": self.media_type,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "orientation": self.orientation,
            "tags": self.tags,
            "inferred_role": self.inferred_role,
            "scene_match": self.scene_match,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class MediaIngestResult:
    job_id: str
    intake_paths: list[str]
    stored_assets: list[MediaAsset]
    skipped_files: list[str]
    errors: list[str]
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "intake_paths": self.intake_paths,
            "stored_assets": [a.to_dict() for a in self.stored_assets],
            "skipped_files": self.skipped_files,
            "errors": self.errors,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class SceneMediaMatch:
    scene_id: str
    section_name: str
    selected_assets: list[str]   # stored_path values
    fallback_needed: bool
    confidence: float            # 0.0–1.0
    reason: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "section_name": self.section_name,
            "selected_assets": self.selected_assets,
            "fallback_needed": self.fallback_needed,
            "confidence": self.confidence,
            "reason": self.reason,
            "warnings": self.warnings,
        }


@dataclass
class MediaManifest:
    job_id: str
    media_dir: str
    assets: list[MediaAsset]
    scene_matches: list[SceneMediaMatch]
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "media_dir": self.media_dir,
            "assets": [a.to_dict() for a in self.assets],
            "scene_matches": [m.to_dict() for m in self.scene_matches],
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
