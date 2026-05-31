"""Genesis Studio — Validate generated and imported visual assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from genesis.ai_visuals.visual_models import GeneratedVisualAsset, VisualFillStatus

_MIN_SHORT_EDGE = 480
_TARGET_ASPECT = 9 / 16
_ASPECT_TOLERANCE = 0.25


def _pil_available() -> bool:
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


def inspect_visual_dimensions(path: Path) -> tuple[int, int, list[str]]:
    """Return (width, height, warnings)."""
    warnings: list[str] = []
    if not path.is_file():
        return 0, 0, [f"file not found: {path}"]

    if path.suffix.lower() in {".mp4", ".mov", ".m4v", ".webm"}:
        return _inspect_video_dimensions(path)

    if _pil_available():
        try:
            from PIL import Image

            with Image.open(path) as img:
                w, h = img.size
                return w, h, warnings
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"could not read image dimensions: {exc}")
            return 0, 0, warnings

    warnings.append("PIL not available — dimensions unknown")
    return 0, 0, warnings


def _inspect_video_dimensions(path: Path) -> tuple[int, int, list[str]]:
    warnings: list[str] = []
    try:
        from moviepy import VideoFileClip

        with VideoFileClip(str(path)) as clip:
            w, h = int(clip.w or 0), int(clip.h or 0)
            dur = float(clip.duration or 0)
            if dur < 1.0:
                warnings.append(f"video very short ({dur:.1f}s)")
            elif dur > 30.0:
                warnings.append(f"video long for short-form ({dur:.1f}s)")
            return w, h, warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"could not inspect video: {exc}")
        return 0, 0, warnings


def infer_visual_asset_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".mp4", ".mov", ".m4v", ".webm"}:
        return "video"
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    return "unknown"


def check_aspect_ratio_fit(
    width: int,
    height: int,
    *,
    target_aspect: str = "9:16",
) -> list[str]:
    warnings: list[str] = []
    if width <= 0 or height <= 0:
        return warnings

    ratio = width / height
    if target_aspect == "9:16":
        target = _TARGET_ASPECT
    elif ":" in target_aspect:
        parts = target_aspect.split(":", 1)
        try:
            target = float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            target = _TARGET_ASPECT
    else:
        target = _TARGET_ASPECT

    if abs(ratio - target) > _ASPECT_TOLERANCE:
        if ratio > 1.0:
            warnings.append("horizontal asset for vertical short-form project")
        else:
            warnings.append(f"aspect ratio {width}x{height} differs from {target_aspect}")
    return warnings


def validate_generated_visual_asset(
    asset: GeneratedVisualAsset,
    *,
    target_aspect: str = "9:16",
    repo_root: Path | None = None,
) -> GeneratedVisualAsset:
    """Return asset with validation_status and validation_warnings filled."""
    warnings: list[str] = list(asset.validation_warnings or asset.warnings or [])
    if asset.asset_type not in ("image", "video"):
        asset.validation_status = VisualFillStatus.SKIPPED
        asset.validation_warnings = warnings
        return asset

    p = Path(asset.path)
    if not p.is_absolute() and repo_root:
        candidate = repo_root / asset.path
        if candidate.is_file():
            p = candidate

    w, h, dim_warn = inspect_visual_dimensions(p)
    warnings.extend(dim_warn)
    if w and h:
        asset.width = w
        asset.height = h
        short = min(w, h)
        if short < _MIN_SHORT_EDGE:
            warnings.append(f"resolution small for short-form ({w}x{h})")
        warnings.extend(check_aspect_ratio_fit(w, h, target_aspect=target_aspect))

    if not asset.scene_id or asset.scene_id == "thumbnail":
        warnings.append("no scene assignment")
    elif asset.assignment_confidence and asset.assignment_confidence < 0.5:
        warnings.append("uncertain scene assignment")

    asset.validation_warnings = list(dict.fromkeys(warnings))
    asset.validation_status = VisualFillStatus.COMPLETE if not warnings else VisualFillStatus.PARTIAL
    return asset


def validate_scene_assignment(
    scene_id: str,
    scenes: list[dict[str, Any]],
) -> list[str]:
    if not scene_id or scene_id == "thumbnail":
        return []
    ids = {s.get("scene_id") for s in scenes}
    if scene_id not in ids:
        return [f"scene_id {scene_id} not in storyboard"]
    return []


def write_visual_asset_validation_report(
    run_dir: Path,
    assets: list[GeneratedVisualAsset],
    *,
    target_aspect: str = "9:16",
) -> Path:
    path = run_dir / "visual_asset_validation.md"
    lines = [
        "# Visual asset validation",
        "",
        f"**Assets checked:** {len(assets)}",
        f"**Target aspect:** {target_aspect}",
        "",
    ]
    warn_count = 0
    for a in assets:
        lines.append(f"## {a.asset_id or a.scene_id}")
        lines.append(f"- path: `{a.path}`")
        lines.append(f"- type: {a.asset_type} ({a.source_type})")
        lines.append(f"- status: {a.validation_status or a.status}")
        if a.validation_warnings:
            warn_count += len(a.validation_warnings)
            for w in a.validation_warnings:
                lines.append(f"  - {w}")
        lines.append("")
    lines.extend(["", f"**Total warnings:** {warn_count}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def validate_run_visual_assets(
    run_dir: Path,
    *,
    repo_root: Path | None = None,
    target_aspect: str = "9:16",
) -> list[GeneratedVisualAsset]:
    """Load manifest assets, validate, write report."""
    from genesis.ai_visuals.generated_asset_manifest import load_generated_visuals_manifest

    data = load_generated_visuals_manifest(run_dir) or {}
    assets = [
        GeneratedVisualAsset.from_dict(a)
        for a in data.get("assets") or []
        if isinstance(a, dict)
    ]
    validated = [
        validate_generated_visual_asset(a, target_aspect=target_aspect, repo_root=repo_root)
        for a in assets
    ]
    write_visual_asset_validation_report(run_dir, validated, target_aspect=target_aspect)
    return validated
