"""Genesis Studio — Audio file inspection."""

from __future__ import annotations

import hashlib
from pathlib import Path

from genesis.audio.audio_models import AudioAsset

_AUDIO_EXT = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".m4a": "m4a",
    ".aac": "aac",
    ".ogg": "ogg",
}


def get_audio_extension_type(path: Path) -> str:
    return _AUDIO_EXT.get(path.suffix.lower(), "unknown")


def get_audio_duration(path: Path) -> tuple[float, list[str]]:
    warnings: list[str] = []
    try:
        from moviepy import AudioFileClip
        with AudioFileClip(str(path)) as clip:
            return float(clip.duration or 0.0), warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"duration unavailable: {exc}")
    return 0.0, warnings


def safe_get_audio_metadata(path: Path) -> tuple[float, int, int, list[str]]:
    dur, warnings = get_audio_duration(path)
    return dur, 0, 0, warnings


def inspect_audio_file(path: Path, *, stored_path: str = "", audio_type: str = "") -> AudioAsset:
    warnings: list[str] = []
    ext = path.suffix.lower()
    atype = audio_type or get_audio_extension_type(path)
    if atype == "unknown":
        warnings.append(f"unsupported extension: {ext}")

    dur, sr, ch, meta_warns = safe_get_audio_metadata(path)
    warnings.extend(meta_warns)

    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    raw = f"{path.name}:{size}"
    aid = hashlib.md5(raw.encode()).hexdigest()[:10]

    return AudioAsset(
        asset_id=aid,
        source_path=str(path),
        stored_path=stored_path or str(path),
        filename=path.name,
        audio_type=atype,
        extension=ext,
        size_bytes=size,
        duration_seconds=round(dur, 3),
        sample_rate=sr,
        channels=ch,
        volume_role="",
        warnings=warnings,
    )
