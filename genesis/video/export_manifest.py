"""
Genesis Studio — Export manifest for video render outputs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.video.timeline_models import RenderResult, TimelineStatus

_FORBIDDEN_SUBSTRINGS = (
    "api_key",
    "sk_",
    "xi-api",
    "voice_id",
    "openai_api",
    "local_model_path",
)


def build_export_manifest(
    *,
    job_id: str,
    run_dir: Path,
    render_result: RenderResult,
    source_files: dict[str, str],
    narration_path: str = "",
    target_platform: str = "tiktok",
    timeline_status: str = TimelineStatus.COMPLETE,
    brand_preset: str = "clean_creator",
) -> dict[str, Any]:
    created = []
    for name in (
        "timeline.json",
        "caption_timing.json",
        "render_style.json",
        "caption_style.json",
        "render_notes.md",
        "export_manifest.json",
        "draft_video.mp4",
    ):
        if (run_dir / name).exists():
            created.append(name)

    render_style: dict[str, Any] = {}
    if (run_dir / "render_style.json").is_file():
        try:
            render_style = json.loads((run_dir / "render_style.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            render_style = {}

    manifest = {
        "job_id": job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": render_result.status,
        "renderer": render_result.renderer,
        "target_platform": target_platform,
        "brand_preset": brand_preset,
        "created_files": created,
        "source_package": {k: v for k, v in source_files.items() if v},
        "narration_path": narration_path or "",
        "video_output": render_result.output_path or "",
        "timeline_path": "timeline.json",
        "caption_timing_path": "caption_timing.json",
        "render_style_path": "render_style.json" if (run_dir / "render_style.json").exists() else "",
        "caption_style_path": "caption_style.json" if (run_dir / "caption_style.json").exists() else "",
        "render_style_summary": {
            "brand_preset": render_style.get("brand_preset", brand_preset),
            "features": render_style.get("features", {}),
            "target_resolution": render_style.get("target_resolution"),
            "fps": render_style.get("fps"),
        },
        "warnings": list(dict.fromkeys(render_result.warnings)),
        "notes": render_result.notes,
    }
    return manifest


def validate_export_manifest(manifest: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    blob = json.dumps(manifest).lower()
    for token in _FORBIDDEN_SUBSTRINGS:
        if token in blob:
            warnings.append(f"manifest may contain sensitive token: {token}")
    if not manifest.get("job_id"):
        warnings.append("missing job_id")
    return warnings


def write_export_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    path = run_dir / "export_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
