"""
Genesis Studio — Title, scene, end, and placeholder cards for draft video.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from genesis.video.render_styles import CardStyle

_FORBIDDEN_TOPIC = re.compile(r"\b(?:solar|lighter|sunlight)\b", re.I)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 26, 31, 46


def _load_font(size: int, font_name: str = "default") -> Any:
    from PIL import ImageFont

    for candidate in (
        font_name if font_name and font_name != "default" else "",
        "arial.ttf",
        "Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ):
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_card_text(text: str, *, max_chars: int = 36, max_lines: int = 4) -> list[str]:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    words = t.split()
    lines: list[str] = []
    chunk: list[str] = []
    for w in words:
        trial = " ".join(chunk + [w])
        if len(trial) > max_chars and chunk:
            lines.append(" ".join(chunk))
            chunk = [w]
            if len(lines) >= max_lines:
                break
        else:
            chunk.append(w)
    if chunk and len(lines) < max_lines:
        lines.append(" ".join(chunk))
    return lines[:max_lines]


def validate_card_readability(title: str, body: str, style: CardStyle) -> list[str]:
    warnings: list[str] = []
    if len(title) > 80:
        warnings.append("title truncated for card")
    if len(body) > 200:
        warnings.append("body truncated for card")
    if style.title_size < 24:
        warnings.append("title_size very small")
    return warnings


def _gradient_bg(
    draw: Any,
    size: tuple[int, int],
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> None:
    """Draw a vertical gradient background."""
    from PIL import ImageDraw
    w, h = size
    for y in range(h):
        t = y / h
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def _vignette(img: Any, intensity: float = 0.55) -> Any:
    """Apply a radial vignette to add cinematic depth."""
    try:
        from PIL import Image, ImageDraw, ImageFilter
        import math
        w, h = img.size
        mask = Image.new("L", (w, h), 255)
        mask_draw = ImageDraw.Draw(mask)
        cx, cy = w // 2, h // 2
        max_r = math.sqrt(cx * cx + cy * cy)
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                alpha = max(0, 1 - (dist / max_r) * intensity * 2)
                val = int(255 * alpha)
                mask_draw.point([(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)], fill=val)
        mask = mask.filter(ImageFilter.GaussianBlur(30))
        black = Image.new("RGB", (w, h), (0, 0, 0))
        return Image.composite(img, black, mask)
    except Exception:  # noqa: BLE001
        return img


# Cinematic color palettes for placeholder cards
_CARD_PALETTES = [
    # (top_bg, bottom_bg, accent, text)
    ((10, 15, 30), (5, 8, 20), (70, 130, 220), (240, 245, 255)),   # deep blue / electric
    ((20, 8, 25), (10, 5, 18), (180, 80, 220), (248, 235, 255)),   # dark purple / violet
    ((8, 22, 18), (4, 12, 10), (50, 200, 140), (230, 255, 245)),   # dark teal / emerald
    ((25, 12, 8), (15, 6, 4), (220, 110, 50), (255, 240, 225)),    # dark amber / fire
    ((5, 5, 15), (2, 2, 8), (200, 170, 80), (255, 248, 215)),      # midnight / gold
    ((15, 20, 25), (8, 12, 18), (130, 180, 230), (235, 245, 255)), # slate / light blue
]


def _draw_card(
    out_path: Path,
    *,
    title: str,
    body: str,
    footer: str,
    style: CardStyle,
    size: tuple[int, int],
    label: str = "",
    palette_index: int = 0,
) -> str:
    from PIL import Image, ImageDraw, ImageFilter

    out_path.parent.mkdir(parents=True, exist_ok=True)
    w, h = size

    pal = _CARD_PALETTES[palette_index % len(_CARD_PALETTES)]
    top_bg, bot_bg, accent, text_col = pal

    img = Image.new("RGB", size, color=top_bg)
    draw = ImageDraw.Draw(img)

    # Gradient background
    _gradient_bg(draw, size, top_bg, bot_bg)

    # Accent bar at top — thicker for better visual
    margin = style.safe_margin
    draw.rectangle([margin, margin, w - margin, margin + 6], fill=accent)
    draw.rectangle([margin, margin + 9, w // 3, margin + 11], fill=accent)

    title_font = _load_font(style.title_size, style.font_name)
    body_font = _load_font(style.body_size, style.font_name)
    foot_font = _load_font(style.footer_size, style.font_name)

    title_lines = wrap_card_text(title, max_chars=26, max_lines=3)
    body_lines = wrap_card_text(body, max_chars=38, max_lines=4)

    # Position text in the lower 60% of the frame (cinematic lower-third style)
    total_lines = len(title_lines) + len(body_lines)
    line_h = style.title_size + 10
    body_line_h = style.body_size + 8
    total_h = len(title_lines) * line_h + 20 + len(body_lines) * body_line_h
    y = max(h // 3, h - margin - total_h - 80)

    # Draw subtle text shadow for readability
    shadow_offset = 2
    for line in title_lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            tw = bbox[2] - bbox[0]
        except Exception:  # noqa: BLE001
            tw = len(line) * (style.title_size // 2)
        x = (w - tw) // 2
        draw.text((x + shadow_offset, y + shadow_offset), line, font=title_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=title_font, fill=text_col)
        y += line_h

    y += 14
    # Horizontal separator line
    draw.line([(margin + 40, y - 7), (w - margin - 40, y - 7)], fill=accent, width=1)

    for i, line in enumerate(body_lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            tw = bbox[2] - bbox[0]
        except Exception:  # noqa: BLE001
            tw = len(line) * (style.body_size // 2)
        x = (w - tw) // 2
        # Slightly dimmer body text
        body_color = tuple(min(255, int(c * 0.85)) for c in text_col)
        draw.text((x + 1, y + 1), line, font=body_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=body_font, fill=body_color)
        y += body_line_h

    # Footer / label area
    if footer:
        try:
            bbox = draw.textbbox((0, 0), footer, font=foot_font)
            tw = bbox[2] - bbox[0]
        except Exception:  # noqa: BLE001
            tw = len(footer) * (style.footer_size // 2)
        draw.text(((w - tw) // 2, h - margin - 32), footer, font=foot_font, fill=accent)

    if label:
        # Small label pill in top-left
        lbl = label[:24].upper()
        try:
            bbox = draw.textbbox((0, 0), lbl, font=foot_font)
            lw = bbox[2] - bbox[0] + 16
        except Exception:  # noqa: BLE001
            lw = len(lbl) * 9 + 16
        draw.rectangle([margin, margin + 18, margin + lw, margin + 36], fill=accent)
        draw.text((margin + 8, margin + 20), lbl, font=foot_font, fill=(10, 10, 10))

    # Apply vignette for cinematic depth
    img = _vignette(img, intensity=0.45)
    img.save(out_path)
    return str(out_path)


def render_title_card(
    out_path: Path,
    primary_hook: str,
    style: CardStyle,
    size: tuple[int, int],
    *,
    subtitle: str = "",
) -> str:
    hook = (primary_hook or "Your hook here").strip()
    return _draw_card(
        out_path,
        title=hook[:120],
        body=subtitle or "Draft vertical video",
        footer="Genesis Studio",
        style=style,
        size=size,
        label="HOOK",
    )


def render_scene_card(
    out_path: Path,
    *,
    section_name: str,
    visual_goal: str,
    narration_snippet: str,
    style: CardStyle,
    size: tuple[int, int],
    content_format: str = "",
    scene_index: int = 0,
) -> str:
    title = section_name or "Scene"
    body = (visual_goal or narration_snippet or "")[:180]
    if content_format == "wellness_teaching":
        body = _FORBIDDEN_TOPIC.sub("", body).strip() or body
    return _draw_card(
        out_path,
        title=title[:60],
        body=body,
        footer="",
        style=style,
        size=size,
        label=section_name[:20] if section_name else "",
        palette_index=scene_index,
    )


def render_end_card(
    out_path: Path,
    cta: str,
    style: CardStyle,
    size: tuple[int, int],
    *,
    disclosure_note: str = "",
) -> str:
    body = cta or "Comment / Follow / Save"
    if disclosure_note:
        body = f"{body}\n{disclosure_note[:80]}"
    return _draw_card(
        out_path,
        title="NEXT STEP",
        body=body[:160],
        footer="",
        style=style,
        size=size,
        label="CTA",
    )


def render_placeholder_card(
    out_path: Path,
    *,
    scene_id: str,
    section_name: str,
    visual_goal: str,
    caption_text: str,
    style: CardStyle,
    size: tuple[int, int],
    scene_index: int = 0,
) -> str:
    return render_scene_card(
        out_path,
        section_name=section_name or scene_id,
        visual_goal=visual_goal or caption_text,
        narration_snippet=caption_text,
        style=style,
        size=size,
        scene_index=scene_index,
    )
