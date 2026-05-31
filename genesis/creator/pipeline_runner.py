"""Genesis Studio — Master pipeline runner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.creator.creator_models import (
    CreatorRunRequest,
    CreatorRunResult,
    CreatorRunStep,
    CreatorStatus,
)
from genesis.creator.project_templates import get_template_or_default
from genesis.workflows.social_media import run_social_media_workflow
from genesis.media.ingest import ingest_folder_for_run, ingest_media_for_run
from genesis.media.media_manifest import run_full_match
from genesis.video.timeline_refiner import run_trim_for_job
from genesis.video.render_run import render_run_video
from genesis.review.run_loader import load_review_package
from genesis.review.html_report import write_html_report
from genesis.review.export_builder import build_export_package

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"
_FORBIDDEN = ("api_key", "sk_", "xi-api", "voice_id", "openai_api", "local_model_path")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(name: str, status: str, *, outputs: list[str] | None = None,
          warnings: list[str] | None = None, notes: list[str] | None = None) -> CreatorRunStep:
    return CreatorRunStep(
        step_name=name,
        status=status,
        completed_at=_now(),
        output_paths=outputs or [],
        warnings=warnings or [],
        notes=notes or [],
    )


def _safe_json_dump(data: dict[str, Any]) -> str:
    text = json.dumps(data, indent=2)
    for token in _FORBIDDEN:
        if token in text.lower():
            text = text.replace(token, "[REDACTED]")
    return text


def create_workflow_step(
    req: CreatorRunRequest,
    *,
    runs_base: Path | None = None,
) -> tuple[CreatorRunStep, dict[str, Any]]:
    """Run the social workflow. Returns (step, data dict with job_id/run_dir)."""
    runs_base = runs_base or _RUNS_BASE
    tmpl = get_template_or_default(req.template)

    content_format = req.content_format or tmpl.content_format
    audience = req.audience or tmpl.audience
    content_goal = req.content_goal or tmpl.content_goal
    tone = req.tone or tmpl.tone
    cta = req.cta or tmpl.cta_style

    platforms = list(req.platforms or tmpl.platform_defaults)
    if req.primary_platform and req.primary_platform not in platforms:
        platforms = [req.primary_platform] + platforms

    try:
        result = run_social_media_workflow(
            req.idea,
            job_id=req.job_id or None,
            platforms=platforms,
            audience=audience,
            content_goal=content_goal,
            tone=tone,
            cta=cta,
            content_format=content_format,
            narration_enabled=req.narration_enabled,
            write_package=True,
        )
        job_id = result.job_id
        # The workflow always writes to its own _RUNS_BASE; compute expected run_dir here
        run_dir = runs_base / job_id
        warnings = list(result.errors or [])
        return _step("workflow", CreatorStatus.COMPLETE,
                     outputs=[str(run_dir)], warnings=warnings), {
            "run_dir": str(run_dir),
            "job_id": job_id,
        }
    except Exception as exc:  # noqa: BLE001
        return _step("workflow", CreatorStatus.FAILED, warnings=[str(exc)]), {}


def ingest_media_step(
    job_id: str,
    media_path: str,
    *,
    runs_base: Path | None = None,
    repo_root: Path | None = None,
) -> CreatorRunStep:
    if not media_path:
        return _step("ingest_media", CreatorStatus.SKIPPED, notes=["no --media path provided"])

    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT
    p = Path(media_path)

    try:
        if p.is_dir():
            result = ingest_folder_for_run(job_id, p, runs_base=runs_base, repo_root=repo_root)
        elif p.is_file():
            result = ingest_media_for_run(job_id, [p], runs_base=runs_base, repo_root=repo_root)
        else:
            return _step("ingest_media", CreatorStatus.SKIPPED, warnings=[f"media path not found: {media_path}"])

        run_full_match(job_id, runs_base=runs_base, repo_root=repo_root)

        run_dir = runs_base / job_id
        outputs = [str(run_dir / "media_manifest.json"), str(run_dir / "clip_match_report.md")]
        return _step("ingest_media", result.status,
                     outputs=outputs,
                     warnings=result.warnings + result.errors[:3],
                     notes=[f"{len(result.stored_assets)} asset(s) ingested"])
    except Exception as exc:  # noqa: BLE001
        return _step("ingest_media", CreatorStatus.FAILED, warnings=[str(exc)])


def trim_media_step(
    job_id: str,
    *,
    runs_base: Path | None = None,
    repo_root: Path | None = None,
) -> CreatorRunStep:
    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT
    try:
        trims, result = run_trim_for_job(job_id, runs_base=runs_base, repo_root=repo_root)
        if not trims:
            return _step("trim_media", CreatorStatus.SKIPPED, notes=["no trimable media found"])
        run_dir = runs_base / job_id
        outputs = [str(run_dir / "trim_decisions.json")]
        if result:
            outputs.append(str(run_dir / "timeline_refinement.json"))
        return _step("trim_media", CreatorStatus.COMPLETE,
                     outputs=outputs, notes=[f"{len(trims)} trim(s)"])
    except Exception as exc:  # noqa: BLE001
        return _step("trim_media", CreatorStatus.FAILED, warnings=[str(exc)])


def render_video_step(
    req: CreatorRunRequest,
    *,
    runs_base: Path | None = None,
) -> CreatorRunStep:
    runs_base = runs_base or _RUNS_BASE
    try:
        tp = req.options.get("transition_preset", "auto") if req.options else "auto"
        result = render_run_video(
            req.job_id,
            target_platform=req.primary_platform or "tiktok",
            brand_preset=req.brand_preset or "clean_creator",
            render_enabled=req.render_enabled,
            audio_mix_enabled=bool(req.music_path or (runs_base / req.job_id / "music").is_dir()),
            music_path=req.music_path or None,
            runs_base=runs_base,
            transition_preset=str(tp),
            beat_sync_enabled=req.options.get("beat_sync_enabled", True) if req.options else True,
            motion_effects_enabled=req.options.get("motion_effects_enabled", True) if req.options else True,
        )
        run_dir = runs_base / req.job_id
        outputs = [str(run_dir / "draft_video.mp4")] if result.output_path else []
        return _step("render_video", result.status,
                     outputs=outputs, warnings=result.warnings[:5])
    except Exception as exc:  # noqa: BLE001
        return _step("render_video", CreatorStatus.FAILED, warnings=[str(exc)])


def review_step(
    job_id: str,
    *,
    runs_base: Path | None = None,
) -> CreatorRunStep:
    runs_base = runs_base or _RUNS_BASE
    run_dir = runs_base / job_id
    try:
        pkg = load_review_package(job_id, runs_base=runs_base)
        rp = write_html_report(run_dir / "review.html", review_pkg=pkg, run_dir=run_dir)
        return _step("review", CreatorStatus.COMPLETE,
                     outputs=[str(rp)], warnings=pkg.warnings[:3])
    except Exception as exc:  # noqa: BLE001
        return _step("review", CreatorStatus.FAILED, warnings=[str(exc)])


def export_step(
    job_id: str,
    platform: str,
    *,
    runs_base: Path | None = None,
    exports_base: Path | None = None,
) -> CreatorRunStep:
    runs_base = runs_base or _RUNS_BASE
    try:
        pkg = build_export_package(job_id, platform=platform,
                                   runs_base=runs_base, exports_base=exports_base)
        return _step("export", pkg.status,
                     outputs=[pkg.export_dir], warnings=pkg.warnings[:3],
                     notes=[f"platform={platform}"])
    except Exception as exc:  # noqa: BLE001
        return _step("export", CreatorStatus.FAILED, warnings=[str(exc)])


def write_creator_run_summary(
    run_dir: Path,
    result: CreatorRunResult,
    req: CreatorRunRequest,
    *,
    quality_info: dict | None = None,
) -> Path:
    doc = {
        "job_id": result.job_id,
        "status": result.status,
        "run_dir": result.run_dir,
        "draft_video_path": result.draft_video_path,
        "export_dir": result.export_dir,
        "review_html_path": result.review_html_path,
        "template": req.template,
        "primary_platform": req.primary_platform,
        "brand_preset": req.brand_preset,
        "steps": [s.to_dict() for s in result.steps],
        "warnings": result.warnings,
        "notes": result.notes,
    }
    if quality_info:
        doc["quality_score"] = quality_info.get("quality_score", 0)
        doc["readiness_label"] = quality_info.get("readiness_label", "")
        doc["quality_report_json"] = quality_info.get("quality_report_json", "")
        doc["quality_report_md"] = quality_info.get("quality_report_md", "")
        doc["quality_badge"] = quality_info.get("quality_badge", "")
    path = run_dir / "creator_run_summary.json"
    path.write_text(_safe_json_dump(doc), encoding="utf-8")
    return path


def run_creator_pipeline(
    req: CreatorRunRequest,
    *,
    runs_base: Path | None = None,
    exports_base: Path | None = None,
    repo_root: Path | None = None,
) -> CreatorRunResult:
    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT
    steps: list[CreatorRunStep] = []
    all_warnings: list[str] = []

    # Step 1: workflow
    wf_step, wf_data = create_workflow_step(req, runs_base=runs_base)
    steps.append(wf_step)
    all_warnings.extend(wf_step.warnings)

    if wf_step.status == CreatorStatus.FAILED:
        return CreatorRunResult(
            job_id=req.job_id, status=CreatorStatus.FAILED, run_dir="",
            draft_video_path="", export_dir="", review_html_path="",
            steps=steps, warnings=all_warnings,
        )

    job_id = wf_data.get("job_id") or req.job_id
    run_dir = Path(wf_data.get("run_dir") or str(runs_base / job_id))

    # Step 2: media ingest + match
    ingest = ingest_media_step(job_id, req.media_path, runs_base=runs_base, repo_root=repo_root)
    steps.append(ingest)
    all_warnings.extend(ingest.warnings)

    # Step 3: trim
    trim = trim_media_step(job_id, runs_base=runs_base, repo_root=repo_root)
    steps.append(trim)
    all_warnings.extend(trim.warnings)

    # Step 3b: optional AI visual fill
    if req.options.get("ai_visual_fill"):
        try:
            from genesis.ai_visuals.visual_fill import run_visual_fill_for_run
            vf = run_visual_fill_for_run(
                job_id,
                runs_base=runs_base,
                repo_root=repo_root,
                provider_mode=str(req.options.get("visual_provider", "prompt_card_only")),
                asset_type=str(req.options.get("visual_asset_type", "")) or None,
                brand_preset=req.brand_preset,
                content_format=req.content_format,
                platform=req.primary_platform,
            )
            vf_step = CreatorRunStep(
                step_name="ai_visual_fill",
                status=vf.status,
                completed_at=_now(),
                output_paths=[vf.manifest_path] if vf.manifest_path else [],
                warnings=vf.warnings[:5],
                notes=[f"missing={len(vf.missing_scenes)}", f"assets={len(vf.generated_assets)}"],
            )
            steps.append(vf_step)
            all_warnings.extend(vf.warnings)
        except Exception as exc:  # noqa: BLE001
            steps.append(_step("ai_visual_fill", CreatorStatus.PARTIAL, warnings=[str(exc)]))
            all_warnings.append(f"ai visual fill: {exc}")

    if req.options.get("import_visuals") or req.options.get("manual_visuals_path"):
        try:
            from genesis.ai_visuals.manual_import import import_generated_visuals_for_run

            ext = [req.options["manual_visuals_path"]] if req.options.get("manual_visuals_path") else None
            imp = import_generated_visuals_for_run(
                job_id,
                runs_base=runs_base,
                repo_root=repo_root,
                external_paths=ext,
            )
            steps.append(CreatorRunStep(
                step_name="manual_visual_import",
                status=imp.get("status", CreatorStatus.PARTIAL),
                completed_at=_now(),
                warnings=imp.get("warnings", [])[:5],
                notes=[f"imported={imp.get('import_count', 0)}"],
            ))
            all_warnings.extend(imp.get("warnings", [])[:3])
        except Exception as exc:  # noqa: BLE001
            steps.append(_step("manual_visual_import", CreatorStatus.PARTIAL, warnings=[str(exc)]))
            all_warnings.append(f"manual visual import: {exc}")

    # Step 4: render
    # Update job_id in req to ensure it matches the actual run
    req.job_id = job_id
    render = render_video_step(req, runs_base=runs_base)
    steps.append(render)
    all_warnings.extend(render.warnings)

    # Step 5: review HTML
    rev = review_step(job_id, runs_base=runs_base)
    steps.append(rev)

    # Step 6: export
    export_dir = ""
    if req.export_enabled:
        exp = export_step(job_id, req.primary_platform or "tiktok",
                          runs_base=runs_base, exports_base=exports_base)
        steps.append(exp)
        all_warnings.extend(exp.warnings)
        if exp.output_paths:
            export_dir = exp.output_paths[0]

    # Derive overall status
    essential = [wf_step, render]
    has_failure = any(s.status == CreatorStatus.FAILED for s in essential)
    has_partial = any(s.status in (CreatorStatus.PARTIAL, CreatorStatus.FAILED) for s in steps)
    if has_failure:
        status = CreatorStatus.FAILED
    elif has_partial:
        status = CreatorStatus.PARTIAL
    else:
        status = CreatorStatus.COMPLETE

    video_path = str(run_dir / "draft_video.mp4") if (run_dir / "draft_video.mp4").is_file() else ""
    review_html = str(run_dir / "review.html") if (run_dir / "review.html").is_file() else ""

    result = CreatorRunResult(
        job_id=job_id,
        status=status,
        run_dir=str(run_dir),
        draft_video_path=video_path,
        export_dir=export_dir,
        review_html_path=review_html,
        steps=steps,
        warnings=list(dict.fromkeys(all_warnings)),
        notes=[f"template={req.template}", f"brand={req.brand_preset}"],
    )

    # ─── Thumbnail selection step ─────────────────────────────────────────────
    if req.options.get("select_thumbnail") or req.options.get("thumbnail_path"):
        try:
            from genesis.thumbnail.thumbnail_selector import run_thumbnail_selection
            from genesis.thumbnail.thumbnail_export import (
                write_thumbnail_selection_json,
                write_thumbnail_selection_md,
            )

            manual_path = req.options.get("thumbnail_path") or None
            thumb_result = run_thumbnail_selection(
                job_id,
                runs_base=runs_base,
                extract_frames=True,
                manual_path=manual_path,
            )
            write_thumbnail_selection_json(run_dir, thumb_result)
            write_thumbnail_selection_md(run_dir, thumb_result)
            steps.append(CreatorRunStep(
                step_name="thumbnail_selection",
                status=thumb_result.status,
                completed_at=_now(),
                output_paths=[thumb_result.selected_thumbnail_path] if thumb_result.selected_thumbnail_path else [],
                warnings=thumb_result.warnings[:3],
                notes=thumb_result.notes,
            ))
            if thumb_result.warnings:
                all_warnings.extend(thumb_result.warnings[:2])
            if req.export_enabled and thumb_result.selected_thumbnail_path:
                from genesis.thumbnail.thumbnail_export import copy_thumbnail_to_export_package
                if export_dir and Path(export_dir).is_dir():
                    copy_thumbnail_to_export_package(
                        Path(thumb_result.selected_thumbnail_path), Path(export_dir),
                    )
        except Exception as exc:  # noqa: BLE001
            steps.append(_step("thumbnail_selection", CreatorStatus.PARTIAL, warnings=[str(exc)]))
            all_warnings.append(f"thumbnail selection: {exc}")

    quality_info: dict | None = None
    if req.options.get("quality_check") or req.options.get("strict_quality_check"):
        try:
            from genesis.quality.readiness_scorer import evaluate_run_readiness
            from genesis.quality.quality_models import ReadinessLabel

            strict = bool(req.options.get("strict_quality_check"))
            qr = evaluate_run_readiness(
                job_id,
                runs_base=runs_base,
                platform=req.primary_platform or "tiktok",
                strict_mode=strict,
                require_export_package=req.export_enabled,
            )
            quality_info = {
                "quality_score": qr.score,
                "readiness_label": qr.readiness_label,
                "quality_report_json": str(run_dir / "ready_to_post_report.json"),
                "quality_report_md": str(run_dir / "ready_to_post_report.md"),
                "quality_badge": str(run_dir / "ready_to_post_badge.txt"),
            }
            steps.append(CreatorRunStep(
                step_name="quality_gate",
                status=qr.readiness_label,
                completed_at=_now(),
                output_paths=[
                    quality_info["quality_report_json"],
                    quality_info["quality_report_md"],
                ],
                warnings=qr.blocking_issues[:3],
                notes=[f"score={qr.score}"],
            ))
            all_warnings.extend(qr.blocking_issues[:2])
            if strict and qr.readiness_label == ReadinessLabel.NOT_READY:
                result.status = CreatorStatus.PARTIAL
                status = CreatorStatus.PARTIAL
        except Exception as exc:  # noqa: BLE001
            steps.append(_step("quality_gate", CreatorStatus.PARTIAL, warnings=[str(exc)]))
            all_warnings.append(f"quality gate: {exc}")

    write_creator_run_summary(run_dir, result, req, quality_info=quality_info)
    return result
