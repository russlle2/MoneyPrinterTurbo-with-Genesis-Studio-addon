"""
Genesis Studio — Media ingestion CLI.

Usage:
    python -m genesis.media.media_cli ingest <job_id> <path1> [<path2> ...]
    python -m genesis.media.media_cli ingest-folder <job_id> <folder>
    python -m genesis.media.media_cli match <job_id>
    python -m genesis.media.media_cli report <job_id>
    python -m genesis.media.media_cli ingest-and-render <job_id> <folder> [--platform tiktok] [--brand bold_viral]
"""

from __future__ import annotations

import argparse
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


# ─── ingest ────────────────────────────────────────────────────────────────────

def cmd_ingest(args: argparse.Namespace) -> int:
    from genesis.media.ingest import ingest_media_for_run
    from genesis.media.media_manifest import run_full_match

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None

    _header(f"Ingesting media for: {args.job_id}")
    result = ingest_media_for_run(
        args.job_id,
        args.paths,
        mode=getattr(args, "mode", "copy") or "copy",
        runs_base=runs_base,
        repo_root=repo_root,
    )
    _print(f"  Status:  {result.status}")
    _print(f"  Stored:  {len(result.stored_assets)} asset(s)")
    for a in result.stored_assets:
        _print(f"    ✓ {a.filename} ({a.media_type}, {a.inferred_role or '—'})")
    for s in result.skipped_files:
        _print(f"    ✗ {s} (skipped)")
    for e in result.errors:
        _print(f"    ! {e}")

    if result.stored_assets and not getattr(args, "no_match", False):
        _print("\n  Auto-matching media to storyboard...")
        kw: dict = {}
        if runs_base:
            kw["runs_base"] = runs_base
        if repo_root:
            kw["repo_root"] = repo_root
        manifest, mp, rp = run_full_match(args.job_id, **kw)
        _print(f"  Manifest: {mp}")
        _print(f"  Report:   {rp}")

    return 0 if result.status in ("complete", "partial") else 1


# ─── ingest-folder ─────────────────────────────────────────────────────────────

def cmd_ingest_folder(args: argparse.Namespace) -> int:
    from genesis.media.ingest import ingest_folder_for_run
    from genesis.media.media_manifest import run_full_match

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None

    _header(f"Ingesting folder for: {args.job_id}")
    _print(f"  Folder: {args.folder}")

    kw: dict = dict(mode=getattr(args, "mode", "copy") or "copy")
    if runs_base:
        kw["runs_base"] = runs_base
    if repo_root:
        kw["repo_root"] = repo_root

    result = ingest_folder_for_run(args.job_id, args.folder, **kw)
    _print(f"  Status:  {result.status}")
    _print(f"  Stored:  {len(result.stored_assets)} asset(s)")
    for a in result.stored_assets:
        _print(f"    ✓ {a.filename} ({a.media_type}, {a.inferred_role or '—'})")
    for e in result.errors[:5]:
        _print(f"    ! {e}")

    if result.stored_assets:
        mkw: dict = {}
        if runs_base:
            mkw["runs_base"] = runs_base
        if repo_root:
            mkw["repo_root"] = repo_root
        manifest, mp, rp = run_full_match(args.job_id, **mkw)
        _print(f"  Manifest: {mp}")
        _print(f"  Report:   {rp}")

    return 0 if result.status in ("complete", "partial") else 1


# ─── match ─────────────────────────────────────────────────────────────────────

def cmd_match(args: argparse.Namespace) -> int:
    from genesis.media.media_manifest import run_full_match

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None

    _header(f"Matching media for: {args.job_id}")
    kw: dict = {}
    if runs_base:
        kw["runs_base"] = runs_base
    if repo_root:
        kw["repo_root"] = repo_root

    manifest, mp, rp = run_full_match(args.job_id, **kw)
    _print(f"  Status:  {manifest.status}")
    _print(f"  Assets:  {len(manifest.assets)}")
    matched = sum(1 for m in manifest.scene_matches if not m.fallback_needed)
    _print(f"  Scenes matched: {matched}/{len(manifest.scene_matches)}")
    _print(f"  Manifest: {mp}")
    _print(f"  Report:   {rp}")
    return 0


# ─── report ───────────────────────────────────────────────────────────────────

def cmd_report(args: argparse.Namespace) -> int:
    from genesis.media.media_manifest import load_media_manifest

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    base = runs_base or (_REPO_ROOT / "assets" / "runs")
    run_dir = base / args.job_id

    _header(f"Media report: {args.job_id}")
    manifest = load_media_manifest(run_dir)
    if not manifest:
        _print("  No media_manifest.json found. Run `match` first.")
        return 1

    rp = run_dir / "clip_match_report.md"
    if rp.is_file():
        _print(rp.read_text(encoding="utf-8"))
    else:
        _print(f"  Status: {manifest.status}")
        for sm in manifest.scene_matches:
            mark = "✓" if not sm.fallback_needed else "✗"
            _print(f"  {mark} {sm.scene_id} — {sm.section_name}")
    return 0


# ─── ingest-and-render ─────────────────────────────────────────────────────────

def cmd_ingest_and_render(args: argparse.Namespace) -> int:
    from genesis.media.ingest import ingest_folder_for_run
    from genesis.media.media_manifest import run_full_match

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", None) else None
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None

    _header(f"Ingest + render: {args.job_id}")

    kw: dict = dict(mode="copy")
    if runs_base:
        kw["runs_base"] = runs_base
    if repo_root:
        kw["repo_root"] = repo_root

    result = ingest_folder_for_run(args.job_id, args.folder, **kw)
    _print(f"  Ingested: {len(result.stored_assets)} asset(s), status={result.status}")

    mkw: dict = {}
    if runs_base:
        mkw["runs_base"] = runs_base
    if repo_root:
        mkw["repo_root"] = repo_root
    manifest, _, rp = run_full_match(args.job_id, **mkw)
    _print(f"  Matched: {sum(1 for m in manifest.scene_matches if not m.fallback_needed)}/{len(manifest.scene_matches)} scenes")

    rkw: dict = dict(
        target_platform=getattr(args, "platform", "tiktok") or "tiktok",
        brand_preset=getattr(args, "brand", "clean_creator") or "clean_creator",
        render_enabled=True,
        captions_enabled=not getattr(args, "no_captions", False),
        title_card_enabled=not getattr(args, "no_title_card", False),
        end_card_enabled=not getattr(args, "no_end_card", False),
    )
    if runs_base:
        rkw["runs_base"] = runs_base

    _print(f"\n  Rendering with brand={rkw['brand_preset']} platform={rkw['target_platform']} ...")
    render_result = render_run_video(args.job_id, **rkw)
    _print(f"  Render status: {render_result.status}")
    if render_result.output_path:
        _print(f"  Output:        {render_result.output_path}")
    for w in render_result.warnings[:3]:
        _print(f"  ! {w}")
    return 0 if render_result.status in ("complete", "partial") else 1


# ─── CLI wiring ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="genesis.media.media_cli",
        description="Genesis Studio media ingestion CLI",
    )
    p.add_argument("--runs-base", dest="runs_base", default="")
    p.add_argument("--repo-root", dest="repo_root", default="")
    sub = p.add_subparsers(dest="command")

    ingest_p = sub.add_parser("ingest", help="Ingest specific media files")
    ingest_p.add_argument("job_id")
    ingest_p.add_argument("paths", nargs="+")
    ingest_p.add_argument("--mode", default="copy", choices=["copy", "link", "reference"])
    ingest_p.add_argument("--no-match", action="store_true", dest="no_match")

    folder_p = sub.add_parser("ingest-folder", help="Ingest all media in a folder")
    folder_p.add_argument("job_id")
    folder_p.add_argument("folder")
    folder_p.add_argument("--mode", default="copy", choices=["copy", "link", "reference"])

    match_p = sub.add_parser("match", help="Match ingested media to storyboard")
    match_p.add_argument("job_id")

    report_p = sub.add_parser("report", help="Print clip match report")
    report_p.add_argument("job_id")

    iar_p = sub.add_parser("ingest-and-render", help="Ingest, match, then render")
    iar_p.add_argument("job_id")
    iar_p.add_argument("folder")
    iar_p.add_argument("--platform", default="tiktok")
    iar_p.add_argument("--brand", default="clean_creator")
    iar_p.add_argument("--no-captions", action="store_true", dest="no_captions")
    iar_p.add_argument("--no-title-card", action="store_true", dest="no_title_card")
    iar_p.add_argument("--no-end-card", action="store_true", dest="no_end_card")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "ingest": cmd_ingest,
        "ingest-folder": cmd_ingest_folder,
        "match": cmd_match,
        "report": cmd_report,
        "ingest-and-render": cmd_ingest_and_render,
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
