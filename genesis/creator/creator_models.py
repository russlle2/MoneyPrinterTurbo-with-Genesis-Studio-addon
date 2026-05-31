"""Genesis Studio — Creator run request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class CreatorStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class CreatorRunRequest:
    idea: str
    job_id: str = ""
    template: str = "affiliate_product"
    platforms: list[str] = field(default_factory=list)
    primary_platform: str = "tiktok"
    brand_preset: str = "clean_creator"
    media_path: str = ""
    music_path: str = ""
    narration_enabled: bool = True
    render_enabled: bool = True
    export_enabled: bool = False
    content_format: str = ""
    audience: str = ""
    content_goal: str = ""
    tone: str = ""
    cta: str = ""
    location: str = ""
    notes: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "idea": self.idea,
            "job_id": self.job_id,
            "template": self.template,
            "platforms": self.platforms,
            "primary_platform": self.primary_platform,
            "brand_preset": self.brand_preset,
            "media_path": self.media_path,
            "music_path": self.music_path,
            "narration_enabled": self.narration_enabled,
            "render_enabled": self.render_enabled,
            "export_enabled": self.export_enabled,
            "content_format": self.content_format,
            "audience": self.audience,
            "content_goal": self.content_goal,
            "tone": self.tone,
            "cta": self.cta,
            "notes": self.notes,
        }


@dataclass
class CreatorRunStep:
    step_name: str
    status: str
    started_at: str = ""
    completed_at: str = ""
    output_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "output_paths": self.output_paths,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class CreatorRunResult:
    job_id: str
    status: str
    run_dir: str
    draft_video_path: str
    export_dir: str
    review_html_path: str
    steps: list[CreatorRunStep]
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "run_dir": self.run_dir,
            "draft_video_path": self.draft_video_path,
            "export_dir": self.export_dir,
            "review_html_path": self.review_html_path,
            "steps": [s.to_dict() for s in self.steps],
            "warnings": self.warnings,
            "notes": self.notes,
        }
