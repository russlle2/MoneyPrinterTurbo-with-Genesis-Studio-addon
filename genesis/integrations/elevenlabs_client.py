"""
Genesis Studio — ElevenLabs voice synthesis client.

Loads config from genesis/config/elevenlabs.json (gitignored, local-only) or
environment variables (env vars take precedence over saved JSON).

Never calls the API on import.
Never logs, prints, or exposes the raw API key.
Never requires a real key during unit tests.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from genesis.utils.config_loader import load_elevenlabs_config
from genesis.utils.logger import get_logger

logger = get_logger("elevenlabs_client")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _REPO_ROOT / "genesis" / "config" / "elevenlabs.json"
_DEFAULT_AUDIO_DIR = _REPO_ROOT / "assets" / "audio"
_BASE_URL = "https://api.elevenlabs.io/v1"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_config() -> dict[str, Any]:
    """Return merged ElevenLabs config (defaults <- JSON file <- env vars)."""
    return load_elevenlabs_config()


def _get_api_key(config: dict[str, Any]) -> str:
    key = config.get("api_key", "")
    if not key or not key.strip():
        raise RuntimeError(
            "ElevenLabs API key not configured. "
            "Set GENESIS_ELEVENLABS_API_KEY or add api_key to "
            "genesis/config/elevenlabs.json (never commit this file)."
        )
    return key.strip()


def _get_base_url(config: dict[str, Any]) -> str:
    return config.get("base_url", _BASE_URL).rstrip("/")


def _headers(api_key: str) -> dict[str, str]:
    return {"xi-api-key": api_key, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Voice discovery
# ---------------------------------------------------------------------------

def list_voices(config: dict[str, Any] | None = None) -> list[dict]:
    """
    Return all voices available on the ElevenLabs account.

    Args:
        config: Optional pre-loaded config dict. Loads from JSON/env if omitted.

    Returns:
        List of voice dicts as returned by the ElevenLabs /voices endpoint.
    """
    try:
        import requests  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "requests is required for ElevenLabs API calls. "
            "It is already a MoneyPrinterTurbo dependency."
        ) from exc

    cfg = config or _get_config()
    key = _get_api_key(cfg)
    base_url = _get_base_url(cfg)

    resp = requests.get(
        f"{base_url}/voices",
        headers={"xi-api-key": key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("voices", [])


def find_voice_by_name(name: str, config: dict[str, Any] | None = None) -> dict | None:
    """
    Find a voice by display name (case-insensitive substring match).

    Returns the first matching voice dict, or None if not found.
    """
    voices = list_voices(config)
    name_lower = name.lower()
    for voice in voices:
        if name_lower in voice.get("name", "").lower():
            return voice
    return None


# ---------------------------------------------------------------------------
# Config persistence (local-only, never committed)
# ---------------------------------------------------------------------------

def save_elevenlabs_config(
    api_key: str,
    voice_id: str,
    voice_name: str,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
) -> None:
    """
    Write a full ElevenLabs config to genesis/config/elevenlabs.json.

    This file is gitignored and must never be committed. The API key is written
    to local disk only; it is never printed or logged.
    """
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "api_key": api_key,
        "voice_id": voice_id,
        "voice_name": voice_name,
        "model_id": model_id,
        "output_format": output_format,
        "base_url": _BASE_URL,
    }
    _CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("ElevenLabs config saved to %s (api_key=sk-***)", _CONFIG_PATH.name)


def save_selected_voice_config(
    voice_id: str,
    voice_name: str,
    model_id: str = "eleven_multilingual_v2",
) -> None:
    """
    Patch only the voice-selection fields in genesis/config/elevenlabs.json,
    preserving any existing api_key and other settings.
    """
    existing: dict[str, Any] = {}
    if _CONFIG_PATH.is_file():
        try:
            existing = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    existing.update({"voice_id": voice_id, "voice_name": voice_name, "model_id": model_id})
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    logger.info("Voice selection saved: %s (id=%.8s...)", voice_name, voice_id)


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def synthesize_voice(
    text: str,
    voice_id: str | None = None,
    output_path: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Synthesize speech from text using ElevenLabs TTS.

    Args:
        text:        Text to convert to speech.
        voice_id:    Voice ID override. If None, uses voice_id from saved config.
        output_path: Destination file path. If None, saves under assets/audio/.
        **kwargs:    Optional overrides: model_id, output_format, voice_settings.

    Returns:
        Absolute path string to the saved audio file.

    Raises:
        RuntimeError: If API key or voice_id is missing, or the API call fails.
    """
    try:
        import requests  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "requests is required for ElevenLabs API calls."
        ) from exc

    cfg = _get_config()
    key = _get_api_key(cfg)
    base_url = _get_base_url(cfg)

    effective_voice_id = (voice_id or cfg.get("voice_id", "")).strip()
    if not effective_voice_id:
        raise RuntimeError(
            "No voice_id available for synthesis. "
            "Set GENESIS_ELEVENLABS_VOICE_ID or add voice_id to "
            "genesis/config/elevenlabs.json."
        )

    model_id: str = (kwargs.get("model_id") or cfg.get("model_id") or "eleven_multilingual_v2")
    output_format: str = (kwargs.get("output_format") or cfg.get("output_format") or "mp3_44100_128")

    if output_path is None:
        _DEFAULT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"genesis_voice_{uuid.uuid4().hex[:8]}.mp3"
        output_path = str(_DEFAULT_AUDIO_DIR / filename)

    payload: dict[str, Any] = {
        "text": text,
        "model_id": model_id,
        "voice_settings": kwargs.get(
            "voice_settings",
            {"stability": 0.5, "similarity_boost": 0.75},
        ),
    }

    url = f"{base_url}/text-to-speech/{effective_voice_id}"
    logger.info(
        "synthesize_voice: voice=%.8s... model=%s format=%s",
        effective_voice_id,
        model_id,
        output_format,
    )

    resp = requests.post(
        url,
        headers=_headers(key),
        json=payload,
        params={"output_format": output_format},
        timeout=60,
    )
    resp.raise_for_status()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(resp.content)
    logger.info("Voice saved: %s (%d bytes)", output_path, len(resp.content))
    return str(out)


def synthesize_test_voice_sample(text: str | None = None) -> str:
    """
    Generate a short test audio file using the currently configured voice.

    Saves to assets/audio/elevenlabs_voice_test.mp3.
    Returns the output path on success.
    """
    test_text = text or (
        "This is Genesis Studio. Local-first video creation, powered by my own voice."
    )
    output_path = str(_DEFAULT_AUDIO_DIR / "elevenlabs_voice_test.mp3")
    return synthesize_voice(test_text, output_path=output_path)
