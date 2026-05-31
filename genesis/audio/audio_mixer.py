"""Genesis Studio — Local audio mixing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.audio.audio_models import (
    AudioMixResult,
    AudioMixSettings,
    AudioStatus,
    AudioTrackPlan,
)
from genesis.audio.audio_inspector import inspect_audio_file
from genesis.audio.music_bed import loop_or_trim_music_to_duration, select_music_bed, validate_music_asset

_REPO_ROOT = Path(__file__).resolve().parents[2]


def apply_fades(clip: Any, *, fade_in: float, fade_out: float) -> Any:
    from moviepy import afx
    if fade_in > 0:
        try:
            clip = afx.AudioFadeIn(clip, fade_in)
        except Exception:  # noqa: BLE001
            pass
    if fade_out > 0 and clip.duration:
        try:
            clip = afx.AudioFadeOut(clip, fade_out)
        except Exception:  # noqa: BLE001
            pass
    return clip


def apply_ducking(music_clip: Any, *, ducking_level: float, narration_duration: float) -> tuple[Any, bool]:
    """Conservative: lower music volume for full narration span."""
    try:
        vol = max(0.01, ducking_level)
        return music_clip.with_volume_scaled(vol), True
    except Exception:  # noqa: BLE001
        return music_clip, False


def normalize_audio_if_available(clip: Any, *, target_lufs: float = -14.0) -> tuple[Any, bool]:
    try:
        from moviepy import afx
        return afx.AudioNormalize(clip), True
    except Exception:  # noqa: BLE001
        return clip, False


def build_audio_mix_plan(
    job_id: str,
    *,
    narration_path: Path,
    music_path: Path | None = None,
    target_duration: float = 0.0,
    settings: AudioMixSettings | None = None,
    repo_root: Path | None = None,
) -> tuple[list[AudioTrackPlan], AudioMixSettings, list[str]]:
    settings = settings or AudioMixSettings()
    warnings: list[str] = []
    plans: list[AudioTrackPlan] = []

    narr_asset = inspect_audio_file(narration_path)
    narr_dur = narr_asset.duration_seconds or target_duration or 30.0
    if narr_asset.duration_seconds <= 0:
        warnings.append("narration duration unknown; using target duration estimate")

    plans.append(AudioTrackPlan(
        track_id="narration",
        source_path=str(narration_path),
        track_type="narration",
        start_time=0.0,
        duration=narr_dur,
        volume=settings.narration_volume,
        fade_in=0.0,
        fade_out=0.0,
        ducking_applied=False,
        notes="primary voiceover",
    ))

    if music_path and music_path.is_file():
        ok, mw = validate_music_asset(music_path)
        warnings.extend(mw)
        if ok:
            music_vol = settings.music_volume
            plans.append(AudioTrackPlan(
                track_id="music",
                source_path=str(music_path),
                track_type="music",
                start_time=0.0,
                duration=narr_dur,
                volume=music_vol,
                fade_in=settings.fade_in_seconds,
                fade_out=settings.fade_out_seconds,
                ducking_applied=settings.duck_music_under_voice,
                notes="background music bed",
            ))
    elif not narration_path.is_file():
        warnings.append("no narration file")

    return plans, settings, warnings


def validate_audio_mix(plans: list[AudioTrackPlan], settings: AudioMixSettings) -> list[str]:
    warnings: list[str] = []
    has_narr = any(p.track_type == "narration" for p in plans)
    has_music = any(p.track_type == "music" for p in plans)
    if not has_narr:
        warnings.append("no narration in mix plan")
    if has_music and settings.music_volume >= settings.narration_volume:
        warnings.append("music volume should stay below narration")
    if has_music and not has_narr:
        warnings.append("music-only mix")
    return warnings


def mix_audio_tracks(
    plans: list[AudioTrackPlan],
    settings: AudioMixSettings,
    *,
    target_duration: float,
) -> tuple[Any | None, list[str]]:
    from moviepy import AudioFileClip, CompositeAudioClip

    warnings: list[str] = []
    clips: list[Any] = []
    narr_dur = target_duration

    for plan in plans:
        p = Path(plan.source_path)
        if not p.is_file():
            warnings.append(f"missing audio: {plan.track_id}")
            continue
        try:
            if plan.track_type == "music":
                clip = loop_or_trim_music_to_duration(p, narr_dur or plan.duration)
            else:
                clip = AudioFileClip(str(p))
                if narr_dur and clip.duration and clip.duration > narr_dur:
                    clip = clip.subclipped(0, narr_dur)
            clip = clip.with_volume_scaled(plan.volume)
            clip = apply_fades(clip, fade_in=plan.fade_in, fade_out=plan.fade_out)
            if plan.ducking_applied and plan.track_type == "music":
                clip, _ = apply_ducking(clip, ducking_level=settings.ducking_level, narration_duration=narr_dur)
            clips.append(clip)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{plan.track_id} load failed: {exc}")

    if not clips:
        return None, warnings

    try:
        if len(clips) == 1:
            mixed = clips[0]
        else:
            mixed = CompositeAudioClip(clips)
        if settings.normalize_output:
            mixed, _ = normalize_audio_if_available(mixed, target_lufs=settings.target_lufs)
        return mixed, warnings
    except Exception as exc:  # noqa: BLE001
        return None, warnings + [f"composite failed: {exc}"]


def write_mixed_audio(mixed_clip: Any, out_path: Path) -> bool:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mixed_clip.write_audiofile(str(out_path), logger=None)
        return out_path.is_file() and out_path.stat().st_size > 500
    except Exception:  # noqa: BLE001
        return False
    finally:
        try:
            mixed_clip.close()
        except Exception:  # noqa: BLE001
            pass


def write_audio_mix_plan(run_dir: Path, result: AudioMixResult) -> Path:
    path = run_dir / "audio_mix_plan.json"
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path


def run_audio_mix_for_job(
    job_id: str,
    *,
    narration_rel: str,
    run_dir: Path,
    repo_root: Path | None = None,
    music_path: str | None = None,
    settings: AudioMixSettings | None = None,
    allow_global_music: bool = False,
    target_duration: float = 0.0,
) -> AudioMixResult:
    repo_root = repo_root or _REPO_ROOT
    settings = settings or AudioMixSettings()
    if music_path is None and hasattr(settings, "music_volume"):
        pass

    narr_abs = repo_root / narration_rel if narration_rel and not Path(narration_rel).is_absolute() else Path(narration_rel or "")
    warnings: list[str] = []

    from genesis.audio.music_bed import find_music_assets_for_run

    music_assets = find_music_assets_for_run(run_dir, repo_root=repo_root, allow_global=allow_global_music)
    music_asset = select_music_bed(music_assets, explicit_path=music_path or "", repo_root=repo_root)
    music_abs = None
    if music_asset:
        music_abs = repo_root / music_asset.stored_path if not Path(music_asset.stored_path).is_absolute() else Path(music_asset.stored_path)

    if not narr_abs.is_file():
        return AudioMixResult(
            job_id=job_id, output_path="", track_plans=[], settings=settings,
            status=AudioStatus.FAILED, warnings=["narration file not found"],
        )

    plans, settings, pw = build_audio_mix_plan(
        job_id, narration_path=narr_abs, music_path=music_abs,
        target_duration=target_duration, settings=settings, repo_root=repo_root,
    )
    warnings.extend(pw)
    warnings.extend(validate_audio_mix(plans, settings))

    td = target_duration or next((p.duration for p in plans if p.track_type == "narration"), 30.0)
    mixed_clip, mw = mix_audio_tracks(plans, settings, target_duration=td)
    warnings.extend(mw)

    out_abs = run_dir / "mixed_audio.mp3"
    out_rel = ""
    status = AudioStatus.PARTIAL

    if mixed_clip:
        if write_mixed_audio(mixed_clip, out_abs):
            try:
                out_rel = str(out_abs.resolve().relative_to(repo_root.resolve()))
            except ValueError:
                out_rel = "mixed_audio.mp3"
            status = AudioStatus.COMPLETE if not warnings else AudioStatus.PARTIAL
        else:
            warnings.append("mixed_audio write failed")
            status = AudioStatus.FAILED
    else:
        warnings.append("mix failed; use narration only")
        status = AudioStatus.FAILED

    result = AudioMixResult(
        job_id=job_id,
        output_path=out_rel,
        track_plans=plans,
        settings=settings,
        status=status,
        warnings=warnings,
        notes=["ducking uses conservative volume reduction under voice"] if settings.duck_music_under_voice else [],
    )
    write_audio_mix_plan(run_dir, result)
    return result
