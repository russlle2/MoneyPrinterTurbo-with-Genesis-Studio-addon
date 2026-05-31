"""
Genesis Studio — Run loader: load and preview run packages for review.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from genesis.review.review_models import ReviewAsset, ReviewPackage, ReviewStatus, RunSummary
from genesis.review.run_index import summarize_run

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"

_SECRET_PATTERNS = re.compile(
    r'("?(?:api_key|xi_api_key|openai_api_key|local_model_path|voice_id)\s*"?\s*[:=]\s*"?)([^"\s,}]{6,})',
    re.I,
)

_ASSET_TYPES = [
    ("brief", "brief.json"),
    ("script_text", "script.txt"),
    ("script_package", "script_package.json"),
    ("metadata", "metadata_pack.json"),
    ("storyboard", "storyboard.json"),
    ("shot_plan", "shot_plan.json"),
    ("timeline", "timeline.json"),
    ("caption_timing", "caption_timing.json"),
    ("overlay_captions", "overlay_captions.json"),
    ("render_style", "render_style.json"),
    ("caption_style", "caption_style.json"),
    ("render_notes", "render_notes.md"),
    ("posting_checklist", "posting_checklist.md"),
    ("filming_checklist", "filming_checklist.md"),
    ("visual_plan", "visual_plan.md"),
    ("draft_video", "draft_video.mp4"),
    ("export_manifest", "export_manifest.json"),
]


def load_json_file_safe(path: Path) -> dict[str, Any]:
    """Load JSON; return empty dict on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def load_text_file_safe(path: Path, *, max_chars: int = 4000) -> str:
    """Load text file; return empty string on any error."""
    try:
        text = path.read_text(encoding="utf-8")
        return text[:max_chars] if len(text) > max_chars else text
    except Exception:  # noqa: BLE001
        return ""


def _scrub_secrets(text: str) -> str:
    return _SECRET_PATTERNS.sub(r"\1[REDACTED]", text)


def _mtime_str(path: Path) -> str:
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return ""


def build_script_preview(run_dir: Path) -> str:
    sp = load_json_file_safe(run_dir / "script_package.json")
    if sp:
        lines = [f"Content format: {sp.get('content_format', '')}"]
        ps = sp.get("primary_script") or {}
        sections = ps.get("sections") or []
        for s in sections[:3]:
            name = s.get("section_name", "")
            narr = s.get("narration_text", "")[:100]
            lines.append(f"  [{name}] {narr}")
        if len(sections) > 3:
            lines.append(f"  ... +{len(sections) - 3} more sections")
        hooks = sp.get("hooks") or []
        if hooks:
            lines.append(f"Top hook: {hooks[0].get('text', '')[:80]}")
        ctas = sp.get("cta_options") or []
        if ctas:
            lines.append(f"CTA: {ctas[0].get('text', '')[:80]}")
        return "\n".join(lines)

    txt = load_text_file_safe(run_dir / "script.txt", max_chars=600)
    return txt if txt else "[no script found]"


def build_metadata_preview(run_dir: Path) -> str:
    mp = load_json_file_safe(run_dir / "metadata_pack.json")
    if not mp:
        return "[no metadata found]"
    lines = [f"Platforms: {', '.join(mp.get('platforms') or [])}"]
    hook = mp.get("primary_hook", "")
    if hook:
        lines.append(f"Hook: {hook[:100]}")
    mby = mp.get("metadata_by_platform") or {}
    for platform, pdata in list(mby.items())[:2]:
        cap = (pdata.get("caption") or "")[:120]
        disc = ""
        d = pdata.get("disclosure") or {}
        if d.get("required"):
            disc = f" | Disclosure: {d.get('short_text', '')[:60]}"
        lines.append(f"  [{platform}] {cap}{disc}")
    if len(mby) > 2:
        lines.append(f"  ... +{len(mby) - 2} more platforms")
    return "\n".join(lines)


def build_storyboard_preview(run_dir: Path) -> str:
    sb = load_json_file_safe(run_dir / "storyboard.json")
    if not sb:
        return "[no storyboard found]"
    lines = []
    hook = sb.get("primary_hook", "")
    if hook:
        lines.append(f"Hook: {hook[:80]}")
    sp = sb.get("shot_plan") or []
    # shot_plan may be a dict with a "scenes" key, or a list directly
    if isinstance(sp, dict):
        shots = sp.get("scenes") or []
    else:
        shots = list(sp)
    for shot in shots[:4]:
        name = shot.get("section_name", shot.get("scene_id", ""))
        goal = shot.get("visual_goal", "")[:80]
        lines.append(f"  [{name}] {goal}")
    if len(shots) > 4:
        lines.append(f"  ... +{len(shots) - 4} more scenes")
    return "\n".join(lines) if lines else "[empty storyboard]"


def collect_review_assets(run_dir: Path) -> list[ReviewAsset]:
    assets: list[ReviewAsset] = []
    for asset_type, filename in _ASSET_TYPES:
        p = run_dir / filename
        exists = p.is_file()
        size = p.stat().st_size if exists else 0
        modified = _mtime_str(p) if exists else ""
        warnings = []
        if not exists and asset_type in ("brief", "storyboard", "timeline"):
            warnings.append(f"{filename} missing")
        assets.append(ReviewAsset(
            asset_type=asset_type,
            path=str(p),
            exists=exists,
            size_bytes=size,
            modified_at=modified,
            warnings=warnings,
        ))
    return assets


def load_review_package(
    job_id: str,
    *,
    runs_base: Path | None = None,
) -> ReviewPackage:
    """Load a full review package for the given job_id."""
    base = runs_base or _RUNS_BASE
    run_dir = base / job_id

    if not run_dir.is_dir():
        from genesis.review.review_models import RunSummary
        stub = RunSummary(
            job_id=job_id,
            run_dir=str(run_dir),
            created_at="",
            idea="",
            content_format="",
            platforms=[],
            status=ReviewStatus.FAILED,
            has_script=False,
            has_narration=False,
            has_metadata=False,
            has_storyboard=False,
            has_timeline=False,
            has_draft_video=False,
            draft_video_path="",
            warnings=[f"run folder not found: {run_dir}"],
        )
        return ReviewPackage(
            job_id=job_id,
            run_summary=stub,
            script_preview="",
            metadata_preview="",
            storyboard_preview="",
            video_preview_path="",
            assets=[],
            warnings=[f"run folder not found: {run_dir}"],
            status=ReviewStatus.FAILED,
        )

    summary = summarize_run(run_dir)
    script_preview = _scrub_secrets(build_script_preview(run_dir))
    metadata_preview = _scrub_secrets(build_metadata_preview(run_dir))
    storyboard_preview = build_storyboard_preview(run_dir)
    video_path = str(run_dir / "draft_video.mp4") if (run_dir / "draft_video.mp4").is_file() else ""
    assets = collect_review_assets(run_dir)

    warnings = list(summary.warnings)
    status = summary.status if summary.status else ReviewStatus.PARTIAL

    return ReviewPackage(
        job_id=job_id,
        run_summary=summary,
        script_preview=script_preview,
        metadata_preview=metadata_preview,
        storyboard_preview=storyboard_preview,
        video_preview_path=video_path,
        assets=assets,
        warnings=warnings,
        status=status,
    )
