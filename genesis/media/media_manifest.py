"""
Genesis Studio — Media manifest builder: persist clip matches and reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.media.clip_matcher import match_media_to_storyboard, validate_scene_matches
from genesis.media.media_models import MediaAsset, MediaManifest, MediaStatus, SceneMediaMatch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def build_media_manifest(
    job_id: str,
    assets: list[MediaAsset],
    storyboard: dict[str, Any],
    *,
    runs_base: Path | None = None,
    repo_root: Path | None = None,
) -> MediaManifest:
    """Run clip matching and produce a MediaManifest."""
    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT
    run_dir = runs_base / job_id
    media_dir = run_dir / "media"

    scene_matches = match_media_to_storyboard(storyboard, assets)
    warnings = validate_scene_matches(scene_matches, [])

    for asset in assets:
        for sm in scene_matches:
            if asset.stored_path in sm.selected_assets and not asset.scene_match:
                asset.scene_match = sm.scene_id

    needs_fallback = sum(1 for m in scene_matches if m.fallback_needed)
    if not assets:
        status = MediaStatus.SKIPPED
    elif needs_fallback == len(scene_matches):
        status = MediaStatus.PARTIAL
    else:
        status = MediaStatus.COMPLETE if needs_fallback == 0 else MediaStatus.PARTIAL

    try:
        media_dir_rel = _rel(media_dir, repo_root)
    except Exception:  # noqa: BLE001
        media_dir_rel = str(media_dir)

    return MediaManifest(
        job_id=job_id,
        media_dir=media_dir_rel,
        assets=assets,
        scene_matches=scene_matches,
        status=status,
        warnings=warnings,
        notes=[f"{len(assets)} asset(s); {len(scene_matches) - needs_fallback}/{len(scene_matches)} scene(s) matched"],
    )


def write_media_manifest(
    run_dir: Path,
    manifest: MediaManifest,
) -> Path:
    path = run_dir / "media_manifest.json"
    path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return path


def load_media_manifest(run_dir: Path) -> MediaManifest | None:
    """Load media_manifest.json from a run folder; returns None if missing."""
    path = run_dir / "media_manifest.json"
    if not path.is_file():
        return None
    data = _safe_json(path)
    if not data:
        return None
    try:
        assets = [
            MediaAsset(**{k: v for k, v in a.items() if k in MediaAsset.__dataclass_fields__})
            for a in data.get("assets", [])
        ]
        matches = [
            SceneMediaMatch(**{k: v for k, v in m.items() if k in SceneMediaMatch.__dataclass_fields__})
            for m in data.get("scene_matches", [])
        ]
        return MediaManifest(
            job_id=data.get("job_id", ""),
            media_dir=data.get("media_dir", ""),
            assets=assets,
            scene_matches=matches,
            status=data.get("status", MediaStatus.PARTIAL),
            warnings=data.get("warnings", []),
            notes=data.get("notes", []),
        )
    except Exception:  # noqa: BLE001
        return None


def write_clip_match_report(
    run_dir: Path,
    manifest: MediaManifest,
) -> Path:
    lines = [
        f"# Clip Match Report — {manifest.job_id}",
        "",
        f"**Status:** {manifest.status}",
        f"**Assets found:** {len(manifest.assets)}",
        "",
    ]

    if manifest.assets:
        lines.append("## Assets ingested")
        lines.append("")
        for a in manifest.assets:
            meta = f"{a.media_type.upper()} {a.orientation} {a.duration_seconds:.1f}s" if a.duration_seconds else f"{a.media_type.upper()} {a.orientation}"
            lines.append(f"- `{a.filename}` — {meta} | role: {a.inferred_role or '—'} | tags: {', '.join(a.tags[:5])}")
        lines.append("")

    matched = [m for m in manifest.scene_matches if not m.fallback_needed]
    unmatched = [m for m in manifest.scene_matches if m.fallback_needed]

    lines.append("## Scene matches")
    lines.append("")
    for m in manifest.scene_matches:
        mark = "✓" if not m.fallback_needed else "✗"
        assets_str = ", ".join(f"`{Path(p).name}`" for p in m.selected_assets) or "—"
        lines.append(f"- {mark} `{m.scene_id}` [{m.section_name}] — {assets_str} (conf: {m.confidence:.2f})")
        if m.reason:
            lines.append(f"  _{m.reason}_")
    lines.append("")

    if unmatched:
        lines.append("## Scenes needing footage")
        lines.append("")
        for m in unmatched:
            lines.append(f"- `{m.scene_id}` — {m.section_name}")
        lines.append("")

    unmatched_assets = [a for a in manifest.assets if not a.scene_match]
    if unmatched_assets:
        lines.append("## Unmatched assets")
        lines.append("")
        for a in unmatched_assets:
            lines.append(f"- `{a.filename}` (role: {a.inferred_role or '—'})")
        lines.append("")

    lines.append("## Suggested filenames for better matching")
    lines.append("")
    for m in unmatched:
        lines.append(f"- For `{m.scene_id}` ({m.section_name}): try `scene_{m.scene_id[-2:]}_footage.mp4` or a name containing the shot type")
    lines.append("")

    if manifest.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in manifest.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("---")
    lines.append("_Generated by Genesis Studio media ingestion._")

    path = run_dir / "clip_match_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_full_match(
    job_id: str,
    *,
    runs_base: Path | None = None,
    repo_root: Path | None = None,
) -> tuple[MediaManifest, Path, Path]:
    """
    Load storyboard + scanned media → build manifest → write files.
    Returns (manifest, manifest_path, report_path).
    """
    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT
    run_dir = runs_base / job_id

    storyboard = _safe_json(run_dir / "storyboard.json")

    from genesis.video.media_resolver import find_run_media_assets, classify_media_asset
    from genesis.media.media_inspector import inspect_media_file

    raw_assets = find_run_media_assets(run_dir, repo_root=repo_root)
    assets: list[MediaAsset] = []
    for ra in raw_assets:
        p = repo_root / ra.path if not Path(ra.path).is_absolute() else Path(ra.path)
        if p.is_file():
            assets.append(inspect_media_file(p, stored_path=ra.path, source_path=ra.path))

    manifest = build_media_manifest(
        job_id, assets, storyboard,
        runs_base=runs_base, repo_root=repo_root,
    )
    mp = write_media_manifest(run_dir, manifest)
    rp = write_clip_match_report(run_dir, manifest)
    return manifest, mp, rp
