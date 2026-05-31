"""Genesis Studio — Ready-to-post quality gate models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class CheckStatus:
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"


class CheckSeverity:
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKER = "blocker"


class ReadinessLabel:
    READY_TO_POST = "READY_TO_POST"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_READY = "NOT_READY"


@dataclass
class QualityCheckResult:
    check_id: str
    name: str
    category: str
    status: str
    severity: str
    score_impact: int
    message: str
    recommended_fix: str = ""
    evidence_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "severity": self.severity,
            "score_impact": self.score_impact,
            "message": self.message,
            "recommended_fix": self.recommended_fix,
            "evidence_paths": self.evidence_paths,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class ReadyToPostReport:
    job_id: str
    platform: str
    status: str
    score: int
    max_score: int
    readiness_label: str
    checks: list[QualityCheckResult]
    blocking_issues: list[str]
    warnings: list[str]
    recommended_fixes: list[str]
    output_path: str
    created_at: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "platform": self.platform,
            "status": self.status,
            "score": self.score,
            "max_score": self.max_score,
            "readiness_label": self.readiness_label,
            "checks": [c.to_dict() for c in self.checks],
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "recommended_fixes": self.recommended_fixes,
            "output_path": self.output_path,
            "created_at": self.created_at,
            "notes": self.notes,
        }


@dataclass
class QualityGateConfig:
    min_ready_score: int = 90
    min_review_score: int = 70
    allow_placeholders: bool = True
    require_caption_file: bool = True
    require_metadata: bool = True
    require_audio: bool = False
    require_disclosure_when_needed: bool = True
    require_export_package: bool = False
    require_thumbnail: bool = False
    platform: str = "tiktok"
    strict_mode: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_ready_score": self.min_ready_score,
            "min_review_score": self.min_review_score,
            "allow_placeholders": self.allow_placeholders,
            "require_caption_file": self.require_caption_file,
            "require_metadata": self.require_metadata,
            "require_audio": self.require_audio,
            "require_disclosure_when_needed": self.require_disclosure_when_needed,
            "require_export_package": self.require_export_package,
            "require_thumbnail": self.require_thumbnail,
            "platform": self.platform,
            "strict_mode": self.strict_mode,
            "notes": self.notes,
        }
