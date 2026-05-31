"""Genesis Studio — Ready-to-post report writers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from genesis.quality.quality_models import ReadyToPostReport

_FORBIDDEN = re.compile(
    r"(sk-[a-zA-Z0-9]{12,}|api[_-]?key\s*[:=]\s*\S+|voice[_-]?id\s*[:=]\s*\S+)",
    re.I,
)


def _scrub(text: str) -> str:
    return _FORBIDDEN.sub("[REDACTED]", text)


def write_ready_to_post_report_json(run_dir: Path, report: ReadyToPostReport) -> Path:
    path = run_dir / "ready_to_post_report.json"
    data = report.to_dict()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_ready_to_post_report_md(run_dir: Path, report: ReadyToPostReport) -> Path:
    path = run_dir / "ready_to_post_report.md"
    lines = [
        f"# Ready to Post — {report.job_id}",
        "",
        f"**Readiness:** {report.readiness_label}",
        f"**Score:** {report.score}/{report.max_score}",
        f"**Platform:** {report.platform}",
        f"**Generated:** {report.created_at}",
        "",
    ]
    if report.blocking_issues:
        lines.extend(["## Blocking issues", ""])
        for b in report.blocking_issues:
            lines.append(f"- {_scrub(b)}")
        lines.append("")

    if report.warnings:
        lines.extend(["## Warnings", ""])
        for w in report.warnings[:12]:
            lines.append(f"- {_scrub(w)}")
        lines.append("")

    if report.recommended_fixes:
        lines.extend(["## Recommended fixes", ""])
        for f in report.recommended_fixes:
            lines.append(f"- {_scrub(f)}")
        lines.append("")

    lines.extend(["## Checks", ""])
    for c in report.checks:
        mark = {"pass": "OK", "warn": "!", "fail": "X", "skipped": "-"}.get(c.status, "?")
        lines.append(f"- [{mark}] **{c.name}** ({c.category}): {_scrub(c.message)}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_ready_to_post_badge(run_dir: Path, report: ReadyToPostReport) -> Path:
    path = run_dir / "ready_to_post_badge.txt"
    path.write_text(
        f"{report.readiness_label} — {report.score}/{report.max_score}\n",
        encoding="utf-8",
    )
    return path


def write_all_ready_to_post_reports(
    run_dir: Path,
    report: ReadyToPostReport,
) -> dict[str, Path]:
    return {
        "json": write_ready_to_post_report_json(run_dir, report),
        "md": write_ready_to_post_report_md(run_dir, report),
        "badge": write_ready_to_post_badge(run_dir, report),
    }


def load_ready_to_post_report(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "ready_to_post_report.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def read_quality_badge(run_dir: Path) -> str:
    badge = run_dir / "ready_to_post_badge.txt"
    if badge.is_file():
        return badge.read_text(encoding="utf-8").strip()
    data = load_ready_to_post_report(run_dir)
    if data:
        return f"{data.get('readiness_label', '')} — {data.get('score', 0)}/{data.get('max_score', 100)}"
    return ""
