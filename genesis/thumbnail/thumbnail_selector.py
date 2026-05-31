"""Genesis Studio — Thumbnail candidate detection and selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.thumbnail.thumbnail_models import (
    ThumbnailCandidate,
    ThumbnailSelectionResult,
    ThumbnailStatus,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_MIN_SIZE_BYTES = 512


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _aspect_str(w: int, h: int) -> str:
    if not w or not h:
        return "unknown"
    ratio = w / h
    if abs(ratio - 9 / 16) < 0.1:
        return "9:16"
    if abs(ratio - 16 / 9) < 0.1:
        return "16:9"
    if abs(ratio - 1) < 0.1:
        return "1:1"
    return f"{w}x{h}"


def _image_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size
    except Exception:  # noqa: BLE001
        pass
    try:
        from moviepy import ImageClip
        c = ImageClip(str(path))
        return (c.w or 0, c.h or 0)
    except Exception:  # noqa: BLE001
        pass
    return (0, 0)


def score_thumbnail_candidate(
    path: Path,
    source_type: str,
) -> tuple[float, list[str]]:
    """Return (score 0-100, warnings)."""
    warnings: list[str] = []

    if not path.is_file():
        return 0.0, ["file not found"]
    size = path.stat().st_size
    if size < _MIN_SIZE_BYTES:
        return 0.0, [f"file too small ({size} bytes)"]

    base_scores = {
        "manual": 95.0,
        "generated": 80.0,
        "video_frame": 60.0,
        "placeholder": 30.0,
    }
    score = base_scores.get(source_type, 50.0)

    w, h = _image_dimensions(path)
    if w and h:
        ratio = w / h
        if abs(ratio - 9 / 16) < 0.15:
            score = min(100, score + 5)
        elif ratio > 1.2:
            warnings.append("horizontal image for vertical short-form")
            score -= 10
        if min(w, h) < 400:
            warnings.append(f"small resolution ({w}x{h})")
            score -= 10

    return max(0.0, min(100.0, score)), warnings


def validate_thumbnail_candidate(path: Path) -> list[str]:
    warnings: list[str] = []
    if not path.is_file():
        warnings.append(f"file not found: {path.name}")
        return warnings
    if path.stat().st_size < _MIN_SIZE_BYTES:
        warnings.append(f"file too small: {path.name}")
    if path.suffix.lower() not in _IMAGE_EXT:
        warnings.append(f"unsupported image format: {path.suffix}")
    return warnings


def _make_candidate(
    path: Path,
    source_type: str,
    *,
    cid: str = "",
    timestamp: float = 0.0,
    reason: str = "",
) -> ThumbnailCandidate:
    score, warns = score_thumbnail_candidate(path, source_type)
    w, h = _image_dimensions(path)
    return ThumbnailCandidate(
        candidate_id=cid or f"{source_type}_{path.stem}",
        source_path=str(path),
        source_type=source_type,
        timestamp_seconds=timestamp,
        score=score,
        reason=reason or f"{source_type} thumbnail",
        width=w,
        height=h,
        aspect_ratio=_aspect_str(w, h),
        warnings=warns,
    )


def use_manual_thumbnail_candidate(run_dir: Path) -> ThumbnailCandidate | None:
    for name in (
        "thumbnail.jpg", "thumbnail.png", "thumbnail.jpeg", "thumbnail.webp",
    ):
        for folder in (run_dir / "manual_visual_imports", run_dir):
            p = folder / name
            if p.is_file() and p.stat().st_size >= _MIN_SIZE_BYTES:
                return _make_candidate(p, "manual", reason="manually provided thumbnail")
    return None


def use_generated_visual_thumbnail_candidate(run_dir: Path) -> ThumbnailCandidate | None:
    gv_dir = run_dir / "generated_visuals"
    if not gv_dir.is_dir():
        return None

    manifest = _safe_json(run_dir / "generated_visuals_manifest.json")
    for asset in manifest.get("assets") or []:
        if isinstance(asset, dict) and asset.get("asset_type") == "thumbnail_candidate":
            p = Path(asset.get("path", ""))
            if not p.is_absolute():
                p = _REPO_ROOT / asset["path"]
            if p.is_file() and p.suffix.lower() in _IMAGE_EXT:
                return _make_candidate(p, "generated", reason="generated visual thumbnail candidate")

    for p in sorted(gv_dir.iterdir()):
        if "thumbnail" in p.stem.lower() and p.suffix.lower() in _IMAGE_EXT:
            if p.stat().st_size >= _MIN_SIZE_BYTES:
                return _make_candidate(p, "generated", reason="generated thumbnail file")
    return None


def extract_video_thumbnail_candidates(
    run_dir: Path,
    *,
    max_candidates: int = 4,
) -> list[ThumbnailCandidate]:
    from genesis.dashboard.thumbnailer import extract_video_thumbnail

    video = run_dir / "draft_video.mp4"
    if not video.is_file():
        return []

    candidates: list[ThumbnailCandidate] = []
    try:
        from moviepy import VideoFileClip
        with VideoFileClip(str(video), audio=False) as clip:
            dur = float(clip.duration or 0)
    except Exception:  # noqa: BLE001
        dur = 0.0

    if dur <= 0:
        return []

    timestamps = [1.0, dur * 0.10, dur * 0.30, dur * 0.60]
    timestamps = list(dict.fromkeys(round(t, 2) for t in timestamps if 0 < t < dur))[:max_candidates]

    out_dir = run_dir / "generated_visuals" / "thumb_frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, t in enumerate(timestamps):
        out = out_dir / f"frame_{i:02d}_{int(t):04d}s.jpg"
        result = extract_video_thumbnail(video, out, time_sec=t)
        if result and result.is_file() and result.stat().st_size >= _MIN_SIZE_BYTES:
            score, warns = score_thumbnail_candidate(result, "video_frame")
            w, h = _image_dimensions(result)
            candidates.append(ThumbnailCandidate(
                candidate_id=f"frame_{i:02d}",
                source_path=str(result),
                source_type="video_frame",
                timestamp_seconds=t,
                score=score,
                reason=f"video frame at {t:.1f}s",
                width=w,
                height=h,
                aspect_ratio=_aspect_str(w, h),
                warnings=warns,
            ))
    return candidates


def find_thumbnail_candidates(
    run_dir: Path,
    *,
    extract_frames: bool = True,
    max_frame_candidates: int = 4,
) -> list[ThumbnailCandidate]:
    candidates: list[ThumbnailCandidate] = []

    manual = use_manual_thumbnail_candidate(run_dir)
    if manual:
        candidates.append(manual)

    generated = use_generated_visual_thumbnail_candidate(run_dir)
    if generated:
        candidates.append(generated)

    if extract_frames:
        frames = extract_video_thumbnail_candidates(
            run_dir, max_candidates=max_frame_candidates,
        )
        candidates.extend(frames)

    if not candidates:
        placeholder = _make_placeholder_thumbnail(run_dir)
        if placeholder:
            candidates.append(placeholder)

    return sorted(candidates, key=lambda c: c.score, reverse=True)


def _make_placeholder_thumbnail(run_dir: Path) -> ThumbnailCandidate | None:
    """Use any existing image as a placeholder candidate."""
    for name in ("visual_plan.png", "title_card.png"):
        p = run_dir / name
        if p.is_file():
            return _make_candidate(p, "placeholder", reason="title card fallback")
    for p in (run_dir / "generated_visuals").glob("*.png") if (run_dir / "generated_visuals").is_dir() else []:
        if p.stat().st_size >= _MIN_SIZE_BYTES:
            return _make_candidate(p, "placeholder", reason="generated image fallback")
    return None


def select_best_thumbnail(
    candidates: list[ThumbnailCandidate],
) -> ThumbnailCandidate | None:
    if not candidates:
        return None
    best = max(candidates, key=lambda c: c.score)
    if best.score <= 0:
        return None
    best.selected = True
    return best


def run_thumbnail_selection(
    job_id: str,
    *,
    runs_base: Path | None = None,
    extract_frames: bool = True,
    manual_path: str | Path | None = None,
) -> ThumbnailSelectionResult:
    runs_base = runs_base or _RUNS_BASE
    run_dir = runs_base / job_id
    warnings: list[str] = []

    if not run_dir.is_dir():
        return ThumbnailSelectionResult(
            job_id=job_id,
            selected_thumbnail_path="",
            candidates=[],
            status=ThumbnailStatus.FAILED,
            warnings=[f"run folder not found: {run_dir}"],
        )

    if manual_path:
        src = Path(manual_path)
        if src.is_file() and src.suffix.lower() in _IMAGE_EXT:
            import shutil
            dest = run_dir / ("thumbnail" + src.suffix.lower())
            shutil.copy2(src, dest)
        else:
            warnings.append(f"manual_path not usable: {manual_path}")

    candidates = find_thumbnail_candidates(run_dir, extract_frames=extract_frames)
    best = select_best_thumbnail(candidates)

    if not best:
        return ThumbnailSelectionResult(
            job_id=job_id,
            selected_thumbnail_path="",
            candidates=candidates,
            status=ThumbnailStatus.PARTIAL,
            warnings=warnings + ["no usable thumbnail candidate found"],
        )

    from genesis.thumbnail.thumbnail_export import export_selected_thumbnail

    export_result = export_selected_thumbnail(
        job_id, Path(best.source_path), run_dir=run_dir,
    )
    selected_path = export_result.output_path

    return ThumbnailSelectionResult(
        job_id=job_id,
        selected_thumbnail_path=selected_path,
        candidates=candidates,
        status=ThumbnailStatus.COMPLETE,
        warnings=warnings + best.warnings,
        notes=[f"source_type={best.source_type}", f"score={best.score:.1f}"],
    )
