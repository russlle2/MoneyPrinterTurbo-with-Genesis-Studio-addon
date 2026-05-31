"""
Genesis Studio — Local review/export CLI.

Usage:
    python -m genesis.review.review_cli list
    python -m genesis.review.review_cli latest
    python -m genesis.review.review_cli show <job_id>
    python -m genesis.review.review_cli render <job_id> [--platform tiktok] [--brand bold_viral]
                                                         [--no-captions] [--no-title-card]
                                                         [--no-end-card] [--no-scene-cards]
    python -m genesis.review.review_cli export <job_id> [--platform tiktok] [--no-video]
    python -m genesis.review.review_cli open-path <job_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from genesis.video.render_run import render_run_video  # noqa: E402


def _print(msg: str) -> None:
    print(msg)


def _header(title: str) -> None:
    bar = "─" * min(len(title) + 4, 72)
    _print(f"\n{bar}")
    _print(f"  {title}")
    _print(f"{bar}")


# ─── list ────────────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> int:
    from genesis.review.run_index import list_runs
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    runs = list_runs(runs_base=runs_base)
    if not runs:
        _print("No runs found.")
        return 0
    _header(f"{len(runs)} run(s) found")
    for r in runs:
        video_mark = "[MP4]" if r.has_draft_video else "     "
        fmt = r.content_format[:20] if r.content_format else "—"
        idea = r.idea[:55] if r.idea else "—"
        ts = r.created_at[:10] if r.created_at else "?"
        _print(f"  {video_mark} {r.job_id:<40} {ts}  {fmt:<22} {idea}")
    return 0


# ─── latest ──────────────────────────────────────────────────────────────────

def cmd_latest(args: argparse.Namespace) -> int:
    from genesis.review.run_index import find_latest_run
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    run = find_latest_run(runs_base=runs_base)
    if not run:
        _print("No runs found.")
        return 1
    _header(f"Latest run: {run.job_id}")
    _print(f"  Idea:    {run.idea}")
    _print(f"  Status:  {run.status}")
    _print(f"  Created: {run.created_at}")
    _print(f"  Video:   {'yes — ' + run.draft_video_path if run.has_draft_video else 'no'}")
    return 0


# ─── show ─────────────────────────────────────────────────────────────────────

def cmd_show(args: argparse.Namespace) -> int:
    from genesis.review.run_loader import load_review_package
    from genesis.review.html_report import write_html_report

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    pkg = load_review_package(args.job_id, runs_base=runs_base)
    rs = pkg.run_summary

    _header(f"Review: {args.job_id}")
    _print(f"  Idea:          {rs.idea}")
    _print(f"  Format:        {rs.content_format}")
    _print(f"  Platforms:     {', '.join(rs.platforms)}")
    _print(f"  Status:        {rs.status}")
    _print(f"  Created:       {rs.created_at}")
    _print(f"  Script:        {'yes' if rs.has_script else 'no'}")
    _print(f"  Narration:     {'yes' if rs.has_narration else 'no'}")
    _print(f"  Metadata:      {'yes' if rs.has_metadata else 'no'}")
    _print(f"  Storyboard:    {'yes' if rs.has_storyboard else 'no'}")
    _print(f"  Timeline:      {'yes' if rs.has_timeline else 'no'}")
    _print(f"  Draft video:   {'yes — ' + rs.draft_video_path if rs.has_draft_video else 'no'}")

    run_dir = Path(rs.run_dir) if rs.run_dir else None
    if run_dir and (run_dir / "ready_to_post_report.json").is_file():
        try:
            q = json.loads((run_dir / "ready_to_post_report.json").read_text(encoding="utf-8"))
            _print(f"  Quality:       {q.get('readiness_label', '?')} ({q.get('score', 0)}/{q.get('max_score', 100)})")
        except Exception:  # noqa: BLE001
            _print("  Quality:       report present (parse error)")

    if rs.warnings:
        _print("\n  Warnings:")
        for w in rs.warnings:
            _print(f"    ! {w}")

    _print("\n── Script Preview ──")
    _print(pkg.script_preview or "  [none]")

    _print("\n── Metadata Preview ──")
    _print(pkg.metadata_preview or "  [none]")

    _print("\n── Storyboard Preview ──")
    _print(pkg.storyboard_preview or "  [none]")

    _print("\n── Assets ──")
    for a in pkg.assets:
        mark = "✓" if a.exists else "✗"
        kb = f"{a.size_bytes // 1024}KB" if a.exists else "—"
        _print(f"  {mark} {a.asset_type:<22} {kb}")

    if run_dir and run_dir.is_dir():
        report_path = run_dir / "review.html"
        write_html_report(
            report_path,
            review_pkg=pkg,
            brand_preset="clean_creator",
            run_dir=run_dir,
        )
        _print(f"\n  HTML report: {report_path}")

    return 0 if pkg.status != "failed" else 1


# ─── render ───────────────────────────────────────────────────────────────────

def cmd_render(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    kw = dict(
        target_platform=getattr(args, "platform", "tiktok") or "tiktok",
        render_enabled=True,
        brand_preset=getattr(args, "brand", "clean_creator") or "clean_creator",
        captions_enabled=not getattr(args, "no_captions", False),
        title_card_enabled=not getattr(args, "no_title_card", False),
        end_card_enabled=not getattr(args, "no_end_card", False),
        scene_cards_enabled=not getattr(args, "no_scene_cards", False),
        transition_preset=getattr(args, "transition_preset", "auto") or "auto",
        beat_sync_enabled=not getattr(args, "no_beat_sync", False),
        motion_effects_enabled=not getattr(args, "no_motion_effects", False),
    )
    if runs_base:
        kw["runs_base"] = runs_base

    _header(f"Rendering: {args.job_id}")
    _print(f"  Platform:  {kw['target_platform']}")
    _print(f"  Brand:     {kw['brand_preset']}")
    _print(f"  Captions:  {'on' if kw['captions_enabled'] else 'off'}")

    result = render_run_video(args.job_id, **kw)

    _print(f"\n  Status:   {result.status}")
    _print(f"  Renderer: {result.renderer}")
    if result.output_path:
        _print(f"  Output:   {result.output_path}")
    if result.warnings:
        for w in result.warnings[:5]:
            _print(f"  ! {w}")
    return 0 if result.status in ("complete", "partial") else 1


# ─── export ───────────────────────────────────────────────────────────────────

def cmd_export(args: argparse.Namespace) -> int:
    from genesis.review.export_builder import build_export_package

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    exports_base = Path(args.exports_base) if getattr(args, "exports_base", None) else None
    platform = getattr(args, "platform", "tiktok") or "tiktok"
    include_video = not getattr(args, "no_video", False)

    kw: dict = dict(platform=platform, include_video=include_video)
    if runs_base:
        kw["runs_base"] = runs_base
    if exports_base:
        kw["exports_base"] = exports_base

    _header(f"Exporting: {args.job_id} → {platform}")
    pkg = build_export_package(args.job_id, **kw)

    _print(f"  Status:  {pkg.status}")
    _print(f"  Folder:  {pkg.export_dir}")
    _print(f"  Files:   {', '.join(pkg.included_files)}")
    if pkg.warnings:
        for w in pkg.warnings:
            _print(f"  ! {w}")
    return 0 if pkg.status != "failed" else 1


# ─── open-path ────────────────────────────────────────────────────────────────

def cmd_open_path(args: argparse.Namespace) -> int:
    from genesis.review.run_index import _RUNS_BASE
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else _RUNS_BASE
    run_dir = runs_base / args.job_id
    if not run_dir.is_dir():
        _print(f"Run not found: {run_dir}")
        return 1
    _print(str(run_dir))
    return 0


# ─── media ────────────────────────────────────────────────────────────────────

def cmd_media(args: argparse.Namespace) -> int:
    from genesis.review.run_index import _RUNS_BASE
    from genesis.media.media_manifest import load_media_manifest

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else _RUNS_BASE
    run_dir = runs_base / args.job_id

    if not run_dir.is_dir():
        _print(f"Run not found: {run_dir}")
        return 1

    _header(f"Media status: {args.job_id}")
    media_dir = run_dir / "media"
    _print(f"  Media folder:    {'exists' if media_dir.is_dir() else 'missing'}")

    if media_dir.is_dir():
        files = [f for f in media_dir.iterdir() if f.is_file()]
        _print(f"  Files in media/: {len(files)}")
        for f in files[:8]:
            _print(f"    • {f.name}")
        if len(files) > 8:
            _print(f"    ... +{len(files) - 8} more")

    manifest = load_media_manifest(run_dir)
    if manifest:
        _print(f"\n  media_manifest.json: present")
        _print(f"  Status: {manifest.status}")
        _print(f"  Assets: {len(manifest.assets)}")
        matched = [m for m in manifest.scene_matches if not m.fallback_needed]
        unmatched = [m for m in manifest.scene_matches if m.fallback_needed]
        _print(f"  Scenes matched:      {len(matched)}")
        _print(f"  Scenes need footage: {len(unmatched)}")
        for m in unmatched:
            _print(f"    ✗ {m.scene_id} — {m.section_name}")
    else:
        _print("\n  media_manifest.json: not found (run `media_cli match` to generate)")

    return 0


# ─── CLI wiring ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="genesis.review.review_cli",
        description="Genesis Studio local review/export CLI",
    )
    p.add_argument("--runs-base", dest="runs_base", default="", help="Override runs base directory")
    p.add_argument("--exports-base", dest="exports_base", default="", help="Override exports base directory")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("list", help="List all runs")
    sub.add_parser("latest", help="Show the most recent run")

    show_p = sub.add_parser("show", help="Show details for a run")
    show_p.add_argument("job_id")

    render_p = sub.add_parser("render", help="Render a run to draft_video.mp4")
    render_p.add_argument("job_id")
    render_p.add_argument("--platform", default="tiktok")
    render_p.add_argument("--brand", default="clean_creator")
    render_p.add_argument("--no-captions", action="store_true", dest="no_captions")
    render_p.add_argument("--no-title-card", action="store_true", dest="no_title_card")
    render_p.add_argument("--no-end-card", action="store_true", dest="no_end_card")
    render_p.add_argument("--no-scene-cards", action="store_true", dest="no_scene_cards")
    render_p.add_argument("--transition-preset", dest="transition_preset", default="auto")
    render_p.add_argument("--no-beat-sync", action="store_true")
    render_p.add_argument("--no-motion-effects", action="store_true")

    export_p = sub.add_parser("export", help="Build a platform export package")
    export_p.add_argument("job_id")
    export_p.add_argument("--platform", default="tiktok")
    export_p.add_argument("--no-video", action="store_true", dest="no_video")

    open_p = sub.add_parser("open-path", help="Print the run folder path")
    open_p.add_argument("job_id")

    media_p = sub.add_parser("media", help="Show media ingestion status for a run")
    media_p.add_argument("job_id")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "list": cmd_list,
        "latest": cmd_latest,
        "show": cmd_show,
        "render": cmd_render,
        "export": cmd_export,
        "open-path": cmd_open_path,
        "media": cmd_media,
    }
    if not args.command:
        parser.print_help()
        return 0
    handler = commands.get(args.command)
    if not handler:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
