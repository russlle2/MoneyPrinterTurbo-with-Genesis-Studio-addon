"""Genesis Studio — Thumbnail generation for dashboard."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_THUMB_DIR = _REPO_ROOT / "assets" / "dashboard" / "thumbnails"

_THUMB_W = 320
_THUMB_H = 180


def safe_thumbnail_filename(job_id: str) -> str:
    safe = re.sub(r"[^\w\.\-]+", "_", job_id.strip())[:80] or "run"
    return f"{safe}.jpg"


def find_existing_thumbnail(
    job_id: str,
    *,
    thumb_dir: Path | None = None,
) -> Path | None:
    thumb_dir = thumb_dir or _DEFAULT_THUMB_DIR
    path = thumb_dir / safe_thumbnail_filename(job_id)
    return path if path.is_file() and path.stat().st_size > 0 else None


def extract_video_thumbnail(
    video_path: Path,
    out_path: Path,
    *,
    time_sec: float | None = None,
) -> Path | None:
    """Extract one frame to JPEG; returns out_path or None on failure."""
    if not video_path.is_file():
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from moviepy import VideoFileClip

        clip = VideoFileClip(str(video_path), audio=False)
        try:
            dur = max(float(clip.duration or 1.0), 0.1)
            if time_sec is None:
                t = min(max(dur * 0.1, 1.0), max(dur - 0.05, 0.5)) if dur > 1.0 else dur * 0.5
            else:
                t = min(max(float(time_sec), 0.0), max(dur - 0.01, 0.0))

            if hasattr(clip, "save_frame"):
                clip.save_frame(str(out_path), t=t)
            else:
                frame = clip.get_frame(t)
                _save_frame_array(frame, out_path)
        finally:
            clip.close()
        if out_path.is_file() and out_path.stat().st_size > 0:
            _resize_jpeg(out_path)
            return out_path
    except Exception:  # noqa: BLE001
        pass
    return None


def _save_frame_array(frame: Any, out_path: Path) -> None:
    from PIL import Image
    import numpy as np

    arr = np.asarray(frame)
    if arr.ndim < 2:
        raise ValueError("invalid frame")
    if arr.dtype != np.uint8:
        if arr.max() <= 1.0:
            arr = (arr * 255).clip(0, 255).astype(np.uint8)
        else:
            arr = arr.astype(np.uint8)
    if arr.shape[-1] == 4:
        img = Image.fromarray(arr, "RGBA").convert("RGB")
    else:
        img = Image.fromarray(arr[:, :, :3], "RGB")
    img.thumbnail((_THUMB_W, _THUMB_H))
    img.save(out_path, "JPEG", quality=85)


def _resize_jpeg(path: Path) -> None:
    try:
        from PIL import Image
        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((_THUMB_W, _THUMB_H))
            img.save(path, "JPEG", quality=85)
    except Exception:  # noqa: BLE001
        pass


def generate_placeholder_thumbnail(
    out_path: Path,
    *,
    job_id: str = "",
    idea: str = "",
    status: str = "partial",
) -> Path:
    """Create a simple placeholder JPEG with run info."""
    from PIL import Image, ImageDraw, ImageFont

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (_THUMB_W, _THUMB_H), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:  # noqa: BLE001
        font = None

    lines = [
        "No preview",
        (job_id or "run")[:28],
        f"status: {status}",
    ]
    if idea:
        lines.append((idea[:36] + "…") if len(idea) > 36 else idea)

    y = 24
    for line in lines:
        draw.text((12, y), line, fill=(220, 220, 230), font=font)
        y += 22

    img.save(out_path, "JPEG", quality=85)
    return out_path


def generate_thumbnail_for_run(
    job_id: str,
    *,
    run_dir: Path,
    thumb_dir: Path | None = None,
    force: bool = False,
) -> Path:
    """
    Return thumbnail path for a run.
    Uses existing file unless force=True; extracts from video or builds placeholder.
    """
    thumb_dir = thumb_dir or _DEFAULT_THUMB_DIR
    thumb_dir.mkdir(parents=True, exist_ok=True)
    out_path = thumb_dir / safe_thumbnail_filename(job_id)

    if not force:
        existing = find_existing_thumbnail(job_id, thumb_dir=thumb_dir)
        if existing:
            return existing

    video = run_dir / "draft_video.mp4"
    if video.is_file():
        result = extract_video_thumbnail(video, out_path)
        if result:
            return result

    brief_idea = ""
    brief_path = run_dir / "brief.json"
    if brief_path.is_file():
        try:
            import json
            brief_idea = json.loads(brief_path.read_text(encoding="utf-8")).get("idea", "")
        except Exception:  # noqa: BLE001
            pass

    status = "partial"
    summary_path = run_dir / "creator_run_summary.json"
    if summary_path.is_file():
        try:
            import json
            status = json.loads(summary_path.read_text(encoding="utf-8")).get("status", status)
        except Exception:  # noqa: BLE001
            pass

    return generate_placeholder_thumbnail(
        out_path, job_id=job_id, idea=brief_idea, status=status,
    )


def build_thumbnail_contact_sheet(
    thumbnail_paths: list[Path],
    out_path: Path,
    *,
    cols: int = 4,
    cell_w: int = _THUMB_W,
    cell_h: int = _THUMB_H,
) -> Path | None:
    """Compose thumbnails into a single contact sheet image."""
    paths = [p for p in thumbnail_paths if p.is_file()]
    if not paths:
        return None

    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return None

    cols = max(1, cols)
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (20, 20, 28))
    for i, tp in enumerate(paths[: cols * rows]):
        try:
            thumb = Image.open(tp).convert("RGB")
            thumb.thumbnail((cell_w, cell_h))
            x = (i % cols) * cell_w
            y = (i // cols) * cell_h
            sheet.paste(thumb, (x, y))
        except Exception:  # noqa: BLE001
            continue

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, "JPEG", quality=85)
    return out_path if out_path.is_file() else None
