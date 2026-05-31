"""Genesis Studio — Static dashboard builder."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.dashboard.dashboard_models import (
    DashboardBuildResult,
    DashboardRunCard,
    DashboardStatus,
    DashboardSummary,
)
from genesis.dashboard.thumbnailer import (
    build_thumbnail_contact_sheet,
    generate_thumbnail_for_run,
    safe_thumbnail_filename,
)
from genesis.project.project_index import build_project_index, load_project_index
from genesis.project.project_models import ProjectRunRecord

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DASHBOARD_DIR = _REPO_ROOT / "assets" / "dashboard"
_THUMB_DIR = _DASHBOARD_DIR / "thumbnails"
_INDEX_PATH = _REPO_ROOT / "assets" / "project_index.json"
_BATCHES_DIR = _REPO_ROOT / "assets" / "batches"

_FORBIDDEN = re.compile(
    r"(api_key|sk_[a-z0-9]+|xi-api|voice_id|openai_api|local_model_path|"
    r"config\.toml|config\.json)",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _scrub(text: str) -> str:
    return _FORBIDDEN.sub("[REDACTED]", text)


def _scrub_list(items: list[str]) -> list[str]:
    return [_scrub(x) for x in items]


def _rel_link(from_dir: Path, target: Path) -> str:
    """Relative path for local file links."""
    try:
        return Path(os_path_relpath(target.resolve(), from_dir.resolve())).as_posix()
    except Exception:  # noqa: BLE001
        return target.as_posix()


def os_path_relpath(path: Path, start: Path) -> str:
    import os
    return os.path.relpath(str(path), str(start))


def read_project_index_safe(
    *,
    index_path: Path | None = None,
    runs_base: Path | None = None,
    refresh: bool = False,
) -> list[ProjectRunRecord]:
    if refresh or not (index_path or _INDEX_PATH).is_file():
        index = build_project_index(runs_base=runs_base, index_path=index_path or _INDEX_PATH)
        return index.runs
    loaded = load_project_index(index_path=index_path or _INDEX_PATH)
    if loaded:
        return loaded.runs
    index = build_project_index(runs_base=runs_base, index_path=index_path or _INDEX_PATH)
    return index.runs


def read_creator_summary_safe(run_dir: Path) -> dict[str, Any]:
    data = _safe_json(run_dir / "creator_run_summary.json")
    return {k: _scrub(str(v)) if isinstance(v, str) else v for k, v in data.items()}


def read_media_status_safe(run_dir: Path) -> dict[str, Any]:
    data = _safe_json(run_dir / "media_manifest.json")
    if not data:
        return {
            "has_manifest": False,
            "matched": 0,
            "total": 0,
            "placeholders": 0,
        }
    matches = data.get("scene_matches") or []
    total = len(matches)
    placeholders = sum(1 for m in matches if m.get("fallback_needed"))
    matched = total - placeholders
    return {
        "has_manifest": True,
        "matched": matched,
        "total": total,
        "placeholders": placeholders,
    }


def read_export_status_safe(run_dir: Path, record_export_dir: str) -> dict[str, Any]:
    export_dir = record_export_dir
    if not export_dir:
        manifest = _safe_json(run_dir / "export_manifest.json")
        export_dir = manifest.get("export_dir", "")
    has_export = bool(export_dir) and Path(export_dir).is_dir()
    return {"export_dir": export_dir, "has_export": has_export}


def read_quality_status_safe(run_dir: Path) -> dict[str, Any]:
    from genesis.quality.quality_report import load_ready_to_post_report, read_quality_badge

    data = load_ready_to_post_report(run_dir) or {}
    summary = _safe_json(run_dir / "creator_run_summary.json")
    if not data and summary:
        data = {
            "readiness_label": summary.get("readiness_label", ""),
            "score": summary.get("quality_score", 0),
            "max_score": 100,
        }
    badge = read_quality_badge(run_dir)
    label = data.get("readiness_label", "") or summary.get("readiness_label", "")
    score = int(data.get("score", 0) or summary.get("quality_score", 0) or 0)
    if badge and not label:
        parts = badge.split("\u2014", 1) if "\u2014" in badge else badge.split("-", 1)
        if parts:
            label = parts[0].strip()
        if len(parts) > 1 and "/" in parts[1]:
            try:
                score = int(parts[1].split("/")[0].strip())
            except ValueError:
                pass
    return {
        "readiness_label": label,
        "quality_score": score,
        "quality_badge": badge,
        "has_quality_report": (run_dir / "ready_to_post_report.json").is_file(),
    }


def read_ai_visual_status_safe(run_dir: Path) -> dict[str, Any]:
    gvm = _safe_json(run_dir / "generated_visuals_manifest.json")
    validation_warns = 0
    val_path = run_dir / "visual_asset_validation.md"
    if val_path.is_file():
        try:
            m = re.search(r"\*\*Total warnings:\*\*\s*(\d+)", val_path.read_text(encoding="utf-8"))
            if m:
                validation_warns = int(m.group(1))
        except OSError:
            pass
    manual_dir = run_dir / "manual_visual_imports"
    manual_on_disk = len([
        p for p in manual_dir.iterdir()
        if manual_dir.is_dir() and p.is_file()
    ]) if manual_dir.is_dir() else 0
    return {
        "missing_scene_count": int(gvm.get("missing_scene_count", 0)) if gvm else 0,
        "generated_visual_count": int(gvm.get("generated_asset_count", 0)) if gvm else 0,
        "manual_import_count": int(gvm.get("manual_import_count", 0)) if gvm else manual_on_disk,
        "validation_warning_count": validation_warns,
        "has_fill_report": (run_dir / "ai_visual_fill_report.md").is_file(),
        "has_manual_import_dir": manual_dir.is_dir(),
    }


def read_transition_status_safe(run_dir: Path) -> dict[str, str]:
    tp = _safe_json(run_dir / "transition_plan.json")
    bt = _safe_json(run_dir / "beat_timing.json")
    return {
        "transition_preset": tp.get("preset_name", ""),
        "beat_sync_status": bt.get("status", "") if bt else "",
    }


def _suggested_commands(
    card: DashboardRunCard,
) -> list[str]:
    jid = card.job_id
    plat = card.primary_platform or "tiktok"
    brand = card.brand_preset or "clean_creator"
    cmds: list[str] = []

    if card.review_html_path:
        cmds.append(f"python -m genesis.review.review_cli show {jid}")
    if card.draft_video_path:
        tp = card.transition_preset or "auto"
        if brand == "bold_viral" and tp == "auto":
            tp = "product_snap"
        elif brand == "wellness_soft" and tp == "auto":
            tp = "wellness_flow"
        cmds.append(
            f"python -m genesis.creator.creator_cli rerender {jid} "
            f"--platform {plat} --brand {brand} --transition-preset {tp}"
        )
    if card.draft_video_path and not card.has_export:
        cmds.append(
            f"python -m genesis.project.batch_cli batch-export {jid} --platform {plat}"
        )
    if card.placeholder_scene_count > 0:
        cmds.append(f"python -m genesis.media.media_cli ingest-folder {jid} ./clips")
    cmds.append(f"python -m genesis.project.batch_cli index")
    cmds.append(f"python -m genesis.dashboard.dashboard_cli build")
    return cmds


def build_run_card(
    record: ProjectRunRecord,
    *,
    run_dir: Path,
    dashboard_dir: Path,
    thumb_dir: Path,
    generate_thumbs: bool = True,
) -> DashboardRunCard:
    summary = read_creator_summary_safe(run_dir)
    media = read_media_status_safe(run_dir)
    export_info = read_export_status_safe(run_dir, record.export_dir)

    draft = record.draft_video_path
    if not draft and (run_dir / "draft_video.mp4").is_file():
        draft = str(run_dir / "draft_video.mp4")

    review = record.review_html_path
    if not review and (run_dir / "review.html").is_file():
        review = str(run_dir / "review.html")

    # Prefer selected_thumbnail.jpg if it exists in the run folder
    selected_thumb = run_dir / "selected_thumbnail.jpg"
    has_selected_thumbnail = selected_thumb.is_file() and selected_thumb.stat().st_size > 0

    if generate_thumbs:
        thumb_abs = generate_thumbnail_for_run(
            record.job_id, run_dir=run_dir, thumb_dir=thumb_dir,
            preferred_source=selected_thumb if has_selected_thumbnail else None,
        )
    else:
        thumb_abs = thumb_dir / safe_thumbnail_filename(record.job_id)

    thumb_rel = f"thumbnails/{safe_thumbnail_filename(record.job_id)}"
    if thumb_abs.is_file():
        thumb_rel = _rel_link(dashboard_dir, thumb_abs)

    has_audio = (run_dir / "mixed_audio.mp3").is_file()
    trans = read_transition_status_safe(run_dir)
    ai_vis = read_ai_visual_status_safe(run_dir)
    quality = read_quality_status_safe(run_dir)

    warnings = _scrub_list(list(record.warnings))
    if media["placeholders"]:
        warnings.append(f"{media['placeholders']} scene(s) use placeholders")
    if not draft:
        warnings.append("draft_video.mp4 missing")

    card = DashboardRunCard(
        job_id=record.job_id,
        idea=_scrub(record.idea),
        template=record.template or summary.get("template", ""),
        status=record.status or summary.get("status", "partial"),
        primary_platform=record.primary_platform,
        brand_preset=record.brand_preset or summary.get("brand_preset", ""),
        run_dir=_rel_link(dashboard_dir, run_dir) if run_dir.is_dir() else record.run_dir,
        draft_video_path=_rel_link(dashboard_dir, Path(draft)) if draft and Path(draft).is_file() else "",
        thumbnail_path=thumb_rel,
        review_html_path=_rel_link(dashboard_dir, Path(review)) if review and Path(review).is_file() else "",
        export_dir=export_info["export_dir"],
        has_media_manifest=media["has_manifest"],
        matched_scene_count=media["matched"],
        total_scene_count=media["total"],
        placeholder_scene_count=media["placeholders"],
        has_audio_mix=has_audio,
        has_export=export_info["has_export"],
        transition_preset=trans.get("transition_preset", ""),
        beat_sync_status=trans.get("beat_sync_status", ""),
        missing_scene_count=ai_vis.get("missing_scene_count", 0),
        generated_visual_count=ai_vis.get("generated_visual_count", 0),
        manual_import_count=ai_vis.get("manual_import_count", 0),
        validation_warning_count=ai_vis.get("validation_warning_count", 0),
        readiness_label=quality.get("readiness_label", ""),
        quality_score=quality.get("quality_score", 0),
        quality_badge=quality.get("quality_badge", ""),
        selected_thumbnail_path=_rel_link(dashboard_dir, selected_thumb) if has_selected_thumbnail else "",
        has_selected_thumbnail=has_selected_thumbnail,
        warnings=warnings[:8],
        notes=[],
    )
    card.suggested_commands = _suggested_commands(card)
    plat = card.primary_platform or "tiktok"
    brand = card.brand_preset or "clean_creator"
    if (
        ai_vis.get("missing_scene_count", 0)
        or ai_vis.get("has_fill_report")
        or ai_vis.get("has_manual_import_dir")
        or ai_vis.get("manual_import_count", 0)
    ):
        card.suggested_commands.insert(
            0,
            f"python -m genesis.ai_visuals.visual_cli import-and-render {card.job_id} "
            f"--platform {plat} --brand {brand}",
        )
    card.suggested_commands.insert(
        0,
        f"python -m genesis.quality.quality_cli check {card.job_id} --platform {plat}",
    )
    if not card.has_selected_thumbnail:
        card.suggested_commands.insert(
            0,
            f"python -m genesis.thumbnail.thumbnail_cli select {card.job_id}",
        )
    return card


def _scan_batch_notes() -> list[str]:
    notes: list[str] = []
    if not _BATCHES_DIR.is_dir():
        return notes
    count = 0
    for d in _BATCHES_DIR.iterdir():
        if d.is_dir() and (d / "batch_summary.json").is_file():
            count += 1
    if count:
        notes.append(f"batch_summaries_found={count} under assets/batches/")
    return notes


def build_dashboard_summary(cards: list[DashboardRunCard]) -> DashboardSummary:
    complete = sum(1 for c in cards if c.status == "complete")
    partial = sum(1 for c in cards if c.status == "partial")
    failed = sum(1 for c in cards if c.status == "failed")
    missing_video = sum(1 for c in cards if not c.draft_video_path)
    ready_export = sum(
        1 for c in cards if c.draft_video_path and not c.has_export
    )
    with_ph = sum(1 for c in cards if c.placeholder_scene_count > 0)

    warnings: list[str] = []
    if failed:
        warnings.append(f"{failed} run(s) failed")
    if missing_video:
        warnings.append(f"{missing_video} run(s) missing draft video")

    return DashboardSummary(
        generated_at=_now(),
        total_runs=len(cards),
        complete_runs=complete,
        partial_runs=partial,
        failed_runs=failed,
        missing_video_runs=missing_video,
        ready_to_export_runs=ready_export,
        runs_with_placeholders=with_ph,
        runs=cards,
        warnings=warnings,
        notes=_scan_batch_notes(),
    )


def _e(s: Any) -> str:
    return html.escape(str(s or ""))


def _status_color(status: str) -> str:
    if status == "complete":
        return "#22c55e"
    if status == "failed":
        return "#ef4444"
    return "#f59e0b"


def write_dashboard_html(
    summary: DashboardSummary,
    out_path: Path,
) -> Path:
    cards_html = []
    for card in summary.runs:
        warn_badges = "".join(
            f'<span class="badge warn">{_e(w[:40])}</span>' for w in card.warnings[:3]
        )
        cmds = "<br>".join(_e(c) for c in card.suggested_commands[:4])
        media_line = (
            f"{card.matched_scene_count}/{card.total_scene_count} matched"
            if card.total_scene_count
            else "no manifest"
        )
        trans_line = ""
        if card.transition_preset:
            trans_line = f'<span class="badge">{_e(card.transition_preset)}</span> '
        if card.beat_sync_status:
            trans_line += f'<span class="badge">beats:{_e(card.beat_sync_status)}</span> '
        if card.missing_scene_count:
            trans_line += f'<span class="badge warn">{card.missing_scene_count} missing</span> '
        if card.generated_visual_count:
            trans_line += f'<span class="badge">{card.generated_visual_count} generated</span> '
        if card.readiness_label:
            qcls = "badge ok" if card.readiness_label == "READY_TO_POST" else (
                "badge warn" if card.readiness_label == "NEEDS_REVIEW" else "badge fail"
            )
            trans_line += (
                f'<span class="{qcls}">{_e(card.readiness_label)}'
                f' {card.quality_score}/100</span> '
            )
        ph_line = (
            f'<span class="badge warn">{card.placeholder_scene_count} placeholder(s)</span>'
            if card.placeholder_scene_count
            else ""
        )

        thumb_src = _e(card.thumbnail_path)
        video_link = (
            f'<a href="{_e(card.draft_video_path)}">draft video</a>'
            if card.draft_video_path else "<em>no video</em>"
        )
        review_link = (
            f'<a href="{_e(card.review_html_path)}">review</a>'
            if card.review_html_path else ""
        )
        export_link = (
            f'<a href="{_e(card.export_dir)}">export folder</a>'
            if card.has_export else "<em>not exported</em>"
        )
        thumb_status = (
            f'<span class="badge ok">thumbnail ready</span>'
            if card.has_selected_thumbnail
            else f'<span class="badge warn">no thumbnail</span>'
        )
        selected_thumb_link = (
            f' · <a href="{_e(card.selected_thumbnail_path)}">thumbnail</a>'
            if card.has_selected_thumbnail and card.selected_thumbnail_path
            else ""
        )

        cards_html.append(f"""
<article class="card">
  <img class="thumb" src="{thumb_src}" alt="{_e(card.job_id)}" loading="lazy">
  <div class="body">
    <h3>{_e(card.job_id)}</h3>
    <p class="idea">{_e(card.idea[:120])}</p>
    <div class="meta">
      <span class="badge status" style="background:{_status_color(card.status)}">{_e(card.status)}</span>
      <span class="badge">{_e(card.template or "—")}</span>
      <span class="badge">{_e(card.primary_platform or "—")}</span>
      {ph_line}
      {thumb_status}
    </div>
    <p class="detail">Media: {media_line} · Audio mix: {"yes" if card.has_audio_mix else "no"}</p>
    <p class="detail">Readiness: {trans_line or "—"}</p>
    <p class="links">{video_link} · {review_link} · {export_link}{selected_thumb_link}</p>
    <div class="warns">{warn_badges}</div>
    <details><summary>Suggested commands</summary><pre class="cmds">{cmds}</pre></details>
  </div>
</article>""")

    body = "\n".join(cards_html)
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Genesis Studio Dashboard</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #0f1117; color: #e8e8ed; }}
header {{ margin-bottom: 24px; }}
h1 {{ margin: 0 0 4px; font-size: 1.6rem; letter-spacing: -0.5px; }}
.subtitle {{ margin: 0 0 12px; font-size: 0.85rem; color: #6b7280; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }}
.stat {{ background: #1a1d27; padding: 8px 14px; border-radius: 8px; font-size: 0.9rem; }}
.stat.ready {{ border-left: 3px solid #22c55e; }}
.stat.warn {{ border-left: 3px solid #f59e0b; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}
.card {{ background: #1a1d27; border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }}
.thumb {{ width: 100%; height: 180px; object-fit: cover; background: #252830; }}
.body {{ padding: 12px 14px; flex: 1; }}
.card h3 {{ margin: 0 0 6px; font-size: 1rem; word-break: break-all; }}
.idea {{ margin: 0 0 8px; font-size: 0.85rem; color: #a8a8b8; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }}
.badge {{ font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; background: #2a2d3a; color: #d1d5db; }}
.badge.warn {{ background: #92400e; color: #fde68a; }}
.badge.ok {{ background: #14532d; color: #86efac; }}
.badge.fail {{ background: #7f1d1d; color: #fca5a5; }}
.badge.status {{ font-weight: 600; }}
.detail, .links {{ font-size: 0.8rem; margin: 4px 0; color: #9ca3af; }}
.links a {{ color: #60a5fa; text-decoration: none; }}
.links a:hover {{ text-decoration: underline; }}
.path {{ word-break: break-all; }}
.warns {{ margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }}
pre.cmds {{ font-size: 0.7rem; white-space: pre-wrap; background: #0a0c12; padding: 8px; border-radius: 6px; margin: 0; }}
details summary {{ cursor: pointer; font-size: 0.82rem; color: #94a3b8; padding: 6px 0; }}
details[open] summary {{ color: #e2e8f0; }}
.workflow {{ background: #1a1d27; border-radius: 12px; padding: 20px 24px; margin-top: 32px; }}
.workflow h2 {{ margin: 0 0 16px; font-size: 1.1rem; color: #f1f5f9; }}
.workflow ol {{ margin: 0; padding-left: 20px; }}
.workflow li {{ margin-bottom: 10px; font-size: 0.87rem; color: #cbd5e1; }}
.workflow code {{ background: #0a0c12; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; color: #7dd3fc; }}
footer {{ margin-top: 32px; font-size: 0.78rem; color: #4b5563; border-top: 1px solid #1f2937; padding-top: 16px; }}
</style>
</head>
<body>
<header>
  <h1>Genesis Studio Dashboard</h1>
  <p class="subtitle">Local static interface — generated {_e(summary.generated_at)}</p>
  <div class="stats">
    <span class="stat">Total runs: {summary.total_runs}</span>
    <span class="stat ready">Complete: {summary.complete_runs}</span>
    <span class="stat warn">Partial: {summary.partial_runs}</span>
    <span class="stat">Failed: {summary.failed_runs}</span>
    <span class="stat">Missing video: {summary.missing_video_runs}</span>
    <span class="stat ready">Ready to export: {summary.ready_to_export_runs}</span>
    <span class="stat warn">With placeholders: {summary.runs_with_placeholders}</span>
  </div>
</header>
<main class="grid">
{body}
</main>
<section class="workflow">
  <h2>Daily Workflow</h2>
  <ol>
    <li>Create a video:<br><code>python -m genesis.creator.creator_cli create "your idea" --template affiliate_product --platform tiktok --select-thumbnail --quality-check --export</code></li>
    <li>Check quality:<br><code>python -m genesis.quality.quality_cli strict-check &lt;job_id&gt; --platform tiktok</code></li>
    <li>Select thumbnail:<br><code>python -m genesis.thumbnail.thumbnail_cli select &lt;job_id&gt;</code></li>
    <li>Review the run:<br><code>python -m genesis.review.review_cli show &lt;job_id&gt;</code></li>
    <li>Export for posting:<br><code>python -m genesis.project.batch_cli batch-export &lt;job_id&gt; --platform tiktok</code></li>
    <li>Rebuild &amp; open this dashboard:<br><code>python -m genesis.dashboard.dashboard_cli build &amp;&amp; python -m genesis.dashboard.dashboard_cli open</code></li>
  </ol>
</section>
<footer>
  Genesis Studio — local static dashboard. No external assets, no server, no cloud.
  To open: <code>python -m genesis.dashboard.dashboard_cli open</code>
  &nbsp;|&nbsp; Path: <code>assets/dashboard/index.html</code>
</footer>
</body>
</html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def write_dashboard_json(summary: DashboardSummary, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary.to_dict(), indent=2)
    out_path.write_text(_scrub(text), encoding="utf-8")
    return out_path


def write_dashboard_markdown(summary: DashboardSummary, out_path: Path) -> Path:
    lines = [
        "# Genesis Studio Dashboard",
        "",
        f"Generated: {summary.generated_at}",
        "",
        "## Summary",
        "",
        f"- Total runs: {summary.total_runs}",
        f"- Complete: {summary.complete_runs}",
        f"- Partial: {summary.partial_runs}",
        f"- Failed: {summary.failed_runs}",
        f"- Missing video: {summary.missing_video_runs}",
        f"- Ready to export: {summary.ready_to_export_runs}",
        f"- Runs with placeholders: {summary.runs_with_placeholders}",
        "",
        "## Runs",
        "",
        "| Job ID | Status | Template | Platform | Media | Video | Export |",
        "|--------|--------|----------|----------|-------|-------|--------|",
    ]
    for c in summary.runs:
        media = f"{c.matched_scene_count}/{c.total_scene_count}" if c.total_scene_count else "—"
        vid = "yes" if c.draft_video_path else "no"
        exp = "yes" if c.has_export else "no"
        lines.append(
            f"| {c.job_id} | {c.status} | {c.template or '—'} | {c.primary_platform or '—'} | "
            f"{media} | {vid} | {exp} |"
        )
    if summary.warnings:
        lines.extend(["", "## Warnings", ""])
        for w in summary.warnings:
            lines.append(f"- {w}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def build_dashboard(
    *,
    runs_base: Path | None = None,
    index_path: Path | None = None,
    dashboard_dir: Path | None = None,
    refresh_index: bool = True,
    generate_thumbs: bool = True,
    contact_sheet: bool = True,
) -> DashboardBuildResult:
    dashboard_dir = dashboard_dir or _DASHBOARD_DIR
    thumb_dir = dashboard_dir / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    records = read_project_index_safe(
        index_path=index_path,
        runs_base=runs_base,
        refresh=refresh_index,
    )

    cards: list[DashboardRunCard] = []
    build_warnings: list[str] = []

    for record in records:
        run_dir = Path(record.run_dir) if record.run_dir else (_REPO_ROOT / "assets" / "runs" / record.job_id)
        if not run_dir.is_dir():
            run_dir = _REPO_ROOT / "assets" / "runs" / record.job_id
        try:
            cards.append(build_run_card(
                record,
                run_dir=run_dir,
                dashboard_dir=dashboard_dir,
                thumb_dir=thumb_dir,
                generate_thumbs=generate_thumbs,
            ))
        except Exception as exc:  # noqa: BLE001
            build_warnings.append(f"{record.job_id}: {exc}")

    summary = build_dashboard_summary(cards)
    summary.warnings.extend(build_warnings)

    html_path = dashboard_dir / "index.html"
    json_path = dashboard_dir / "dashboard.json"
    md_path = dashboard_dir / "dashboard.md"

    write_dashboard_html(summary, html_path)
    write_dashboard_json(summary, json_path)
    write_dashboard_markdown(summary, md_path)

    if contact_sheet and cards:
        thumb_paths = [
            thumb_dir / safe_thumbnail_filename(c.job_id)
            for c in cards
            if (thumb_dir / safe_thumbnail_filename(c.job_id)).is_file()
        ]
        build_thumbnail_contact_sheet(
            thumb_paths, dashboard_dir / "contact_sheet.jpg",
        )

    status = DashboardStatus.COMPLETE
    if build_warnings:
        status = DashboardStatus.PARTIAL
    if not cards:
        status = DashboardStatus.PARTIAL

    return DashboardBuildResult(
        output_path=str(html_path),
        thumbnail_dir=str(thumb_dir),
        cards=cards,
        status=status,
        warnings=summary.warnings,
        notes=summary.notes,
    )
