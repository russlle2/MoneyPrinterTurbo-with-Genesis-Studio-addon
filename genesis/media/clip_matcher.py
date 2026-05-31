"""
Genesis Studio — Deterministic clip-to-scene matching.
"""

from __future__ import annotations

import re
from typing import Any

from genesis.media.media_models import MediaAsset, SceneMediaMatch

# ─── Keyword tables ────────────────────────────────────────────────────────────
# Each entry: (scene keywords, asset role keywords, weight)
# A score ∈ [0, 1] is accumulated per asset×scene pair.

_SHOT_TYPE_ROLES: dict[str, list[str]] = {
    "product_closeup": ["product_closeup", "product_demo", "demonstration"],
    "demonstration": ["demonstration", "product_demo", "product_closeup", "social_proof"],
    "broll": ["broll", "walk_talk", "wellness", "ambient"],
    "text_overlay": ["social_proof", "reaction"],
    "talking_head": ["demonstration", "walk_talk", "social_proof"],
    "wellness": ["wellness"],
    "walking_talking": ["walk_talk"],
    "fundraiser_context": ["fundraiser"],
    "unboxing": ["unboxing", "product_demo"],
    "reaction": ["reaction", "social_proof"],
    "tutorial": ["tutorial", "demonstration"],
}

# Section-name → preferred asset roles
_SECTION_ROLES: dict[str, list[str]] = {
    "pattern interrupt": ["hook", "product_closeup", "demonstration"],
    "hook": ["hook", "product_closeup"],
    "problem": ["demonstration", "broll"],
    "solution": ["product_demo", "product_closeup", "demonstration"],
    "proof": ["social_proof", "reaction"],
    "cta": ["cta"],
    "outro": ["cta"],
    "b-roll": ["broll"],
    "broll": ["broll"],
    "context": ["fundraiser", "broll"],
    "support": ["fundraiser"],
    "meditation": ["wellness"],
    "breathwork": ["wellness"],
    "grounding": ["wellness"],
    "demonstration": ["demonstration", "product_demo"],
    "tutorial": ["tutorial"],
    "walkthrough": ["walk_talk", "tutorial"],
    "intro": ["hook", "demonstration"],
}

# Words in visual_goal / broll_suggestions → boost specific asset roles
_BROLL_ROLE_HINTS: list[tuple[str, str]] = [
    ("close-up", "product_closeup"),
    ("closeup", "product_closeup"),
    ("product", "product_demo"),
    ("demo", "demonstration"),
    ("bowl", "wellness"),
    ("meditation", "wellness"),
    ("breath", "wellness"),
    ("donation", "fundraiser"),
    ("fundrais", "fundraiser"),
    ("walking", "walk_talk"),
    ("store", "walk_talk"),
    ("reaction", "reaction"),
    ("unbox", "unboxing"),
    ("screen", "social_proof"),
    ("comment", "social_proof"),
]


def infer_scene_keywords(scene: dict[str, Any]) -> list[str]:
    """Extract searchable keyword tokens from a storyboard scene dict."""
    parts = [
        scene.get("section_name", ""),
        scene.get("visual_goal", ""),
        scene.get("shot_type", ""),
        " ".join(scene.get("broll_suggestions", [])),
        scene.get("overlay_text", ""),
        scene.get("narration_text", "")[:80],
    ]
    text = " ".join(p for p in parts if p).lower()
    tokens = re.findall(r"[a-z]{3,}", text)
    return list(dict.fromkeys(tokens))  # deduped, order-preserved


def score_asset_for_scene(
    asset: MediaAsset,
    scene: dict[str, Any],
    *,
    all_assets: list[MediaAsset] | None = None,
) -> float:
    """Return a match score ∈ [0, 1] for an asset×scene pair."""
    score = 0.0

    # 1. Explicit scene hint from filename (scene_01, scene_02 …)
    scene_id = scene.get("scene_id", "")
    scene_hint = _scene_hint_from_filename(asset.filename)
    if scene_hint and scene_hint == scene_id:
        score += 0.9

    # 2. Asset role vs. shot_type preferred roles
    shot_type = scene.get("shot_type", "")
    preferred_roles = _SHOT_TYPE_ROLES.get(shot_type, [])
    if asset.inferred_role and asset.inferred_role in preferred_roles:
        score += 0.35

    # 3. Asset role vs. section name preferred roles
    section = scene.get("section_name", "").lower().strip()
    for key, roles in _SECTION_ROLES.items():
        if key in section and asset.inferred_role in roles:
            score += 0.25
            break

    # 4. broll_suggestions / visual_goal keyword match
    visual_text = (
        scene.get("visual_goal", "") + " "
        + " ".join(scene.get("broll_suggestions", []))
    ).lower()
    for hint, role in _BROLL_ROLE_HINTS:
        if hint in visual_text and asset.inferred_role == role:
            score += 0.2
            break

    # 5. Tag overlap with scene keywords
    scene_kws = set(infer_scene_keywords(scene))
    asset_tags = set(t.lower() for t in asset.tags)
    overlap = len(scene_kws & asset_tags)
    if overlap:
        score += min(0.15, overlap * 0.05)

    # 6. Vertical orientation bonus (9:16 preferred)
    if asset.orientation == "vertical":
        score += 0.05

    return min(score, 1.0)


def _scene_hint_from_filename(name: str) -> str:
    m = re.search(r"scene[_\-]?(\d+)", name, re.I)
    if m:
        return f"scene_{int(m.group(1)):02d}"
    return ""


def assign_assets_to_scenes(
    scenes: list[dict[str, Any]],
    assets: list[MediaAsset],
    *,
    min_confidence: float = 0.05,
) -> list[SceneMediaMatch]:
    """
    Assign available assets to scenes deterministically.
    Each asset may be reused across scenes (no exclusive assignment).
    """
    visual_assets = [a for a in assets if a.media_type in ("video", "image")]
    matches: list[SceneMediaMatch] = []

    for scene in scenes:
        scene_id = scene.get("scene_id", "")
        section = scene.get("section_name", "")

        if not visual_assets:
            matches.append(SceneMediaMatch(
                scene_id=scene_id,
                section_name=section,
                selected_assets=[],
                fallback_needed=True,
                confidence=0.0,
                reason="no visual assets available",
            ))
            continue

        scored = [
            (a, score_asset_for_scene(a, scene, all_assets=visual_assets))
            for a in visual_assets
        ]
        scored.sort(key=lambda t: t[1], reverse=True)
        best_asset, best_score = scored[0]

        if best_score >= min_confidence:
            matches.append(SceneMediaMatch(
                scene_id=scene_id,
                section_name=section,
                selected_assets=[best_asset.stored_path],
                fallback_needed=False,
                confidence=round(best_score, 3),
                reason=f"top match: {best_asset.filename} (role={best_asset.inferred_role})",
            ))
        else:
            matches.append(SceneMediaMatch(
                scene_id=scene_id,
                section_name=section,
                selected_assets=[],
                fallback_needed=True,
                confidence=0.0,
                reason="no asset scored above threshold",
            ))

    return matches


def validate_scene_matches(
    matches: list[SceneMediaMatch],
    scenes: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    unmatched = [m.scene_id for m in matches if m.fallback_needed]
    if unmatched:
        warnings.append(f"{len(unmatched)} scene(s) need placeholder footage: {', '.join(unmatched)}")
    for m in matches:
        if not m.fallback_needed and m.confidence < 0.2:
            warnings.append(f"{m.scene_id}: low-confidence match ({m.confidence:.2f})")
    return warnings


def match_media_to_storyboard(
    storyboard: dict[str, Any],
    assets: list[MediaAsset],
) -> list[SceneMediaMatch]:
    """Top-level: match assets to all scenes in a storyboard dict."""
    sp = storyboard.get("shot_plan", {})
    scenes = sp.get("scenes", []) if isinstance(sp, dict) else list(sp) if isinstance(sp, list) else []
    return assign_assets_to_scenes(scenes, assets)
