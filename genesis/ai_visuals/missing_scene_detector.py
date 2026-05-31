"""Genesis Studio — Detect storyboard scenes missing matched media."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.ai_visuals.visual_models import MissingScene

_HIGH_SECTIONS = (
    "pattern interrupt", "hook", "demonstration", "demo", "teaching", "proof",
)
_MEDIUM_SECTIONS = ("cta", "call to action", "result", "close")
_LOW_SECTIONS = ("b-roll", "broll", "filler", "transition")


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def read_storyboard_scenes(run_dir: Path) -> list[dict[str, Any]]:
    data = _safe_json(run_dir / "storyboard.json")
    sp = data.get("shot_plan") or {}
    if isinstance(sp, dict):
        return list(sp.get("scenes") or [])
    if isinstance(sp, list):
        return sp
    return []


def read_media_manifest_matches(run_dir: Path) -> dict[str, dict[str, Any]]:
    """scene_id -> match info (matched bool, paths)."""
    data = _safe_json(run_dir / "media_manifest.json")
    out: dict[str, dict[str, Any]] = {}
    for m in data.get("scene_matches") or []:
        sid = m.get("scene_id", "")
        if not sid:
            continue
        assets = m.get("selected_assets") or []
        out[sid] = {
            "matched": bool(assets) and not m.get("fallback_needed"),
            "fallback_needed": bool(m.get("fallback_needed")),
            "selected_assets": assets,
        }
    return out


def classify_missing_scene_priority(section_name: str, shot_type: str = "") -> str:
    s = (section_name or "").lower()
    st = (shot_type or "").lower()
    blob = f"{s} {st}"
    for token in _HIGH_SECTIONS:
        if token in blob:
            return "high"
    for token in _MEDIUM_SECTIONS:
        if token in blob:
            return "medium"
    for token in _LOW_SECTIONS:
        if token in blob:
            return "low"
    return "medium"


def recommend_fallback_type(
    scene: dict[str, Any],
    *,
    content_format: str = "",
    default_asset_type: str = "image",
) -> str:
    fmt = (content_format or "").lower()
    section = (scene.get("section_name") or "").lower()
    shot = (scene.get("shot_type") or "").lower()

    if "screenshot" in section or "screen" in shot:
        return "screenshot_needed"
    if "stock" in section or "b-roll" in section or "broll" in section:
        return "stock_broll_needed"
    if fmt in ("wellness_teaching", "fundraising_story"):
        return "styled_scene_card" if default_asset_type == "image" else "generated_image"
    if fmt in ("affiliate_followup", "product_demo"):
        return "generated_video" if default_asset_type == "video" else "generated_image"
    if default_asset_type == "video":
        return "generated_video"
    return "generated_image"


def detect_missing_scenes(
    run_dir: Path,
    *,
    force: bool = False,
) -> list[MissingScene]:
    """
    Identify scenes without real matched media.
    If media_manifest.json is missing, all storyboard scenes are treated as missing.
    """
    scenes = read_storyboard_scenes(run_dir)
    matches = read_media_manifest_matches(run_dir)
    missing: list[MissingScene] = []

    for scene in scenes:
        sid = scene.get("scene_id") or ""
        if not sid or sid in ("title", "end"):
            continue

        info = matches.get(sid)
        has_real = info and info.get("matched")
        needs_fallback = info and info.get("fallback_needed")

        if has_real and not force:
            continue
        if not info and not force:
            # No manifest — still missing unless media/ has scene file (handled at render)
            reason = "no media_manifest match"
        elif needs_fallback or force:
            reason = "fallback_needed in media_manifest"
        else:
            reason = "no matched asset"

        section = scene.get("section_name", sid)
        missing.append(MissingScene(
            scene_id=sid,
            section_name=section,
            narration_text=(scene.get("narration_text") or scene.get("overlay_text") or "")[:500],
            visual_goal=(scene.get("visual_goal") or scene.get("visual_description") or "")[:300],
            shot_type=scene.get("shot_type", ""),
            reason_missing=reason,
            fallback_type=recommend_fallback_type(scene),
            priority=classify_missing_scene_priority(section, scene.get("shot_type", "")),
        ))

    missing.sort(key=lambda m: {"high": 0, "medium": 1, "low": 2}.get(m.priority, 3))
    return missing
