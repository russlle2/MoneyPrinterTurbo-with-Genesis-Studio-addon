"""Genesis Studio — Generated visual asset manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.ai_visuals.visual_models import (
    GeneratedVisualAsset,
    MissingScene,
    VisualFillStatus,
    VisualGenerationPrompt,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VIDEO_EXT = {".mp4", ".mov", ".webm"}
_RENDERABLE_EXT = {".png", ".jpg", ".jpeg", ".webp"} | _VIDEO_EXT


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def build_generated_visuals_manifest(
    job_id: str,
    *,
    missing_scenes: list[MissingScene],
    prompts: list[VisualGenerationPrompt],
    generated_assets: list[GeneratedVisualAsset],
    status: str = VisualFillStatus.COMPLETE,
    warnings: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": status,
        "missing_scene_count": len(missing_scenes),
        "prompt_count": len(prompts),
        "generated_asset_count": len(generated_assets),
        "missing_scenes": [m.to_dict() for m in missing_scenes],
        "prompts": [p.to_dict() for p in prompts],
        "assets": [a.to_dict() for a in generated_assets],
        "scene_assignments": {
            a.scene_id: a.path
            for a in generated_assets
            if a.path and a.asset_type in ("image", "video") and Path(a.path).suffix.lower() in _RENDERABLE_EXT
        },
        "warnings": warnings or [],
        "notes": notes or [],
    }


def write_generated_visuals_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    path = run_dir / "generated_visuals_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def load_generated_visuals_manifest(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "generated_visuals_manifest.json"
    if not path.is_file():
        return None
    data = _safe_json(path)
    return data if data else None


def load_generated_scene_assignments(
    run_dir: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, str]:
    """scene_id -> relative path for renderable generated assets only."""
    repo_root = repo_root or _REPO_ROOT
    data = load_generated_visuals_manifest(run_dir)
    if not data:
        return {}

    assignments = dict(data.get("scene_assignments") or {})
    out: dict[str, str] = {}
    for sid, rel in assignments.items():
        p = Path(rel)
        if not p.is_absolute():
            p = repo_root / rel if not (run_dir / rel).is_file() else run_dir / rel
        if not p.is_file():
            p2 = run_dir / Path(rel).name
            if p2.is_file():
                p = p2
        if p.is_file() and p.suffix.lower() in _RENDERABLE_EXT:
            try:
                out[sid] = str(p.resolve().relative_to(repo_root.resolve()))
            except ValueError:
                out[sid] = str(p)
    return out


def update_media_manifest_with_generated_assets(
    run_dir: Path,
    generated_assignments: dict[str, str],
    *,
    repo_root: Path | None = None,
) -> Path | None:
    """
    Supplement media_manifest.json: only add generated paths for scenes
    that still have fallback_needed or no selected_assets.
    """
    repo_root = repo_root or _REPO_ROOT
    path = run_dir / "media_manifest.json"
    data = _safe_json(path) if path.is_file() else {
        "job_id": run_dir.name,
        "scene_matches": [],
        "assets": [],
    }

    matches = {m.get("scene_id"): m for m in data.get("scene_matches") or []}
    for sid, gen_path in generated_assignments.items():
        m = matches.get(sid) or {
            "scene_id": sid,
            "section_name": sid,
            "selected_assets": [],
            "fallback_needed": True,
            "confidence": 0.0,
            "reason": "",
        }
        if m.get("selected_assets") and not m.get("fallback_needed"):
            continue  # preserve real media
        m["selected_assets"] = [gen_path]
        m["fallback_needed"] = False
        m["reason"] = "generated_visual_asset"
        m["confidence"] = 0.5
        matches[sid] = m

    data["scene_matches"] = list(matches.values())
    data["notes"] = list(dict.fromkeys(
        list(data.get("notes") or []) + ["updated with generated_visuals_manifest assignments"]
    ))
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
