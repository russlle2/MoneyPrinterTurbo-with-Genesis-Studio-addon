"""Genesis Studio UI — helper wrapper functions.

All wrappers catch exceptions and return UIActionResult rather than raising.
No secrets/private config values are exposed in returned data.
"""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from genesis.ui.ui_models import UIActionResult, UICreateRequest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"
_EXPORTS_BASE = _REPO_ROOT / "exports"

_FORBIDDEN = re.compile(
    r"(sk-[a-zA-Z0-9]{12,}|api[_-]?key\s*[:=]\s*\S+|voice[_-]?id\s*[:=]\s*['\"]?\S{8,}|"
    r"local_model_path\s*[:=]\s*\S+)",
    re.I,
)


def _scrub(text: str) -> str:
    return _FORBIDDEN.sub("[REDACTED]", str(text or ""))


def _safe_str(v: Any) -> str:
    return _scrub(str(v or ""))


def _parse_duration_seconds(duration: str | int | float) -> float:
    if isinstance(duration, (int, float)):
        return float(duration)
    m = re.search(r"\d+(?:\.\d+)?", str(duration or ""))
    return float(m.group(0)) if m else 30.0


def build_video_plan(
    idea: str,
    *,
    platform: str = "tiktok",
    brand: str = "clean_creator",
    duration: str = "30 seconds",
    template: str = "product_demo",
    audience: str = "",
    cta: str = "",
    tone: str = "",
    job_id: str = "",
    use_local_llm: bool = False,
    runs_base: Path | None = None,
) -> dict[str, Any]:
    """
    Build (and persist) the advanced video-prompt plan + a script preview.

    Pure local work — no paid API calls. Returns:
        {"job_id", "plan", "script_preview", "warnings", "error"}
    """
    try:
        from genesis.forge.creator_bridge import plan_forge_video, write_forge_plan
        from genesis.creator.project_templates import get_template_or_default

        base = runs_base or _RUNS_BASE
        jid = (job_id or "").strip() or generate_job_id(idea)
        brand_preset = brand if brand != "auto" else "clean_creator"

        tmpl = get_template_or_default(template)
        content_format = tmpl.content_format

        plan = plan_forge_video(
            idea,
            target_platform=platform,
            brand_preset=brand_preset,
            duration_seconds=_parse_duration_seconds(duration),
        )

        run_dir = base / jid
        write_forge_plan(run_dir, plan)

        # Script preview (deterministic template or local LLM if available) — free.
        script_preview = ""
        warnings: list[str] = []
        try:
            from genesis.creative.script_engine import generate_script_package
            pkg = generate_script_package(
                idea, job_id=jid, audience=audience, tone=tone or "engaging",
                cta=cta, content_format=content_format,
                llm_config={"enabled": True} if use_local_llm else None,
            )
            script_preview = (pkg.primary_script.full_text or pkg.primary_script.title or "")[:1200]
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"script preview unavailable: {exc}")

        return {
            "job_id": jid,
            "plan": plan,
            "script_preview": _scrub(script_preview),
            "warnings": [_scrub(w) for w in warnings],
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {"job_id": job_id, "plan": None, "script_preview": "",
                "warnings": [], "error": _scrub(str(exc))}


def save_video_plan(
    job_id: str,
    plan: dict[str, Any],
    *,
    runs_base: Path | None = None,
) -> bool:
    """Persist a (possibly user-edited) forge plan to the run folder."""
    try:
        from genesis.forge.creator_bridge import write_forge_plan
        base = runs_base or _RUNS_BASE
        write_forge_plan(base / job_id, plan)
        return True
    except Exception:  # noqa: BLE001
        return False


def generate_job_id(idea: str = "") -> str:
    """Generate a short unique job ID from idea slug + UUID fragment."""
    slug = re.sub(r"[^\w]+", "_", (idea or "run").strip().lower())[:20].strip("_")
    uid = uuid.uuid4().hex[:6]
    return f"{slug}_{uid}" if slug else f"run_{uid}"


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", Path(name).name)[:120]


def copy_uploaded_file(
    src_path: Path | str,
    dest_dir: Path,
    *,
    filename: str = "",
) -> Path | None:
    src = Path(src_path)
    if not src.is_file():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = sanitize_filename(filename or src.name)
    dest = dest_dir / name
    try:
        shutil.copy2(src, dest)
        return dest
    except Exception:  # noqa: BLE001
        return None


def prepare_run_uploads(
    job_id: str,
    *,
    media_files: list[str] | None = None,
    music_file: str | None = None,
    thumbnail_file: str | None = None,
    manual_visuals: list[str] | None = None,
    runs_base: Path | None = None,
) -> dict[str, list[str]]:
    """Copy uploaded files into the correct run subfolders. Returns dict of copied paths."""
    base = runs_base or _RUNS_BASE
    run_dir = base / job_id
    copied: dict[str, list[str]] = {
        "media": [], "music": [], "thumbnail": [], "manual_visuals": [],
    }

    for fp in (media_files or []):
        dest = copy_uploaded_file(fp, run_dir / "media")
        if dest:
            copied["media"].append(str(dest))

    if music_file:
        dest = copy_uploaded_file(music_file, run_dir / "music")
        if dest:
            copied["music"].append(str(dest))

    if thumbnail_file:
        src = Path(thumbnail_file)
        if src.is_file():
            dest = run_dir / f"thumbnail{src.suffix.lower()}"
            run_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dest)
                copied["thumbnail"].append(str(dest))
            except Exception:  # noqa: BLE001
                pass

    for fp in (manual_visuals or []):
        dest = copy_uploaded_file(fp, run_dir / "manual_visual_imports")
        if dest:
            copied["manual_visuals"].append(str(dest))

    return copied


def create_video(req: UICreateRequest, *, runs_base: Path | None = None) -> UIActionResult:
    """Run the full creator pipeline from a UICreateRequest."""
    try:
        from genesis.creator.creator_models import CreatorRunRequest
        from genesis.creator.pipeline_runner import run_creator_pipeline

        base = runs_base or _RUNS_BASE
        job_id = req.job_id.strip() or generate_job_id(req.idea)

        cr = CreatorRunRequest(
            idea=req.idea,
            job_id=job_id,
            template=req.template,
            primary_platform=req.platform,
            brand_preset=req.brand if req.brand != "auto" else "clean_creator",
            media_path=req.media_path,
            music_path=req.music_path if req.use_music else "",
            # Voiceover is globally disabled; pass through but it will be skipped.
            narration_enabled=req.narration,
            render_enabled=req.render_enabled,
            export_enabled=req.export,
            audience=req.audience,
            cta=req.cta,
            tone=req.tone,
            options={
                # Forge (real AI video generation) is the default video engine.
                "video_engine": "forge",
                "duration_seconds": _parse_duration_seconds(req.duration),
                "ai_visual_fill": req.ai_visual_fill,
                # "auto" = use ComfyUI if running, else fall back to prompt_card_only gracefully
                # "prompt_card_only" = always just generate prompt markdown cards (no image gen)
                "visual_provider": "auto" if req.ai_visual_fill else "prompt_card_only",
                "import_visuals": req.import_visuals,
                "select_thumbnail": req.select_thumbnail,
                "thumbnail_path": req.thumbnail_path,
                "quality_check": req.quality_check,
                "strict_quality_check": req.strict_quality,
                "transitions_enabled": req.transitions,
                "motion_effects_enabled": req.motion_effects,
                "use_local_llm": req.use_local_llm,
            },
        )

        result = run_creator_pipeline(cr, runs_base=base)
        run_dir = base / result.job_id

        output_paths: dict[str, str] = {}
        if result.draft_video_path and Path(result.draft_video_path).is_file():
            output_paths["draft_video"] = result.draft_video_path
        if result.export_dir and Path(result.export_dir).is_dir():
            output_paths["export_dir"] = result.export_dir
        selected = run_dir / "selected_thumbnail.jpg"
        if selected.is_file():
            output_paths["selected_thumbnail"] = str(selected)

        # Read quality info
        readiness_label = ""
        quality_score = 0
        badge_path = run_dir / "ready_to_post_badge.txt"
        if badge_path.is_file():
            badge = badge_path.read_text(encoding="utf-8").strip()
            readiness_label = badge.split("—")[0].strip()
            try:
                quality_score = int(badge.split("/")[0].split()[-1])
            except Exception:  # noqa: BLE001
                pass

        return UIActionResult(
            success=result.status != "failed",
            job_id=result.job_id,
            status=result.status,
            message=f"Job {result.job_id}: {result.status}",
            warnings=[_scrub(w) for w in result.warnings[:8]],
            output_paths=output_paths,
            readiness_label=readiness_label,
            quality_score=quality_score,
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(
            success=False, error=_scrub(str(exc)),
            message=f"Error: {_scrub(str(exc))}",
        )


def render_video(
    job_id: str,
    *,
    platform: str = "tiktok",
    brand: str = "clean_creator",
    runs_base: Path | None = None,
) -> UIActionResult:
    """Rerender an existing run."""
    try:
        from genesis.video.render_run import render_run_video
        base = runs_base or _RUNS_BASE
        result = render_run_video(
            job_id, target_platform=platform, brand_preset=brand, runs_base=base,
        )
        run_dir = base / job_id
        video = run_dir / "draft_video.mp4"
        return UIActionResult(
            success=result.status not in ("failed",),
            job_id=job_id,
            status=result.status,
            message=f"Render: {result.status}",
            warnings=[_scrub(w) for w in (result.warnings or [])[:5]],
            output_paths={"draft_video": str(video)} if video.is_file() else {},
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def ingest_media(
    job_id: str,
    media_path: str,
    *,
    runs_base: Path | None = None,
) -> UIActionResult:
    try:
        from genesis.media.ingest import ingest_media_for_run
        base = runs_base or _RUNS_BASE
        result = ingest_media_for_run(job_id, media_path, runs_base=base)
        return UIActionResult(
            success=True,
            job_id=job_id,
            message=f"Ingested {result.matched_count if hasattr(result, 'matched_count') else 'media'} clips",
            warnings=[],
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def match_clips(
    job_id: str,
    *,
    runs_base: Path | None = None,
) -> UIActionResult:
    try:
        from genesis.media.media_manifest import run_full_match
        base = runs_base or _RUNS_BASE
        result = run_full_match(job_id, runs_base=base)
        return UIActionResult(
            success=True,
            job_id=job_id,
            message=f"Matched {getattr(result, 'matched', '?')} clips",
            warnings=[],
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def import_visuals(
    job_id: str,
    *,
    runs_base: Path | None = None,
) -> UIActionResult:
    try:
        from genesis.ai_visuals.manual_import import import_generated_visuals_for_run
        base = runs_base or _RUNS_BASE
        result = import_generated_visuals_for_run(job_id, runs_base=base)
        return UIActionResult(
            success=True,
            job_id=job_id,
            message=f"Imported: {getattr(result, 'status', 'done')}",
            warnings=[_scrub(w) for w in getattr(result, "warnings", [])[:5]],
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def run_visual_fill(
    job_id: str,
    *,
    runs_base: Path | None = None,
) -> UIActionResult:
    try:
        from genesis.ai_visuals.visual_fill import run_visual_fill_for_run
        base = runs_base or _RUNS_BASE
        result = run_visual_fill_for_run(job_id, runs_base=base)
        return UIActionResult(
            success=True,
            job_id=job_id,
            message=f"Visual fill: {getattr(result, 'status', 'done')}",
            warnings=[_scrub(w) for w in getattr(result, "warnings", [])[:5]],
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def select_thumbnail(
    job_id: str,
    *,
    runs_base: Path | None = None,
    thumbnail_path: str = "",
) -> UIActionResult:
    try:
        from genesis.thumbnail.thumbnail_selector import run_thumbnail_selection
        from genesis.thumbnail.thumbnail_export import write_thumbnail_selection_json, write_thumbnail_selection_md
        base = runs_base or _RUNS_BASE
        result = run_thumbnail_selection(
            job_id, runs_base=base, manual_path=thumbnail_path or None,
        )
        run_dir = base / job_id
        if run_dir.is_dir():
            write_thumbnail_selection_json(run_dir, result)
            write_thumbnail_selection_md(run_dir, result)
        return UIActionResult(
            success=result.status != "failed",
            job_id=job_id,
            status=result.status,
            message=f"Thumbnail: {result.status}",
            warnings=[_scrub(w) for w in result.warnings[:5]],
            output_paths={"selected_thumbnail": result.selected_thumbnail_path} if result.selected_thumbnail_path else {},
            preview_paths={"thumbnail": result.selected_thumbnail_path} if result.selected_thumbnail_path else {},
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def run_quality_check(
    job_id: str,
    *,
    platform: str = "tiktok",
    strict: bool = False,
    runs_base: Path | None = None,
) -> UIActionResult:
    try:
        from genesis.quality.readiness_scorer import evaluate_run_readiness
        from genesis.quality.quality_report import write_all_ready_to_post_reports
        base = runs_base or _RUNS_BASE
        report = evaluate_run_readiness(
            job_id, runs_base=base, platform=platform, strict_mode=strict,
        )
        write_all_ready_to_post_reports(base / job_id, report)
        blocking = [_scrub(b) for b in report.blocking_issues[:5]]
        return UIActionResult(
            success=True,
            job_id=job_id,
            status=report.readiness_label,
            message=f"{report.readiness_label} — {report.score}/{report.max_score}",
            warnings=blocking,
            readiness_label=report.readiness_label,
            quality_score=report.score,
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def export_package(
    job_id: str,
    *,
    platform: str = "tiktok",
    runs_base: Path | None = None,
    exports_base: Path | None = None,
) -> UIActionResult:
    try:
        from genesis.review.export_builder import build_export_package
        base = runs_base or _RUNS_BASE
        pkg = build_export_package(
            job_id, platform=platform, runs_base=base,
            exports_base=exports_base or _EXPORTS_BASE,
        )
        return UIActionResult(
            success=pkg.status != "failed",
            job_id=job_id,
            status=pkg.status,
            message=f"Exported to {_scrub(pkg.export_dir)}",
            warnings=[_scrub(w) for w in pkg.warnings[:5]],
            output_paths={"export_dir": pkg.export_dir} if pkg.export_dir else {},
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def rebuild_dashboard(*, runs_base: Path | None = None) -> UIActionResult:
    try:
        from genesis.dashboard.dashboard_builder import build_dashboard
        result = build_dashboard(runs_base=runs_base)
        return UIActionResult(
            success=result.status != "failed",
            status=result.status,
            message=f"Dashboard: {result.status} — {len(result.cards)} runs",
            output_paths={"dashboard_html": result.output_path},
        )
    except Exception as exc:  # noqa: BLE001
        return UIActionResult(success=False, error=_scrub(str(exc)), message=_scrub(str(exc)))


def load_run_preview(job_id: str, *, runs_base: Path | None = None) -> dict[str, str]:
    """Return preview data (paths, text snippets) for a run. No secrets."""
    base = runs_base or _RUNS_BASE
    run_dir = base / job_id
    data: dict[str, str] = {}
    if not run_dir.is_dir():
        return data

    video = run_dir / "draft_video.mp4"
    if video.is_file():
        data["draft_video"] = str(video)

    thumb = run_dir / "selected_thumbnail.jpg"
    if not thumb.is_file():
        for n in ("thumbnail.jpg", "thumbnail.png"):
            if (run_dir / n).is_file():
                thumb = run_dir / n
                break
    if thumb.is_file():
        data["thumbnail"] = str(thumb)

    script = run_dir / "script.txt"
    if script.is_file():
        try:
            data["script_preview"] = script.read_text(encoding="utf-8")[:800]
        except Exception:  # noqa: BLE001
            pass

    badge = run_dir / "ready_to_post_badge.txt"
    if badge.is_file():
        try:
            data["quality_badge"] = _scrub(badge.read_text(encoding="utf-8").strip())
        except Exception:  # noqa: BLE001
            pass

    caption_p = run_dir / "caption.txt"
    if not caption_p.is_file():
        caption_p = run_dir / "captions.txt"
    if caption_p.is_file():
        try:
            data["caption"] = caption_p.read_text(encoding="utf-8")[:500]
        except Exception:  # noqa: BLE001
            pass

    import json
    meta = run_dir / "metadata_pack.json"
    if meta.is_file():
        try:
            mdata = json.loads(meta.read_text(encoding="utf-8"))
            plat_data = (mdata.get("metadata_by_platform") or {})
            for _, pd in plat_data.items():
                if pd.get("hashtags"):
                    data["hashtags"] = " ".join(pd["hashtags"][:20])
                    break
        except Exception:  # noqa: BLE001
            pass

    return {k: _scrub(v) for k, v in data.items()}


def list_run_ids(*, runs_base: Path | None = None, limit: int = 30) -> list[str]:
    base = runs_base or _RUNS_BASE
    if not base.is_dir():
        return []
    runs = sorted(
        [d.name for d in base.iterdir() if d.is_dir()],
        reverse=True,
    )
    return runs[:limit]


def get_dashboard_path() -> str:
    return str(_REPO_ROOT / "assets" / "dashboard" / "index.html")


def open_in_browser(path: str) -> bool:
    import webbrowser
    p = Path(path)
    if p.is_file():
        try:
            return webbrowser.open(p.resolve().as_uri())
        except Exception:  # noqa: BLE001
            pass
    return False
