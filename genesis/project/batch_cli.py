"""
Genesis Studio — Batch and project history CLI.

Usage:
    python -m genesis.project.batch_cli index
    python -m genesis.project.batch_cli list [--status complete] [--template affiliate_product]
    python -m genesis.project.batch_cli batch-create batch_jobs.json
    python -m genesis.project.batch_cli batch-rerender job-001 job-002 --platform tiktok
    python -m genesis.project.batch_cli batch-export job-001 --platform tiktok
    python -m genesis.project.batch_cli batch-status <batch_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from genesis.project.batch_runner import (  # noqa: E402
    load_batch_summary,
    parse_batch_items,
    run_batch_create,
    run_batch_export,
    run_batch_rerender,
)
from genesis.project.project_index import (  # noqa: E402
    build_project_index,
    find_runs_by_platform,
    find_runs_by_status,
    find_runs_by_template,
    load_project_index,
    summarize_project_index,
    write_project_index,
)

_RUNS_BASE = _REPO / "assets" / "runs"
_INDEX_PATH = _REPO / "assets" / "project_index.json"


def _print(msg: str) -> None:
    print(msg)


def _header(title: str) -> None:
    bar = "─" * min(len(title) + 4, 72)
    _print(f"\n{bar}")
    _print(f"  {title}")
    _print(f"{bar}")


def cmd_index(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else None
    index = build_project_index(runs_base=runs_base, index_path=index_path)
    path = write_project_index(index, index_path=index_path)
    summary = summarize_project_index(index)
    _header("Project index refreshed")
    _print(f"  Path:        {path}")
    _print(f"  Total runs:  {summary['total_runs']}")
    _print(f"  With video:  {summary['with_video']}")
    _print(f"  Status:      {index.status}")
    if summary.get("by_status"):
        _print("  By status:")
        for k, v in summary["by_status"].items():
            _print(f"    {k}: {v}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else _INDEX_PATH
    index = load_project_index(index_path=index_path)
    if not index:
        runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
        index = build_project_index(runs_base=runs_base, index_path=index_path)

    runs = index.runs
    if getattr(args, "status", ""):
        runs = find_runs_by_status(index, args.status)
    if getattr(args, "template", ""):
        runs = find_runs_by_template(index, args.template)
    if getattr(args, "platform", ""):
        runs = find_runs_by_platform(index, args.platform)

    _header(f"Project runs ({len(runs)})")
    _print(f"  {'JOB ID':<28} {'STATUS':<10} {'TEMPLATE':<20} {'PLATFORM':<12} IDEA")
    _print("  " + "─" * 90)
    for r in runs:
        idea = (r.idea[:35] + "…") if len(r.idea) > 35 else r.idea
        _print(
            f"  {r.job_id:<28} {r.status:<10} {(r.template or '—'):<20} "
            f"{(r.primary_platform or '—'):<12} {idea}"
        )
    return 0


def cmd_batch_create(args: argparse.Namespace) -> int:
    items = parse_batch_items(args.batch_file)
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else None
    batch_id = getattr(args, "batch_id", "") or None

    _header(f"Batch create — {len(items)} item(s)")
    result = run_batch_create(
        items,
        batch_id=batch_id,
        runs_base=runs_base,
        index_path=index_path,
    )
    _print(f"  Batch ID:   {result.batch_id}")
    _print(f"  Status:     {result.status}")
    _print(f"  Complete:   {result.completed}  Partial: {result.partial}  "
           f"Failed: {result.failed}  Skipped: {result.skipped}")
    _print(f"  Output:     {result.output_path}")
    for item in result.items:
        mark = "✓" if item.status == "complete" else ("~" if item.status == "partial" else "✗")
        _print(f"    {mark} {item.job_id:<24} {item.status}")
    return 0 if result.status in ("complete", "partial") else 1


def cmd_batch_rerender(args: argparse.Namespace) -> int:
    job_ids = args.job_ids
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else None

    _header(f"Batch rerender — {len(job_ids)} job(s)")
    result = run_batch_rerender(
        job_ids,
        platform=args.platform or "tiktok",
        brand=args.brand or "clean_creator",
        music_path=getattr(args, "music", "") or "",
        runs_base=runs_base,
        index_path=index_path,
    )
    _print(f"  Batch ID: {result.batch_id}")
    _print(f"  Complete: {result.completed}  Failed: {result.failed}")
    return 0 if result.failed == 0 else 1


def cmd_batch_export(args: argparse.Namespace) -> int:
    job_ids = args.job_ids
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else None

    _header(f"Batch export — {len(job_ids)} job(s)")
    result = run_batch_export(
        job_ids,
        platform=args.platform or "tiktok",
        runs_base=runs_base,
        index_path=index_path,
    )
    _print(f"  Batch ID: {result.batch_id}")
    _print(f"  Complete: {result.completed}  Failed: {result.failed}")
    return 0 if result.failed == 0 else 1


def cmd_dashboard(args: argparse.Namespace) -> int:
    import webbrowser
    from genesis.dashboard.dashboard_builder import build_dashboard

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    index_path = Path(args.index_path) if getattr(args, "index_path", "") else None
    result = build_dashboard(runs_base=runs_base, index_path=index_path)
    _header("Dashboard built")
    _print(f"  Open:  {result.output_path}")
    _print(f"  Runs:  {len(result.cards)}")

    if getattr(args, "open", False):
        html_path = Path(result.output_path)
        if html_path.is_file():
            file_url = html_path.resolve().as_uri()
            opened = False
            try:
                opened = webbrowser.open(file_url)
            except Exception:  # noqa: BLE001
                opened = False
            if opened:
                _print(f"  Browser opened: {file_url}")
            else:
                _print(f"  Could not open browser. Manually open: {file_url}")
        else:
            _print(f"  Dashboard HTML not found at {result.output_path}")
    else:
        _print("  To open in browser: python -m genesis.dashboard.dashboard_cli open")
    return 0


def cmd_batch_status(args: argparse.Namespace) -> int:
    batches_base = Path(args.batches_base) if getattr(args, "batches_base", "") else None
    data = load_batch_summary(args.batch_id, batches_base=batches_base)
    if not data:
        _print(f"Batch not found: {args.batch_id}")
        return 1
    _header(f"Batch: {args.batch_id}")
    _print(f"  Status:    {data.get('status')}")
    _print(f"  Complete:  {data.get('completed')}  Partial: {data.get('partial')}  "
           f"Failed: {data.get('failed')}  Skipped: {data.get('skipped')}")
    _print(f"  Output:    {data.get('output_path')}")
    _print("\n  Items:")
    for item in data.get("items", []):
        mark = "✓" if item.get("status") == "complete" else "✗"
        _print(f"    {mark} {item.get('job_id', '—'):<24} {item.get('status')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="genesis.project.batch_cli",
        description="Genesis Studio batch runs and project history",
    )
    p.add_argument("--runs-base", dest="runs_base", default="")
    p.add_argument("--index-path", dest="index_path", default="")
    p.add_argument("--batches-base", dest="batches_base", default="")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("index", help="Build or refresh project index")

    ls = sub.add_parser("list", help="List indexed runs")
    ls.add_argument("--status", default="")
    ls.add_argument("--template", default="")
    ls.add_argument("--platform", default="")

    bc = sub.add_parser("batch-create", help="Run batch from JSON/CSV file")
    bc.add_argument("batch_file")
    bc.add_argument("--batch-id", dest="batch_id", default="")

    br = sub.add_parser("batch-rerender", help="Rerender multiple jobs")
    br.add_argument("job_ids", nargs="+")
    br.add_argument("--platform", default="tiktok")
    br.add_argument("--brand", default="clean_creator")
    br.add_argument("--music", default="")

    be = sub.add_parser("batch-export", help="Export multiple jobs")
    be.add_argument("job_ids", nargs="+")
    be.add_argument("--platform", default="tiktok")

    bs = sub.add_parser("batch-status", help="Show batch summary")
    bs.add_argument("batch_id")

    db = sub.add_parser("dashboard", help="Build local review dashboard (alias)")
    db.add_argument("--open", action="store_true", help="Open in default browser after building")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "index": cmd_index,
        "list": cmd_list,
        "batch-create": cmd_batch_create,
        "batch-rerender": cmd_batch_rerender,
        "batch-export": cmd_batch_export,
        "batch-status": cmd_batch_status,
        "dashboard": cmd_dashboard,
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
