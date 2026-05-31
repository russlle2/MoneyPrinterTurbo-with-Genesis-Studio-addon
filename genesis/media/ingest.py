"""
Genesis Studio — Media ingestion: copy/link files into a run's media folder.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from genesis.media.media_inspector import get_media_type, inspect_media_file
from genesis.media.media_models import MediaAsset, MediaIngestResult, MediaStatus

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"

_SAFE_NAME = re.compile(r"[^\w\.\-]+")
_SUPPORTED_TYPES = {"video", "image", "audio"}


def sanitize_media_filename(name: str) -> str:
    """Produce a safe, lowercase filename preserving extension."""
    p = Path(name)
    stem = _SAFE_NAME.sub("_", p.stem).strip("_").lower()
    stem = stem[:80] if len(stem) > 80 else stem
    return f"{stem}{p.suffix.lower()}"


def dedupe_media_filename(dest_dir: Path, filename: str) -> str:
    """If filename exists in dest_dir, add _2, _3, ... suffix."""
    p = Path(filename)
    stem, ext = p.stem, p.suffix
    candidate = filename
    n = 2
    while (dest_dir / candidate).exists():
        candidate = f"{stem}_{n}{ext}"
        n += 1
    return candidate


def validate_intake_paths(paths: list[str | Path]) -> tuple[list[Path], list[str]]:
    """Return (valid_paths, errors). Never raises."""
    valid: list[Path] = []
    errors: list[str] = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            errors.append(f"path not found: {raw}")
        elif p.is_dir():
            errors.append(f"path is a directory (use ingest-folder): {raw}")
        elif not p.is_file():
            errors.append(f"not a regular file: {raw}")
        else:
            valid.append(p)
    return valid, errors


def copy_media_to_run(
    src: Path,
    media_dir: Path,
    *,
    repo_root: Path | None = None,
) -> tuple[MediaAsset | None, str]:
    """
    Copy src into media_dir. Returns (MediaAsset, stored_rel_path) or (None, error).
    """
    repo_root = repo_root or _REPO_ROOT
    media_type = get_media_type(src)
    if media_type == "unknown":
        return None, f"unsupported type: {src.suffix}"

    media_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_media_filename(src.name)
    final_name = dedupe_media_filename(media_dir, safe_name)
    dest = media_dir / final_name

    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        return None, f"copy failed: {exc}"

    try:
        rel = str(dest.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        rel = str(dest)

    asset = inspect_media_file(dest, stored_path=rel, source_path=str(src))
    return asset, rel


def link_media_to_run_if_supported(
    src: Path,
    media_dir: Path,
    *,
    repo_root: Path | None = None,
) -> tuple[MediaAsset | None, str]:
    """Try symlink; fall back to copy if unsupported."""
    repo_root = repo_root or _REPO_ROOT
    media_type = get_media_type(src)
    if media_type == "unknown":
        return None, f"unsupported type: {src.suffix}"

    media_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_media_filename(src.name)
    final_name = dedupe_media_filename(media_dir, safe_name)
    dest = media_dir / final_name

    try:
        dest.symlink_to(src.resolve())
    except (OSError, NotImplementedError):
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            return None, f"link+copy failed: {exc}"

    try:
        rel = str(dest.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        rel = str(dest)

    asset = inspect_media_file(dest, stored_path=rel, source_path=str(src))
    return asset, rel


def ingest_media_for_run(
    job_id: str,
    intake_paths: list[str | Path],
    *,
    mode: str = "copy",
    runs_base: Path | None = None,
    repo_root: Path | None = None,
) -> MediaIngestResult:
    """
    Ingest media files into the run's media/ folder.

    mode:
      "copy"      — copy files (default, safe)
      "link"      — symlink with copy fallback
      "reference" — record paths only, no file movement
    """
    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT
    run_dir = runs_base / job_id
    media_dir = run_dir / "media"

    if not run_dir.is_dir():
        return MediaIngestResult(
            job_id=job_id,
            intake_paths=[str(p) for p in intake_paths],
            stored_assets=[],
            skipped_files=[],
            errors=[f"run folder not found: {run_dir}"],
            status=MediaStatus.FAILED,
        )

    valid_paths, errors = validate_intake_paths(intake_paths)
    stored: list[MediaAsset] = []
    skipped: list[str] = []

    for src in valid_paths:
        mt = get_media_type(src)
        if mt not in _SUPPORTED_TYPES:
            skipped.append(src.name)
            continue

        if mode == "link":
            asset, err = link_media_to_run_if_supported(src, media_dir, repo_root=repo_root)
        elif mode == "reference":
            try:
                rel = str(src.resolve().relative_to(repo_root.resolve()))
            except ValueError:
                rel = str(src)
            asset = inspect_media_file(src, stored_path=rel, source_path=str(src))
            err = ""
        else:
            asset, err = copy_media_to_run(src, media_dir, repo_root=repo_root)

        if asset:
            stored.append(asset)
        else:
            errors.append(f"{src.name}: {err}")
            skipped.append(src.name)

    if not stored and valid_paths:
        status = MediaStatus.FAILED
    elif errors:
        status = MediaStatus.PARTIAL
    elif not valid_paths:
        status = MediaStatus.SKIPPED
    else:
        status = MediaStatus.COMPLETE

    notes = [f"mode={mode}", f"copied {len(stored)} of {len(valid_paths)} files"]
    return MediaIngestResult(
        job_id=job_id,
        intake_paths=[str(p) for p in intake_paths],
        stored_assets=stored,
        skipped_files=skipped,
        errors=errors,
        status=status,
        notes=notes,
    )


def ingest_folder_for_run(
    job_id: str,
    folder: str | Path,
    *,
    mode: str = "copy",
    runs_base: Path | None = None,
    repo_root: Path | None = None,
    recurse: bool = False,
) -> MediaIngestResult:
    """Ingest all supported media from a folder."""
    folder = Path(folder)
    if not folder.is_dir():
        return MediaIngestResult(
            job_id=job_id,
            intake_paths=[str(folder)],
            stored_assets=[],
            skipped_files=[],
            errors=[f"folder not found: {folder}"],
            status=MediaStatus.FAILED,
        )

    pattern = "**/*" if recurse else "*"
    paths = [p for p in folder.glob(pattern) if p.is_file()]
    return ingest_media_for_run(
        job_id,
        paths,
        mode=mode,
        runs_base=runs_base,
        repo_root=repo_root,
    )
