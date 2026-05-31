"""
Genesis Studio — Draft vertical MP4 renderer (MoviePy when available).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genesis.video.brand_presets import get_brand_preset
from genesis.video.caption_renderer import render_caption_overlay
from genesis.video.card_renderer import (
    render_end_card,
    render_placeholder_card,
    render_scene_card,
    render_title_card,
)
from genesis.video.render_styles import BrandPreset, RenderOptions, write_render_style_artifacts
from genesis.video.timeline_models import RenderResult, TimelineStatus, VideoTimeline

_SCENE_COLORS = [
    (35, 45, 62),
    (48, 58, 78),
    (55, 70, 90),
    (42, 52, 68),
    (60, 75, 95),
]


@dataclass
class RenderContext:
    preset: BrandPreset
    options: RenderOptions
    repo_root: Path
    job_id: str
    timeline: VideoTimeline
    primary_hook: str = ""
    disclosure_note: str = ""
    content_format: str = ""


def renderer_available() -> bool:
    try:
        from moviepy import ColorClip  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _parse_resolution(resolution: str) -> tuple[int, int]:
    parts = resolution.lower().split("x")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return 1080, 1920


def _resolve_path(path_str: str, repo_root: Path) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return repo_root / path_str


def _scene_lookup(timeline: VideoTimeline, scene_id: str) -> dict[str, Any]:
    for s in timeline.scenes:
        if s.get("scene_id") == scene_id:
            return s
    return {}


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root.resolve()))
    except ValueError:
        return path.name


def _ensure_card_png(
    ctx: RenderContext,
    png_path: Path,
    item: Any,
    *,
    scene_index: int,
) -> str:
    size = ctx.options.target_resolution
    preset = ctx.preset
    opts = ctx.options
    cache_dir = ctx.repo_root / "assets" / "runs" / ctx.job_id / "render_cache"

    if item.media_type == "title_card":
        if not opts.title_card_enabled:
            from genesis.video.card_renderer import render_placeholder_card
            return render_placeholder_card(
                png_path,
                scene_id="title",
                section_name="Title",
                visual_goal=item.caption_text or "Draft",
                caption_text="",
                style=preset.scene_card_style,
                size=size,
            )
        return render_title_card(
            png_path,
            ctx.primary_hook or item.caption_text or "Hook",
            preset.title_card_style,
            size,
            subtitle="Draft vertical video",
        )

    if item.media_type == "end_card":
        if not opts.end_card_enabled:
            return render_end_card(png_path, item.caption_text or "Follow", preset.end_card_style, size)
        return render_end_card(
            png_path,
            item.caption_text or "Comment / Follow / Save",
            preset.end_card_style,
            size,
            disclosure_note=ctx.disclosure_note,
        )

    scene = _scene_lookup(ctx.timeline, item.scene_id)
    section = scene.get("section_name", item.scene_id)
    visual_goal = scene.get("visual_goal", "") or item.notes or ""
    narr = scene.get("narration_text", "") or item.caption_text or ""

    use_scene_style = opts.scene_cards_enabled or not item.source_path
    if use_scene_style:
        return render_scene_card(
            png_path,
            section_name=section,
            visual_goal=visual_goal,
            narration_snippet=narr,
            style=preset.scene_card_style,
            size=size,
            content_format=ctx.content_format,
        )

    color = _SCENE_COLORS[scene_index % len(_SCENE_COLORS)]
    return render_placeholder_card(
        png_path,
        scene_id=item.scene_id,
        section_name=section,
        visual_goal=visual_goal,
        caption_text=narr,
        style=preset.scene_card_style,
        size=size,
    )


def _overlay_captions_on_clip(
    base_clip: Any,
    clip_def: Any,
    ctx: RenderContext,
    size: tuple[int, int],
) -> Any:
    if not ctx.options.captions_enabled or not ctx.timeline.captions:
        return base_clip

    import numpy as np
    from moviepy import CompositeVideoClip, ImageClip

    overlays: list[Any] = [base_clip]
    for cue in ctx.timeline.captions:
        if not (clip_def.start_time <= cue.start_time < clip_def.start_time + clip_def.duration):
            continue
        if not (cue.text or "").strip():
            continue
        layer = render_caption_overlay(
            cue.text,
            ctx.preset.caption_style,
            size,
            scene_shot_type=clip_def.visual_role,
        )
        arr = np.array(layer)
        rel_start = max(0.0, cue.start_time - clip_def.start_time)
        rel_dur = min(cue.end_time - cue.start_time, clip_def.duration - rel_start)
        if rel_dur <= 0.05:
            continue
        cap = ImageClip(arr).with_duration(rel_dur).with_start(rel_start)
        overlays.append(cap)

    if len(overlays) == 1:
        return base_clip
    return CompositeVideoClip(overlays, size=size).with_duration(clip_def.duration)


def _clip_for_timeline_item(
    item: Any,
    *,
    ctx: RenderContext,
    scene_index: int,
) -> Any:
    from moviepy import ColorClip, ImageClip, VideoFileClip

    size = ctx.options.target_resolution
    dur = float(item.duration)
    media_type = item.media_type
    repo_root = ctx.repo_root
    job_id = ctx.job_id
    cache_dir = repo_root / "assets" / "runs" / job_id / "render_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if media_type == "title_card" and not ctx.options.title_card_enabled:
        from moviepy import ColorClip
        return ColorClip(size=size, color=(20, 22, 28), duration=dur)

    if media_type == "end_card" and not ctx.options.end_card_enabled:
        from moviepy import ColorClip
        return ColorClip(size=size, color=(20, 28, 26), duration=dur)

    if media_type in ("title_card", "end_card"):
        name = "title_card.png" if media_type == "title_card" else "end_card.png"
        png_path = cache_dir / name
        if not png_path.is_file() or png_path.stat().st_size < 100:
            _ensure_card_png(ctx, png_path, item, scene_index=scene_index)
        clip = ImageClip(str(png_path)).with_duration(dur).resized(size)
        return _overlay_captions_on_clip(clip, item, ctx, size)

    if media_type in ("placeholder",) or not item.source_path:
        if item.source_path:
            png_path = _resolve_path(item.source_path, repo_root)
        else:
            png_path = cache_dir / f"{item.scene_id}.png"
        if not png_path.is_file():
            _ensure_card_png(ctx, png_path, item, scene_index=scene_index)
        clip = ImageClip(str(png_path)).with_duration(dur).resized(size)
        return _overlay_captions_on_clip(clip, item, ctx, size)

    src = _resolve_path(item.source_path, repo_root)
    if not src.is_file():
        png_path = cache_dir / f"{item.scene_id}_missing.png"
        _ensure_card_png(ctx, png_path, item, scene_index=scene_index)
        clip = ImageClip(str(png_path)).with_duration(dur).resized(size)
        return _overlay_captions_on_clip(clip, item, ctx, size)

    if media_type == "video":
        try:
            clip = VideoFileClip(str(src), audio=False)
            src_start = float(getattr(item, "source_start", 0) or 0)
            src_end = float(getattr(item, "source_end", 0) or 0)
            if src_end > src_start > 0:
                use_end = min(src_end, clip.duration or src_end)
                clip = clip.subclipped(src_start, use_end)
            else:
                clip = clip.subclipped(0, min(dur, clip.duration or dur))
            clip = clip.resized(size).with_duration(dur)
            return _overlay_captions_on_clip(clip, item, ctx, size)
        except Exception as exc:  # noqa: BLE001
            png_path = cache_dir / f"{item.scene_id}_trim_fail.png"
            _ensure_card_png(ctx, png_path, item, scene_index=scene_index)
            item.warnings = list(getattr(item, "warnings", [])) + [f"trim failed: {exc}"]
            clip = ImageClip(str(png_path)).with_duration(dur).resized(size)
            return _overlay_captions_on_clip(clip, item, ctx, size)

    if media_type == "image":
        clip = ImageClip(str(src)).with_duration(dur).resized(size)
        return _overlay_captions_on_clip(clip, item, ctx, size)

    return ColorClip(size=size, color=(40, 40, 50), duration=dur)


def _apply_simple_transitions(segments: list[Any], options: RenderOptions) -> list[Any]:
    td = options.transition_duration
    if not options.simple_transitions or td <= 0 or len(segments) < 2:
        return segments
    out: list[Any] = []
    for i, seg in enumerate(segments):
        try:
            if i > 0 and hasattr(seg, "crossfadein"):
                seg = seg.crossfadein(td)
            if i < len(segments) - 1 and hasattr(seg, "crossfadeout"):
                seg = seg.crossfadeout(td)
        except Exception:  # noqa: BLE001
            pass
        out.append(seg)
    return out


def render_with_moviepy_if_available(
    timeline: VideoTimeline,
    output_path: Path,
    *,
    repo_root: Path,
    ctx: RenderContext | None = None,
) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    if not renderer_available():
        return False, ["moviepy not available"]

    if ctx is None:
        opts = RenderOptions()
        ctx = RenderContext(
            preset=get_brand_preset(opts.brand_preset),
            options=opts,
            repo_root=repo_root,
            job_id=timeline.job_id,
            timeline=timeline,
        )

    try:
        from moviepy import AudioFileClip, CompositeVideoClip, concatenate_videoclips
    except ImportError as exc:
        return False, [f"moviepy import failed: {exc}"]

    size = ctx.options.target_resolution
    if timeline.resolution:
        size = _parse_resolution(timeline.resolution)

    scene_idx = 0
    segments = []
    for clip_def in timeline.clips:
        if clip_def.media_type == "title_card" and not ctx.options.title_card_enabled:
            continue
        if clip_def.media_type == "end_card" and not ctx.options.end_card_enabled:
            continue
        try:
            seg = _clip_for_timeline_item(
                clip_def,
                ctx=ctx,
                scene_index=scene_idx if clip_def.visual_role == "scene" else 0,
            )
            seg = seg.with_duration(clip_def.duration)
            segments.append(seg)
            if clip_def.visual_role == "scene":
                scene_idx += 1
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{clip_def.clip_id}: {exc}")
            from moviepy import ColorClip
            segments.append(ColorClip(size=size, color=(50, 50, 50), duration=clip_def.duration))

    if not segments:
        return False, ["no segments to render"]

    segments = _apply_simple_transitions(segments, ctx.options)

    try:
        video = concatenate_videoclips(segments, method="compose")
    except Exception:
        video = CompositeVideoClip(
            [s.with_start(timeline.clips[i].start_time) for i, s in enumerate(segments)],
            size=size,
        ).with_duration(timeline.duration)

    if timeline.audio_tracks:
        track = timeline.audio_tracks[0]
        apath = _resolve_path(track.source_path, repo_root)
        if apath.is_file():
            try:
                audio = AudioFileClip(str(apath))
                use_dur = min(video.duration, audio.duration, track.duration or audio.duration)
                audio = audio.subclipped(0, use_dur)
                video = video.with_audio(audio)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"narration attach failed: {exc}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fps = ctx.options.fps or timeline.fps
    try:
        video.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
    finally:
        try:
            video.close()
        except Exception:  # noqa: BLE001
            pass
        for s in segments:
            try:
                s.close()
            except Exception:  # noqa: BLE001
                pass

    if output_path.is_file() and output_path.stat().st_size > 1000:
        return True, warnings
    return False, warnings + ["output file missing or too small"]


def _build_render_notes(
    timeline: VideoTimeline,
    ctx: RenderContext,
    *,
    status: str,
    renderer: str,
    output_name: str = "",
    reason: str = "",
    trim_notes: list[str] | None = None,
    audio_notes: list[str] | None = None,
) -> str:
    preset = ctx.preset
    opts = ctx.options
    export_notes = [
        "Export at 1080x1920 (9:16) for TikTok/Reels/Shorts.",
        "Use H.264 + AAC in your editor if re-encoding.",
        f"Brand preset: {preset.preset_name}",
    ]
    for note in preset.notes:
        export_notes.append(note)
    if ctx.disclosure_note:
        export_notes.append(ctx.disclosure_note)
    if ctx.content_format == "fundraising_story":
        export_notes.append(
            "Fundraiser reminder: include truthful donation disclosure in post caption; do not imply guaranteed donations."
        )

    lines = [
        f"# Render Notes — {timeline.job_id}",
        "",
        f"**Status:** {status}",
        f"**Renderer:** {renderer}",
    ]
    if output_name:
        lines.append(f"**Output:** {output_name}")
    if reason:
        lines.append(f"**Reason:** {reason}")
    lines.extend([
        "",
        f"**Duration:** {timeline.duration}s",
        f"**Resolution:** {timeline.resolution} @ {opts.fps}fps",
        f"**Brand preset:** {preset.preset_name}",
        "",
        "## Features",
        "",
        f"- Captions: {'on' if opts.captions_enabled else 'off'}",
        f"- Title card: {'on' if opts.title_card_enabled else 'off'}",
        f"- End card: {'on' if opts.end_card_enabled else 'off'}",
        f"- Scene cards: {'on' if opts.scene_cards_enabled else 'off'}",
        "",
        "## Trim",
        "",
    ])
    if trim_notes:
        for n in trim_notes:
            lines.append(f"- {n}")
        lines.append("- See `trim_decisions.json` and `timeline_refinement.json`")
    else:
        lines.append("- No clip trims applied")
    lines.extend(["", "## Audio mix", ""])
    if audio_notes:
        for n in audio_notes:
            lines.append(f"- {n}")
    else:
        lines.append("- No audio mix applied")
    lines.extend([
        "",
        "## Export quality",
        "",
    ])
    for n in export_notes:
        lines.append(f"- {n}")
    lines.extend([
        "",
        "## Artifacts",
        "",
        "- `render_style.json`",
        "- `caption_style.json`",
        "- `timeline.json`",
        "- `caption_timing.json`",
        "- `trim_decisions.json`",
        "- `timeline_refinement.json`",
        "- `audio_manifest.json`",
        "- `audio_mix_plan.json`",
        "- `mixed_audio.mp3`",
        "- `export_manifest.json`",
    ])
    if output_name:
        lines.append(f"- `{output_name}`")
    return "\n".join(lines) + "\n"


def render_placeholder_package(
    run_dir: Path,
    timeline: VideoTimeline,
    *,
    caption_data: dict[str, Any],
    reason: str = "",
    ctx: RenderContext | None = None,
) -> RenderResult:
    if ctx:
        write_render_style_artifacts(run_dir, ctx.preset, ctx.options)
    notes_path = run_dir / "render_notes.md"
    if ctx:
        body = _build_render_notes(
            timeline, ctx, status="partial (no MP4 rendered)", renderer="placeholder", reason=reason
        )
    else:
        body = textwrap.dedent(f"""\
            # Render Notes — {timeline.job_id}

            **Status:** partial (no MP4 rendered)
            **Reason:** {reason or "renderer unavailable or render disabled"}
        """)
    notes_path.write_text(body, encoding="utf-8")
    return RenderResult(
        job_id=timeline.job_id,
        output_path="",
        timeline_path=str(run_dir / "timeline.json"),
        caption_timing_path=str(run_dir / "caption_timing.json"),
        manifest_path=str(run_dir / "export_manifest.json"),
        status=TimelineStatus.PARTIAL,
        renderer="placeholder",
        warnings=timeline.warnings + ([reason] if reason else []),
        notes=["Draft MP4 not created — timeline package ready for manual edit."],
    )


def render_video_timeline(
    timeline: VideoTimeline,
    run_dir: Path,
    *,
    repo_root: Path,
    render_enabled: bool = True,
    caption_data: dict[str, Any] | None = None,
    brand_preset: str = "clean_creator",
    captions_enabled: bool = True,
    title_card_enabled: bool = True,
    end_card_enabled: bool = True,
    scene_cards_enabled: bool = True,
    target_resolution: tuple[int, int] = (1080, 1920),
    fps: int = 30,
    primary_hook: str = "",
    disclosure_note: str = "",
    content_format: str = "",
    trim_notes: list[str] | None = None,
    audio_notes: list[str] | None = None,
) -> RenderResult:
    """Render draft MP4 or write partial package."""
    options = RenderOptions(
        brand_preset=brand_preset,
        captions_enabled=captions_enabled,
        title_card_enabled=title_card_enabled,
        end_card_enabled=end_card_enabled,
        scene_cards_enabled=scene_cards_enabled,
        target_resolution=target_resolution,
        fps=fps,
    )
    preset = get_brand_preset(brand_preset)
    timeline.fps = fps
    timeline.resolution = f"{target_resolution[0]}x{target_resolution[1]}"

    ctx = RenderContext(
        preset=preset,
        options=options,
        repo_root=repo_root,
        job_id=timeline.job_id,
        timeline=timeline,
        primary_hook=primary_hook,
        disclosure_note=disclosure_note,
        content_format=content_format,
    )

    timeline_path = run_dir / "timeline.json"
    caption_path = run_dir / "caption_timing.json"
    manifest_path = run_dir / "export_manifest.json"
    output_path = run_dir / "draft_video.mp4"

    timeline_path.write_text(timeline.to_json(), encoding="utf-8")
    if caption_data:
        import json
        caption_path.write_text(json.dumps(caption_data, indent=2), encoding="utf-8")

    write_render_style_artifacts(run_dir, preset, options)

    if not render_enabled:
        return render_placeholder_package(
            run_dir, timeline, caption_data=caption_data or {}, reason="render_enabled=False", ctx=ctx
        )

    if not renderer_available():
        return render_placeholder_package(
            run_dir, timeline, caption_data=caption_data or {}, reason="moviepy/ffmpeg unavailable", ctx=ctx
        )

    ok, render_warnings = render_with_moviepy_if_available(
        timeline, output_path, repo_root=repo_root, ctx=ctx
    )
    if ok:
        notes_path = run_dir / "render_notes.md"
        notes_path.write_text(
            _build_render_notes(
                timeline, ctx, status="complete", renderer="moviepy",
                output_name="draft_video.mp4", trim_notes=trim_notes, audio_notes=audio_notes,
            ),
            encoding="utf-8",
        )
        return RenderResult(
            job_id=timeline.job_id,
            output_path=_rel_path(output_path, repo_root),
            timeline_path=_rel_path(timeline_path, repo_root),
            caption_timing_path=_rel_path(caption_path, repo_root),
            manifest_path=_rel_path(manifest_path, repo_root),
            status=TimelineStatus.COMPLETE,
            renderer="moviepy",
            warnings=timeline.warnings + render_warnings,
            notes=[f"Draft vertical MP4 rendered with preset {preset.preset_name}."],
        )

    return render_placeholder_package(
        run_dir,
        timeline,
        caption_data=caption_data or {},
        reason="; ".join(render_warnings) or "render failed",
        ctx=ctx,
    )
