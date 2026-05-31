"""Genesis Studio — Manual import of Diffus.me / external AI visuals."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.ai_visuals.generated_asset_manifest import (
    build_generated_visuals_manifest,
    load_generated_visuals_manifest,
    update_media_manifest_with_generated_assets,
    write_generated_visuals_manifest,
)
from genesis.ai_visuals.missing_scene_detector import read_storyboard_scenes
from genesis.ai_visuals.visual_models import GeneratedVisualAsset, VisualFillStatus
from genesis.utils.config_loader import load_ai_visuals_config

_REPO_ROOT = Path(__file__).resolve().parents[2]
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
_SUPPORTED_EXT = _IMAGE_EXT | _VIDEO_EXT

_MANUAL_IMPORT_DIR = "manual_visual_imports"
_SCENE_ID_RE = re.compile(r"scene[_-]?0*(\d+)", re.I)
_ALIAS_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("hook", ("pattern interrupt", "hook")),
    ("demo", ("demonstration", "demo", "teaching")),
    ("cta", ("cta", "call to action")),
    ("broll", ("b-roll", "broll", "filler")),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_imported_visual(path: Path) -> dict[str, Any]:
    """Infer asset type and role from filename."""
    name = path.stem.lower()
    ext = path.suffix.lower()
    asset_type = "video" if ext in _VIDEO_EXT else "image" if ext in _IMAGE_EXT else "unknown"
    role = "scene_media"
    if "thumbnail" in name:
        role = "thumbnail_candidate"
    return {"asset_type": asset_type, "role": role, "filename": path.name}


def _normalize_scene_id(raw: str) -> str:
    m = _SCENE_ID_RE.search(raw)
    if m:
        return f"scene_{int(m.group(1)):02d}"
    return ""


def match_imported_visual_to_scene(
    path: Path,
    scenes: list[dict[str, Any]],
    *,
    already_assigned: set[str] | None = None,
) -> tuple[str, float, list[str]]:
    """
    Return (scene_id, confidence, warnings).
    Empty scene_id for thumbnail candidates.
    """
    already_assigned = already_assigned or set()
    warnings: list[str] = []
    name = path.stem.lower()
    info = classify_imported_visual(path)

    if info["role"] == "thumbnail_candidate":
        return "", 0.0, ["thumbnail candidate — not auto-assigned to scene timeline"]

    sid = _normalize_scene_id(name)
    if sid and sid not in already_assigned:
        by_id = {s.get("scene_id"): s for s in scenes if s.get("scene_id")}
        if sid in by_id or not scenes:
            return sid, 0.95, warnings
        warnings.append(f"scene id {sid} not in storyboard — assigning anyway")

    for alias, section_tokens in _ALIAS_RULES:
        if alias in name:
            for scene in scenes:
                sid2 = scene.get("scene_id", "")
                if not sid2 or sid2 in already_assigned:
                    continue
                section = (scene.get("section_name") or "").lower()
                shot = (scene.get("shot_type") or "").lower()
                blob = f"{section} {shot}"
                if any(tok in blob for tok in section_tokens):
                    return sid2, 0.75, warnings
            if alias == "broll":
                for scene in scenes:
                    sid2 = scene.get("scene_id", "")
                    if sid2 and sid2 not in already_assigned:
                        return sid2, 0.4, warnings + ["broll alias matched first unassigned scene"]
            warnings.append(f"alias '{alias}' in filename but no matching storyboard scene")

    if scenes:
        for scene in scenes:
            sid2 = scene.get("scene_id", "")
            if sid2 and sid2 not in already_assigned:
                return sid2, 0.25, warnings + ["uncertain scene match — first unassigned scene"]
    return "", 0.0, warnings + ["could not match to any scene"]


def copy_imported_visual_to_generated_folder(
    source: Path,
    run_dir: Path,
    scene_id: str,
    *,
    config: dict[str, Any] | None = None,
) -> Path:
    cfg = config or load_ai_visuals_config()
    out_dir = run_dir / cfg.get("output_dir", "generated_visuals")
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = source.suffix.lower()
    if scene_id:
        dest = out_dir / f"{scene_id}_imported{ext}"
    else:
        dest = out_dir / f"imported_{source.stem}{ext}"
    shutil.copy2(source, dest)
    return dest


def scan_manual_visual_imports(
    run_dir: Path,
    *,
    import_dir: Path | None = None,
) -> list[Path]:
    folder = import_dir or (run_dir / _MANUAL_IMPORT_DIR)
    if not folder.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXT:
            files.append(p)
    return files


def update_manifest_with_imported_visuals(
    run_dir: Path,
    assets: list[GeneratedVisualAsset],
    *,
    job_id: str = "",
    repo_root: Path | None = None,
) -> Path:
    repo_root = repo_root or _REPO_ROOT
    job_id = job_id or run_dir.name
    existing = load_generated_visuals_manifest(run_dir) or {}
    prior = [GeneratedVisualAsset.from_dict(a) for a in existing.get("assets") or [] if isinstance(a, dict)]
    by_scene = {a.scene_id: a for a in prior if a.scene_id}
    for a in assets:
        if a.asset_type in ("image", "video") and a.scene_id:
            by_scene[a.scene_id] = a
    merged = list(by_scene.values()) + [a for a in assets if a.asset_type == "thumbnail_candidate"]

    manifest = build_generated_visuals_manifest(
        job_id,
        missing_scenes=[],
        prompts=[],
        generated_assets=merged,
        status=VisualFillStatus.COMPLETE,
        notes=["updated with manual imports"],
    )
    manifest["manual_import_count"] = sum(1 for a in assets if a.source_type == "manual_import")
    write_generated_visuals_manifest(run_dir, manifest)

    assignments: dict[str, str] = {}
    for a in merged:
        if a.asset_type in ("image", "video") and a.path and a.scene_id:
            p = Path(a.path)
            if p.is_file():
                try:
                    assignments[a.scene_id] = str(p.resolve().relative_to(repo_root.resolve()))
                except ValueError:
                    assignments[a.scene_id] = str(p)
    if assignments:
        update_media_manifest_with_generated_assets(run_dir, assignments, repo_root=repo_root)
    return run_dir / "generated_visuals_manifest.json"


def import_generated_visuals_for_run(
    job_id: str,
    *,
    runs_base: Path | None = None,
    repo_root: Path | None = None,
    import_dir: Path | None = None,
    external_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    """
    Import manual visuals into generated_visuals/ and update manifests.
    """
    runs_base = runs_base or (_REPO_ROOT / "assets" / "runs")
    repo_root = repo_root or _REPO_ROOT
    run_dir = runs_base / job_id
    if not run_dir.is_dir():
        return {
            "job_id": job_id,
            "status": VisualFillStatus.FAILED,
            "imported": [],
            "warnings": [f"run folder not found: {run_dir}"],
        }

    cfg = load_ai_visuals_config()
    scenes = read_storyboard_scenes(run_dir)
    sources: list[Path] = list(scan_manual_visual_imports(run_dir, import_dir=import_dir))

    if external_paths:
        ext_dir = run_dir / _MANUAL_IMPORT_DIR
        ext_dir.mkdir(parents=True, exist_ok=True)
        for raw in external_paths:
            src = Path(raw)
            if not src.is_file():
                continue
            if src.suffix.lower() not in _SUPPORTED_EXT:
                continue
            dest = ext_dir / src.name
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            sources.append(dest)

    sources = list(dict.fromkeys(sources))
    imported: list[GeneratedVisualAsset] = []
    warnings: list[str] = []
    assigned: set[str] = set()

    for src in sources:
        info = classify_imported_visual(src)
        if info["asset_type"] == "unknown":
            warnings.append(f"skipped unsupported file: {src.name}")
            continue

        scene_id, confidence, match_warn = match_imported_visual_to_scene(
            src, scenes, already_assigned=assigned,
        )
        warnings.extend(match_warn)

        dest = copy_imported_visual_to_generated_folder(
            src, run_dir, scene_id, config=cfg,
        )

        asset_type = info["asset_type"]
        if info["role"] == "thumbnail_candidate":
            asset_type = "thumbnail_candidate"
            scene_id = ""

        if scene_id:
            assigned.add(scene_id)

        try:
            rel = str(dest.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            rel = str(dest)

        imported.append(GeneratedVisualAsset(
            asset_id=f"import_{src.stem}",
            scene_id=scene_id or "thumbnail",
            prompt_id="",
            asset_type=asset_type,
            provider="manual_import",
            path=rel,
            width=0,
            height=0,
            duration_seconds=0,
            status=VisualFillStatus.COMPLETE,
            source_type="manual_import",
            original_path=str(src),
            imported_at=_utc_now(),
            assignment_confidence=confidence,
            warnings=match_warn,
            notes=[info["role"]],
        ))

    if imported:
        update_manifest_with_imported_visuals(
            run_dir, imported, job_id=job_id, repo_root=repo_root,
        )

    status = VisualFillStatus.COMPLETE if imported else VisualFillStatus.SKIPPED
    return {
        "job_id": job_id,
        "status": status,
        "imported": imported,
        "warnings": warnings,
        "import_count": len(imported),
    }
