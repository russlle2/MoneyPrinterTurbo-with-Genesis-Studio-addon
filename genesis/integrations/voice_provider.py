"""
Genesis Studio — Voice provider abstraction layer.

Thin dispatch layer so the pipeline can call generate_voice() without
being coupled to ElevenLabs directly. Additional backends can be registered here.

Supported backends:
  "elevenlabs"  — ElevenLabs TTS via genesis/integrations/elevenlabs_client.py
"""

from __future__ import annotations

from typing import Any

from genesis.utils.logger import get_logger

logger = get_logger("voice_provider")

_SUPPORTED_BACKENDS: tuple[str, ...] = ("elevenlabs",)


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
    """
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
    if backend == "elevenlabs":
        from genesis.utils.config_loader import elevenlabs_ready
        return elevenlabs_ready()

    return False, (
        f"Unknown voice backend: {backend!r}. "
        f"Supported: {', '.join(_SUPPORTED_BACKENDS)}"
    )
