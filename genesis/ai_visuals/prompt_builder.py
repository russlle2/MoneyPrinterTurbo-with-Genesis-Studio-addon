"""Genesis Studio — Visual generation prompt builder."""

from __future__ import annotations

import re
from typing import Any

from genesis.ai_visuals.visual_models import MissingScene, VisualGenerationPrompt

_FORBIDDEN = re.compile(
    r"(api_key|sk_[a-z0-9]+|xi-api|voice_id|openai_api|local_model_path|"
    r"config\.toml|config\.json|official partner|sponsored by|guaranteed cure|"
    r"miracle cure|shock imagery)",
    re.I,
)

_AWKWARD_FRAGMENTS = re.compile(
    r"\b(my girlfriend|went viral|comment keyword|link in bio)\b",
    re.I,
)


def sanitize_prompt_text(text: str) -> str:
    t = _FORBIDDEN.sub("", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def validate_visual_generation_prompt(prompt: VisualGenerationPrompt) -> list[str]:
    warnings: list[str] = []
    blob = (prompt.prompt_text + prompt.negative_prompt).lower()
    for token in ("api_key", "voice_id", "sk_", "config.json"):
        if token in blob:
            warnings.append(f"prompt may contain forbidden token: {token}")
    if len(prompt.prompt_text) < 20:
        warnings.append("prompt_text very short")
    if "cure" in blob and "wellness" in prompt.intended_use:
        warnings.append("check wellness prompts for medical claims")
    return warnings


def _style_for_brand(brand_preset: str, content_format: str) -> str:
    if brand_preset == "wellness_soft" or content_format == "wellness_teaching":
        return "calm, soft natural light, slow movement, 9:16 vertical"
    if brand_preset == "bold_viral":
        return "energetic, sharp focus, practical demo, 9:16 vertical social"
    if brand_preset == "cinematic_dark":
        return "cinematic, moody lighting, shallow depth of field, 9:16 vertical"
    return "clean, well-lit, social short-form, 9:16 vertical"


def _safety_for_format(content_format: str) -> str:
    if content_format == "wellness_teaching":
        return "Educational wellness only; no medical cure claims."
    if content_format == "fundraising_story":
        return "Respectful, compassionate; no shock or exploitative imagery."
    if content_format in ("affiliate_followup", "product_demo"):
        return "No fake official partnership unless approved in brief."
    return "No misleading claims; safe for short-form social."


def build_scene_image_prompt(
    scene: dict[str, Any],
    missing: MissingScene,
    *,
    brand_preset: str = "clean_creator",
    content_format: str = "",
    platform: str = "tiktok",
) -> VisualGenerationPrompt:
    subject = sanitize_prompt_text(
        missing.visual_goal or missing.narration_text or missing.section_name
    )
    style = _style_for_brand(brand_preset, content_format)
    fmt = content_format or "general"

    if fmt in ("affiliate_followup", "product_demo"):
        body = (
            f"Vertical 9:16 product visual for {platform}. "
            f"Subject: {subject}. Product close-up or hands-on demonstration, "
            f"practical use case, clean background. Style: {style}."
        )
        negative = "blurry, watermark, text overlay, fake logo, partnership badge"
    elif fmt == "wellness_teaching":
        body = (
            f"Vertical 9:16 calm wellness scene. "
            f"Subject: {subject}. Peaceful environment, slow gentle movement, "
            f"breath or practice cue. Style: {style}."
        )
        negative = "medical claim, hospital, cure, panic, harsh lighting"
    elif fmt == "fundraising_story":
        body = (
            f"Vertical 9:16 respectful story b-roll. "
            f"Context: {subject}. Warm, honest, community support tone. Style: {style}."
        )
        negative = "shock, exploitation, violence, sensational headlines"
    elif fmt == "tutorial":
        body = (
            f"Vertical 9:16 tutorial step visual. "
            f"Step: {subject}. Clear materials/process/result framing. Style: {style}."
        )
        negative = "cluttered, unreadable, dark"
    else:
        body = f"Vertical 9:16 scene. {subject}. Style: {style}."

    body = sanitize_prompt_text(body)
    if _AWKWARD_FRAGMENTS.search(body):
        body = re.sub(_AWKWARD_FRAGMENTS, "", body)
        body = sanitize_prompt_text(body)

    return VisualGenerationPrompt(
        prompt_id=f"prompt_{missing.scene_id}_image",
        scene_id=missing.scene_id,
        prompt_type="scene_image",
        provider_hint="image",
        prompt_text=body,
        negative_prompt=negative if fmt in ("affiliate_followup", "product_demo", "wellness_teaching", "fundraising_story", "tutorial") else "blurry, low quality",
        aspect_ratio="9:16",
        duration_seconds=0.0,
        style_hint=style,
        intended_use=fmt,
        safety_notes=_safety_for_format(content_format),
    )


def build_scene_video_prompt(
    scene: dict[str, Any],
    missing: MissingScene,
    *,
    brand_preset: str = "clean_creator",
    content_format: str = "",
    duration_seconds: float = 4.0,
) -> VisualGenerationPrompt:
    img = build_scene_image_prompt(
        scene, missing, brand_preset=brand_preset, content_format=content_format,
    )
    img.prompt_type = "scene_video"
    img.provider_hint = "video"
    img.duration_seconds = duration_seconds
    img.prompt_text = img.prompt_text + f" Short {int(duration_seconds)}s clip, subtle motion."
    img.prompt_id = f"prompt_{missing.scene_id}_video"
    return img


def build_hero_shot_prompt(
    scene: dict[str, Any],
    missing: MissingScene,
    *,
    brand_preset: str = "bold_viral",
    content_format: str = "",
) -> VisualGenerationPrompt:
    p = build_scene_image_prompt(scene, missing, brand_preset=brand_preset, content_format=content_format)
    p.prompt_type = "hero_shot"
    p.prompt_id = f"prompt_{missing.scene_id}_hero"
    p.prompt_text = sanitize_prompt_text(
        f"Hero opening shot, vertical 9:16. Hook visual: {missing.visual_goal or missing.section_name}. "
        + p.prompt_text[:200]
    )
    return p


def build_broll_prompt(
    scene: dict[str, Any],
    missing: MissingScene,
    *,
    content_format: str = "",
) -> VisualGenerationPrompt:
    p = build_scene_image_prompt(scene, missing, content_format=content_format)
    p.prompt_type = "broll"
    p.prompt_id = f"prompt_{missing.scene_id}_broll"
    p.prompt_text = sanitize_prompt_text(
        f"Supporting b-roll, vertical 9:16. {missing.section_name}: ambient context, no faces required."
    )
    return p


def build_visual_generation_prompts(
    missing_scenes: list[MissingScene],
    scenes_by_id: dict[str, dict[str, Any]],
    *,
    brand_preset: str = "clean_creator",
    content_format: str = "",
    platform: str = "tiktok",
    default_asset_type: str = "image",
    duration_seconds: float = 4.0,
) -> list[VisualGenerationPrompt]:
    prompts: list[VisualGenerationPrompt] = []
    for ms in missing_scenes:
        scene = scenes_by_id.get(ms.scene_id, {})
        if ms.priority == "high" and ms.fallback_type in ("generated_video", "generated_image"):
            if default_asset_type == "video" or ms.fallback_type == "generated_video":
                p = build_scene_video_prompt(
                    scene, ms, brand_preset=brand_preset,
                    content_format=content_format, duration_seconds=duration_seconds,
                )
            else:
                p = build_hero_shot_prompt(scene, ms, brand_preset=brand_preset, content_format=content_format)
                if "hook" not in (ms.section_name or "").lower():
                    p = build_scene_image_prompt(
                        scene, ms, brand_preset=brand_preset, content_format=content_format, platform=platform,
                    )
        elif "b-roll" in (ms.section_name or "").lower() or ms.fallback_type == "stock_broll_needed":
            p = build_broll_prompt(scene, ms, content_format=content_format)
        elif default_asset_type == "video":
            p = build_scene_video_prompt(
                scene, ms, brand_preset=brand_preset,
                content_format=content_format, duration_seconds=duration_seconds,
            )
        else:
            p = build_scene_image_prompt(
                scene, ms, brand_preset=brand_preset, content_format=content_format, platform=platform,
            )

        if ms.fallback_type in ("manual_prompt_card", "styled_scene_card", "screenshot_needed"):
            p.provider_hint = "prompt_card_only"
            p.notes.append(f"fallback_type={ms.fallback_type}")

        p.warnings = validate_visual_generation_prompt(p)
        prompts.append(p)
    return prompts
