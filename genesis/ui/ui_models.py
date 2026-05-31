"""Genesis Studio UI — data models for UI state and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UICreateRequest:
    """Fields collected from the Create Video form."""
    idea: str
    job_id: str = ""
    template: str = "affiliate_product"
    platform: str = "tiktok"
    brand: str = "clean_creator"
    duration: str = "30 seconds"
    audience: str = ""
    cta: str = ""
    tone: str = ""
    media_path: str = ""
    music_path: str = ""
    thumbnail_path: str = ""
    narration: bool = True
    use_local_llm: bool = False
    ai_visual_fill: bool = False
    import_visuals: bool = False
    select_thumbnail: bool = True
    quality_check: bool = True
    strict_quality: bool = False
    export: bool = True
    use_music: bool = False
    transitions: bool = True
    motion_effects: bool = True
    render_enabled: bool = True


@dataclass
class UIActionResult:
    """Result returned from any UI action."""
    success: bool
    job_id: str = ""
    status: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    output_paths: dict[str, str] = field(default_factory=dict)
    preview_paths: dict[str, str] = field(default_factory=dict)
    readiness_label: str = ""
    quality_score: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "job_id": self.job_id,
            "status": self.status,
            "message": self.message,
            "warnings": self.warnings,
            "output_paths": self.output_paths,
            "readiness_label": self.readiness_label,
            "quality_score": self.quality_score,
            "error": self.error,
        }
