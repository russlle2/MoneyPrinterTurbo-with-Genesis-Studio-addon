"""
Genesis Studio — Dashboard CLI.

Usage:
    python -m genesis.dashboard.dashboard_cli build
    python -m genesis.dashboard.dashboard_cli open
    python -m genesis.dashboard.dashboard_cli open-path
    python -m genesis.dashboard.dashboard_cli summary
    python -m genesis.dashboard.dashboard_cli thumbnails
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from genesis.dashboard.dashboard_builder import (  # noqa: E402
    build_dashboard,
    build_dashboard_summary,
    read_project_index_safe,
)
from genesis.dashboard.thumbnailer import generate_thumbnail_for_run  # noqa: E402

_DASHBOARD_DIR = _REPO / "assets" / "dashboard"
_RUNS_BASE = _REPO / "assets" / "runs"


def _print(msg: str) -> None:
    print(msg)


def cmd_build(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else None
    dashboard_dir = Path(args.dashboard_dir) if getattr(args, "dashboard_dir", "") else None

    result = build_dashboard(
        runs_base=runs_base,
        index_path=index_path,
        dashboard_dir=dashboard_dir,
        refresh_index=not getattr(args, "no_refresh_index", False),
        generate_thumbs=not getattr(args, "no_thumbnails", False),
    )
    _print(f"Dashboard built: {result.status}")
    _print(f"  HTML:       {result.output_path}")
    _print(f"  Thumbnails: {result.thumbnail_dir}")
    _print(f"  Runs:       {len(result.cards)}")
    if result.warnings:
        _print("  Warnings:")
        for w in result.warnings[:5]:
            _print(f"    ! {w}")
    return 0 if result.status != "failed" else 1


def cmd_open(args: argparse.Namespace) -> int:
    """Build dashboard (if needed) and open in default browser."""
    import webbrowser

    dashboard_dir = Path(args.dashboard_dir) if getattr(args, "dashboard_dir", "") else _DASHBOARD_DIR
    html_path = dashboard_dir / "index.html"

    # Build if missing or stale (older than 10 min or missing)
    needs_build = not html_path.is_file()
    if html_path.is_file():
        import time
        age_sec = time.time() - html_path.stat().st_mtime
        if age_sec > 600:
            needs_build = True

    if needs_build:
        runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
        index_path = Path(args.index_path) if getattr(args, "index_path", "") else None
        build_dashboard(
            runs_base=runs_base,
            index_path=index_path,
            dashboard_dir=dashboard_dir,
        )

    file_url = html_path.resolve().as_uri()
    opened = False
    try:
        opened = webbrowser.open(file_url)
    except Exception:  # noqa: BLE001
        opened = False

    if opened:
        _print(f"Dashboard opened: {file_url}")
    else:
        _print("Could not open browser automatically.")
        _print(f"Manually open: {file_url}")
    return 0


def cmd_open_path(args: argparse.Namespace) -> int:
    dashboard_dir = Path(args.dashboard_dir) if getattr(args, "dashboard_dir", "") else _DASHBOARD_DIR
    html = dashboard_dir / "index.html"
    _print(str(html.resolve()))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else None

    records = read_project_index_safe(
        index_path=index_path,
        runs_base=runs_base,
        refresh=getattr(args, "refresh", False),
    )
    from genesis.dashboard.dashboard_builder import build_run_card

    dashboard_dir = _DASHBOARD_DIR
    thumb_dir = dashboard_dir / "thumbnails"
    cards = []
    for record in records[:50]:
        run_dir = Path(record.run_dir) if record.run_dir else _RUNS_BASE / record.job_id
        if not run_dir.is_dir():
            run_dir = _RUNS_BASE / record.job_id
        if run_dir.is_dir():
            cards.append(build_run_card(
                record, run_dir=run_dir, dashboard_dir=dashboard_dir,
                thumb_dir=thumb_dir, generate_thumbs=False,
            ))

    summary = build_dashboard_summary(cards)
    _print(f"Total runs:          {summary.total_runs}")
    _print(f"Complete:            {summary.complete_runs}")
    _print(f"Partial:             {summary.partial_runs}")
    _print(f"Failed:              {summary.failed_runs}")
    _print(f"Missing video:       {summary.missing_video_runs}")
    _print(f"Ready to export:     {summary.ready_to_export_runs}")
    _print(f"With placeholders:   {summary.runs_with_placeholders}")
    return 0


def _cmd_creator_ui(args: argparse.Namespace) -> int:
    """Launch the Genesis Studio Creator UI."""
    from genesis.ui.launch_ui import launch
    port = getattr(args, "port", 8501) or 8501
    no_browser = getattr(args, "no_browser", False)
    launch(port=port, open_browser=not no_browser)
    return 0


def cmd_thumbnails(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    thumb_dir = _DASHBOARD_DIR / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    if not runs_base.is_dir():
        _print(f"Runs base not found: {runs_base}")
        return 1
    for run_dir in runs_base.iterdir():
        if not run_dir.is_dir():
            continue
        generate_thumbnail_for_run(
            run_dir.name, run_dir=run_dir, thumb_dir=thumb_dir, force=True,
        )
        count += 1
    _print(f"Thumbnails regenerated: {count} run(s) → {thumb_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="genesis.dashboard.dashboard_cli",
        description="Genesis Studio local review dashboard",
    )
    p.add_argument("--runs-base", dest="runs_base", default="")
    p.add_argument("--index-path", dest="index_path", default="")
    p.add_argument("--dashboard-dir", dest="dashboard_dir", default="")

    sub = p.add_subparsers(dest="command")

    b = sub.add_parser("build", help="Build dashboard HTML/JSON/MD")
    b.add_argument("--no-refresh-index", action="store_true")
    b.add_argument("--no-thumbnails", action="store_true")

    sub.add_parser("open", help="Build dashboard and open in default browser")
    sub.add_parser("open-path", help="Print dashboard index.html path")

    cui = sub.add_parser("creator-ui", help="Launch Genesis Studio Creator UI")
    cui.add_argument("--port", type=int, default=8501)
    cui.add_argument("--no-browser", action="store_true")

    s = sub.add_parser("summary", help="Print summary counts")
    s.add_argument("--refresh", action="store_true")

    sub.add_parser("thumbnails", help="Regenerate thumbnails only")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "build": cmd_build,
        "open": cmd_open,
        "open-path": cmd_open_path,
        "summary": cmd_summary,
        "thumbnails": cmd_thumbnails,
        "creator-ui": _cmd_creator_ui,
    }
    if not args.command:
        parser.print_help()
        return 0
    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
