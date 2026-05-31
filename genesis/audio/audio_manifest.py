"""Genesis Studio — Audio manifest persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.audio.audio_models import AudioAsset, AudioMixResult, AudioStatus


def build_audio_manifest(
    job_id: str,
    *,
    narration: AudioAsset | None = None,
    music: AudioAsset | None = None,
    mix_result: AudioMixResult | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "narration": narration.to_dict() if narration else None,
        "music": music.to_dict() if music else None,
        "mix_result": mix_result.to_dict() if mix_result else None,
        "mixed_audio_path": mix_result.output_path if mix_result else "",
        "status": mix_result.status if mix_result else AudioStatus.SKIPPED,
    }


def write_audio_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    path = run_dir / "audio_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def load_audio_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "audio_manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
