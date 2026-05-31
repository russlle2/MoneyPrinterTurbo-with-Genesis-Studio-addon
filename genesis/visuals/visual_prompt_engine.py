"""
Genesis Studio — Text-only visual prompt cards (no image/video API calls).
"""

from __future__ import annotations

import re
from typing import Any

from genesis.visuals.storyboard_models import VisualPrompt, VisualScene

_BAD_FRAGMENT_PATTERNS = [
    re.compile(r"\bmy girlfriend demonstrates\b", re.I),
    re.compile(r"\bnobody talks about my\b", re.I),
    re.compile(r"\bdemonstrates a solar-powered\b", re.I),
    re.compile(r"\bi tested my\b", re.I),
]

_FORBIDDEN_PROMPT_TERMS = re.compile(
    r"\b(?:api[_-]?key|sk_[a-z0-9]{8,}|voice_id|xi-api|openai_api)\b",
    re.I,
)

_PROVIDER_HINTS = frozenset({
    "manual",
    "chatgpt_sora",
    "comfyui_cogvideox",
    "runway_optional",
    "pika_optional",
    "generic_image_model",
})


def sanitize_visual_prompt(text: str, *, clean_subject: str = "") -> str:
    """Remove awkward fragments and secret-like tokens from prompt text."""
    out = text.strip()
    for pat in _BAD_FRAGMENT_PATTERNS:
        out = pat.sub("", out)
    out = _FORBIDDEN_PROMPT_TERMS.sub("", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    if clean_subject and len(out) < 20:
        out = f"Cinematic short-form clip featuring {clean_subject}. {out}".strip()
    return out[:1200]


def validate_visual_prompt(prompt: VisualPrompt) -> list[str]:
    warnings: list[str] = []
    if not prompt.prompt_text.strip():
        warnings.append(f"empty prompt_text for {prompt.prompt_id}")
    if _FORBIDDEN_PROMPT_TERMS.search(prompt.prompt_text):
        warnings.append(f"prompt {prompt.prompt_id} may contain sensitive tokens")
    if prompt.provider_hint not in _PROVIDER_HINTS:
        warnings.append(f"unknown provider_hint: {prompt.provider_hint}")
    return warnings


def build_hero_prompt(
    clean_subject: str,
    visual_style: str,
    *,
    content_format: str = "product_demo",
    hook: str = "",
) -> str:
    hook_line = f" Opening energy: {hook[:100]}." if hook else ""
    base = (
        f"Short-form vertical hero shot, {visual_style}. "
        f"Subject: {clean_subject or 'the main subject'}.{hook_line} "
        f"Photorealistic, social-native framing, 9:16, 3–5 seconds."
    )
    if content_format == "wellness_teaching":
        base += " Calm, soft light, no medical imagery."
    if content_format == "fundraising_story":
        base += " Respectful, documentary tone, no sensationalism."
    return sanitize_visual_prompt(base, clean_subject=clean_subject)


def build_scene_prompt(scene: VisualScene, clean_subject: str, visual_style: str) -> str:
    overlay = f" On-screen text area: {scene.overlay_text}." if scene.overlay_text else ""
    return sanitize_visual_prompt(
        f"{visual_style}. {scene.visual_goal} "
        f"Shot: {scene.shot_type}. Action: {scene.subject_action}. "
        f"Camera: {scene.camera_direction}{overlay}",
        clean_subject=clean_subject,
    )


def build_broll_prompt(broll_line: str, clean_subject: str, visual_style: str) -> str:
    return sanitize_visual_prompt(
        f"B-roll insert, {visual_style}. {broll_line}. "
        f"Context: {clean_subject or 'main subject'}. Slow motion optional, 9:16.",
        clean_subject=clean_subject,
    )


def build_hero_prompt_card_markdown(
    prompt_text: str,
    *,
    job_id: str,
    provider_hint: str = "manual",
) -> str:
    """Markdown body aligned with hero_shot_provider manual card pattern (text only)."""
    return (
        f"# Hero Shot Prompt Card\n\n"
        f"**Job ID:** `{job_id}`\n"
        f"**Provider hint:** {provider_hint} (text only — no auto-generation in Phase 14)\n\n"
        f"## Prompt\n\n{prompt_text}\n\n"
        f"## Settings\n\n"
        f"- Duration: 3–5s\n- Aspect ratio: 9:16\n"
        f"- Import path: `assets/manual_hero_shots/imports/`\n\n"
        f"Use `generate_hero_shot()` from `genesis.integrations.hero_shot_provider` "
        f"when you are ready to generate — not called automatically.\n"
    )


def generate_visual_prompts(
    scenes: list[VisualScene],
    *,
    job_id: str,
    clean_subject: str,
    visual_style: str,
    content_format: str,
    primary_hook: str,
    broll_plan: list[str],
) -> list[VisualPrompt]:
    prompts: list[VisualPrompt] = []

    hero_text = build_hero_prompt(
        clean_subject, visual_style, content_format=content_format, hook=primary_hook
    )
    prompts.append(VisualPrompt(
        prompt_id=f"{job_id}_hero",
        scene_id="hero",
        prompt_type="hero_shot",
        prompt_text=hero_text,
        negative_prompt="blurry, watermark, text gibberish, low quality, distorted hands",
        intended_use="Opening hook or thumbnail source",
        provider_hint="manual",
        safety_notes=["Do not auto-call paid video APIs in Phase 14."],
    ))

    for scene in scenes:
        scene_text = build_scene_prompt(scene, clean_subject, visual_style)
        provider = "comfyui_cogvideox" if scene.shot_type in ("product_closeup", "environment_broll") else "manual"
        prompts.append(VisualPrompt(
            prompt_id=f"{job_id}_{scene.scene_id}",
            scene_id=scene.scene_id,
            prompt_type="manual_shot_card",
            prompt_text=scene_text,
            negative_prompt="shaky, overexposed, copyrighted logos, misleading claims",
            intended_use=f"Reference for filming {scene.section_name}",
            provider_hint=provider,
            safety_notes=list(scene.risk_notes[:3]),
        ))

    for i, broll in enumerate(broll_plan[:6]):
        prompts.append(VisualPrompt(
            prompt_id=f"{job_id}_broll_{i+1:02d}",
            scene_id=scenes[min(i, len(scenes) - 1)].scene_id if scenes else "scene_01",
            prompt_type="broll",
            prompt_text=build_broll_prompt(broll, clean_subject, visual_style),
            intended_use="Supplemental B-roll",
            provider_hint="generic_image_model",
            safety_notes=[],
        ))

    if content_format in ("affiliate_followup", "product_demo"):
        prompts.append(VisualPrompt(
            prompt_id=f"{job_id}_thumb",
            scene_id="hero",
            prompt_type="thumbnail_concept",
            prompt_text=sanitize_visual_prompt(
                f"Thumbnail concept: {clean_subject or 'product'}, bold contrast, "
                f"curiosity gap, no false claims.",
                clean_subject=clean_subject,
            ),
            intended_use="Cover frame reference",
            provider_hint="generic_image_model",
        ))

    return prompts


def format_visual_prompts_md(prompts: list[VisualPrompt], *, job_id: str) -> str:
    lines = [f"# Visual Prompts — {job_id}\n", "_Text-only prompt cards. No images generated in Phase 14._\n"]
    for p in prompts:
        lines.append(f"## {p.prompt_id} ({p.prompt_type})\n")
        lines.append(f"- **Scene:** {p.scene_id}")
        lines.append(f"- **Provider hint:** {p.provider_hint}")
        lines.append(f"- **Use:** {p.intended_use}\n")
        lines.append(f"**Prompt:**\n\n{p.prompt_text}\n")
        if p.negative_prompt:
            lines.append(f"**Negative:** {p.negative_prompt}\n")
        if p.safety_notes:
            lines.append(f"**Safety:** {'; '.join(p.safety_notes)}\n")
    return "\n".join(lines)
