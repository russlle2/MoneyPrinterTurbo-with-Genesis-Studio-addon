"""
Genesis Studio — Visual storyboard dataclass models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class StoryboardStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class VisualScene:
    scene_id: str
    section_name: str
    narration_text: str
    visual_goal: str
    shot_type: str
    camera_direction: str
    subject_action: str
    broll_suggestions: list[str] = field(default_factory=list)
    overlay_text: str | None = None
    timing_hint: str = ""
    props_needed: list[str] = field(default_factory=list)
    location_notes: str | None = None
    editing_notes: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "section_name": self.section_name,
            "narration_text": self.narration_text,
            "visual_goal": self.visual_goal,
            "shot_type": self.shot_type,
            "camera_direction": self.camera_direction,
            "subject_action": self.subject_action,
            "broll_suggestions": self.broll_suggestions,
            "overlay_text": self.overlay_text,
            "timing_hint": self.timing_hint,
            "props_needed": self.props_needed,
            "location_notes": self.location_notes,
            "editing_notes": self.editing_notes,
            "risk_notes": self.risk_notes,
        }


@dataclass
class ShotPlan:
    job_id: str
    content_format: str
    visual_style: str
    scenes: list[VisualScene] = field(default_factory=list)
    broll_plan: list[str] = field(default_factory=list)
    required_props: list[str] = field(default_factory=list)
    filming_locations: list[str] = field(default_factory=list)
    audio_notes: list[str] = field(default_factory=list)
    lighting_notes: list[str] = field(default_factory=list)
    editing_notes: list[str] = field(default_factory=list)
    status: str = StoryboardStatus.COMPLETE
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "content_format": self.content_format,
            "visual_style": self.visual_style,
            "scenes": [s.to_dict() for s in self.scenes],
            "broll_plan": self.broll_plan,
            "required_props": self.required_props,
            "filming_locations": self.filming_locations,
            "audio_notes": self.audio_notes,
            "lighting_notes": self.lighting_notes,
            "editing_notes": self.editing_notes,
            "status": self.status,
            "warnings": self.warnings,
        }


@dataclass
class VisualPrompt:
    prompt_id: str
    scene_id: str
    prompt_type: str
    prompt_text: str
    negative_prompt: str | None = None
    intended_use: str = ""
    provider_hint: str = "manual"
    safety_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "scene_id": self.scene_id,
            "prompt_type": self.prompt_type,
            "prompt_text": self.prompt_text,
            "negative_prompt": self.negative_prompt,
            "intended_use": self.intended_use,
            "provider_hint": self.provider_hint,
            "safety_notes": self.safety_notes,
        }


@dataclass
class StoryboardPackage:
    job_id: str
    idea: str
    content_format: str
    primary_hook: str
    visual_style: str
    shot_plan: ShotPlan
    visual_prompts: list[VisualPrompt] = field(default_factory=list)
    filming_checklist: list[str] = field(default_factory=list)
    editing_checklist: list[str] = field(default_factory=list)
    status: str = StoryboardStatus.COMPLETE
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "idea": self.idea,
            "content_format": self.content_format,
            "primary_hook": self.primary_hook,
            "visual_style": self.visual_style,
            "shot_plan": self.shot_plan.to_dict(),
            "visual_prompts": [p.to_dict() for p in self.visual_prompts],
            "filming_checklist": self.filming_checklist,
            "editing_checklist": self.editing_checklist,
            "status": self.status,
            "notes": self.notes,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
