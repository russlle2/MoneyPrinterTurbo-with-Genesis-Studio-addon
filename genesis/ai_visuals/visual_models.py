"""Genesis Studio — AI visual fill models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class VisualFillStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class MissingScene:
    scene_id: str
    section_name: str
    narration_text: str
    visual_goal: str
    shot_type: str
    reason_missing: str
    fallback_type: str
    priority: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "section_name": self.section_name,
            "narration_text": self.narration_text,
            "visual_goal": self.visual_goal,
            "shot_type": self.shot_type,
            "reason_missing": self.reason_missing,
            "fallback_type": self.fallback_type,
            "priority": self.priority,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class VisualGenerationPrompt:
    prompt_id: str
    scene_id: str
    prompt_type: str
    provider_hint: str
    prompt_text: str
    negative_prompt: str
    aspect_ratio: str
    duration_seconds: float
    style_hint: str
    intended_use: str
    safety_notes: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "scene_id": self.scene_id,
            "prompt_type": self.prompt_type,
            "provider_hint": self.provider_hint,
            "prompt_text": self.prompt_text,
            "negative_prompt": self.negative_prompt,
            "aspect_ratio": self.aspect_ratio,
            "duration_seconds": self.duration_seconds,
            "style_hint": self.style_hint,
            "intended_use": self.intended_use,
            "safety_notes": self.safety_notes,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class GeneratedVisualAsset:
    asset_id: str
    scene_id: str
    prompt_id: str
    asset_type: str
    provider: str
    path: str
    width: int
    height: int
    duration_seconds: float
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source_type: str = "generated"
    original_path: str = ""
    imported_at: str = ""
    validation_status: str = ""
    validation_warnings: list[str] = field(default_factory=list)
    assignment_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "asset_id": self.asset_id,
            "scene_id": self.scene_id,
            "prompt_id": self.prompt_id,
            "asset_type": self.asset_type,
            "provider": self.provider,
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
        if self.source_type:
            d["source_type"] = self.source_type
        if self.original_path:
            d["original_path"] = self.original_path
        if self.imported_at:
            d["imported_at"] = self.imported_at
        if self.validation_status:
            d["validation_status"] = self.validation_status
        if self.validation_warnings:
            d["validation_warnings"] = self.validation_warnings
        if self.assignment_confidence:
            d["assignment_confidence"] = self.assignment_confidence
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeneratedVisualAsset:
        fields = cls.__dataclass_fields__
        kwargs = {k: data[k] for k in fields if k in data}
        return cls(**kwargs)


@dataclass
class VisualFillResult:
    job_id: str
    missing_scenes: list[MissingScene]
    prompts: list[VisualGenerationPrompt]
    generated_assets: list[GeneratedVisualAsset]
    manifest_path: str
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "missing_scenes": [m.to_dict() for m in self.missing_scenes],
            "prompts": [p.to_dict() for p in self.prompts],
            "generated_assets": [a.to_dict() for a in self.generated_assets],
            "manifest_path": self.manifest_path,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
