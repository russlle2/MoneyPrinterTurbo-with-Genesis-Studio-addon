"""Genesis Studio — Music bed discovery and preparation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from genesis.audio.audio_inspector import get_audio_extension_type, inspect_audio_file
from genesis.audio.audio_models import AudioAsset

_MUSIC_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def validate_music_asset(path: Path) -> tuple[bool, list[str]]:
    if not path.is_file():
        return False, ["file not found"]
    if path.suffix.lower() not in _MUSIC_EXT:
        return False, [f"unsupported music format: {path.suffix}"]
    return True, []


def find_music_assets_for_run(
    run_dir: Path,
    *,
    repo_root: Path,
    allow_global: bool = False,
) -> list[AudioAsset]:
    assets: list[AudioAsset] = []
    run_music = run_dir / "music"
    if run_music.is_dir():
        for p in sorted(run_music.iterdir()):
            if p.is_file() and p.suffix.lower() in _MUSIC_EXT:
                try:
                    rel = str(p.resolve().relative_to(repo_root.resolve()))
                except ValueError:
                    rel = str(p)
                a = inspect_audio_file(p, stored_path=rel, audio_type="music")
                a.volume_role = "music"
                assets.append(a)

    if allow_global:
        global_music = repo_root / "assets" / "music"
        if global_music.is_dir():
            for p in sorted(global_music.iterdir()):
                if p.is_file() and p.suffix.lower() in _MUSIC_EXT:
                    try:
                        rel = str(p.resolve().relative_to(repo_root.resolve()))
                    except ValueError:
                        rel = str(p)
                    a = inspect_audio_file(p, stored_path=rel, audio_type="music")
                    a.volume_role = "music_global"
                    assets.append(a)
    return assets


def select_music_bed(
    assets: list[AudioAsset],
    *,
    explicit_path: str = "",
    repo_root: Path | None = None,
) -> AudioAsset | None:
    if explicit_path:
        p = Path(explicit_path)
        repo_root = repo_root or Path(__file__).resolve().parents[2]
        if not p.is_absolute():
            p = repo_root / explicit_path
        if p.is_file():
            ok, _ = validate_music_asset(p)
            if ok:
                try:
                    rel = str(p.resolve().relative_to(repo_root.resolve()))
                except ValueError:
                    rel = str(p)
                a = inspect_audio_file(p, stored_path=rel, audio_type="music")
                a.volume_role = "music_explicit"
                return a
        return None
    run_local = [a for a in assets if a.volume_role == "music"]
    if run_local:
        return run_local[0]
    global_a = [a for a in assets if a.volume_role == "music_global"]
    return global_a[0] if global_a else None


def copy_music_to_run(src: Path, run_dir: Path) -> Path:
    dest_dir = run_dir / "music"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.is_file():
        shutil.copy2(src, dest)
    return dest


def loop_or_trim_music_to_duration(path: Path, target_duration: float) -> Any:
    """Return MoviePy clip trimmed or looped to target_duration."""
    from moviepy import AudioFileClip, afx

    clip = AudioFileClip(str(path))
    dur = clip.duration or 0.0
    if dur <= 0:
        return clip
    if dur >= target_duration:
        return clip.subclipped(0, target_duration)
    try:
        return afx.AudioLoop(clip, duration=target_duration)
    except Exception:  # noqa: BLE001
        loops = int(target_duration / dur) + 1
        parts = [clip] * loops
        from moviepy import concatenate_audioclips
        combined = concatenate_audioclips(parts)
        return combined.subclipped(0, target_duration)
