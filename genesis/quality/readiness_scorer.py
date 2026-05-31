"""Genesis Studio — Readiness scoring and report assembly."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.quality.quality_checks import RunInspection, build_run_inspection, run_all_quality_checks
from genesis.quality.quality_models import (
    CheckSeverity,
    CheckStatus,
    QualityCheckResult,
    QualityGateConfig,
    ReadinessLabel,
    ReadyToPostReport,
)
from genesis.quality.quality_report import (
    write_all_ready_to_post_reports,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"


def default_quality_config(
    *,
    platform: str = "tiktok",
    strict_mode: bool = False,
    require_export_package: bool = False,
) -> QualityGateConfig:
    cfg = QualityGateConfig(platform=platform, strict_mode=strict_mode)
    if strict_mode:
        cfg.allow_placeholders = False
        cfg.require_audio = False
        cfg.min_ready_score = 90
        cfg.min_review_score = 70
        cfg.require_disclosure_when_needed = True
    return cfg


def score_quality_checks(
    checks: list[QualityCheckResult],
    *,
    max_score: int = 100,
) -> tuple[int, bool]:
    """
    Return (score, has_blocker).
    Blocker fail forces NOT_READY regardless of score.
    """
    has_blocker = any(
        c.status == CheckStatus.FAIL and c.severity == CheckSeverity.BLOCKER
        for c in checks
    )
    if has_blocker:
        return 0, True

    score = max_score
    for c in checks:
        if c.status == CheckStatus.SKIPPED:
            continue
        if c.status == CheckStatus.PASS:
            continue
        if c.status == CheckStatus.WARN:
            score -= 2
            continue
        if c.status == CheckStatus.FAIL:
            if c.severity == CheckSeverity.HIGH:
                score -= 20
            elif c.severity == CheckSeverity.MEDIUM:
                score -= 10
            elif c.severity == CheckSeverity.LOW:
                score -= 5
            else:
                score -= c.score_impact or 5
    return max(0, min(max_score, score)), False


def determine_readiness_label(
    score: int,
    *,
    has_blocker: bool,
    config: QualityGateConfig,
) -> str:
    if has_blocker:
        return ReadinessLabel.NOT_READY
    if score >= config.min_ready_score:
        return ReadinessLabel.READY_TO_POST
    if score >= config.min_review_score:
        return ReadinessLabel.NEEDS_REVIEW
    return ReadinessLabel.NOT_READY


def build_ready_to_post_report(
    ins: RunInspection,
    checks: list[QualityCheckResult],
    *,
    score: int,
    has_blocker: bool,
    max_score: int = 100,
) -> ReadyToPostReport:
    label = determine_readiness_label(score, has_blocker=has_blocker, config=ins.config)
    blocking = [
        c.message for c in checks
        if c.status == CheckStatus.FAIL and c.severity in (CheckSeverity.BLOCKER, CheckSeverity.HIGH)
    ]
    warnings = [c.message for c in checks if c.status in (CheckStatus.WARN, CheckStatus.FAIL)]
    fixes = list(dict.fromkeys(
        c.recommended_fix for c in checks if c.recommended_fix
    ))[:12]

    return ReadyToPostReport(
        job_id=ins.job_id,
        platform=ins.platform,
        status="complete",
        score=score,
        max_score=max_score,
        readiness_label=label,
        checks=checks,
        blocking_issues=blocking[:10],
        warnings=warnings[:15],
        recommended_fixes=fixes,
        output_path=str(ins.run_dir),
        created_at=datetime.now(timezone.utc).isoformat(),
        notes=[f"strict_mode={ins.config.strict_mode}"],
    )


def evaluate_run_readiness(
    job_id: str,
    *,
    runs_base: Path | None = None,
    platform: str = "tiktok",
    strict_mode: bool = False,
    require_export_package: bool = False,
    write_reports: bool = True,
    config: QualityGateConfig | None = None,
) -> ReadyToPostReport:
    runs_base = runs_base or _RUNS_BASE
    run_dir = runs_base / job_id
    if not run_dir.is_dir():
        return ReadyToPostReport(
            job_id=job_id,
            platform=platform,
            status="failed",
            score=0,
            max_score=100,
            readiness_label=ReadinessLabel.NOT_READY,
            checks=[],
            blocking_issues=[f"run folder not found: {run_dir}"],
            warnings=[],
            recommended_fixes=["Create run via creator pipeline first"],
            output_path=str(run_dir),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    cfg = config or default_quality_config(
        platform=platform,
        strict_mode=strict_mode,
        require_export_package=require_export_package,
    )
    cfg.platform = platform or cfg.platform

    ins = build_run_inspection(
        run_dir,
        job_id=job_id,
        platform=platform,
        config=cfg,
        check_export_package=require_export_package,
    )
    checks = run_all_quality_checks(ins)
    score, has_blocker = score_quality_checks(checks)
    report = build_ready_to_post_report(ins, checks, score=score, has_blocker=has_blocker)

    if write_reports:
        paths = write_all_ready_to_post_reports(run_dir, report)
        report.output_path = str(paths.get("json", run_dir))

    return report
