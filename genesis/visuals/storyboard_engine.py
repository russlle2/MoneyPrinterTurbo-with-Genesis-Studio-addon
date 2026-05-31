"""
Genesis Studio — Storyboard package generation (no video rendering).
"""

from __future__ import annotations

import re
from typing import Any

from genesis.creative.script_models import VIRAL_SPINE_SECTIONS
from genesis.visuals.filming_checklist import (
    generate_editing_checklist,
    generate_filming_checklist,
)
from genesis.visuals.shot_planner import (
    build_scene_from_section,
    default_section_names,
    generate_broll_suggestions,
    generate_props_needed,
)
from genesis.visuals.storyboard_models import (
    ShotPlan,
    StoryboardPackage,
    StoryboardStatus,
    VisualScene,
)
from genesis.visuals.visual_prompt_engine import (
    format_visual_prompts_md,
    generate_visual_prompts,
    validate_visual_prompt,
)

_STYLE_BY_FORMAT: dict[str, str] = {
    "affiliate_followup": "clean product-forward, natural light, social-native",
    "product_demo": "crisp demo, hands-on, practical",
    "wellness_teaching": "calm, soft tones, minimal clutter",
    "fundraising_story": "documentary-respectful, warm, honest",
    "motivational_walkthrough": "outdoor energy, reflective cutaways",
    "tutorial": "step-by-step clarity, well-lit workspace",
    "controversial_take": "direct talking head, clean framing",
    "personal_story": "intimate, natural light, paced pauses",
}

_TOPIC_LEAK_SOLAR = re.compile(r"\b(?:solar|lighter|sunlight|sun angle)\b", re.I)
_TOPIC_LEAK_FUNDRAISE = re.compile(r"\b(?:gofundme|donate now|mutual aid)\b", re.I)


def infer_visual_style(content_format: str, tone: str = "") -> str:
    base = _STYLE_BY_FORMAT.get(content_format, "short-form social, vertical, authentic")
    if tone:
        return f"{base}; tone: {tone}"
    return base


def _primary_hook(script_package: Any | None, metadata_package: Any | None, idea: str) -> str:
    if metadata_package is not None:
        h = getattr(metadata_package, "primary_hook", "") or ""
        if h.strip():
            return h.strip()
    if script_package is not None:
        hooks = getattr(script_package, "hooks", None) or []
        if hooks:
            return str(hooks[0].text).strip()
    return idea.strip()[:200]


def _clean_subject(brief: Any, script_package: Any | None) -> str:
    try:
        from genesis.creative.idea_normalizer import normalize_idea_context
        fmt = getattr(script_package, "content_format", None) or "product_demo"
        norm = normalize_idea_context(
            brief.idea,
            audience=getattr(brief, "audience", ""),
            content_goal=getattr(brief, "content_goal", ""),
            offer=getattr(brief, "offer", ""),
            cta=getattr(brief, "cta", ""),
            content_format=fmt,
        )
        return norm.clean_subject or brief.idea[:80]
    except Exception:  # noqa: BLE001
        return brief.idea[:80]


def align_sections_to_scenes(
    script_package: Any | None,
    script_text: str = "",
) -> list[tuple[str, str]]:
    """Return (section_name, narration_text) pairs."""
    pairs: list[tuple[str, str]] = []
    if script_package is not None:
        primary = getattr(script_package, "primary_script", None)
        sections = getattr(primary, "sections", None) if primary else None
        if sections:
            for sec in sections:
                name = getattr(sec, "name", "Section")
                text = getattr(sec, "text", "").strip()
                pairs.append((name, text))
            return pairs

    if script_text.strip():
        blocks = [b.strip() for b in re.split(r"\n\s*\n", script_text) if b.strip()]
        names = list(VIRAL_SPINE_SECTIONS)
        for i, block in enumerate(blocks[: len(names)]):
            pairs.append((names[i], block))
        if pairs:
            return pairs

    return [(name, "") for name in VIRAL_SPINE_SECTIONS]


def align_overlay_captions_to_scenes(
    scenes: list[VisualScene],
    overlay_captions: list[Any],
) -> list[VisualScene]:
    if not overlay_captions:
        return scenes
    caps = list(overlay_captions)
    for i, scene in enumerate(scenes):
        if i < len(caps):
            cap = caps[i]
            text = getattr(cap, "text", "") or ""
            timing = getattr(cap, "timing_hint", "") or scene.timing_hint
            if text and not scene.overlay_text:
                scene.overlay_text = text
            if timing:
                scene.timing_hint = timing
        elif caps and not scene.overlay_text:
            scene.overlay_text = getattr(caps[-1], "text", None)
    return scenes


def _risk_context_from_metadata(metadata_package: Any | None, content_format: str) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "affiliate_disclosure": False,
        "fundraising": content_format == "fundraising_story",
        "sponsorship": False,
        "affiliate_approved": False,
    }
    if metadata_package is None:
        return ctx
    disclosures = getattr(metadata_package, "disclosures", None) or {}
    ctx["affiliate_disclosure"] = "affiliate" in disclosures
    ctx["fundraising"] = "fundraising" in disclosures or ctx["fundraising"]
    ctx["sponsorship"] = "sponsored" in disclosures
    brief_aff = getattr(metadata_package, "content_format", "")
    if brief_aff == "affiliate_followup":
        pass
    return ctx


def _quality_filter_scenes(
    scenes: list[VisualScene],
    *,
    content_format: str,
    idea: str,
) -> list[str]:
    warnings: list[str] = []
    idea_low = idea.lower()
    for scene in scenes:
        blob = f"{scene.narration_text} {scene.visual_goal} {scene.subject_action} ".lower()
        if _TOPIC_LEAK_SOLAR.search(blob) and not _TOPIC_LEAK_SOLAR.search(idea_low):
            scene.visual_goal = re.sub(
                _TOPIC_LEAK_SOLAR, "the product", scene.visual_goal, flags=re.I
            )
            warnings.append(f"{scene.scene_id}: removed unrelated solar references")
        if content_format != "fundraising_story" and _TOPIC_LEAK_FUNDRAISE.search(blob):
            if not _TOPIC_LEAK_FUNDRAISE.search(idea_low):
                scene.visual_goal = re.sub(
                    _TOPIC_LEAK_FUNDRAISE, "support link", scene.visual_goal, flags=re.I
                )
                warnings.append(f"{scene.scene_id}: softened fundraising language")
        for pat in (
            r"\bmy girlfriend demonstrates\b",
            r"\bnobody talks about my\b",
        ):
            if re.search(pat, blob, re.I):
                scene.narration_text = re.sub(pat, "", scene.narration_text, flags=re.I).strip()
                warnings.append(f"{scene.scene_id}: sanitized awkward narration fragment")
    return warnings


def generate_visual_scenes(
    brief: Any,
    *,
    script_package: Any | None = None,
    script_text: str = "",
    metadata_package: Any | None = None,
    content_format: str = "product_demo",
    platforms: list[str] | None = None,
    filming_context: str = "",
    available_props: list[str] | None = None,
    location: str = "",
    creator_on_camera: bool = True,
    overlay_captions: list[Any] | None = None,
) -> list[VisualScene]:
    fmt = content_format or (
        getattr(script_package, "content_format", None) or "product_demo"
    )
    clean = _clean_subject(brief, script_package)
    plats = platforms or getattr(brief, "platforms", []) or []
    risk = _risk_context_from_metadata(metadata_package, fmt)

    section_pairs = align_sections_to_scenes(script_package, script_text)
    if not section_pairs:
        section_pairs = [(n, "") for n in VIRAL_SPINE_SECTIONS]

    scenes: list[VisualScene] = []
    for i, (name, narration) in enumerate(section_pairs):
        timing = f"section {i + 1}/{len(section_pairs)}"
        scenes.append(build_scene_from_section(
            scene_index=i,
            section_name=name,
            narration_text=narration or f"[{name}]",
            content_format=fmt,
            clean_subject=clean,
            platforms=plats,
            creator_on_camera=creator_on_camera,
            location=location,
            filming_context=filming_context,
            available_props=available_props,
            overlay_text=None,
            timing_hint=timing,
            risk_context=risk,
        ))

    overlays = overlay_captions
    if overlays is None and script_package is not None:
        overlays = getattr(script_package, "overlay_captions", None) or []
    scenes = align_overlay_captions_to_scenes(scenes, overlays or [])

    if scenes and metadata_package is not None:
        hook = _primary_hook(script_package, metadata_package, brief.idea)
        scenes[0].narration_text = hook or scenes[0].narration_text
        scenes[0].visual_goal = (
            f"Open with primary hook energy. {scenes[0].visual_goal}"
        )[:300]

    return scenes


def validate_storyboard_package(package: StoryboardPackage) -> list[str]:
    warnings: list[str] = package.notes.copy()
    if not package.shot_plan.scenes:
        warnings.append("shot plan has no scenes")
    for p in package.visual_prompts:
        warnings.extend(validate_visual_prompt(p))
    if len(package.shot_plan.scenes) != len(
        set(s.section_name for s in package.shot_plan.scenes)
    ) and len(package.shot_plan.scenes) < 3:
        warnings.append("fewer than 3 distinct scenes")
    return list(dict.fromkeys(warnings))


def generate_storyboard_package(
    brief: Any,
    script_package: Any | None = None,
    *,
    metadata_package: Any | None = None,
    script_text: str = "",
    overlay_captions: list[Any] | None = None,
    narration_path: str = "",
    content_format: str = "",
    platforms: list[str] | None = None,
    filming_context: str = "",
    available_props: list[str] | None = None,
    location: str = "",
    creator_on_camera: bool = True,
) -> StoryboardPackage:
    """Build full StoryboardPackage from workflow inputs."""
    fmt = content_format or (
        getattr(script_package, "content_format", None) or "product_demo"
    )
    hook = _primary_hook(script_package, metadata_package, brief.idea)
    clean = _clean_subject(brief, script_package)
    style = infer_visual_style(fmt, getattr(brief, "tone", ""))

    scenes = generate_visual_scenes(
        brief,
        script_package=script_package,
        script_text=script_text,
        metadata_package=metadata_package,
        content_format=fmt,
        platforms=platforms,
        filming_context=filming_context,
        available_props=available_props,
        location=location,
        creator_on_camera=creator_on_camera,
        overlay_captions=overlay_captions,
    )

    quality_warnings = _quality_filter_scenes(scenes, content_format=fmt, idea=brief.idea)

    broll_master: list[str] = []
    for s in scenes:
        broll_master.extend(s.broll_suggestions)
    broll_plan = list(dict.fromkeys(broll_master))[:12]

    props = generate_props_needed(fmt, clean, available_props)
    loc_notes = [location] if location else []
    for s in scenes:
        if s.location_notes and s.location_notes not in loc_notes:
            loc_notes.append(s.location_notes)

    shot_plan = ShotPlan(
        job_id=brief.job_id,
        content_format=fmt,
        visual_style=style,
        scenes=scenes,
        broll_plan=broll_plan,
        required_props=props,
        filming_locations=loc_notes,
        audio_notes=[],
        lighting_notes=[
            "Soft key light for talking head; diffuse window light preferred.",
            "Avoid mixed color temperatures (tungsten + daylight).",
        ],
        editing_notes=["Sync to Viral Spine section order", "Caption safe zone on all text overlays"],
        status=StoryboardStatus.COMPLETE if scenes else StoryboardStatus.PARTIAL,
        warnings=quality_warnings,
    )

    prompts = generate_visual_prompts(
        scenes,
        job_id=brief.job_id,
        clean_subject=clean,
        visual_style=style,
        content_format=fmt,
        primary_hook=hook,
        broll_plan=broll_plan,
    )

    overlay_count = len(overlay_captions or [])
    if script_package and not overlay_count:
        overlay_count = len(getattr(script_package, "overlay_captions", []) or [])

    filming = generate_filming_checklist(
        shot_plan,
        metadata_package=metadata_package,
        narration_path=narration_path,
        platforms=platforms or getattr(brief, "platforms", []),
    )
    editing = generate_editing_checklist(shot_plan, overlay_count=overlay_count)

    package = StoryboardPackage(
        job_id=brief.job_id,
        idea=brief.idea,
        content_format=fmt,
        primary_hook=hook,
        visual_style=style,
        shot_plan=shot_plan,
        visual_prompts=prompts,
        filming_checklist=filming,
        editing_checklist=editing,
        status=StoryboardStatus.COMPLETE if scenes else StoryboardStatus.PARTIAL,
        notes=quality_warnings,
    )
    package.notes.extend(validate_storyboard_package(package))
    return package


def format_scene_markdown(scene: VisualScene) -> str:
    lines = [
        f"### {scene.scene_id} — {scene.section_name}",
        "",
        f"**Narration:** {scene.narration_text}",
        f"**Visual goal:** {scene.visual_goal}",
        f"**Shot type:** {scene.shot_type}",
        f"**Camera direction:** {scene.camera_direction}",
        f"**Subject action:** {scene.subject_action}",
    ]
    if scene.overlay_text:
        lines.append(f"**Overlay text:** {scene.overlay_text}")
    if scene.timing_hint:
        lines.append(f"**Timing:** {scene.timing_hint}")
    if scene.broll_suggestions:
        lines.append("**B-roll:** " + "; ".join(scene.broll_suggestions))
    if scene.props_needed:
        lines.append("**Props:** " + ", ".join(scene.props_needed))
    if scene.editing_notes:
        lines.append("**Editing:** " + "; ".join(scene.editing_notes))
    if scene.risk_notes:
        lines.append("**Risk notes:** " + "; ".join(scene.risk_notes))
    return "\n".join(lines)
