"""
Genesis Studio — Render styling dataclasses and options.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaptionStyle:
    font_name: str = "default"
    font_size: int = 48
    font_weight: str = "bold"
    text_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 2
    background_color: str = "#000000"
    background_opacity: float = 0.55
    position: str = "bottom_safe"
    max_width_ratio: float = 0.88
    safe_margin_top: float = 0.12
    safe_margin_bottom: float = 0.18
    safe_margin_sides: float = 0.06
    line_spacing: int = 8
    uppercase: bool = False
    shadow_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "font_name": self.font_name,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "text_color": self.text_color,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
            "background_color": self.background_color,
            "background_opacity": self.background_opacity,
            "position": self.position,
            "max_width_ratio": self.max_width_ratio,
            "safe_margin_top": self.safe_margin_top,
            "safe_margin_bottom": self.safe_margin_bottom,
            "safe_margin_sides": self.safe_margin_sides,
            "line_spacing": self.line_spacing,
            "uppercase": self.uppercase,
            "shadow_enabled": self.shadow_enabled,
        }


@dataclass
class CardStyle:
    background_color: str = "#1a1f2e"
    text_color: str = "#FFFFFF"
    accent_color: str = "#4a9eff"
    font_name: str = "default"
    title_size: int = 64
    body_size: int = 36
    footer_size: int = 24
    padding: int = 48
    alignment: str = "center"
    logo_path: str = ""
    texture_path: str = ""
    safe_margin: int = 56

    def to_dict(self) -> dict[str, Any]:
        return {
            "background_color": self.background_color,
            "text_color": self.text_color,
            "accent_color": self.accent_color,
            "font_name": self.font_name,
            "title_size": self.title_size,
            "body_size": self.body_size,
            "footer_size": self.footer_size,
            "padding": self.padding,
            "alignment": self.alignment,
            "logo_path": self.logo_path,
            "texture_path": self.texture_path,
            "safe_margin": self.safe_margin,
        }


@dataclass
class BrandPreset:
    preset_name: str
    caption_style: CaptionStyle
    title_card_style: CardStyle
    scene_card_style: CardStyle
    end_card_style: CardStyle
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_name": self.preset_name,
            "caption_style": self.caption_style.to_dict(),
            "title_card_style": self.title_card_style.to_dict(),
            "scene_card_style": self.scene_card_style.to_dict(),
            "end_card_style": self.end_card_style.to_dict(),
            "notes": self.notes,
        }


@dataclass
class RenderOptions:
    brand_preset: str = "clean_creator"
    captions_enabled: bool = True
    title_card_enabled: bool = True
    end_card_enabled: bool = True
    scene_cards_enabled: bool = True
    target_resolution: tuple[int, int] = (1080, 1920)
    fps: int = 30
    simple_transitions: bool = True
    transition_duration: float = 0.12

    def to_dict(self) -> dict[str, Any]:
        return {
            "brand_preset": self.brand_preset,
            "captions_enabled": self.captions_enabled,
            "title_card_enabled": self.title_card_enabled,
            "end_card_enabled": self.end_card_enabled,
            "scene_cards_enabled": self.scene_cards_enabled,
            "target_resolution": list(self.target_resolution),
            "fps": self.fps,
            "simple_transitions": self.simple_transitions,
            "transition_duration": self.transition_duration,
        }


def write_render_style_artifacts(
    run_dir: Any,
    preset: BrandPreset,
    options: RenderOptions,
) -> None:
    """Write render_style.json and caption_style.json to run folder."""
    from pathlib import Path

    root = Path(run_dir)
    style_doc = {
        "brand_preset": preset.preset_name,
        "caption_style": preset.caption_style.to_dict(),
        "title_card_style": preset.title_card_style.to_dict(),
        "scene_card_style": preset.scene_card_style.to_dict(),
        "end_card_style": preset.end_card_style.to_dict(),
        "target_resolution": list(options.target_resolution),
        "fps": options.fps,
        "features": {
            "captions_enabled": options.captions_enabled,
            "title_card_enabled": options.title_card_enabled,
            "end_card_enabled": options.end_card_enabled,
            "scene_cards_enabled": options.scene_cards_enabled,
            "simple_transitions": options.simple_transitions,
        },
        "notes": preset.notes,
    }
    (root / "render_style.json").write_text(
        json.dumps(style_doc, indent=2), encoding="utf-8"
    )
    (root / "caption_style.json").write_text(
        json.dumps(preset.caption_style.to_dict(), indent=2), encoding="utf-8"
    )
