"""
Genesis Studio — Render video from an existing run package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.utils.logger import get_logger
from genesis.video.caption_timing import caption_timing_to_dict
from genesis.video.export_manifest import (
    build_export_manifest,
    validate_export_manifest,
    write_export_manifest,
)
from genesis.video.media_resolver import find_run_media_assets, resolve_narration_path
from genesis.video.simple_renderer import render_video_timeline
from genesis.video.timeline_builder import build_video_timeline
from genesis.video.timeline_models import RenderResult, TimelineStatus

logger = get_logger("video.render_run")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_overlays(run_dir: Path) -> list[dict[str, Any]]:
    data = _load_json(run_dir / "overlay_captions.json")
    return list(data.get("captions") or [])


def _fundraiser_disclosure_note(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ""
    disclosures = metadata.get("disclosures") or []
    blob = json.dumps(disclosures).lower()
    if any(k in blob for k in ("fundrais", "donation", "charity")):
        return "Post with truthful fundraiser disclosure; do not imply guaranteed donations."
    return ""


def render_run_video(
    job_id: str,
    *,
    target_platform: str = "tiktok",
    render_enabled: bool = True,
    brand_preset: str = "clean_creator",
    captions_enabled: bool = True,
    title_card_enabled: bool = True,
    end_card_enabled: bool = True,
    scene_cards_enabled: bool = True,
    runs_base: Path | None = None,
    narration_path: str = "",
) -> RenderResult:
    """
    Load run package, build timeline, render draft MP4 (or partial package).

    Example::

        from genesis.video import render_run_video
        result = render_run_video(
            "solar-lighter-followup-001",
            target_platform="tiktok",
            render_enabled=True,
            brand_preset="bold_viral",
            captions_enabled=True,
        )
    """
    runs_base = runs_base or _RUNS_BASE
    run_dir = runs_base / job_id
    if not run_dir.is_dir():
        return RenderResult(
            job_id=job_id,
            output_path="",
            timeline_path="",
            caption_timing_path="",
            manifest_path="",
            status=TimelineStatus.FAILED,
            renderer="none",
            warnings=[f"run folder not found: {run_dir}"],
        )

    storyboard = _load_json(run_dir / "storyboard.json")
    script_package = _load_json(run_dir / "script_package.json")
    brief = _load_json(run_dir / "brief.json")
    metadata = _load_json(run_dir / "metadata_pack.json")
    overlays = _load_overlays(run_dir)

    if not storyboard.get("shot_plan"):
        return RenderResult(
            job_id=job_id,
            output_path="",
            timeline_path=str(run_dir / "timeline.json"),
            caption_timing_path=str(run_dir / "caption_timing.json"),
            manifest_path=str(run_dir / "export_manifest.json"),
            status=TimelineStatus.FAILED,
            renderer="none",
            warnings=["storyboard.json missing or empty — run social workflow first"],
        )

    narr = resolve_narration_path(
        job_id, run_dir, repo_root=_REPO_ROOT, explicit_path=narration_path
    )
    media = find_run_media_assets(run_dir, repo_root=_REPO_ROOT)

    timeline = build_video_timeline(
        job_id=job_id,
        storyboard=storyboard,
        script_package=script_package if script_package.get("primary_script") else None,
        overlay_captions=overlays,
        narration_path=narr,
        media_assets=media,
        run_dir=run_dir,
        repo_root=_REPO_ROOT,
        target_platform=target_platform,
    )

    caption_data = caption_timing_to_dict(timeline.captions, job_id)
    content_format = brief.get("content_format", "") or storyboard.get("content_format", "")
    disclosure_note = _fundraiser_disclosure_note(metadata)

    render_result = render_video_timeline(
        timeline,
        run_dir,
        repo_root=_REPO_ROOT,
        render_enabled=render_enabled,
        caption_data=caption_data,
        brand_preset=brand_preset,
        captions_enabled=captions_enabled,
        title_card_enabled=title_card_enabled,
        end_card_enabled=end_card_enabled,
        scene_cards_enabled=scene_cards_enabled,
        primary_hook=storyboard.get("primary_hook", ""),
        disclosure_note=disclosure_note,
        content_format=content_format,
    )

    source_files = {
        "brief": "brief.json" if (run_dir / "brief.json").exists() else "",
        "script_package": "script_package.json" if (run_dir / "script_package.json").exists() else "",
        "storyboard": "storyboard.json",
        "overlay_captions": "overlay_captions.json" if (run_dir / "overlay_captions.json").exists() else "",
        "metadata_pack": "metadata_pack.json" if (run_dir / "metadata_pack.json").exists() else "",
    }
    manifest = build_export_manifest(
        job_id=job_id,
        run_dir=run_dir,
        render_result=render_result,
        source_files=source_files,
        narration_path=narr,
        target_platform=target_platform,
        timeline_status=timeline.status,
        brand_preset=brand_preset,
    )
    manifest["warnings"] = list(dict.fromkeys(manifest["warnings"] + validate_export_manifest(manifest)))
    write_export_manifest(run_dir, manifest)

    notes_path = run_dir / "render_notes.md"
    if not notes_path.exists():
        notes_path.write_text(
            f"# Render Notes — {job_id}\n\nStatus: {render_result.status}\n",
            encoding="utf-8",
        )

    logger.info(
        "render_run_video job=%s status=%s renderer=%s preset=%s",
        job_id, render_result.status, render_result.renderer, brand_preset,
    )
    return render_result
