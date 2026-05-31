"""
Genesis Studio — Brand presets for draft video rendering.
"""

from __future__ import annotations

from genesis.video.render_styles import BrandPreset, CaptionStyle, CardStyle

DEFAULT_PRESET_NAME = "clean_creator"


def _caption(**kwargs) -> CaptionStyle:
    return CaptionStyle(**{k: v for k, v in kwargs.items() if v is not None})


def _card(**kwargs) -> CardStyle:
    return CardStyle(**{k: v for k, v in kwargs.items() if v is not None})


PRESETS: dict[str, BrandPreset] = {
    "clean_creator": BrandPreset(
        preset_name="clean_creator",
        caption_style=_caption(
            font_size=46,
            text_color="#FFFFFF",
            stroke_color="#111111",
            stroke_width=2,
            background_color="#000000",
            background_opacity=0.5,
            position="bottom_safe",
        ),
        title_card_style=_card(
            background_color="#12141a",
            text_color="#FFFFFF",
            accent_color="#3b82f6",
            title_size=62,
            body_size=34,
        ),
        scene_card_style=_card(
            background_color="#1a2030",
            text_color="#E8ECF4",
            accent_color="#3b82f6",
            title_size=52,
            body_size=30,
        ),
        end_card_style=_card(
            background_color="#0f1419",
            text_color="#FFFFFF",
            accent_color="#22c55e",
            title_size=58,
            body_size=32,
        ),
        notes=["Balanced creator style for general short-form content."],
    ),
    "cinematic_dark": BrandPreset(
        preset_name="cinematic_dark",
        caption_style=_caption(
            font_size=44,
            text_color="#F5F5F5",
            stroke_color="#000000",
            stroke_width=3,
            background_color="#000000",
            background_opacity=0.65,
            shadow_enabled=True,
        ),
        title_card_style=_card(
            background_color="#0a0a0c",
            text_color="#E5E5E5",
            accent_color="#c9a227",
            title_size=64,
            body_size=32,
        ),
        scene_card_style=_card(
            background_color="#141418",
            text_color="#D4D4D8",
            accent_color="#a78bfa",
            title_size=50,
            body_size=28,
        ),
        end_card_style=_card(
            background_color="#08080a",
            text_color="#FAFAFA",
            accent_color="#c9a227",
            title_size=56,
            body_size=30,
        ),
        notes=["Moody contrast; good for story-driven or dramatic demos."],
    ),
    "wellness_soft": BrandPreset(
        preset_name="wellness_soft",
        caption_style=_caption(
            font_size=42,
            text_color="#2D3748",
            stroke_color="#FFFFFF",
            stroke_width=1,
            background_color="#F7FAFC",
            background_opacity=0.72,
            position="bottom_safe",
            safe_margin_bottom=0.2,
        ),
        title_card_style=_card(
            background_color="#E8F4F0",
            text_color="#2D4A3E",
            accent_color="#7CB8A0",
            title_size=58,
            body_size=32,
        ),
        scene_card_style=_card(
            background_color="#EDF2F7",
            text_color="#3D5A4C",
            accent_color="#9FD4C4",
            title_size=48,
            body_size=28,
        ),
        end_card_style=_card(
            background_color="#E2E8F0",
            text_color="#2D3748",
            accent_color="#68B0A0",
            title_size=52,
            body_size=30,
        ),
        notes=[
            "Calming palette for sound bowl, meditation, breathwork, nervous system, and grounding.",
            "Soft backgrounds; avoid harsh contrast or aggressive CTAs.",
        ],
    ),
    "bold_viral": BrandPreset(
        preset_name="bold_viral",
        caption_style=_caption(
            font_size=52,
            text_color="#FFFF00",
            stroke_color="#000000",
            stroke_width=3,
            background_color="#000000",
            background_opacity=0.7,
            uppercase=True,
            shadow_enabled=True,
        ),
        title_card_style=_card(
            background_color="#111111",
            text_color="#FFFFFF",
            accent_color="#FF3366",
            title_size=68,
            body_size=36,
        ),
        scene_card_style=_card(
            background_color="#1a1a1a",
            text_color="#FFFFFF",
            accent_color="#FFCC00",
            title_size=54,
            body_size=32,
        ),
        end_card_style=_card(
            background_color="#0d0d0d",
            text_color="#FFFFFF",
            accent_color="#FF3366",
            title_size=60,
            body_size=34,
        ),
        notes=[
            "High-contrast captions for product demos, affiliate follow-ups, controversial takes, and viral hooks.",
            "Readable stroke and bold accent bars.",
        ],
    ),
    "minimal_white": BrandPreset(
        preset_name="minimal_white",
        caption_style=_caption(
            font_size=44,
            text_color="#111111",
            stroke_color="#FFFFFF",
            stroke_width=0,
            background_color="#FFFFFF",
            background_opacity=0.85,
            position="bottom_safe",
        ),
        title_card_style=_card(
            background_color="#FAFAFA",
            text_color="#111111",
            accent_color="#333333",
            title_size=60,
            body_size=32,
        ),
        scene_card_style=_card(
            background_color="#F5F5F5",
            text_color="#222222",
            accent_color="#666666",
            title_size=48,
            body_size=28,
        ),
        end_card_style=_card(
            background_color="#FFFFFF",
            text_color="#111111",
            accent_color="#000000",
            title_size=56,
            body_size=30,
        ),
        notes=["Light minimal layout for tutorials and clean explainers."],
    ),
}


def get_brand_preset(name: str = "") -> BrandPreset:
    """Return preset by name; unknown names fall back to clean_creator."""
    key = (name or DEFAULT_PRESET_NAME).strip().lower().replace(" ", "_")
    return PRESETS.get(key, PRESETS[DEFAULT_PRESET_NAME])


def list_preset_names() -> list[str]:
    return list(PRESETS.keys())
