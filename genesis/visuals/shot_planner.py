"""
Genesis Studio — Per-format shot planning (no video generation).
"""

from __future__ import annotations

import re
from typing import Any

from genesis.creative.script_models import VIRAL_SPINE_SECTIONS
from genesis.visuals.storyboard_models import VisualScene

SHOT_TYPES = (
    "talking_head",
    "product_closeup",
    "hand_demonstration",
    "before_after",
    "walking_talk",
    "environment_broll",
    "text_overlay",
    "screen_recording",
    "reaction_shot",
    "process_demo",
    "meditation_scene",
    "fundraiser_context",
    "local_business_exterior",
    "proof_screenshot",
)

_SECTION_SHOT_DEFAULTS: dict[str, dict[str, str]] = {
    "Pattern Interrupt": {
        "shot_type": "product_closeup",
        "visual_goal": "Stop the scroll with a strong opening visual.",
        "camera": "Vertical 9:16, tight framing, subject centered, high contrast.",
    },
    "Proof": {
        "shot_type": "proof_screenshot",
        "visual_goal": "Establish credibility with real proof or context.",
        "camera": "Vertical 9:16, readable text, steady hold 2–3 seconds.",
    },
    "Demonstration / Teaching": {
        "shot_type": "hand_demonstration",
        "visual_goal": "Show the core action or teaching step clearly.",
        "camera": "Vertical 9:16, hands and subject in frame, stable or slow push-in.",
    },
    "Meaning": {
        "shot_type": "talking_head",
        "visual_goal": "Connect emotionally or explain why this matters.",
        "camera": "Vertical 9:16, eye-level, soft natural light, clean background.",
    },
    "CTA": {
        "shot_type": "text_overlay",
        "visual_goal": "Drive the next step with a clear closing visual.",
        "camera": "Vertical 9:16, leave lower-third safe space for captions.",
    },
}

_FORMAT_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "affiliate_followup": {
        "Pattern Interrupt": {"shot_type": "product_closeup", "visual_goal": "Stop the scroll with a close-up product moment."},
        "Proof": {"shot_type": "proof_screenshot", "visual_goal": "Show buyer interest, comments, or social proof (film separately)."},
        "Demonstration / Teaching": {"shot_type": "hand_demonstration", "visual_goal": "Demonstrate the product in real use."},
        "CTA": {"shot_type": "text_overlay", "visual_goal": "Pinned comment / keyword CTA — film CTA clip separately."},
    },
    "product_demo": {
        "Pattern Interrupt": {"shot_type": "product_closeup"},
        "Demonstration / Teaching": {"shot_type": "process_demo"},
        "Meaning": {"shot_type": "environment_broll"},
    },
    "wellness_teaching": {
        "Pattern Interrupt": {"shot_type": "meditation_scene", "visual_goal": "Calm opening — breath or stillness."},
        "Demonstration / Teaching": {"shot_type": "meditation_scene", "visual_goal": "Guided practice — bowl, breath, or grounding cue."},
        "Proof": {"shot_type": "talking_head", "visual_goal": "Gentle credibility — no medical claims on screen."},
    },
    "fundraising_story": {
        "Pattern Interrupt": {"shot_type": "fundraiser_context", "visual_goal": "Respectful context — who/what needs support."},
        "Proof": {"shot_type": "fundraiser_context", "visual_goal": "Show need without exploitative framing."},
        "Demonstration / Teaching": {"shot_type": "talking_head", "visual_goal": "Explain the situation honestly."},
        "CTA": {"shot_type": "text_overlay", "visual_goal": "Donation/support CTA — link in bio or pinned comment."},
    },
    "motivational_walkthrough": {
        "Pattern Interrupt": {"shot_type": "walking_talk"},
        "Demonstration / Teaching": {"shot_type": "walking_talk"},
        "Meaning": {"shot_type": "environment_broll"},
    },
    "tutorial": {
        "Pattern Interrupt": {"shot_type": "process_demo", "visual_goal": "Preview the finished result or materials."},
        "Demonstration / Teaching": {"shot_type": "process_demo", "visual_goal": "Step-by-step process closeups."},
        "Proof": {"shot_type": "before_after"},
    },
    "controversial_take": {
        "Pattern Interrupt": {"shot_type": "talking_head", "visual_goal": "Direct hook — clean framing, no ragebait cuts."},
        "Proof": {"shot_type": "proof_screenshot"},
    },
    "personal_story": {
        "Pattern Interrupt": {"shot_type": "talking_head", "visual_goal": "Emotional open — honest eye contact."},
        "Meaning": {"shot_type": "environment_broll", "visual_goal": "Memory or context B-roll — paced pauses."},
    },
}


def infer_shot_type(section_name: str, content_format: str) -> str:
    overrides = _FORMAT_OVERRIDES.get(content_format, {})
    sec = overrides.get(section_name, {})
    if sec.get("shot_type"):
        return str(sec["shot_type"])
    return _SECTION_SHOT_DEFAULTS.get(section_name, {}).get("shot_type", "talking_head")


def generate_visual_goal(
    section_name: str,
    content_format: str,
    narration_snippet: str,
) -> str:
    overrides = _FORMAT_OVERRIDES.get(content_format, {})
    sec = overrides.get(section_name, {})
    if sec.get("visual_goal"):
        return str(sec["visual_goal"])
    base = _SECTION_SHOT_DEFAULTS.get(section_name, {}).get("visual_goal", "Support the narration.")
    if narration_snippet and len(narration_snippet) < 120:
        return f"{base} Narration: {narration_snippet[:80]}."
    return base


def generate_camera_direction(
    shot_type: str,
    *,
    creator_on_camera: bool = True,
    platforms: list[str] | None = None,
) -> str:
    vertical = "Vertical 9:16" if not platforms or any(
        p in ("instagram_reels", "tiktok", "clapper", "youtube_shorts") for p in platforms
    ) else "Match primary platform aspect ratio"

    by_type: dict[str, str] = {
        "product_closeup": f"{vertical}, tight close-up, product centered, shallow depth of field.",
        "hand_demonstration": f"{vertical}, hands and product in frame, stable tripod or slow push-in.",
        "proof_screenshot": f"{vertical}, screen recording or filmed phone screen — readable text.",
        "talking_head": f"{vertical}, eye-level, {'creator on camera' if creator_on_camera else 'voiceover with B-roll'}.",
        "meditation_scene": f"{vertical}, soft light, minimal movement, calming composition.",
        "fundraiser_context": f"{vertical}, respectful distance, natural light, no sensational angles.",
        "walking_talk": f"{vertical}, gimbal or steady walk, environment visible, mic wind protection.",
        "process_demo": f"{vertical}, overhead or 45° angle for steps, consistent lighting.",
        "environment_broll": f"{vertical}, slow pans, 2–4 second holds, no shaky handheld.",
        "text_overlay": f"{vertical}, static or subtle motion; leave lower-third safe for captions.",
        "walking_talk": f"{vertical}, walking medium shot, environment context visible.",
    }
    return by_type.get(shot_type, f"{vertical}, clean framing, stable shot.")


def generate_subject_action(
    shot_type: str,
    content_format: str,
    clean_subject: str,
    section_name: str,
) -> str:
    subj = clean_subject or "the subject"
    actions: dict[str, str] = {
        "product_closeup": f"Frame {subj} clearly; show key feature in first second.",
        "hand_demonstration": f"Demonstrate {subj} in one continuous action — hands in frame.",
        "proof_screenshot": "Film comment thread, DM, or proof screen separately; hold steady.",
        "meditation_scene": "Slow breath, bowl strike, or grounding gesture — calm pace.",
        "fundraiser_context": "Show the person, animal, or cause context respectfully — no shock imagery.",
        "walking_talk": "Walk and deliver the line naturally; pause for emphasis.",
        "process_demo": "Perform one clear step; repeat for coverage if needed.",
        "text_overlay": "Hold on product or face while CTA text will overlay in edit.",
        "proof_screenshot": "Capture proof UI or comments as a separate insert.",
    }
    if section_name == "CTA" and content_format in ("affiliate_followup", "fundraising_story"):
        return "Film a dedicated CTA beat — point to comment, bio, or support link placeholder."
    return actions.get(shot_type, f"Perform the action that matches: {section_name}.")


def generate_broll_suggestions(
    shot_type: str,
    content_format: str,
    clean_subject: str,
) -> list[str]:
    subj = clean_subject or "subject"
    common: list[str] = ["2–3 second hold before action", "2–3 second hold after action", "wide + close-up coverage"]

    by_format: dict[str, list[str]] = {
        "affiliate_followup": [
            f"{subj} in hand", "feature close-up", "sunlight or use environment if relevant",
            "comment/DM proof screen (separate clip)",
        ],
        "product_demo": [f"{subj} packaging", "use-case environment", "result or reaction"],
        "wellness_teaching": ["calm hands", "breath pause", "soft texture B-roll", "session space wide shot"],
        "fundraising_story": ["gentle context wide", "support materials", "thank-you placeholder — no guilt imagery"],
        "motivational_walkthrough": ["path or street", "skyline cutaway", "feet walking", "pause on horizon"],
        "tutorial": ["materials flat lay", "each step close-up", "before/after comparison"],
        "controversial_take": ["clean talking head alt angle", "context prop wide"],
        "personal_story": ["memory object close-up", "window light", "slow environment pan"],
    }
    out = list(by_format.get(content_format, [f"{subj} context", "environment texture"]))
    if shot_type == "product_closeup":
        out.insert(0, "macro detail of key feature")
    return list(dict.fromkeys(common + out))[:8]


def generate_props_needed(
    content_format: str,
    clean_subject: str,
    available_props: list[str] | None = None,
) -> list[str]:
    props: list[str] = []
    if clean_subject:
        props.append(clean_subject)
    fmt_props: dict[str, list[str]] = {
        "affiliate_followup": ["product sample", "phone for proof screenshot"],
        "product_demo": ["product", "any demo accessories"],
        "wellness_teaching": ["bowl or mat", "comfortable seating"],
        "fundraising_story": ["optional photo of cause", "phone for link overlay"],
        "tutorial": ["materials for each step", "measuring tools if applicable"],
        "motivational_walkthrough": ["comfortable shoes", "optional mic"],
    }
    props.extend(fmt_props.get(content_format, []))
    if available_props:
        props = list(dict.fromkeys(available_props + props))
    return list(dict.fromkeys(props))[:10]


def generate_location_notes(
    content_format: str,
    location: str = "",
    filming_context: str = "",
) -> str | None:
    parts: list[str] = []
    if location:
        parts.append(location)
    if filming_context:
        parts.append(filming_context)
    fmt_loc: dict[str, str] = {
        "affiliate_followup": "Bright natural light or clean desk; avoid cluttered background.",
        "wellness_teaching": "Quiet indoor space; soft light; minimal visual noise.",
        "fundraising_story": "Neutral, respectful setting — home or community space.",
        "motivational_walkthrough": "Outdoor path, park, or store exterior if brief mentions retail.",
        "tutorial": "Well-lit workspace; consistent surface for steps.",
    }
    if content_format in fmt_loc:
        parts.append(fmt_loc[content_format])
    return "; ".join(parts) if parts else None


def generate_editing_notes(
    section_name: str,
    shot_type: str,
    content_format: str,
) -> list[str]:
    notes = ["Match cut to narration beat", "Leave safe margin for on-screen captions"]
    if section_name == "Pattern Interrupt":
        notes.insert(0, "Quick cut within first second; caption punch-in optional")
    if section_name == "CTA":
        notes.append("Hold CTA frame 2–3 seconds minimum")
    if shot_type == "proof_screenshot":
        notes.append("Blur personal info if needed before publish")
    if content_format == "wellness_teaching":
        notes.append("Slow transitions; avoid flashy transitions")
    if content_format == "fundraising_story":
        notes.append("Avoid sensational music or exploitative zooms")
    return notes


def generate_risk_notes(
    content_format: str,
    *,
    has_affiliate_disclosure: bool = False,
    has_fundraising: bool = False,
    sponsorship_claimed: bool = False,
    affiliate_approved: bool = False,
) -> list[str]:
    risks: list[str] = []
    if content_format == "affiliate_followup" and not affiliate_approved:
        risks.append("Do not imply official partnership or affiliate approval unless brief confirms it.")
    if has_affiliate_disclosure:
        risks.append("Include affiliate disclosure on screen or in caption per metadata.")
    if content_format == "fundraising_story":
        risks.extend([
            "Avoid exploitative or shock imagery.",
            "Do not guarantee outcomes from donations.",
        ])
    if content_format == "wellness_teaching":
        risks.append("No medical cure claims or before/after health promises on screen.")
    if not sponsorship_claimed:
        risks.append("Do not show sponsored/#ad overlays unless sponsorship is confirmed.")
    return risks


def build_scene_from_section(
    *,
    scene_index: int,
    section_name: str,
    narration_text: str,
    content_format: str,
    clean_subject: str,
    platforms: list[str],
    creator_on_camera: bool,
    location: str,
    filming_context: str,
    available_props: list[str] | None,
    overlay_text: str | None,
    timing_hint: str,
    risk_context: dict[str, Any],
) -> VisualScene:
    shot_type = infer_shot_type(section_name, content_format)
    return VisualScene(
        scene_id=f"scene_{scene_index + 1:02d}",
        section_name=section_name,
        narration_text=narration_text,
        visual_goal=generate_visual_goal(section_name, content_format, narration_text),
        shot_type=shot_type,
        camera_direction=generate_camera_direction(
            shot_type, creator_on_camera=creator_on_camera, platforms=platforms
        ),
        subject_action=generate_subject_action(shot_type, content_format, clean_subject, section_name),
        broll_suggestions=generate_broll_suggestions(shot_type, content_format, clean_subject),
        overlay_text=overlay_text,
        timing_hint=timing_hint,
        props_needed=generate_props_needed(content_format, clean_subject, available_props),
        location_notes=generate_location_notes(content_format, location, filming_context),
        editing_notes=generate_editing_notes(section_name, shot_type, content_format),
        risk_notes=generate_risk_notes(
            content_format,
            has_affiliate_disclosure=risk_context.get("affiliate_disclosure", False),
            has_fundraising=risk_context.get("fundraising", False),
            sponsorship_claimed=risk_context.get("sponsorship", False),
            affiliate_approved=risk_context.get("affiliate_approved", False),
        ),
    )


def default_section_names(script_sections: list[Any]) -> list[str]:
    if script_sections:
        return [getattr(s, "name", None) or getattr(s, "section_name", f"Section {i+1}")
                for i, s in enumerate(script_sections)]
    return list(VIRAL_SPINE_SECTIONS)
