"""Genesis Studio — Transition preset definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TransitionPreset:
    name: str
    default_transition_type: str
    default_duration: float
    intensity: float
    recommended_content_formats: list[str]
    recommended_brand_presets: list[str]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "default_transition_type": self.default_transition_type,
            "default_duration": self.default_duration,
            "intensity": self.intensity,
            "recommended_content_formats": self.recommended_content_formats,
            "recommended_brand_presets": self.recommended_brand_presets,
            "notes": self.notes,
        }


PRESETS: dict[str, TransitionPreset] = {
    "simple_cuts": TransitionPreset(
        name="simple_cuts",
        default_transition_type="cut",
        default_duration=0.0,
        intensity=0.0,
        recommended_content_formats=["tutorial", "personal_story"],
        recommended_brand_presets=["minimal_white"],
        notes="Hard cuts only; fastest pacing.",
    ),
    "soft_fade": TransitionPreset(
        name="soft_fade",
        default_transition_type="crossfade",
        default_duration=0.25,
        intensity=0.4,
        recommended_content_formats=["wellness_teaching", "personal_story"],
        recommended_brand_presets=["wellness_soft", "cinematic_dark"],
        notes="Gentle crossfades between scenes.",
    ),
    "bold_punch": TransitionPreset(
        name="bold_punch",
        default_transition_type="quick_zoom",
        default_duration=0.08,
        intensity=0.85,
        recommended_content_formats=["reaction_commentary", "affiliate_followup"],
        recommended_brand_presets=["bold_viral"],
        notes="Punchy transitions; may fall back to cut if unsupported.",
    ),
    "wellness_flow": TransitionPreset(
        name="wellness_flow",
        default_transition_type="crossfade",
        default_duration=0.35,
        intensity=0.35,
        recommended_content_formats=["wellness_teaching"],
        recommended_brand_presets=["wellness_soft"],
        notes="Slow, calm pacing with soft fades.",
    ),
    "product_snap": TransitionPreset(
        name="product_snap",
        default_transition_type="card_punch",
        default_duration=0.1,
        intensity=0.75,
        recommended_content_formats=["product_demo", "affiliate_followup"],
        recommended_brand_presets=["bold_viral"],
        notes="Snappy product-style cuts with optional punch zoom on cards.",
    ),
    "documentary_clean": TransitionPreset(
        name="documentary_clean",
        default_transition_type="fade_to_black",
        default_duration=0.2,
        intensity=0.45,
        recommended_content_formats=["fundraising_story", "personal_story"],
        recommended_brand_presets=["clean_creator", "cinematic_dark"],
        notes="Brief fade-to-black between major beats.",
    ),
}

_BRAND_AUTO: dict[str, str] = {
    "clean_creator": "documentary_clean",
    "bold_viral": "product_snap",
    "wellness_soft": "wellness_flow",
    "cinematic_dark": "soft_fade",
    "minimal_white": "simple_cuts",
}

_FORMAT_AUTO: dict[str, str] = {
    "wellness_teaching": "wellness_flow",
    "affiliate_followup": "product_snap",
    "product_demo": "product_snap",
    "fundraising_story": "documentary_clean",
    "tutorial": "simple_cuts",
}


def get_transition_preset(name: str) -> TransitionPreset | None:
    return PRESETS.get(name)


def get_transition_preset_or_default(name: str) -> TransitionPreset:
    return PRESETS.get(name) or PRESETS["simple_cuts"]


def list_transition_preset_names() -> list[str]:
    return list(PRESETS.keys())


def resolve_transition_preset(
    preset_name: str,
    *,
    brand_preset: str = "",
    content_format: str = "",
) -> TransitionPreset:
    """Resolve 'auto' or unknown preset to a concrete preset."""
    key = (preset_name or "auto").strip().lower()
    if key == "auto":
        if content_format and content_format in _FORMAT_AUTO:
            key = _FORMAT_AUTO[content_format]
        elif brand_preset and brand_preset in _BRAND_AUTO:
            key = _BRAND_AUTO[brand_preset]
        else:
            key = "simple_cuts"
    if key not in PRESETS:
        return PRESETS["simple_cuts"]
    return PRESETS[key]
