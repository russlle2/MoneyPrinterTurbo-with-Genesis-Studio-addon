"""
Genesis Studio — Run index: scan and summarize run folders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.review.review_models import ReviewStatus, RunSummary

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"

_NARRATION_PREFIX = "narration_"
_AUDIO_DIR = _REPO_ROOT / "assets" / "audio"


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _mtime_str(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return ""


def _has_narration(job_id: str) -> bool:
    for p in (_AUDIO_DIR / f"{_NARRATION_PREFIX}{job_id}.mp3",
              _AUDIO_DIR / f"{_NARRATION_PREFIX}{job_id}.wav"):
        if p.is_file():
            return True
    return False


def _status_for(run_dir: Path) -> str:
    if (run_dir / "draft_video.mp4").is_file():
        return ReviewStatus.COMPLETE
    if (run_dir / "timeline.json").is_file():
        return ReviewStatus.PARTIAL
    if (run_dir / "brief.json").is_file():
        return ReviewStatus.PARTIAL
    return ReviewStatus.MISSING


def summarize_run(run_dir: Path) -> RunSummary:
    """Build a RunSummary from a run folder; never raises."""
    job_id = run_dir.name
    brief = _safe_json(run_dir / "brief.json")
    manifest = _safe_json(run_dir / "export_manifest.json")

    created_at = (
        brief.get("created_at")
        or manifest.get("generated_at")
        or _mtime_str(run_dir / "brief.json")
        or _mtime_str(run_dir)
        or ""
    )
    idea = brief.get("idea", "")
    content_format = (
        brief.get("content_format")
        or _safe_json(run_dir / "script_package.json").get("content_format", "")
        or ""
    )
    platforms = brief.get("platforms") or []

    has_video = (run_dir / "draft_video.mp4").is_file()
    video_path = str(run_dir / "draft_video.mp4") if has_video else ""

    warnings: list[str] = []
    if not brief:
        warnings.append("brief.json missing")
    if not (run_dir / "storyboard.json").is_file():
        warnings.append("storyboard.json missing")
    if not (run_dir / "timeline.json").is_file():
        warnings.append("timeline.json missing")

    return RunSummary(
        job_id=job_id,
        run_dir=str(run_dir),
        created_at=created_at,
        idea=idea,
        content_format=content_format,
        platforms=platforms,
        status=_status_for(run_dir),
        has_script=(run_dir / "script.txt").is_file() or (run_dir / "script_package.json").is_file(),
        has_narration=_has_narration(job_id),
        has_metadata=(run_dir / "metadata_pack.json").is_file(),
        has_storyboard=(run_dir / "storyboard.json").is_file(),
        has_timeline=(run_dir / "timeline.json").is_file(),
        has_draft_video=has_video,
        draft_video_path=video_path,
        warnings=warnings,
    )


def list_runs(
    *,
    runs_base: Path | None = None,
) -> list[RunSummary]:
    """Return all run summaries sorted newest first."""
    base = runs_base or _RUNS_BASE
    if not base.is_dir():
        return []
    summaries = []
    for d in base.iterdir():
        if d.is_dir():
            try:
                summaries.append(summarize_run(d))
            except Exception:  # noqa: BLE001
                pass
    summaries.sort(key=lambda s: s.created_at or "", reverse=True)
    return summaries


def find_latest_run(*, runs_base: Path | None = None) -> RunSummary | None:
    runs = list_runs(runs_base=runs_base)
    return runs[0] if runs else None


def filter_runs(
    summaries: list[RunSummary],
    *,
    has_video: bool | None = None,
    status: str | None = None,
    content_format: str | None = None,
) -> list[RunSummary]:
    out = summaries
    if has_video is not None:
        out = [s for s in out if s.has_draft_video == has_video]
    if status:
        out = [s for s in out if s.status == status]
    if content_format:
        out = [s for s in out if s.content_format == content_format]
    return out
