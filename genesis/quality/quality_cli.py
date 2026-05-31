"""
Genesis Studio — Quality gate CLI.

Usage:
    python -m genesis.quality.quality_cli check <job_id> --platform tiktok
    python -m genesis.quality.quality_cli strict-check <job_id> --platform tiktok
    python -m genesis.quality.quality_cli batch-check job1 job2 --platform tiktok
    python -m genesis.quality.quality_cli latest --platform tiktok
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from genesis.quality.readiness_scorer import evaluate_run_readiness  # noqa: E402

_RUNS_BASE = _REPO / "assets" / "runs"
_BATCH_DIR = _REPO / "assets" / "batches"


def _print(msg: str) -> None:
    print(msg)


def _header(title: str) -> None:
    bar = "-" * min(len(title) + 4, 72)
    _print(f"\n{bar}\n  {title}\n{bar}")


def _show_report(report) -> None:
    _print(f"  Label:    {report.readiness_label}")
    _print(f"  Score:    {report.score}/{report.max_score}")
    _print(f"  Platform: {report.platform}")
    if report.blocking_issues:
        _print("  Blockers:")
        for b in report.blocking_issues[:5]:
            _print(f"    ! {b}")
    if report.recommended_fixes:
        _print("  Fixes:")
        for f in report.recommended_fixes[:3]:
            _print(f"    -> {f}")


def cmd_check(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    report = evaluate_run_readiness(
        args.job_id,
        runs_base=runs_base,
        platform=getattr(args, "platform", "tiktok") or "tiktok",
        strict_mode=False,
        require_export_package=getattr(args, "require_export", False),
    )
    _header(f"Quality check — {args.job_id}")
    _show_report(report)
    _print(f"\n  Reports: {runs_base / args.job_id / 'ready_to_post_report.md'}")
    return 0 if report.readiness_label != "NOT_READY" else 1


def cmd_strict_check(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    report = evaluate_run_readiness(
        args.job_id,
        runs_base=runs_base,
        platform=getattr(args, "platform", "tiktok") or "tiktok",
        strict_mode=True,
        require_export_package=getattr(args, "require_export", False),
    )
    _header(f"Strict quality check — {args.job_id}")
    _show_report(report)
    return 0 if report.readiness_label == "READY_TO_POST" else 1


def cmd_batch_check(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    plat = getattr(args, "platform", "tiktok") or "tiktok"
    strict = getattr(args, "strict", False)
    rows: list[dict] = []
    for jid in args.job_ids:
        report = evaluate_run_readiness(
            jid, runs_base=runs_base, platform=plat, strict_mode=strict,
        )
        rows.append({
            "job_id": jid,
            "readiness_label": report.readiness_label,
            "score": report.score,
            "blockers": len(report.blocking_issues),
        })

    _header(f"Batch quality — {len(rows)} run(s)")
    for r in rows:
        _print(f"  {r['job_id']:<36} {r['readiness_label']:<16} {r['score']}/100")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": plat,
        "strict_mode": strict,
        "runs": rows,
    }
    _BATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = _BATCH_DIR / f"quality_batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _print(f"\n  Summary: {out}")
    return 0


def cmd_latest(args: argparse.Namespace) -> int:
    from genesis.review.run_index import find_latest_run

    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    run = find_latest_run(runs_base=runs_base)
    if not run:
        _print("No runs found.")
        return 1
    plat = getattr(args, "platform", "tiktok") or "tiktok"
    report = evaluate_run_readiness(run.job_id, runs_base=runs_base, platform=plat)
    _header(f"Latest quality — {run.job_id}")
    _show_report(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="genesis.quality.quality_cli")
    p.add_argument("--runs-base", dest="runs_base", default="")
    p.add_argument("--platform", default="tiktok")
    p.add_argument("--require-export", action="store_true")
    sub = p.add_subparsers(dest="command")

    c = sub.add_parser("check", help="Run quality gate and write reports")
    c.add_argument("job_id")

    sc = sub.add_parser("strict-check", help="Strict quality gate")
    sc.add_argument("job_id")

    bc = sub.add_parser("batch-check", help="Check multiple job IDs")
    bc.add_argument("job_ids", nargs="+")
    bc.add_argument("--strict", action="store_true")

    lat = sub.add_parser("latest", help="Check latest run")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    handlers = {
        "check": cmd_check,
        "strict-check": cmd_strict_check,
        "batch-check": cmd_batch_check,
        "latest": cmd_latest,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
