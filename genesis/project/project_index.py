"""Genesis Studio — Project history index."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.project.project_models import ProjectIndex, ProjectRunRecord, ProjectStatus
from genesis.review.run_index import summarize_run

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"
_DEFAULT_INDEX = _REPO_ROOT / "assets" / "project_index.json"

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


def _mtime_str(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return ""


def _scrub_text(text: str) -> str:
    return _FORBIDDEN.sub("[REDACTED]", text)


def _scrub_list(items: list[str]) -> list[str]:
    return [_scrub_text(x) for x in items]


def _record_from_creator_summary(run_dir: Path, summary: dict[str, Any]) -> ProjectRunRecord:
    brief = _safe_json(run_dir / "brief.json")
    idea = _scrub_text(brief.get("idea", "") or "")
    platforms = brief.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [platforms]
    created = brief.get("created_at") or _mtime_str(run_dir / "brief.json") or _mtime_str(run_dir)
    updated = _mtime_str(run_dir / "creator_run_summary.json") or created

    return ProjectRunRecord(
        job_id=summary.get("job_id") or run_dir.name,
        idea=idea,
        template=summary.get("template", ""),
        primary_platform=summary.get("primary_platform", ""),
        platforms=list(platforms),
        brand_preset=summary.get("brand_preset", ""),
        status=summary.get("status", ProjectStatus.PARTIAL),
        run_dir=summary.get("run_dir") or str(run_dir),
        draft_video_path=summary.get("draft_video_path", ""),
        export_dir=summary.get("export_dir", ""),
        review_html_path=summary.get("review_html_path", ""),
        created_at=created,
        updated_at=updated,
        warnings=_scrub_list(summary.get("warnings") or []),
        notes=_scrub_list(summary.get("notes") or []),
    )


def _record_from_review_summary(run_dir: Path) -> ProjectRunRecord:
    rs = summarize_run(run_dir)
    warnings = list(rs.warnings)
    if rs.status not in (ProjectStatus.COMPLETE,):
        warnings.append(f"run status: {rs.status}")

    return ProjectRunRecord(
        job_id=rs.job_id,
        idea=_scrub_text(rs.idea),
        template="",
        primary_platform=rs.platforms[0] if rs.platforms else "",
        platforms=list(rs.platforms),
        brand_preset="",
        status=rs.status,
        run_dir=rs.run_dir,
        draft_video_path=rs.draft_video_path,
        export_dir="",
        review_html_path=str(run_dir / "review.html") if (run_dir / "review.html").is_file() else "",
        created_at=rs.created_at,
        updated_at=_mtime_str(run_dir),
        warnings=_scrub_list(warnings),
        notes=[],
    )


def scan_runs_for_index(
    *,
    runs_base: Path | None = None,
) -> list[ProjectRunRecord]:
    """Scan run folders; never raises on individual run failures."""
    base = runs_base or _RUNS_BASE
    if not base.is_dir():
        return []

    records: list[ProjectRunRecord] = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        try:
            summary_path = run_dir / "creator_run_summary.json"
            if summary_path.is_file():
                summary = _safe_json(summary_path)
                records.append(_record_from_creator_summary(run_dir, summary))
            else:
                records.append(_record_from_review_summary(run_dir))
        except Exception:  # noqa: BLE001
            records.append(ProjectRunRecord(
                job_id=run_dir.name,
                idea="",
                template="",
                primary_platform="",
                platforms=[],
                brand_preset="",
                status=ProjectStatus.PARTIAL,
                run_dir=str(run_dir),
                draft_video_path="",
                export_dir="",
                review_html_path="",
                created_at=_mtime_str(run_dir),
                updated_at=_mtime_str(run_dir),
                warnings=["could not summarize run"],
                notes=[],
            ))

    records.sort(key=lambda r: r.updated_at or r.created_at or "", reverse=True)
    return records


def build_project_index(
    *,
    runs_base: Path | None = None,
    index_path: Path | None = None,
) -> ProjectIndex:
    runs_base = runs_base or _RUNS_BASE
    index_path = index_path or _DEFAULT_INDEX
    runs = scan_runs_for_index(runs_base=runs_base)

    warnings: list[str] = []
    for r in runs:
        if r.status in (ProjectStatus.PARTIAL, ProjectStatus.FAILED):
            warnings.append(f"{r.job_id}: {r.status}")
        if not r.idea:
            warnings.append(f"{r.job_id}: missing idea in brief")

    if not runs:
        status = ProjectStatus.SKIPPED
    elif all(r.status == ProjectStatus.COMPLETE for r in runs):
        status = ProjectStatus.COMPLETE
    elif any(r.status == ProjectStatus.FAILED for r in runs):
        status = ProjectStatus.PARTIAL
    else:
        status = ProjectStatus.PARTIAL

    return ProjectIndex(
        index_path=str(index_path),
        runs=runs,
        last_updated=_now(),
        status=status,
        warnings=warnings[:50],
        notes=[f"total_runs={len(runs)}"],
    )


def write_project_index(
    index: ProjectIndex,
    *,
    index_path: Path | None = None,
) -> Path:
    path = index_path or Path(index.index_path) or _DEFAULT_INDEX
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(index.to_dict(), indent=2)
    text = _scrub_text(text)
    path.write_text(text, encoding="utf-8")
    return path


def load_project_index(
    *,
    index_path: Path | None = None,
) -> ProjectIndex | None:
    path = index_path or _DEFAULT_INDEX
    if not path.is_file():
        return None
    data = _safe_json(path)
    runs = [
        ProjectRunRecord(
            job_id=r.get("job_id", ""),
            idea=r.get("idea", ""),
            template=r.get("template", ""),
            primary_platform=r.get("primary_platform", ""),
            platforms=r.get("platforms") or [],
            brand_preset=r.get("brand_preset", ""),
            status=r.get("status", ""),
            run_dir=r.get("run_dir", ""),
            draft_video_path=r.get("draft_video_path", ""),
            export_dir=r.get("export_dir", ""),
            review_html_path=r.get("review_html_path", ""),
            created_at=r.get("created_at", ""),
            updated_at=r.get("updated_at", ""),
            warnings=r.get("warnings") or [],
            notes=r.get("notes") or [],
        )
        for r in data.get("runs", [])
    ]
    return ProjectIndex(
        index_path=str(path),
        runs=runs,
        last_updated=data.get("last_updated", ""),
        status=data.get("status", ""),
        warnings=data.get("warnings") or [],
        notes=data.get("notes") or [],
    )


def update_project_index_from_run(
    job_id: str,
    *,
    runs_base: Path | None = None,
    index_path: Path | None = None,
) -> ProjectIndex:
    """Refresh index after a single run completes."""
    index = build_project_index(runs_base=runs_base, index_path=index_path)
    write_project_index(index, index_path=index_path)
    return index


def find_runs_by_status(
    index: ProjectIndex,
    status: str,
) -> list[ProjectRunRecord]:
    return [r for r in index.runs if r.status == status]


def find_runs_by_template(
    index: ProjectIndex,
    template: str,
) -> list[ProjectRunRecord]:
    t = template.lower()
    return [r for r in index.runs if r.template.lower() == t]


def find_runs_by_platform(
    index: ProjectIndex,
    platform: str,
) -> list[ProjectRunRecord]:
    p = platform.lower()
    return [
        r for r in index.runs
        if r.primary_platform.lower() == p or p in [x.lower() for x in r.platforms]
    ]


def summarize_project_index(index: ProjectIndex) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_template: dict[str, int] = {}
    for r in index.runs:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        if r.template:
            by_template[r.template] = by_template.get(r.template, 0) + 1
    return {
        "total_runs": len(index.runs),
        "last_updated": index.last_updated,
        "index_status": index.status,
        "by_status": by_status,
        "by_template": by_template,
        "with_video": sum(1 for r in index.runs if r.draft_video_path),
        "with_export": sum(1 for r in index.runs if r.export_dir),
    }
