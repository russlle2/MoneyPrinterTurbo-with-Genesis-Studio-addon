"""
Genesis Studio — Resolve run-folder media for video assembly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac"}


@dataclass
class MediaAsset:
    path: str
    media_type: str
    scene_hint: str = ""
    basename: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "media_type": self.media_type,
            "scene_hint": self.scene_hint,
            "basename": self.basename,
        }


@dataclass
class PlaceholderPlan:
    job_id: str
    placeholders: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _relative_public(path: Path, repo_root: Path) -> str:
    """Store path relative to repo when possible (no home-dir leakage in outputs)."""
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return path.name


def classify_media_asset(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _VIDEO_EXT:
        return "video"
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _AUDIO_EXT:
        return "audio"
    return "unknown"


def _scene_hint_from_name(name: str) -> str:
    m = re.search(r"scene[_\-]?(\d+)", name, re.I)
    if m:
        return f"scene_{int(m.group(1)):02d}"
    return ""


def find_run_media_assets(
    run_dir: Path,
    *,
    repo_root: Path | None = None,
) -> list[MediaAsset]:
    """Scan run_dir/media/ and run_dir for supported media (no duplication)."""
    repo_root = repo_root or run_dir.parent.parent.parent
    assets: list[MediaAsset] = []
    seen: set[str] = set()

    search_dirs = [run_dir / "media", run_dir / "generated_visuals", run_dir]
    for folder in search_dirs:
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            mt = classify_media_asset(path)
            if mt == "unknown":
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            rel = _relative_public(path, repo_root)
            assets.append(MediaAsset(
                path=rel,
                media_type=mt,
                scene_hint=_scene_hint_from_name(path.stem),
                basename=path.name,
            ))
    return assets


def match_assets_to_scenes(
    scenes: list[dict[str, Any]],
    assets: list[MediaAsset],
    *,
    manifest_matches: dict[str, str] | None = None,
    generated_matches: dict[str, str] | None = None,
) -> dict[str, MediaAsset]:
    """Map scene_id → best visual asset (video/image only).

    Priority:
      1. manifest_matches (real ingested media)
      2. generated_matches (AI/generated assets for missing scenes)
      3. filename hints / positional fallback
    """
    visual = [a for a in assets if a.media_type in ("video", "image")]
    by_scene: dict[str, MediaAsset] = {}

    def _assign_from_paths(mapping: dict[str, str]) -> None:
        path_index = {a.path: a for a in visual}
        for sid, stored_path in mapping.items():
            if sid in by_scene:
                continue
            from pathlib import Path as _Path
            basename = _Path(stored_path).name
            hit = path_index.get(stored_path)
            if hit is None:
                hit = next((a for a in visual if a.basename == basename), None)
            if hit:
                by_scene[sid] = hit

    # 1. Real matched media from media_manifest
    if manifest_matches:
        _assign_from_paths(manifest_matches)

    # 2. Generated visuals for gaps only
    if generated_matches:
        _assign_from_paths(generated_matches)

    # 3. Filename scene-hint fallback
    for asset in visual:
        if asset.scene_hint:
            by_scene.setdefault(asset.scene_hint, asset)

    # 3. Positional fallback
    unassigned = [a for a in visual if a not in by_scene.values()]
    for i, scene in enumerate(scenes):
        sid = scene.get("scene_id", f"scene_{i+1:02d}")
        if sid in by_scene:
            continue
        if i < len(visual):
            by_scene[sid] = visual[i]
        elif unassigned:
            by_scene[sid] = unassigned.pop(0)
    return by_scene


def create_placeholder_visuals_if_needed(
    run_dir: Path,
    scenes: list[dict[str, Any]],
    *,
    repo_root: Path | None = None,
) -> PlaceholderPlan:
    """
    Plan placeholder cards when no media is present. PNG files written at render time.
    """
    repo_root = repo_root or run_dir.parent.parent.parent
    placeholders: list[dict[str, str]] = []
    for scene in scenes:
        sid = scene.get("scene_id", "scene_01")
        placeholders.append({
            "scene_id": sid,
            "label": (scene.get("section_name") or sid)[:40],
            "caption": (scene.get("overlay_text") or scene.get("narration_text") or "")[:120],
            "planned_path": _relative_public(
                run_dir / "render_cache" / f"{sid}_placeholder.png",
                repo_root,
            ),
        })
    return PlaceholderPlan(
        job_id=run_dir.name,
        placeholders=placeholders,
        notes=["No user media found — renderer will generate placeholder cards."],
    )


def resolve_narration_path(
    job_id: str,
    run_dir: Path,
    *,
    repo_root: Path | None = None,
    explicit_path: str = "",
) -> str:
    """Find narration MP3 without exposing private config paths in outputs."""
    repo_root = repo_root or run_dir.parent.parent.parent
    if explicit_path:
        p = Path(explicit_path)
        if p.is_file():
            return _relative_public(p, repo_root)

    candidates = [
        repo_root / "assets" / "audio" / f"narration_{job_id}.mp3",
        repo_root / "assets" / "audio" / f"{job_id}.mp3",
        run_dir / "narration.mp3",
    ]
    for c in candidates:
        if c.is_file():
            return _relative_public(c, repo_root)

    audio_dir = repo_root / "assets" / "audio"
    if audio_dir.is_dir():
        for p in sorted(audio_dir.glob(f"*{job_id}*.mp3")):
            return _relative_public(p, repo_root)
    return ""
