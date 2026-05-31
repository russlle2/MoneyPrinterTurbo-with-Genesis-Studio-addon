"""
Genesis Studio — Thumbnail selection CLI.

Usage:
    python -m genesis.thumbnail.thumbnail_cli select <job_id>
    python -m genesis.thumbnail.thumbnail_cli export <job_id> --platform tiktok
    python -m genesis.thumbnail.thumbnail_cli candidates <job_id>
    python -m genesis.thumbnail.thumbnail_cli latest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from genesis.thumbnail.thumbnail_selector import (  # noqa: E402
    find_thumbnail_candidates,
    run_thumbnail_selection,
)
from genesis.thumbnail.thumbnail_export import (  # noqa: E402
    run_thumbnail_export,
    write_thumbnail_selection_json,
    write_thumbnail_selection_md,
)

_RUNS_BASE = _REPO / "assets" / "runs"


def _print(msg: str) -> None:
    print(msg)


def _header(title: str) -> None:
    bar = "-" * min(len(title) + 4, 72)
    _print(f"\n{bar}\n  {title}\n{bar}")


def cmd_select(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    manual = getattr(args, "thumbnail_path", "") or None
    no_frames = getattr(args, "no_frames", False)

    result = run_thumbnail_selection(
        args.job_id,
        runs_base=runs_base,
        extract_frames=not no_frames,
        manual_path=manual,
    )
    run_dir = runs_base / args.job_id
    if run_dir.is_dir():
        write_thumbnail_selection_json(run_dir, result)
        write_thumbnail_selection_md(run_dir, result)

    _header(f"Thumbnail select — {args.job_id}")
    _print(f"  Status:     {result.status}")
    _print(f"  Candidates: {len(result.candidates)}")
    _print(f"  Selected:   {result.selected_thumbnail_path or 'none'}")
    for w in result.warnings[:5]:
        _print(f"  ! {w}")
    return 0 if result.status != "failed" else 1


def cmd_export(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    plat = getattr(args, "platform", "tiktok") or "tiktok"

    result = run_thumbnail_export(args.job_id, runs_base=runs_base, platform=plat)
    _header(f"Thumbnail export — {args.job_id}")
    _print(f"  Status:  {result.status}")
    _print(f"  Output:  {result.output_path or 'none'}")
    for w in result.warnings[:5]:
        _print(f"  ! {w}")
    return 0 if result.status != "failed" else 1


def cmd_candidates(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    run_dir = runs_base / args.job_id
    candidates = find_thumbnail_candidates(run_dir, extract_frames=False)
    _header(f"Candidates — {args.job_id}")
    if not candidates:
        _print("  No candidates found.")
        return 0
    for c in candidates:
        mark = ">" if c.selected else " "
        _print(f"  {mark} [{c.source_type:<12}] score={c.score:5.1f}  {Path(c.source_path).name}")
    return 0


def cmd_latest(args: argparse.Namespace) -> int:
    from genesis.review.run_index import find_latest_run
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    run = find_latest_run(runs_base=runs_base)
    if not run:
        _print("No runs found.")
        return 1
    # Delegate to cmd_select with the latest job_id
    ns = argparse.Namespace(
        job_id=run.job_id,
        runs_base=str(runs_base) if runs_base else "",
        thumbnail_path="",
        no_frames=False,
    )
    return cmd_select(ns)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="genesis.thumbnail.thumbnail_cli")
    p.add_argument("--runs-base", dest="runs_base", default="")
    p.add_argument("--platform", default="tiktok")
    sub = p.add_subparsers(dest="command")

    sel = sub.add_parser("select", help="Detect and select best thumbnail")
    sel.add_argument("job_id")
    sel.add_argument("--thumbnail-path", dest="thumbnail_path", default="")
    sel.add_argument("--no-frames", action="store_true")

    exp = sub.add_parser("export", help="Export selected thumbnail to package")
    exp.add_argument("job_id")

    cand = sub.add_parser("candidates", help="List thumbnail candidates (no extraction)")
    cand.add_argument("job_id")

    sub.add_parser("latest", help="Select thumbnail for latest run")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    handlers = {
        "select": cmd_select,
        "export": cmd_export,
        "candidates": cmd_candidates,
        "latest": cmd_latest,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
