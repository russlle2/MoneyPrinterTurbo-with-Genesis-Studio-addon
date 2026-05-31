"""
Genesis Studio — Post-script narration pipeline step.

After a script is produced, call generate_narration_from_script() to synthesize
voiceover audio via the configured ElevenLabs voice replica (local config or env).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from genesis.integrations.voice_provider import (
    generate_voice,
    voice_backend_ready,
    voiceover_enabled,
)
from genesis.schemas.core import AssetType, GeneratedAsset, JobStatus
from genesis.utils.config_loader import load_genesis_settings
from genesis.utils.logger import get_logger

logger = get_logger("pipeline.narration")

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_audio_dir() -> Path:
    settings = load_genesis_settings()
    base = settings.get("output_base_dir", "assets")
    return _REPO_ROOT / str(base) / "audio"


def _narration_output_path(job_id: str | None, output_path: str | None) -> str:
    if output_path:
        return output_path
    slug = job_id or uuid.uuid4().hex[:12]
    out_dir = _default_audio_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    return str(out_dir / f"narration_{slug}.mp3")


def generate_narration_from_script(
    script_text: str,
    *,
    job_id: str | None = None,
    output_path: str | None = None,
    scene_id: str = "narration",
    backend: str = "elevenlabs",
    skip_if_empty: bool = True,
    **kwargs: Any,
) -> GeneratedAsset:
    """
    Pipeline step: turn script text into narration audio using the saved voice.

    Args:
        script_text: Full script or narration lines from the script agent.
        job_id:      Optional job/run id used in the output filename.
        output_path: Explicit MP3 path; default is assets/audio/narration_<job_id>.mp3.
        scene_id:    Scene id stored on the returned GeneratedAsset.
        backend:     Voice backend (default: elevenlabs).
        skip_if_empty: If True, empty/whitespace script returns SKIPPED without API call.
        **kwargs:    Passed to generate_voice (voice_id, model_id, etc.).

    Returns:
        GeneratedAsset with path set on success.

    Raises:
        RuntimeError: If the voice backend is not configured or synthesis fails.
    """
    text = (script_text or "").strip()
    request_id = job_id or uuid.uuid4().hex[:12]
    asset_id = f"narration-{request_id}"

    # Global kill switch: voiceover is paused by default to avoid wasted API
    # spend on poor output. Skip cleanly instead of calling any paid backend.
    if not voiceover_enabled():
        logger.info("narration skipped: voiceover globally disabled (job %s)", request_id)
        return GeneratedAsset(
            id=asset_id,
            request_id=request_id,
            scene_id=scene_id,
            asset_type=AssetType.AUDIO,
            path="",
            provider=backend,
            prompt="",
            status=JobStatus.SKIPPED,
            metadata={"reason": "voiceover_disabled"},
        )

    if not text:
        if skip_if_empty:
            logger.info("narration skipped: empty script for job %s", request_id)
            return GeneratedAsset(
                id=asset_id,
                request_id=request_id,
                scene_id=scene_id,
                asset_type=AssetType.AUDIO,
                path="",
                provider=backend,
                prompt="",
                status=JobStatus.SKIPPED,
                metadata={"reason": "empty_script"},
            )
        raise RuntimeError("Cannot generate narration from an empty script.")

    ready, message = voice_backend_ready(backend)
    if not ready:
        raise RuntimeError(message)

    dest = _narration_output_path(job_id, output_path)
    logger.info("generating narration for job %s → %s", request_id, dest)

    audio_path = generate_voice(
        text,
        output_path=dest,
        backend=backend,
        **kwargs,
    )

    return GeneratedAsset(
        id=asset_id,
        request_id=request_id,
        scene_id=scene_id,
        asset_type=AssetType.AUDIO,
        path=audio_path,
        provider=backend,
        prompt=text[:500],
        status=JobStatus.COMPLETED,
        metadata={"output_format": kwargs.get("output_format")},
    )


def run_post_script_steps(
    script_text: str,
    *,
    job_id: str | None = None,
    generate_narration: bool = True,
    **kwargs: Any,
) -> dict[str, GeneratedAsset]:
    """
    Run pipeline steps that follow script generation.

    Currently: narration only. Additional steps (hero shots, captions) will be
    added in later phases.
    """
    results: dict[str, GeneratedAsset] = {}
    if generate_narration:
        results["narration"] = generate_narration_from_script(
            script_text,
            job_id=job_id,
            **kwargs,
        )
    return results
