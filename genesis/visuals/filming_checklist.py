"""
Genesis Studio — Manual filming and editing checklists.
"""

from __future__ import annotations

from typing import Any

from genesis.visuals.storyboard_models import ShotPlan, StoryboardPackage


def generate_audio_capture_notes(
    *,
    narration_path: str = "",
    narration_enabled: bool = False,
) -> list[str]:
    notes = [
        "Record room tone for 10 seconds if syncing generated voiceover later.",
        "Avoid copyrighted background music when using generated voiceover.",
    ]
    if narration_path:
        notes.insert(0, f"Narration reference: `{narration_path}` — align cuts to audio.")
    elif narration_enabled:
        notes.insert(0, "Narration will be generated — film visuals to match script pacing.")
    else:
        notes.insert(0, "Plan for voiceover or on-camera audio before final edit.")
    return notes


def generate_platform_framing_notes(platforms: list[str] | None = None) -> list[str]:
    plats = platforms or ["instagram_reels", "tiktok"]
    notes = ["Default vertical framing 9:16 for Reels, TikTok, Clapper, Shorts"]
    if "x" in plats and len(plats) == 1:
        notes.append("X may use 16:9 — capture a horizontal safety take if needed")
    return notes


def generate_filming_checklist(
    shot_plan: ShotPlan,
    *,
    metadata_package: Any | None = None,
    narration_path: str = "",
    platforms: list[str] | None = None,
) -> list[str]:
    items = [
        "Clean lens before filming",
        "Charge batteries and free storage space",
        "Record 2–3 seconds before and after each action",
        "Capture both close-up and wide for each key moment",
        "Film proof/comment screenshot as separate clip if needed",
        "Film CTA beat as separate clip",
        "Check lighting — avoid harsh backlit windows",
        "Leave safe space for on-screen captions (lower third)",
    ]
    items.extend(generate_platform_framing_notes(platforms))
    items.extend(shot_plan.lighting_notes)

    if metadata_package is not None:
        disclosures = getattr(metadata_package, "disclosures", None) or {}
        if disclosures:
            for d in disclosures.values():
                short = getattr(d, "short_text", "") or ""
                if short:
                    items.append(f"Disclosure reminder: {short}")
                    break

    if narration_path:
        items.append(f"Sync to narration file: {narration_path}")

    for loc in shot_plan.filming_locations:
        if loc:
            items.append(f"Location: {loc}")

    for prop in shot_plan.required_props[:6]:
        items.append(f"Prop ready: {prop}")

    return list(dict.fromkeys(items))


def generate_editing_checklist(
    shot_plan: ShotPlan,
    *,
    overlay_count: int = 0,
) -> list[str]:
    items = [
        "Import A-roll and B-roll into editor",
        "Place narration or voiceover on timeline first",
        "Cut Pattern Interrupt within first 1–2 seconds",
        "Add overlay captions from overlay_captions.json",
        "Verify caption safe zones on 9:16 preview",
        "Color-correct for consistent exposure across scenes",
        "Export 9:16 master; platform-specific crops if needed",
    ]
    if overlay_count:
        items.insert(4, f"Apply {overlay_count} timed overlay captions from script package")
    items.extend(shot_plan.editing_notes)
    return list(dict.fromkeys(items))


def build_visual_plan_from_storyboard(
    package: StoryboardPackage,
    *,
    script_source: str = "",
    platforms: list[str] | None = None,
) -> str:
    """Backward-compatible visual_plan.md from StoryboardPackage."""
    from genesis.workflows.models import platform_label

    plats = ", ".join(platform_label(p) for p in (platforms or []))
    lines = [
        f"# Visual Plan — {package.job_id}",
        "",
        f"**Content format:** {package.content_format}",
        f"**Visual style:** {package.visual_style}",
        f"**Platforms:** {plats or 'short-form vertical'}",
        f"**Script source:** {script_source or 'unknown'}",
        "",
        f"## Concept\n\n{package.idea}\n",
        f"**Primary hook:** {package.primary_hook}\n",
        "## Shot Breakdown\n",
        "| # | Section | Shot | Visual goal |",
        "|---|---------|------|-------------|",
    ]
    for i, scene in enumerate(package.shot_plan.scenes):
        goal = scene.visual_goal[:60] + ("…" if len(scene.visual_goal) > 60 else "")
        lines.append(
            f"| {i+1} | {scene.section_name} | {scene.shot_type} | {goal} |"
        )

    lines.append("\n## Scene Details\n")
    for scene in package.shot_plan.scenes:
        lines.append(f"### {scene.scene_id} — {scene.section_name}\n")
        lines.append(f"- **Narration:** {scene.narration_text[:200]}")
        lines.append(f"- **Shot type:** {scene.shot_type}")
        lines.append(f"- **Camera:** {scene.camera_direction}")
        lines.append(f"- **Action:** {scene.subject_action}")
        if scene.overlay_text:
            lines.append(f"- **Overlay text:** {scene.overlay_text}")
        if scene.broll_suggestions:
            lines.append(f"- **B-roll:** {', '.join(scene.broll_suggestions[:4])}")
        if scene.risk_notes:
            lines.append(f"- **Risks:** {'; '.join(scene.risk_notes[:2])}")
        lines.append("")

    lines.append("## Hero Shot\n")
    hero = next((p for p in package.visual_prompts if p.prompt_type == "hero_shot"), None)
    if hero:
        lines.append(f"```\n{hero.prompt_text[:400]}\n```\n")
    lines.append(
        "Generate manually via `genesis.integrations.hero_shot_provider.generate_hero_shot` "
        "when ready — not auto-triggered.\n"
    )
    lines.append("## Filming checklist\n")
    for item in package.filming_checklist[:12]:
        lines.append(f"- [ ] {item}")
    return "\n".join(lines)
