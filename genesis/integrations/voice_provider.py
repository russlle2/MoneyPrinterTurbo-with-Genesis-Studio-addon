"""
Genesis Studio — Voice provider abstraction layer.

Thin dispatch layer so the pipeline can call generate_voice() without
being coupled to ElevenLabs directly. Additional backends can be registered here.

Supported backends:
  "elevenlabs"  — ElevenLabs TTS via genesis/integrations/elevenlabs_client.py
"""

from __future__ import annotations

import os
from typing import Any

from genesis.utils.logger import get_logger

logger = get_logger("voice_provider")

_SUPPORTED_BACKENDS: tuple[str, ...] = ("elevenlabs",)


class VoiceoverDisabledError(RuntimeError):
    """Raised when voiceover synthesis is attempted while globally disabled."""


def voiceover_enabled() -> bool:
    """
    Global kill switch for paid voiceover (ElevenLabs) synthesis.

    Voiceover is DISABLED by default so no API tokens are ever spent unless
    explicitly re-enabled via the ``GENESIS_ENABLE_VOICEOVER`` environment
    variable (set to 1/true/yes/on). This is intentional: the project owner
    paused voiceover/captions after wasted spend on garbled output.
    """
    return os.environ.get("GENESIS_ENABLE_VOICEOVER", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def generate_voice(
    text: str,
    output_path: str | None = None,
    *,
    backend: str = "elevenlabs",
    voice_id: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Generate a voiceover from text using the specified backend.

    Args:
        text:        Text to synthesize into speech.
        output_path: Destination file path. If None the backend chooses a default
                     under assets/audio/.
        backend:     Voice synthesis backend (default: "elevenlabs").
        voice_id:    Voice ID override. Falls back to saved config when omitted.
        **kwargs:    Passed through to the backend (model_id, output_format, etc.).

    Returns:
        Absolute path string to the generated audio file.

    Raises:
        RuntimeError: If the backend is unknown or not configured.
        VoiceoverDisabledError: If voiceover is globally disabled (default).
    """
    if not voiceover_enabled():
        raise VoiceoverDisabledError(
            "Voiceover is temporarily disabled (no API tokens will be spent). "
            "Set GENESIS_ENABLE_VOICEOVER=1 to re-enable."
        )

    if backend == "elevenlabs":
        from genesis.integrations.elevenlabs_client import synthesize_voice
        return synthesize_voice(text, voice_id=voice_id, output_path=output_path, **kwargs)

    raise RuntimeError(
        f"Unknown voice backend: {backend!r}. "
        f"Supported backends: {', '.join(_SUPPORTED_BACKENDS)}"
    )


def voice_backend_ready(backend: str = "elevenlabs") -> tuple[bool, str]:
    """
    Check whether a voice backend is configured and ready.

    Returns:
        (True, "") if ready, or (False, reason_message) if not.
    """
    if not voiceover_enabled():
        return False, (
            "Voiceover temporarily disabled (no tokens spent). "
            "Set GENESIS_ENABLE_VOICEOVER=1 to re-enable."
        )

    if backend == "elevenlabs":
        from genesis.utils.config_loader import elevenlabs_ready
        return elevenlabs_ready()

    return False, (
        f"Unknown voice backend: {backend!r}. "
        f"Supported: {', '.join(_SUPPORTED_BACKENDS)}"
    )
