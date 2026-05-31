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


def _draw_card(
    out_path: Path,
    *,
    title: str,
    body: str,
    footer: str,
    style: CardStyle,
    size: tuple[int, int],
    label: str = "",
) -> str:
    from PIL import Image, ImageDraw

    out_path.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    bg = _hex_to_rgb(style.background_color)
    accent = _hex_to_rgb(style.accent_color)
    fg = _hex_to_rgb(style.text_color)

    img = Image.new("RGB", size, color=bg)
    draw = ImageDraw.Draw(img)

    margin = style.safe_margin
    draw.rectangle([margin, margin, w - margin, margin + 8], fill=accent)

    title_font = _load_font(style.title_size, style.font_name)
    body_font = _load_font(style.body_size, style.font_name)
    foot_font = _load_font(style.footer_size, style.font_name)

    title_lines = wrap_card_text(title, max_chars=28, max_lines=2)
    body_lines = wrap_card_text(body, max_chars=40, max_lines=3)

    y = h // 2 - 100
    for line in title_lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            tw = bbox[2] - bbox[0]
        except Exception:  # noqa: BLE001
            tw = len(line) * 20
        draw.text(((w - tw) // 2, y), line, font=title_font, fill=fg)
        y += style.title_size + 8

    y += 12
    for line in body_lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            tw = bbox[2] - bbox[0]
        except Exception:  # noqa: BLE001
            tw = len(line) * 12
        draw.text(((w - tw) // 2, y), line, font=body_font, fill=fg)
        y += style.body_size + 6

    if footer:
        try:
            bbox = draw.textbbox((0, 0), footer, font=foot_font)
            tw = bbox[2] - bbox[0]
        except Exception:  # noqa: BLE001
            tw = len(footer) * 10
        draw.text(((w - tw) // 2, h - margin - 40), footer, font=foot_font, fill=accent)

    if label:
        draw.text((margin, h - margin - 20), label[:30], font=foot_font, fill=accent)

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
) -> str:
    title = section_name or "Scene"
    body = (visual_goal or narration_snippet or "")[:180]
    if content_format == "wellness_teaching":
        body = _FORBIDDEN_TOPIC.sub("", body).strip() or body
    return _draw_card(
        out_path,
        title=title[:60],
        body=body,
        footer="B-roll or film this beat",
        style=style,
        size=size,
        label=section_name[:20] if section_name else "",
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
) -> str:
    return render_scene_card(
        out_path,
        section_name=section_name or scene_id,
        visual_goal=visual_goal or caption_text,
        narration_snippet=caption_text,
        style=style,
        size=size,
    )
