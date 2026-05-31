"""Genesis Studio — Batch run orchestration."""

from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.creator.creator_models import CreatorRunRequest, CreatorStatus
from genesis.creator.pipeline_runner import run_creator_pipeline
from genesis.creator.project_templates import get_template_or_default
from genesis.project.project_index import build_project_index, write_project_index
from genesis.project.project_models import BatchRunItem, BatchRunResult, ProjectStatus
from genesis.review.export_builder import build_export_package
from genesis.video.render_run import render_run_video

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"
_BATCHES_BASE = _REPO_ROOT / "assets" / "batches"
_FORBIDDEN = re.compile(
    r"(api_key|sk_[a-z0-9]+|xi-api|voice_id|openai_api|local_model_path)",
    re.I,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scrub(text: str) -> str:
    return _FORBIDDEN.sub("[REDACTED]", text)


def _safe_json_dump(data: dict[str, Any]) -> str:
    return _scrub(json.dumps(data, indent=2))


def _bool_val(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None or val == "":
        return default
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "on")


def _item_from_dict(row: dict[str, Any]) -> BatchRunItem:
    idea = str(row.get("idea", "")).strip()
    job_id = str(row.get("job_id", "")).strip()
    template = str(row.get("template", "affiliate_product")).strip() or "affiliate_product"
    platform = str(row.get("platform", row.get("primary_platform", "tiktok"))).strip() or "tiktok"
    brand = str(row.get("brand", row.get("brand_preset", ""))).strip()
    if not brand:
        brand = get_template_or_default(template).brand_preset

    opts = row.get("options") or {}
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except Exception:  # noqa: BLE001
            opts = {}

    return BatchRunItem(
        idea=idea,
        job_id=job_id,
        template=template,
        platform=platform,
        brand=brand,
        media_path=str(row.get("media_path", "")).strip(),
        music_path=str(row.get("music_path", "")).strip(),
        export_enabled=_bool_val(row.get("export_enabled"), False),
        narration_enabled=_bool_val(row.get("narration_enabled"), True),
        render_enabled=_bool_val(row.get("render_enabled"), True),
        options=opts if isinstance(opts, dict) else {},
    )


def validate_batch_items(items: list[BatchRunItem]) -> tuple[list[BatchRunItem], list[str]]:
    """Validate items; mark invalid ones as failed with warnings."""
    warnings: list[str] = []
    for item in items:
        if not item.idea:
            item.status = ProjectStatus.FAILED
            item.warnings.append("missing required field: idea")
            warnings.append(f"job {item.job_id or '?'}: missing idea")
    return items, warnings


def load_batch_file(path: str | Path) -> list[dict[str, Any]]:
    """Load raw rows from JSON or CSV batch file."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"batch file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        if not isinstance(data, list):
            raise ValueError("JSON batch file must be a list or {items: [...]}")
        return [x for x in data if isinstance(x, dict)]

    if suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return [dict(row) for row in reader]

    raise ValueError(f"unsupported batch file type: {suffix} (use .json or .csv)")


def parse_batch_items(path: str | Path) -> list[BatchRunItem]:
    rows = load_batch_file(path)
    items = [_item_from_dict(row) for row in rows]
    validate_batch_items(items)
    return items


def _batch_dir(batch_id: str, *, batches_base: Path | None = None) -> Path:
    base = batches_base or _BATCHES_BASE
    d = base / batch_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_batch_summary(
    result: BatchRunResult,
    *,
    batches_base: Path | None = None,
) -> tuple[Path, Path]:
    batch_dir = _batch_dir(result.batch_id, batches_base=batches_base)
    result.output_path = str(batch_dir)
    json_path = batch_dir / "batch_summary.json"
    json_path.write_text(_safe_json_dump(result.to_dict()), encoding="utf-8")

    lines = [
        f"# Batch Report — {result.batch_id}",
        "",
        f"**Status:** {result.status}",
        f"**Completed:** {result.completed} | **Partial:** {result.partial} | "
        f"**Failed:** {result.failed} | **Skipped:** {result.skipped}",
        "",
        "## Items",
        "",
        "| Job ID | Status | Template | Platform | Idea |",
        "|--------|--------|----------|----------|------|",
    ]
    for item in result.items:
        idea_short = (item.idea[:40] + "…") if len(item.idea) > 40 else item.idea
        lines.append(
            f"| {item.job_id or '—'} | {item.status} | {item.template} | "
            f"{item.platform} | {idea_short} |"
        )
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        for w in result.warnings[:20]:
            lines.append(f"- {w}")

    md_path = batch_dir / "batch_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def _creator_request_from_item(item: BatchRunItem) -> CreatorRunRequest:
    return CreatorRunRequest(
        idea=item.idea,
        job_id=item.job_id,
        template=item.template,
        primary_platform=item.platform,
        brand_preset=item.brand,
        media_path=item.media_path,
        music_path=item.music_path,
        narration_enabled=item.narration_enabled,
        render_enabled=item.render_enabled,
        export_enabled=item.export_enabled,
        options=item.options,
    )


def run_batch_create(
    items: list[BatchRunItem],
    *,
    batch_id: str | None = None,
    runs_base: Path | None = None,
    exports_base: Path | None = None,
    repo_root: Path | None = None,
    index_path: Path | None = None,
    batches_base: Path | None = None,
) -> BatchRunResult:
    """Run creator pipeline for each batch item; continue on failures."""
    batch_id = batch_id or f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT

    completed = partial = failed = skipped = 0
    batch_warnings: list[str] = []

    for item in items:
        if item.status == ProjectStatus.FAILED and not item.idea:
            skipped += 1
            continue
        if not item.job_id:
            item.job_id = f"{batch_id}-{uuid.uuid4().hex[:6]}"

        req = _creator_request_from_item(item)
        try:
            result = run_creator_pipeline(
                req,
                runs_base=runs_base,
                exports_base=exports_base,
                repo_root=repo_root,
            )
            item.job_id = result.job_id
            item.status = result.status
            item.warnings.extend(result.warnings[:5])
            if result.status == CreatorStatus.COMPLETE:
                completed += 1
            elif result.status == CreatorStatus.SKIPPED:
                skipped += 1
            elif result.status == CreatorStatus.FAILED:
                failed += 1
                batch_warnings.append(f"{item.job_id}: pipeline failed")
            else:
                partial += 1
                batch_warnings.append(f"{item.job_id}: partial run")
        except Exception as exc:  # noqa: BLE001
            item.status = ProjectStatus.FAILED
            item.warnings.append(str(exc))
            failed += 1
            batch_warnings.append(f"{item.job_id}: {exc}")

    if failed and (completed or partial):
        batch_status = ProjectStatus.PARTIAL
    elif failed:
        batch_status = ProjectStatus.FAILED
    elif partial:
        batch_status = ProjectStatus.PARTIAL
    elif completed:
        batch_status = ProjectStatus.COMPLETE
    else:
        batch_status = ProjectStatus.SKIPPED

    batch_result = BatchRunResult(
        batch_id=batch_id,
        status=batch_status,
        items=items,
        completed=completed,
        partial=partial,
        failed=failed,
        skipped=skipped,
        output_path="",
        warnings=batch_warnings,
        notes=[f"items={len(items)}", f"finished_at={_now()}"],
    )
    write_batch_summary(batch_result, batches_base=batches_base)

    try:
        index = build_project_index(runs_base=runs_base, index_path=index_path)
        write_project_index(index, index_path=index_path)
    except Exception as exc:  # noqa: BLE001
        batch_result.warnings.append(f"index update failed: {exc}")

    return batch_result


def run_batch_rerender(
    job_ids: list[str],
    *,
    platform: str = "tiktok",
    brand: str = "clean_creator",
    music_path: str = "",
    music_volume: float = 0.18,
    batch_id: str | None = None,
    runs_base: Path | None = None,
    index_path: Path | None = None,
    batches_base: Path | None = None,
) -> BatchRunResult:
    batch_id = batch_id or f"rerender-{uuid.uuid4().hex[:8]}"
    runs_base = runs_base or _RUNS_BASE
    items: list[BatchRunItem] = []
    completed = partial = failed = skipped = 0
    batch_warnings: list[str] = []

    for jid in job_ids:
        item = BatchRunItem(
            idea="",
            job_id=jid,
            platform=platform,
            brand=brand,
            music_path=music_path,
            render_enabled=True,
        )
        try:
            result = render_run_video(
                jid,
                target_platform=platform,
                brand_preset=brand,
                music_path=music_path or None,
                music_volume=music_volume,
                runs_base=runs_base,
            )
            item.status = result.status
            item.warnings.extend(result.warnings[:3])
            if result.status == CreatorStatus.COMPLETE:
                completed += 1
            elif result.status == CreatorStatus.FAILED:
                failed += 1
            else:
                partial += 1
        except Exception as exc:  # noqa: BLE001
            item.status = ProjectStatus.FAILED
            item.warnings.append(str(exc))
            failed += 1
        items.append(item)

    status = _aggregate_batch_status(completed, partial, failed, skipped)
    batch_result = BatchRunResult(
        batch_id=batch_id,
        status=status,
        items=items,
        completed=completed,
        partial=partial,
        failed=failed,
        skipped=skipped,
        output_path="",
        warnings=batch_warnings,
        notes=["operation=batch_rerender"],
    )
    write_batch_summary(batch_result, batches_base=batches_base)
    try:
        index = build_project_index(runs_base=runs_base, index_path=index_path)
        write_project_index(index, index_path=index_path)
    except Exception as exc:  # noqa: BLE001
        batch_result.warnings.append(f"index update failed: {exc}")
    return batch_result


def run_batch_export(
    job_ids: list[str],
    *,
    platform: str = "tiktok",
    batch_id: str | None = None,
    runs_base: Path | None = None,
    exports_base: Path | None = None,
    index_path: Path | None = None,
    batches_base: Path | None = None,
) -> BatchRunResult:
    batch_id = batch_id or f"export-{uuid.uuid4().hex[:8]}"
    runs_base = runs_base or _RUNS_BASE
    items: list[BatchRunItem] = []
    completed = partial = failed = skipped = 0

    for jid in job_ids:
        item = BatchRunItem(idea="", job_id=jid, platform=platform, export_enabled=True)
        try:
            pkg = build_export_package(
                jid, platform=platform, runs_base=runs_base, exports_base=exports_base,
            )
            item.status = pkg.status
            item.warnings.extend(pkg.warnings[:3])
            if pkg.export_dir:
                item.notes.append(f"export_dir={pkg.export_dir}")
            if pkg.status == CreatorStatus.COMPLETE:
                completed += 1
            elif pkg.status == CreatorStatus.FAILED:
                failed += 1
            else:
                partial += 1
        except Exception as exc:  # noqa: BLE001
            item.status = ProjectStatus.FAILED
            item.warnings.append(str(exc))
            failed += 1
        items.append(item)

    status = _aggregate_batch_status(completed, partial, failed, skipped)
    batch_result = BatchRunResult(
        batch_id=batch_id,
        status=status,
        items=items,
        completed=completed,
        partial=partial,
        failed=failed,
        skipped=skipped,
        output_path="",
        notes=["operation=batch_export"],
    )
    write_batch_summary(batch_result, batches_base=batches_base)
    try:
        index = build_project_index(runs_base=runs_base, index_path=index_path)
        write_project_index(index, index_path=index_path)
    except Exception as exc:  # noqa: BLE001
        batch_result.warnings.append(f"index update failed: {exc}")
    return batch_result


def _aggregate_batch_status(completed: int, partial: int, failed: int, skipped: int) -> str:
    if failed and (completed or partial):
        return ProjectStatus.PARTIAL
    if failed:
        return ProjectStatus.FAILED
    if partial:
        return ProjectStatus.PARTIAL
    if completed:
        return ProjectStatus.COMPLETE
    return ProjectStatus.SKIPPED


def load_batch_summary(batch_id: str, *, batches_base: Path | None = None) -> dict[str, Any] | None:
    base = batches_base or _BATCHES_BASE
    path = base / batch_id / "batch_summary.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
