"""Genesis Studio — Basic motion effects for stills and cards."""

from __future__ import annotations

from typing import Any

_MOTION_SUPPORTED = ("image", "placeholder", "title_card", "end_card", "scene_card")


def validate_motion_effect(effect_name: str, *, brand_preset: str = "") -> list[str]:
    warnings: list[str] = []
    if effect_name == "product_punch" and brand_preset not in ("bold_viral", ""):
        warnings.append("product_punch intended for bold_viral content")
    if effect_name == "wellness_subtle" and brand_preset not in ("wellness_soft", ""):
        warnings.append("wellness motion best on wellness_soft preset")
    return warnings


def apply_subtle_zoom(clip: Any, duration: float, *, intensity: float = 0.04) -> tuple[Any, list[str]]:
    warnings: list[str] = []
    dur = max(float(duration), 0.1)
    try:
        return clip.resized(lambda t: 1.0 + intensity * min(t / dur, 1.0)), warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"subtle zoom unavailable: {exc}")
        return clip, warnings


def apply_product_punch_zoom(clip: Any, duration: float, *, intensity: float = 0.1) -> tuple[Any, list[str]]:
    warnings: list[str] = []
    dur = max(float(duration), 0.1)
    try:
        def _scale(t: float) -> float:
            p = min(t / dur, 1.0)
            if p < 0.15:
                return 1.0 + intensity * (p / 0.15)
            return 1.0 + intensity * (1.0 - (p - 0.15) / 0.85)
        return clip.resized(_scale), warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"punch zoom fell back to static: {exc}")
        return clip, warnings


def apply_ken_burns_to_card_or_image(
    clip: Any,
    duration: float,
    *,
    direction: str = "in",
) -> tuple[Any, list[str]]:
    """Slow pan/zoom for wellness-style content."""
    intensity = 0.03 if direction == "in" else 0.02
    return apply_subtle_zoom(clip, duration, intensity=intensity)


def apply_basic_motion_effect(
    clip: Any,
    item: Any,
    *,
    brand_preset: str = "clean_creator",
    transition_preset: str = "",
    motion_enabled: bool = True,
    content_format: str = "",
) -> tuple[Any, list[str]]:
    if not motion_enabled:
        return clip, []

    media_type = getattr(item, "media_type", "")
    if media_type not in _MOTION_SUPPORTED and media_type != "image":
        return clip, []

    dur = float(getattr(item, "duration", 3.0) or 3.0)
    warnings: list[str] = []

    if brand_preset == "wellness_soft" or transition_preset in ("wellness_flow", "soft_fade"):
        return apply_ken_burns_to_card_or_image(clip, dur, direction="in")

    if brand_preset == "bold_viral" or transition_preset in ("product_snap", "bold_punch"):
        if media_type in ("title_card", "scene_card", "placeholder"):
            return apply_product_punch_zoom(clip, dur)
        return apply_subtle_zoom(clip, dur, intensity=0.05)

    if media_type in ("image", "placeholder", "scene_card"):
        return apply_subtle_zoom(clip, dur, intensity=0.03)

    return clip, warnings
