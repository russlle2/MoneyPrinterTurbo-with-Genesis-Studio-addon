"""Genesis Studio — Beat timing analysis (local, safe fallbacks)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from genesis.video.transition_models import BeatTimingResult, TransitionStatus

_MIN_CAPTION_GAP = 1.0


def estimate_bpm_simple(duration: float, *, preferred_bpm: float = 120.0) -> float:
    """Pick a reasonable BPM from common ranges based on duration."""
    if duration <= 0:
        return preferred_bpm
    for bpm in (90.0, 100.0, 110.0, 120.0, 128.0, 140.0):
        beats = duration * bpm / 60.0
        if 8 <= beats <= 80:
            return bpm
    return preferred_bpm


def estimate_energy_peaks(
    duration: float,
    *,
    bpm: float,
    max_peaks: int = 64,
) -> list[float]:
    """Evenly spaced beat markers when waveform analysis is unavailable."""
    if duration <= 0 or bpm <= 0:
        return []
    interval = 60.0 / bpm
    times: list[float] = []
    t = interval
    while t < duration and len(times) < max_peaks:
        times.append(round(t, 3))
        t += interval
    return times


def _audio_duration(path: Path) -> float:
    try:
        from moviepy import AudioFileClip
        clip = AudioFileClip(str(path))
        dur = float(clip.duration or 0.0)
        clip.close()
        return dur
    except Exception:  # noqa: BLE001
        pass
    try:
        from genesis.audio.audio_inspector import get_audio_duration
        return float(get_audio_duration(path) or 0.0)
    except Exception:  # noqa: BLE001
        return 0.0


def analyze_audio_beats(
    job_id: str,
    audio_path: str | Path | None,
    *,
    repo_root: Path | None = None,
    is_music: bool = True,
    target_duration: float = 0.0,
) -> BeatTimingResult:
    """
    Analyze beats from music/audio. Uses duration + estimated BPM when waveform unavailable.
    Narration-only paths return skipped/low confidence.
    """
    repo_root = repo_root or Path(__file__).resolve().parents[2]
    warnings: list[str] = []

    if not audio_path:
        return BeatTimingResult(
            job_id=job_id,
            audio_path="",
            duration=0.0,
            estimated_bpm=0.0,
            beat_times=[],
            confidence=0.0,
            status=TransitionStatus.SKIPPED,
            warnings=["no audio path for beat analysis"],
            notes=["narration-only pacing"],
        )

    path = Path(audio_path)
    if not path.is_absolute():
        path = repo_root / path
    if not path.is_file():
        return BeatTimingResult(
            job_id=job_id,
            audio_path=str(audio_path),
            duration=0.0,
            estimated_bpm=0.0,
            beat_times=[],
            confidence=0.0,
            status=TransitionStatus.SKIPPED,
            warnings=[f"audio not found: {audio_path}"],
        )

    duration = _audio_duration(path) or target_duration
    if duration <= 0:
        return BeatTimingResult(
            job_id=job_id,
            audio_path=str(audio_path),
            duration=0.0,
            estimated_bpm=0.0,
            beat_times=[],
            confidence=0.0,
            status=TransitionStatus.FAILED,
            warnings=["could not read audio duration"],
        )

    if not is_music:
        return BeatTimingResult(
            job_id=job_id,
            audio_path=str(audio_path),
            duration=duration,
            estimated_bpm=0.0,
            beat_times=[],
            confidence=0.1,
            status=TransitionStatus.SKIPPED,
            notes=["narration-only — beat sync not applied"],
        )

    bpm = estimate_bpm_simple(duration)
    beats = estimate_energy_peaks(duration, bpm=bpm)
    confidence = 0.35
    warnings.append("beat markers estimated (low confidence — no waveform analysis)")

    return BeatTimingResult(
        job_id=job_id,
        audio_path=str(audio_path),
        duration=duration,
        estimated_bpm=bpm,
        beat_times=beats,
        confidence=confidence,
        status=TransitionStatus.PARTIAL,
        warnings=warnings,
        notes=["approximate beat grid"],
    )


def choose_cut_points_near_beats(
    scene_end_times: list[float],
    beat_times: list[float],
    *,
    max_shift: float = 0.12,
) -> list[float]:
    """Return adjusted end times nudged toward nearest beat within max_shift."""
    if not beat_times:
        return scene_end_times
    out: list[float] = []
    for t in scene_end_times:
        nearest = min(beat_times, key=lambda b: abs(b - t))
        if abs(nearest - t) <= max_shift:
            out.append(nearest)
        else:
            out.append(t)
    return out


def validate_beat_timing(result: BeatTimingResult) -> list[str]:
    warnings: list[str] = []
    if result.duration < 0:
        warnings.append("negative duration")
    if result.beat_times and result.beat_times != sorted(result.beat_times):
        warnings.append("beat_times not monotonic")
    if result.confidence < 0.2 and result.status not in (TransitionStatus.SKIPPED,):
        warnings.append("very low beat confidence")
    return warnings
