"""Genesis Studio — Thumbnail export and report writing."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from genesis.thumbnail.thumbnail_models import (
    ThumbnailExportResult,
    ThumbnailSelectionResult,
    ThumbnailStatus,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORBIDDEN = re.compile(
    r"(sk-[a-zA-Z0-9]{12,}|api[_-]?key\s*[:=]\s*\S+|voice[_-]?id\s*[:=]\s*\S+)",
    re.I,
)


def _scrub(text: str) -> str:
    return _FORBIDDEN.sub("[REDACTED]", text)


def export_selected_thumbnail(
    job_id: str,
    source_path: Path,
    *,
    run_dir: Path | None = None,
    output_name: str = "selected_thumbnail.jpg",
) -> ThumbnailExportResult:
    warnings: list[str] = []
    if run_dir is None:
        run_dir = _REPO_ROOT / "assets" / "runs" / job_id

    if not source_path.is_file():
        return ThumbnailExportResult(
            job_id=job_id, platform="", output_path="",
            source_path=str(source_path),
            status=ThumbnailStatus.FAILED,
            warnings=[f"source not found: {source_path}"],
        )

    dest = run_dir / output_name
    try:
        if source_path.suffix.lower() == ".jpg" or source_path.suffix.lower() == ".jpeg":
            shutil.copy2(source_path, dest)
        else:
            # Try PIL conversion to JPEG; fallback to plain copy
            try:
                from PIL import Image
                with Image.open(source_path) as img:
                    rgb = img.convert("RGB")
                    rgb.save(str(dest), "JPEG", quality=92)
            except Exception:  # noqa: BLE001
                shutil.copy2(source_path, dest)
                if dest.suffix.lower() != source_path.suffix.lower():
                    new_dest = dest.with_suffix(source_path.suffix.lower())
                    dest.rename(new_dest)
                    dest = new_dest
                    warnings.append(f"PIL unavailable — copied as {dest.name}")
    except Exception as exc:  # noqa: BLE001
        return ThumbnailExportResult(
            job_id=job_id, platform="", output_path="",
            source_path=str(source_path),
            status=ThumbnailStatus.FAILED,
            warnings=[f"copy failed: {exc}"],
        )

    return ThumbnailExportResult(
        job_id=job_id, platform="", output_path=str(dest),
        source_path=str(source_path),
        status=ThumbnailStatus.COMPLETE,
        warnings=warnings,
        notes=[f"size={dest.stat().st_size if dest.is_file() else 0}"],
    )


def write_thumbnail_selection_json(
    run_dir: Path,
    result: ThumbnailSelectionResult,
) -> Path:
    path = run_dir / "thumbnail_selection.json"
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path


def write_thumbnail_selection_md(
    run_dir: Path,
    result: ThumbnailSelectionResult,
) -> Path:
    path = run_dir / "thumbnail_selection.md"
    lines = [
        f"# Thumbnail selection — {result.job_id}",
        "",
        f"**Status:** {result.status}",
        f"**Selected:** {_scrub(result.selected_thumbnail_path) or 'none'}",
        "",
        "## Candidates",
        "",
    ]
    for c in result.candidates:
        mark = "[SELECTED]" if c.selected else "[ ]"
        lines.append(
            f"- {mark} `{Path(c.source_path).name}` "
            f"type={c.source_type} score={c.score:.1f} {c.reason}"
        )
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        for w in result.warnings:
            lines.append(f"- {_scrub(w)}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def copy_thumbnail_to_export_package(
    source_path: Path,
    export_dir: Path,
    *,
    output_name: str = "selected_thumbnail.jpg",
) -> Path | None:
    if not source_path.is_file() or not export_dir.is_dir():
        return None
    dest = export_dir / output_name
    try:
        shutil.copy2(source_path, dest)
        return dest
    except Exception:  # noqa: BLE001
        return None


def create_platform_thumbnail_variant(
    source_path: Path,
    out_dir: Path,
    *,
    platform: str = "tiktok",
) -> Path | None:
    """Copy/resize thumbnail to platform spec. Returns output path or None."""
    if not source_path.is_file():
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"thumbnail_{platform}{source_path.suffix}"
    try:
        from PIL import Image
        target_w, target_h = (1080, 1920) if platform in (
            "tiktok", "instagram", "instagram_reels", "clapper",
        ) else (1280, 720)
        with Image.open(source_path) as img:
            img_resized = img.resize((target_w, target_h), resample=3)
            img_resized.convert("RGB").save(str(dest), "JPEG", quality=92)
        return dest
    except Exception:  # noqa: BLE001
        shutil.copy2(source_path, dest)
        return dest


def run_thumbnail_export(
    job_id: str,
    *,
    runs_base: Path | None = None,
    platform: str = "tiktok",
    copy_to_export: bool = True,
) -> ThumbnailExportResult:
    runs_base = runs_base or (_REPO_ROOT / "assets" / "runs")
    run_dir = runs_base / job_id
    selected = run_dir / "selected_thumbnail.jpg"
    warnings: list[str] = []

    if not selected.is_file():
        for name in ("thumbnail.jpg", "thumbnail.png"):
            candidate = run_dir / name
            if candidate.is_file():
                shutil.copy2(candidate, selected)
                break

    if not selected.is_file():
        return ThumbnailExportResult(
            job_id=job_id, platform=platform, output_path="",
            source_path="",
            status=ThumbnailStatus.SKIPPED,
            warnings=["selected_thumbnail.jpg not found — run select first"],
        )

    variant = create_platform_thumbnail_variant(selected, run_dir / "generated_visuals", platform=platform)
    if variant:
        warnings.append(f"platform variant: {variant.name}")

    if copy_to_export:
        creator_summary = json.loads(
            (run_dir / "creator_run_summary.json").read_text(encoding="utf-8")
        ) if (run_dir / "creator_run_summary.json").is_file() else {}
        export_dir_str = creator_summary.get("export_dir", "")
        if export_dir_str and Path(export_dir_str).is_dir():
            copied = copy_thumbnail_to_export_package(selected, Path(export_dir_str))
            if copied:
                warnings.append(f"copied to export: {copied.name}")

    return ThumbnailExportResult(
        job_id=job_id, platform=platform, output_path=str(selected),
        source_path=str(selected),
        status=ThumbnailStatus.COMPLETE,
        warnings=warnings,
        notes=[f"platform={platform}"],
    )
