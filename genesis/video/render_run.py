"""
Genesis Studio — Render video from an existing run package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.utils.logger import get_logger
from genesis.video.caption_timing import caption_timing_to_dict
from genesis.video.export_manifest import (
    build_export_manifest,
    validate_export_manifest,
    write_export_manifest,
)
from genesis.video.media_resolver import find_run_media_assets, resolve_narration_path, match_assets_to_scenes
from genesis.video.simple_renderer import render_video_timeline
from genesis.video.timeline_builder import build_video_timeline
from genesis.video.timeline_models import RenderResult, TimelineStatus

logger = get_logger("video.render_run")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_overlays(run_dir: Path) -> list[dict[str, Any]]:
    data = _load_json(run_dir / "overlay_captions.json")
    return list(data.get("captions") or [])


def _fundraiser_disclosure_note(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ""
    disclosures = metadata.get("disclosures") or []
    blob = json.dumps(disclosures).lower()
    if any(k in blob for k in ("fundrais", "donation", "charity")):
        return "Post with truthful fundraiser disclosure; do not imply guaranteed donations."
    return ""


def render_run_video(
    job_id: str,
    *,
    target_platform: str = "tiktok",
    render_enabled: bool = True,
    brand_preset: str = "clean_creator",
    captions_enabled: bool = True,
    title_card_enabled: bool = True,
    end_card_enabled: bool = True,
    scene_cards_enabled: bool = True,
    runs_base: Path | None = None,
    narration_path: str = "",
    audio_mix_enabled: bool = True,
    music_path: str | None = None,
    music_volume: float = 0.18,
    narration_volume: float = 1.0,
    duck_music: bool = True,
    transition_preset: str = "auto",
    beat_sync_enabled: bool = True,
    motion_effects_enabled: bool = True,
    transition_duration: float | None = None,
) -> RenderResult:
    """
    Load run package, build timeline, render draft MP4 (or partial package).

    Example::

        from genesis.video import render_run_video
        result = render_run_video(
            "solar-lighter-followup-001",
            target_platform="tiktok",
            render_enabled=True,
            brand_preset="bold_viral",
            captions_enabled=True,
        )
    """
    runs_base = runs_base or _RUNS_BASE
    run_dir = runs_base / job_id
    if not run_dir.is_dir():
        return RenderResult(
            job_id=job_id,
            output_path="",
            timeline_path="",
            caption_timing_path="",
            manifest_path="",
            status=TimelineStatus.FAILED,
            renderer="none",
            warnings=[f"run folder not found: {run_dir}"],
        )

    storyboard = _load_json(run_dir / "storyboard.json")
    script_package = _load_json(run_dir / "script_package.json")
    brief = _load_json(run_dir / "brief.json")
    metadata = _load_json(run_dir / "metadata_pack.json")
    overlays = _load_overlays(run_dir)

    if not storyboard.get("shot_plan"):
        return RenderResult(
            job_id=job_id,
            output_path="",
            timeline_path=str(run_dir / "timeline.json"),
            caption_timing_path=str(run_dir / "caption_timing.json"),
            manifest_path=str(run_dir / "export_manifest.json"),
            status=TimelineStatus.FAILED,
            renderer="none",
            warnings=["storyboard.json missing or empty — run social workflow first"],
        )

    narr = resolve_narration_path(
        job_id, run_dir, repo_root=_REPO_ROOT, explicit_path=narration_path
    )
    media = find_run_media_assets(run_dir, repo_root=_REPO_ROOT)

    # Prefer media_manifest.json scene assignments when available
    manifest_matches: dict[str, str] | None = None
    media_manifest_path = run_dir / "media_manifest.json"
    if media_manifest_path.is_file():
        try:
            mm_data = _load_json(media_manifest_path)
            scene_matches = mm_data.get("scene_matches") or []
            manifest_matches = {
                m["scene_id"]: m["selected_assets"][0]
                for m in scene_matches
                if m.get("selected_assets") and not m.get("fallback_needed")
            }
            if manifest_matches:
                logger.info("render_run_video job=%s using media_manifest (%d scene assignments)", job_id, len(manifest_matches))
        except Exception:  # noqa: BLE001
            manifest_matches = None

    timeline = build_video_timeline(
        job_id=job_id,
        storyboard=storyboard,
        script_package=script_package if script_package.get("primary_script") else None,
        overlay_captions=overlays,
        narration_path=narr,
        media_assets=media,
        run_dir=run_dir,
        repo_root=_REPO_ROOT,
        target_platform=target_platform,
        manifest_matches=manifest_matches,
    )

    trim_notes: list[str] = []
    try:
        from genesis.video.timeline_refiner import refine_video_timeline, write_timeline_refinement
        from genesis.video.clip_trimmer import write_trim_decisions, suggest_trims_for_manifest
        from genesis.media.media_manifest import load_media_manifest
        from genesis.video.timeline_builder import estimate_scene_durations

        sp = storyboard.get("shot_plan", {})
        scenes = sp.get("scenes", []) if isinstance(sp, dict) else []
        mm = load_media_manifest(run_dir)
        trims = []
        td_path = run_dir / "trim_decisions.json"
        if td_path.is_file():
            td = _load_json(td_path)
            from genesis.video.trim_models import ClipTrim
            for row in td.get("trim_decisions") or []:
                trims.append(ClipTrim(**{k: v for k, v in row.items() if k in ClipTrim.__dataclass_fields__}))
        elif mm:
            durs = estimate_scene_durations(scenes)
            trims = suggest_trims_for_manifest(mm, scenes, durs)
            write_trim_decisions(run_dir, trims, job_id)
        if trims:
            refinement = refine_video_timeline(timeline, trims=trims)
            write_timeline_refinement(run_dir, refinement)
            trim_notes = [f"{len(trims)} clip trim(s) applied"]
            timeline.warnings = list(dict.fromkeys(timeline.warnings + refinement.warnings))
    except Exception as exc:  # noqa: BLE001
        trim_notes = [f"trim step skipped: {exc}"]

    (run_dir / "timeline.json").write_text(timeline.to_json(), encoding="utf-8")

    audio_notes: list[str] = []
    if audio_mix_enabled and narr:
        try:
            from genesis.audio.audio_models import AudioMixSettings
            from genesis.audio.audio_mixer import run_audio_mix_for_job
            from genesis.audio.audio_manifest import build_audio_manifest, write_audio_manifest
            from genesis.audio.audio_inspector import inspect_audio_file

            settings = AudioMixSettings(
                narration_volume=narration_volume,
                music_volume=music_volume,
                duck_music_under_voice=duck_music,
            )
            mix_result = run_audio_mix_for_job(
                job_id,
                narration_rel=narr,
                run_dir=run_dir,
                repo_root=_REPO_ROOT,
                music_path=music_path,
                settings=settings,
                allow_global_music=bool(music_path),
                target_duration=timeline.duration or 0.0,
            )
            narr_p = _REPO_ROOT / narr if narr and not Path(narr).is_absolute() else Path(narr or "")
            narr_asset = inspect_audio_file(narr_p) if narr_p.is_file() else None
            write_audio_manifest(run_dir, build_audio_manifest(job_id, narration=narr_asset, mix_result=mix_result))
            if mix_result.output_path and mix_result.status in ("complete", "partial"):
                narr = mix_result.output_path
                if timeline.audio_tracks:
                    timeline.audio_tracks[0].source_path = narr
                audio_notes = [
                    f"Audio mix: {mix_result.status}",
                    f"Narration volume: {narration_volume}",
                    f"Music: {'yes' if any(p.track_type == 'music' for p in mix_result.track_plans) else 'no'}",
                    f"Ducking: {'on' if duck_music else 'off'}",
                    "Output: mixed_audio.mp3",
                ]
            else:
                audio_notes = ["Audio mix failed; using narration only", *mix_result.warnings[:3]]
        except Exception as exc:  # noqa: BLE001
            audio_notes = [f"audio mix skipped: {exc}"]

    caption_data = caption_timing_to_dict(timeline.captions, job_id)
    content_format = brief.get("content_format", "") or storyboard.get("content_format", "")
    disclosure_note = _fundraiser_disclosure_note(metadata)

    transition_notes: list[str] = []
    transition_plan = None
    try:
        from genesis.video.pacing_engine import (
            adjust_scene_pacing,
            build_transition_plan,
            write_beat_timing,
            write_transition_plan,
        )
        from genesis.video.transition_presets import resolve_transition_preset

        beat_music_path = music_path or ""
        if not beat_music_path:
            amp = _load_json(run_dir / "audio_mix_plan.json")
            for tp in amp.get("track_plans") or []:
                if tp.get("track_type") == "music" and tp.get("source_path"):
                    beat_music_path = tp["source_path"]
                    break

        resolved = resolve_transition_preset(
            transition_preset, brand_preset=brand_preset, content_format=content_format,
        )
        transition_plan = build_transition_plan(
            timeline,
            preset_name=transition_preset,
            brand_preset=brand_preset,
            content_format=content_format,
            beat_sync_enabled=beat_sync_enabled,
            music_audio_path=beat_music_path if beat_sync_enabled else "",
            repo_root=_REPO_ROOT,
            transition_duration=transition_duration,
        )
        pacing_warnings = adjust_scene_pacing(timeline, transition_plan.pacing_decisions)
        transition_plan.warnings = list(dict.fromkeys(transition_plan.warnings + pacing_warnings))
        write_transition_plan(run_dir, transition_plan)
        if transition_plan.beat_timing:
            write_beat_timing(run_dir, transition_plan.beat_timing)
        (run_dir / "timeline.json").write_text(timeline.to_json(), encoding="utf-8")
        transition_notes = [
            f"Transition preset: {resolved.name} ({resolved.default_transition_type})",
            f"Beat sync: {'on' if beat_sync_enabled else 'off'}",
            f"Motion effects: {'on' if motion_effects_enabled else 'off'}",
            f"Transitions between scenes: {len(transition_plan.transitions)}",
        ]
        if transition_plan.beat_timing:
            transition_notes.append(
                f"Beat timing: {transition_plan.beat_timing.status} "
                f"(BPM ~{transition_plan.beat_timing.estimated_bpm:.0f}, "
                f"confidence {transition_plan.beat_timing.confidence:.2f})"
            )
        transition_notes.extend(transition_plan.warnings[:3])
    except Exception as exc:  # noqa: BLE001
        transition_notes = [f"transition plan skipped: {exc}"]

    render_result = render_video_timeline(
        timeline,
        run_dir,
        repo_root=_REPO_ROOT,
        render_enabled=render_enabled,
        caption_data=caption_data,
        brand_preset=brand_preset,
        captions_enabled=captions_enabled,
        title_card_enabled=title_card_enabled,
        end_card_enabled=end_card_enabled,
        scene_cards_enabled=scene_cards_enabled,
        primary_hook=storyboard.get("primary_hook", ""),
        disclosure_note=disclosure_note,
        content_format=content_format,
        trim_notes=trim_notes,
        audio_notes=audio_notes,
        transition_preset=transition_preset,
        beat_sync_enabled=beat_sync_enabled,
        motion_effects_enabled=motion_effects_enabled,
        transition_duration=transition_duration,
        transition_plan=transition_plan,
        transition_notes=transition_notes,
    )

    source_files = {
        "brief": "brief.json" if (run_dir / "brief.json").exists() else "",
        "script_package": "script_package.json" if (run_dir / "script_package.json").exists() else "",
        "storyboard": "storyboard.json",
        "overlay_captions": "overlay_captions.json" if (run_dir / "overlay_captions.json").exists() else "",
        "metadata_pack": "metadata_pack.json" if (run_dir / "metadata_pack.json").exists() else "",
    }
    manifest = build_export_manifest(
        job_id=job_id,
        run_dir=run_dir,
        render_result=render_result,
        source_files=source_files,
        narration_path=narr,
        target_platform=target_platform,
        timeline_status=timeline.status,
        brand_preset=brand_preset,
    )
    manifest["warnings"] = list(dict.fromkeys(manifest["warnings"] + validate_export_manifest(manifest)))
    write_export_manifest(run_dir, manifest)

    notes_path = run_dir / "render_notes.md"
    if not notes_path.exists():
        notes_path.write_text(
            f"# Render Notes — {job_id}\n\nStatus: {render_result.status}\n",
            encoding="utf-8",
        )

    logger.info(
        "render_run_video job=%s status=%s renderer=%s preset=%s",
        job_id, render_result.status, render_result.renderer, brand_preset,
    )
    return render_result
