"""
Genesis Studio — Caption overlay rendering for vertical draft video.
"""

from __future__ import annotations

import re
from typing import Any

from genesis.video.render_styles import CaptionStyle

_MAX_LINES_DEFAULT = 2
_MAX_CHARS_PER_LINE = 42


def _hex_to_rgba(hex_color: str, alpha: float) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return r, g, b, int(255 * alpha)
    return 0, 0, 0, int(255 * alpha)


def _load_font(size: int, font_name: str = "default") -> Any:
    from PIL import ImageFont

    if font_name and font_name != "default":
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            pass
    for candidate in (
        "arial.ttf",
        "Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def split_caption_lines(
    text: str,
    *,
    max_lines: int = _MAX_LINES_DEFAULT,
    max_chars: int = _MAX_CHARS_PER_LINE,
) -> list[str]:
    """Split caption into 1–max_lines readable lines."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    if len(t) <= max_chars:
        return [t[:max_chars]]

    words = t.split()
    lines: list[str] = []
    current: list[str] = []
    for w in words:
        trial = " ".join(current + [w])
        if len(trial) > max_chars and current:
            lines.append(" ".join(current))
            current = [w]
            if len(lines) >= max_lines:
                break
        else:
            current.append(w)
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1][: max_chars - 1] + "…"
    return lines


def fit_caption_to_safe_area(
    lines: list[str],
    style: CaptionStyle,
    size: tuple[int, int],
    *,
    position: str | None = None,
) -> tuple[int, int, int, int]:
    """Return (x, y, max_width, box_height) for caption block."""
    w, h = size
    margin_x = int(w * style.safe_margin_sides)
    max_width = int(w * style.max_width_ratio)
    line_h = style.font_size + style.line_spacing
    box_h = len(lines) * line_h + style.font_size // 2
    x = (w - max_width) // 2
    pos = position or style.position

    if pos in ("top_safe", "top"):
        y = int(h * style.safe_margin_top)
    else:
        y = int(h * (1.0 - style.safe_margin_bottom)) - box_h
    y = max(int(h * style.safe_margin_top), min(y, h - box_h - 20))
    return x, y, max_width, box_h


def choose_caption_position(
    style: CaptionStyle,
    *,
    scene_shot_type: str = "",
) -> str:
    """Prefer bottom safe; move up for text_overlay scenes."""
    if scene_shot_type == "text_overlay":
        return "bottom_safe"
    return style.position or "bottom_safe"


def validate_caption_readability(
    text: str,
    style: CaptionStyle,
    *,
    size: tuple[int, int] = (1080, 1920),
) -> list[str]:
    warnings: list[str] = []
    lines = split_caption_lines(text)
    if not lines:
        warnings.append("empty caption text")
        return warnings
    if len(lines) > 2:
        warnings.append("caption exceeds 2 lines after split")
    if any(len(ln) > _MAX_CHARS_PER_LINE + 5 for ln in lines):
        warnings.append("caption line may be too wide")
    if style.font_size > size[1] * 0.08:
        warnings.append("font_size large for vertical frame")
    return warnings


def render_caption_overlay(
    text: str,
    style: CaptionStyle,
    size: tuple[int, int],
    *,
    scene_shot_type: str = "",
) -> Any:
    """
    Render RGBA PIL Image with caption on transparent background (full frame size).
    """
    from PIL import Image, ImageDraw

    w, h = size
    display = text.upper() if style.uppercase else text
    lines = split_caption_lines(display)
    if not lines:
        return Image.new("RGBA", size, (0, 0, 0, 0))

    position = choose_caption_position(style, scene_shot_type=scene_shot_type)
    x, y, max_w, box_h = fit_caption_to_safe_area(lines, style, size, position=position)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if style.background_opacity > 0:
        pad = 16
        bg = _hex_to_rgba(style.background_color, style.background_opacity)
        draw.rounded_rectangle(
            [x - pad, y - pad, x + max_w + pad, y + box_h + pad],
            radius=12,
            fill=bg,
        )

    font = _load_font(style.font_size, style.font_name)
    fill = _hex_to_rgba(style.text_color, 1.0)[:3]
    stroke = _hex_to_rgba(style.stroke_color, 1.0)[:3] if style.stroke_width else None
    cy = y
    for line in lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
        except Exception:  # noqa: BLE001
            tw = len(line) * (style.font_size // 2)
        tx = x + (max_w - tw) // 2
        if style.stroke_width and stroke:
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                draw.text((tx + dx, cy + dy), line, font=font, fill=stroke)
        if style.shadow_enabled:
            draw.text((tx + 2, cy + 2), line, font=font, fill=(0, 0, 0))
        draw.text((tx, cy), line, font=font, fill=fill)
        cy += style.font_size + style.line_spacing

    return layer


def composite_caption_on_image(
    base: Any,
    caption_text: str,
    style: CaptionStyle,
) -> Any:
    """Burn caption overlay onto RGB/RGBA PIL image."""
    from PIL import Image

    if not caption_text.strip():
        return base
    base_rgba = base.convert("RGBA")
    overlay = render_caption_overlay(caption_text, style, base_rgba.size)
    return Image.alpha_composite(base_rgba, overlay).convert("RGB")
