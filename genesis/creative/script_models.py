"""
Genesis Studio — Script engine dataclass models.

Pure dataclasses; no pydantic dependency. JSON-serializable via to_dict().
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

class ScriptStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


class ScriptSource:
    LOCAL_LLM = "local_llm"
    TEMPLATE_FALLBACK = "template_fallback"
    PROVIDED = "provided"


CONTENT_FORMATS: tuple[str, ...] = (
    "product_demo",
    "wellness_teaching",
    "personal_story",
    "affiliate_followup",
    "controversial_take",
    "tutorial",
    "fundraising_story",
    "motivational_walkthrough",
)

HOOK_STYLES: tuple[str, ...] = (
    "curiosity",
    "shock",
    "proof_based",
    "emotional",
    "contrarian",
    "practical",
    "story_open_loop",
    "monetization",
)

VIRAL_SPINE_SECTIONS: tuple[str, ...] = (
    "Pattern Interrupt",
    "Proof",
    "Demonstration / Teaching",
    "Meaning",
    "CTA",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class HookOption:
    """A single hook option from the hook bank."""

    text: str
    style: str       # one of HOOK_STYLES
    reason: str = ""
    score: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "style": self.style,
            "reason": self.reason,
            "score": self.score,
        }


@dataclass
class ScriptSection:
    """One section of the Viral Spine framework."""

    name: str        # one of VIRAL_SPINE_SECTIONS
    text: str
    purpose: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "text": self.text,
            "purpose": self.purpose,
        }


@dataclass
class ScriptVariant:
    """A complete script variant (primary or alternate)."""

    title: str
    duration_target: str = "30s"
    platform_fit: list[str] = field(default_factory=list)
    sections: list[ScriptSection] = field(default_factory=list)
    full_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "duration_target": self.duration_target,
            "platform_fit": self.platform_fit,
            "sections": [s.to_dict() for s in self.sections],
            "full_text": self.full_text,
        }


@dataclass
class OverlayCaption:
    """An on-screen text overlay for a specific moment in the video."""

    text: str
    timing_hint: str = ""   # e.g. "0–2s", "3–6s"
    purpose: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "timing_hint": self.timing_hint,
            "purpose": self.purpose,
        }


@dataclass
class CTAOption:
    """A call-to-action option."""

    text: str
    type: str = ""           # e.g. "comment_keyword", "link_in_bio", "save"
    platform_fit: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "type": self.type,
            "platform_fit": self.platform_fit,
        }


@dataclass
class ScriptPackage:
    """Complete script output for a single piece of content."""

    job_id: str
    idea: str
    audience: str = ""
    tone: str = "engaging"
    content_goal: str = ""
    offer: str = ""
    content_format: str = "product_demo"
    hooks: list[HookOption] = field(default_factory=list)
    primary_script: ScriptVariant = field(default_factory=lambda: ScriptVariant(title=""))
    alternate_scripts: list[ScriptVariant] = field(default_factory=list)
    overlay_captions: list[OverlayCaption] = field(default_factory=list)
    cta_options: list[CTAOption] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    status: str = ScriptStatus.COMPLETE
    script_source: str = ScriptSource.TEMPLATE_FALLBACK
    llm_backend: str | None = None
    llm_model: str | None = None
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "idea": self.idea,
            "audience": self.audience,
            "tone": self.tone,
            "content_goal": self.content_goal,
            "offer": self.offer,
            "content_format": self.content_format,
            "hooks": [h.to_dict() for h in self.hooks],
            "primary_script": self.primary_script.to_dict(),
            "alternate_scripts": [s.to_dict() for s in self.alternate_scripts],
            "overlay_captions": [c.to_dict() for c in self.overlay_captions],
            "cta_options": [c.to_dict() for c in self.cta_options],
            "notes": self.notes,
            "status": self.status,
            "script_source": self.script_source,
            "llm_backend": self.llm_backend,
            "llm_model": self.llm_model,
            "fallback_reason": self.fallback_reason,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
