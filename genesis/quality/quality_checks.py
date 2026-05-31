"""Genesis Studio — Ready-to-post quality checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from genesis.quality.quality_models import (
    CheckSeverity,
    CheckStatus,
    QualityCheckResult,
    QualityGateConfig,
)

_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{12,}", re.I),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?\S{8,}", re.I),
    re.compile(r"xi-api-key\s*[:=]\s*\S+", re.I),
    re.compile(r"voice[_-]?id\s*[:=]\s*['\"]?[a-zA-Z0-9]{16,}", re.I),
    re.compile(r"local_model_path\s*[:=]\s*\S+", re.I),
    re.compile(r"genesis/config/\S+\.json", re.I),
]
_MARKETPLACE_CLAIMS = re.compile(
    r"\b(official\s+amazon|amazon\s+partner|#ad\s+amazon|sold\s+on\s+amazon)\b", re.I,
)
_CURE_CLAIMS = re.compile(
    r"\b(cure(s|d)?|miracle\s+treatment|guaranteed\s+healing|reverse\s+disease)\b", re.I,
)
_GOFUNDME = re.compile(r"\b(gofundme|donate\s+now|donation\s+link)\b", re.I)
_SPAM_TAGS = re.compile(r"(#\w+\s*){25,}")


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _safe_text(path: Path, limit: int = 12000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except Exception:  # noqa: BLE001
        return ""


def _result(
    check_id: str,
    name: str,
    category: str,
    *,
    status: str = CheckStatus.PASS,
    severity: str = CheckSeverity.INFO,
    score_impact: int = 0,
    message: str = "",
    recommended_fix: str = "",
    evidence_paths: list[str] | None = None,
) -> QualityCheckResult:
    return QualityCheckResult(
        check_id=check_id,
        name=name,
        category=category,
        status=status,
        severity=severity,
        score_impact=score_impact,
        message=message,
        recommended_fix=recommended_fix,
        evidence_paths=evidence_paths or [],
    )


@dataclass
class RunInspection:
    run_dir: Path
    job_id: str
    platform: str
    config: QualityGateConfig
    brief: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    script_package: dict[str, Any] = field(default_factory=dict)
    export_manifest: dict[str, Any] = field(default_factory=dict)
    creator_summary: dict[str, Any] = field(default_factory=dict)
    media_manifest: dict[str, Any] = field(default_factory=dict)
    generated_visuals: dict[str, Any] = field(default_factory=dict)
    content_format: str = ""
    export_dir: Path | None = None
    text_blob: str = ""

    def path(self, name: str) -> Path:
        return self.run_dir / name

    def exists(self, name: str) -> bool:
        return self.path(name).is_file()

    def platform_meta(self) -> dict[str, Any]:
        mby = self.metadata.get("metadata_by_platform") or {}
        return mby.get(self.platform) or mby.get(self.platform.replace("_", "")) or {}


def build_run_inspection(
    run_dir: Path,
    *,
    job_id: str,
    platform: str,
    config: QualityGateConfig,
    check_export_package: bool = False,
) -> RunInspection:
    ins = RunInspection(
        run_dir=run_dir,
        job_id=job_id or run_dir.name,
        platform=platform or "tiktok",
        config=config,
    )
    ins.brief = _safe_json(run_dir / "brief.json")
    ins.metadata = _safe_json(run_dir / "metadata_pack.json")
    ins.script_package = _safe_json(run_dir / "script_package.json")
    ins.export_manifest = _safe_json(run_dir / "export_manifest.json")
    ins.creator_summary = _safe_json(run_dir / "creator_run_summary.json")
    ins.media_manifest = _safe_json(run_dir / "media_manifest.json")
    ins.generated_visuals = _safe_json(run_dir / "generated_visuals_manifest.json")
    ins.content_format = (
        ins.brief.get("content_format", "")
        or ins.script_package.get("content_format", "")
        or ""
    ).lower()

    exp = ins.export_manifest.get("export_dir") or ins.creator_summary.get("export_dir", "")
    if exp:
        p = Path(exp)
        if p.is_dir():
            ins.export_dir = p

    parts: list[str] = []
    for name in (
        "script.txt", "posting_checklist.md", "render_notes.md",
        "metadata_pack.json", "brief.json",
    ):
        if ins.exists(name):
            parts.append(_safe_text(ins.path(name), 4000))
    ins.text_blob = "\n".join(parts).lower()
    return ins


def _is_affiliate(ins: RunInspection) -> bool:
    fmt = ins.content_format
    return any(k in fmt for k in ("affiliate", "product_demo", "product")) or "affiliate" in ins.text_blob


def _is_fundraising(ins: RunInspection) -> bool:
    return "fundrais" in ins.content_format or "fundraising" in ins.text_blob


def _is_wellness(ins: RunInspection) -> bool:
    return "wellness" in ins.content_format or "teaching" in ins.content_format


def run_core_file_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    cfg = ins.config

    draft = ins.path("draft_video.mp4")
    if draft.is_file():
        results.append(_result(
            "core_draft_video", "Draft video present", "core",
            message=f"draft_video.mp4 ({draft.stat().st_size // 1024} KB)",
            evidence_paths=["draft_video.mp4"],
        ))
    else:
        results.append(_result(
            "core_draft_video", "Draft video present", "core",
            status=CheckStatus.FAIL, severity=CheckSeverity.BLOCKER, score_impact=100,
            message="draft_video.mp4 missing",
            recommended_fix="Run render or creator rerender to produce draft_video.mp4",
        ))

    cap_ok = ins.exists("caption.txt") or ins.exists("captions.txt")
    if cap_ok:
        results.append(_result("core_caption", "Caption file", "core", evidence_paths=["caption.txt"]))
    elif cfg.require_caption_file:
        results.append(_result(
            "core_caption", "Caption file", "core",
            status=CheckStatus.FAIL, severity=CheckSeverity.MEDIUM, score_impact=10,
            message="caption.txt missing",
            recommended_fix="Add caption.txt or platform caption in metadata_pack",
        ))

    for fid, fname, required in (
        ("core_metadata", "metadata_pack.json", cfg.require_metadata),
        ("core_posting_checklist", "posting_checklist.md", False),
        ("core_export_manifest", "export_manifest.json", False),
    ):
        if ins.exists(fname):
            results.append(_result(fid, f"{fname} present", "core", evidence_paths=[fname]))
        elif required:
            results.append(_result(
                fid, f"{fname} present", "core",
                status=CheckStatus.FAIL, severity=CheckSeverity.MEDIUM, score_impact=10,
                message=f"{fname} missing",
                recommended_fix=f"Generate or add {fname} before posting",
            ))
        elif fid == "core_posting_checklist":
            results.append(_result(
                fid, "Posting checklist", "core",
                status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=2,
                message="posting_checklist.md missing (recommended)",
            ))

    if ins.exists("creator_run_summary.json"):
        results.append(_result(
            "core_creator_summary", "Creator summary", "core",
            evidence_paths=["creator_run_summary.json"],
        ))

    if cfg.require_export_package:
        ok = ins.export_dir and ins.export_dir.is_dir()
        if ok:
            results.append(_result("core_export_pkg", "Export package", "core", message=str(ins.export_dir)))
        else:
            results.append(_result(
                "core_export_pkg", "Export package", "core",
                status=CheckStatus.FAIL, severity=CheckSeverity.HIGH, score_impact=20,
                message="export package not found",
                recommended_fix="Run review export or creator --export",
            ))

    # Thumbnail check
    thumb_ok = (
        ins.exists("selected_thumbnail.jpg")
        or ins.exists("thumbnail.jpg")
        or ins.exists("thumbnail.png")
    )
    if thumb_ok:
        thumb_name = (
            "selected_thumbnail.jpg" if ins.exists("selected_thumbnail.jpg")
            else "thumbnail.jpg" if ins.exists("thumbnail.jpg")
            else "thumbnail.png"
        )
        results.append(_result(
            "core_thumbnail", "Thumbnail present", "core",
            message=thumb_name,
            evidence_paths=[thumb_name],
        ))
    elif cfg.require_thumbnail:
        severity = CheckSeverity.HIGH if cfg.strict_mode else CheckSeverity.MEDIUM
        results.append(_result(
            "core_thumbnail", "Thumbnail present", "core",
            status=CheckStatus.FAIL, severity=severity, score_impact=15,
            message="selected_thumbnail.jpg missing",
            recommended_fix="Run: python -m genesis.thumbnail.thumbnail_cli select <job_id>",
        ))
    else:
        results.append(_result(
            "core_thumbnail", "Thumbnail present", "core",
            status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=3,
            message="no thumbnail found (recommended)",
            recommended_fix="Run: python -m genesis.thumbnail.thumbnail_cli select <job_id>",
        ))

    return results


def run_video_render_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    draft = ins.path("draft_video.mp4")
    if draft.is_file():
        size = draft.stat().st_size
        if size < 1024:
            results.append(_result(
                "video_size", "Draft video size", "video",
                status=CheckStatus.FAIL, severity=CheckSeverity.BLOCKER, score_impact=100,
                message=f"draft_video.mp4 too small ({size} bytes)",
                recommended_fix="Re-render; output may be corrupt",
            ))
        else:
            results.append(_result("video_size", "Draft video size", "video", message=f"{size // 1024} KB"))

    render_status = ins.export_manifest.get("render_status") or ins.creator_summary.get("status", "")
    if render_status in ("failed",):
        results.append(_result(
            "video_render_status", "Render status", "video",
            status=CheckStatus.FAIL, severity=CheckSeverity.HIGH, score_impact=20,
            message=f"render status: {render_status}",
        ))
    elif render_status:
        results.append(_result("video_render_status", "Render status", "video", message=render_status))

    notes = _safe_text(ins.path("render_notes.md"))
    if notes and any(w in notes.lower() for w in ("failed", "error", "traceback")):
        results.append(_result(
            "video_render_notes", "Render notes clean", "video",
            status=CheckStatus.WARN, severity=CheckSeverity.MEDIUM, score_impact=10,
            message="render_notes.md mentions errors",
            recommended_fix="Review render_notes.md and fix renderer issues",
            evidence_paths=["render_notes.md"],
        ))
    else:
        results.append(_result("video_render_notes", "Render notes clean", "video", status=CheckStatus.SKIPPED))

    for fname, cid, label in (
        ("timeline.json", "video_timeline", "Timeline"),
        ("caption_timing.json", "video_caption_timing", "Caption timing"),
        ("transition_plan.json", "video_transitions", "Transition plan"),
    ):
        if ins.exists(fname):
            results.append(_result(cid, label, "video", evidence_paths=[fname]))
        elif cid == "video_timeline":
            results.append(_result(
                cid, label, "video",
                status=CheckStatus.WARN, severity=CheckSeverity.MEDIUM, score_impact=10,
                message="timeline.json missing",
            ))

    return results


def run_audio_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    has_narr = ins.exists("narration.mp3") or ins.exists("narration.wav")
    has_mix = ins.exists("mixed_audio.mp3")
    if has_narr or has_mix:
        results.append(_result(
            "audio_present", "Audio track", "audio",
            message="narration or mixed_audio found",
            evidence_paths=[n for n in ("narration.mp3", "mixed_audio.mp3") if ins.exists(n)],
        ))
    elif ins.config.require_audio:
        results.append(_result(
            "audio_present", "Audio track", "audio",
            status=CheckStatus.FAIL, severity=CheckSeverity.HIGH, score_impact=20,
            message="no narration or mixed_audio",
            recommended_fix="Enable narration or audio mix in creator pipeline",
        ))
    else:
        results.append(_result(
            "audio_present", "Audio track", "audio",
            status=CheckStatus.SKIPPED, message="audio not required",
        ))

    if ins.exists("audio_manifest.json"):
        results.append(_result("audio_manifest", "Audio manifest", "audio", evidence_paths=["audio_manifest.json"]))

    notes = _safe_text(ins.path("render_notes.md")).lower()
    if "audio" in notes and "fail" in notes:
        results.append(_result(
            "audio_render_notes", "Audio mix clean", "audio",
            status=CheckStatus.WARN, severity=CheckSeverity.MEDIUM, score_impact=10,
            message="render notes mention audio failure",
        ))
    return results


def run_visual_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    placeholders = 0
    total = 0
    if ins.media_manifest:
        matches = ins.media_manifest.get("scene_matches") or []
        total = len(matches)
        placeholders = sum(1 for m in matches if m.get("fallback_needed"))

    if ins.media_manifest:
        results.append(_result(
            "visual_media_manifest", "Media manifest", "visual",
            message=f"{total - placeholders}/{total} scenes matched",
            evidence_paths=["media_manifest.json"],
        ))

    if ins.generated_visuals:
        missing = int(ins.generated_visuals.get("missing_scene_count", 0))
        results.append(_result(
            "visual_generated_manifest", "Generated visuals manifest", "visual",
            message=f"missing_scenes={missing}",
            evidence_paths=["generated_visuals_manifest.json"],
        ))
        if missing > 0:
            sev = CheckSeverity.MEDIUM if ins.config.allow_placeholders else CheckSeverity.HIGH
            st = CheckStatus.WARN if ins.config.allow_placeholders else CheckStatus.FAIL
            results.append(_result(
                "visual_missing_scenes", "Missing scene coverage", "visual",
                status=st, severity=sev, score_impact=10 if st == CheckStatus.WARN else 20,
                message=f"{missing} scene(s) still missing media",
                recommended_fix="Run visual fill or manual import",
            ))

    if placeholders > 0:
        strict = ins.config.strict_mode or not ins.config.allow_placeholders
        results.append(_result(
            "visual_placeholders", "Placeholder scenes", "visual",
            status=CheckStatus.FAIL if strict else CheckStatus.WARN,
            severity=CheckSeverity.HIGH if strict else CheckSeverity.MEDIUM,
            score_impact=20 if strict else 10,
            message=f"{placeholders} placeholder scene(s)",
            recommended_fix="Add real or imported visuals for placeholder scenes",
        ))
    elif total:
        results.append(_result("visual_placeholders", "Placeholder scenes", "visual", message="none"))

    val_text = _safe_text(ins.path("visual_asset_validation.md"))
    if val_text:
        if "blocker" in val_text.lower():
            results.append(_result(
                "visual_validation", "Visual asset validation", "visual",
                status=CheckStatus.FAIL, severity=CheckSeverity.HIGH, score_impact=20,
                message="visual_asset_validation.md reports blocker issues",
                evidence_paths=["visual_asset_validation.md"],
            ))
        elif "**Total warnings:**" in val_text:
            results.append(_result(
                "visual_validation", "Visual asset validation", "visual",
                status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=2,
                message="visual validation warnings present",
                evidence_paths=["visual_asset_validation.md"],
            ))
        else:
            results.append(_result("visual_validation", "Visual asset validation", "visual"))

    manual = int(ins.generated_visuals.get("manual_import_count", 0))
    if manual and not val_text:
        results.append(_result(
            "visual_manual_import", "Manual import validation", "visual",
            status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=2,
            message="manual imports present — run validate",
            recommended_fix="python -m genesis.ai_visuals.visual_cli validate <job_id>",
        ))
    return results


def run_script_metadata_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    script = _safe_text(ins.path("script.txt"))
    if script.strip():
        results.append(_result("script_txt", "Script text", "script", message=f"{len(script)} chars"))
    else:
        results.append(_result(
            "script_txt", "Script text", "script",
            status=CheckStatus.FAIL, severity=CheckSeverity.MEDIUM, score_impact=10,
            message="script.txt missing or empty",
        ))

    if ins.script_package:
        results.append(_result("script_package", "Script package", "script", evidence_paths=["script_package.json"]))
    else:
        results.append(_result(
            "script_package", "Script package", "script",
            status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=5,
            message="script_package.json missing",
        ))

    pdata = ins.platform_meta()
    if pdata:
        results.append(_result("meta_platform", "Platform metadata", "script", message=ins.platform))
    elif ins.config.require_metadata:
        results.append(_result(
            "meta_platform", "Platform metadata", "script",
            status=CheckStatus.FAIL, severity=CheckSeverity.MEDIUM, score_impact=10,
            message=f"no metadata for platform {ins.platform}",
        ))

    caption = pdata.get("caption") or pdata.get("description") or _safe_text(ins.path("caption.txt"), 500)
    if caption and len(caption.strip()) > 10:
        results.append(_result("meta_caption", "Caption present", "script", message=f"{len(caption)} chars"))
    else:
        results.append(_result(
            "meta_caption", "Caption present", "script",
            status=CheckStatus.WARN, severity=CheckSeverity.MEDIUM, score_impact=10,
            message="caption missing or very short",
            recommended_fix="Add hook-led caption in metadata_pack or caption.txt",
        ))

    cta = pdata.get("cta") or ""
    hooks = ins.script_package.get("hooks") or []
    if cta or hooks:
        results.append(_result("meta_cta", "CTA / hook", "script"))
    else:
        results.append(_result(
            "meta_cta", "CTA / hook", "script",
            status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=5,
            message="no CTA or hook found in metadata",
        ))

    tags = pdata.get("hashtags") or pdata.get("tags") or []
    if ins.platform in ("tiktok", "instagram", "instagram_reels", "clapper"):
        if tags:
            results.append(_result("meta_hashtags", "Hashtags", "script", message=f"{len(tags)} tag(s)"))
        else:
            results.append(_result(
                "meta_hashtags", "Hashtags", "script",
                status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=2,
                message="hashtags recommended for short-form",
            ))

    if ins.platform in ("youtube_shorts", "youtube"):
        title = pdata.get("title") or ""
        desc = pdata.get("description") or ""
        if title and desc:
            results.append(_result("meta_youtube_fields", "YouTube title+description", "script"))
        else:
            results.append(_result(
                "meta_youtube_fields", "YouTube title+description", "script",
                status=CheckStatus.FAIL, severity=CheckSeverity.MEDIUM, score_impact=10,
                message="YouTube Shorts needs title and description",
            ))
        tag_blob = " ".join(str(t) for t in (tags if isinstance(tags, list) else [tags]))
        if _SPAM_TAGS.search(tag_blob) or len(tag_blob) > 400:
            results.append(_result(
                "meta_youtube_tags", "YouTube tags quality", "script",
                status=CheckStatus.WARN, severity=CheckSeverity.MEDIUM, score_impact=10,
                message="tags may be spammy or too long",
            ))

    return results


def run_disclosure_truth_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    pdata = ins.platform_meta()
    disc = pdata.get("disclosure") or {}
    disclosures = ins.metadata.get("disclosures") or []
    disc_text = json.dumps(disclosures).lower() + json.dumps(disc).lower()

    if _is_affiliate(ins):
        has_aff = "affiliat" in disc_text or bool(disc.get("required"))
        if has_aff:
            results.append(_result("disc_affiliate", "Affiliate disclosure", "disclosure"))
        else:
            sev = CheckSeverity.BLOCKER if ins.config.strict_mode else CheckSeverity.HIGH
            results.append(_result(
                "disc_affiliate", "Affiliate disclosure", "disclosure",
                status=CheckStatus.FAIL, severity=sev,
                score_impact=100 if sev == CheckSeverity.BLOCKER else 20,
                message="affiliate content detected without disclosure",
                recommended_fix="Add affiliate disclosure to metadata_pack disclosures",
            ))

    if _is_fundraising(ins):
        has_f = "fundrais" in disc_text or "donation" in disc_text
        if not has_f:
            has_f = "fundrais" in ins.text_blob and "disclosure" in disc_text
        if has_f:
            results.append(_result("disc_fundraising", "Fundraising disclosure", "disclosure"))
        else:
            sev = CheckSeverity.BLOCKER if ins.config.strict_mode else CheckSeverity.HIGH
            results.append(_result(
                "disc_fundraising", "Fundraising disclosure", "disclosure",
                status=CheckStatus.FAIL, severity=sev,
                score_impact=100 if sev == CheckSeverity.BLOCKER else 20,
                message="fundraising content needs disclosure",
            ))

    if not ins.brief.get("official_partnership_approved"):
        if re.search(r"\bofficial\s+partner(ship)?\b", ins.text_blob):
            results.append(_result(
                "disc_partnership", "Partnership claims", "disclosure",
                status=CheckStatus.FAIL, severity=CheckSeverity.HIGH, score_impact=20,
                message="official partnership claimed without approval flag",
            ))

    if not ins.brief.get("marketplace_claim_approved"):
        if _MARKETPLACE_CLAIMS.search(ins.text_blob):
            results.append(_result(
                "disc_marketplace", "Marketplace claims", "disclosure",
                status=CheckStatus.FAIL, severity=CheckSeverity.MEDIUM, score_impact=10,
                message="marketplace claim detected without explicit approval",
            ))

    if _is_wellness(ins) and _CURE_CLAIMS.search(ins.text_blob):
        results.append(_result(
            "disc_wellness_cure", "Wellness truthfulness", "disclosure",
            status=CheckStatus.FAIL, severity=CheckSeverity.HIGH, score_impact=20,
            message="medical cure language in wellness content",
            recommended_fix="Use educational framing; remove cure guarantees",
        ))

    if not _is_fundraising(ins) and _GOFUNDME.search(ins.text_blob):
        results.append(_result(
            "disc_gofundme", "Donation language", "disclosure",
            status=CheckStatus.WARN, severity=CheckSeverity.MEDIUM, score_impact=10,
            message="donation language in non-fundraising content",
        ))

    if not results:
        results.append(_result("disc_general", "Disclosure scan", "disclosure", status=CheckStatus.SKIPPED))
    return results


def run_safety_secret_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    hits: list[str] = []
    scan_paths: list[Path] = []
    for p in ins.run_dir.iterdir():
        if p.is_file() and p.suffix.lower() in (".md", ".json", ".txt", ".html"):
            scan_paths.append(p)

    if ins.export_dir:
        for p in ins.export_dir.iterdir():
            if p.is_file() and p.suffix.lower() in (".md", ".json", ".txt"):
                scan_paths.append(p)

    for p in scan_paths:
        if "config" in p.name.lower() and p.suffix == ".json":
            hits.append(f"config file in run/export: {p.name}")
            continue
        text = _safe_text(p, 8000)
        for pat in _SECRET_PATTERNS:
            if pat.search(text):
                hits.append(f"secret pattern in {p.name}")
                break

    if hits:
        results.append(_result(
            "safety_secrets", "Secrets scan", "safety",
            status=CheckStatus.FAIL, severity=CheckSeverity.BLOCKER, score_impact=100,
            message="; ".join(hits[:5]),
            recommended_fix="Remove API keys, voice IDs, and config copies from run/export",
            evidence_paths=[h.split()[-1] for h in hits[:3]],
        ))
    else:
        results.append(_result("safety_secrets", "Secrets scan", "safety", message="no secrets detected"))
    return results


def run_platform_checks(ins: RunInspection) -> list[QualityCheckResult]:
    results: list[QualityCheckResult] = []
    plat = ins.platform.lower()
    pdata = ins.platform_meta()
    caption = str(pdata.get("caption") or pdata.get("description") or _safe_text(ins.path("caption.txt"), 500))

    vertical_platforms = ("tiktok", "instagram", "instagram_reels", "clapper", "reels")
    if any(p in plat for p in vertical_platforms):
        results.append(_result(
            "plat_vertical", "Vertical short-form", "platform",
            message="9:16 vertical expected for " + plat,
        ))

    if plat in ("x", "twitter"):
        if len(caption) > 280:
            results.append(_result(
                "plat_x_length", "X caption length", "platform",
                status=CheckStatus.FAIL, severity=CheckSeverity.MEDIUM, score_impact=10,
                message=f"caption {len(caption)} chars exceeds 280",
            ))
        else:
            results.append(_result("plat_x_length", "X caption length", "platform", message=f"{len(caption)} chars"))

    if plat in ("tiktok", "instagram", "instagram_reels") and len(caption) > 2200:
        results.append(_result(
            "plat_caption_limit", "Caption length", "platform",
            status=CheckStatus.WARN, severity=CheckSeverity.LOW, score_impact=2,
            message="caption very long for platform",
        ))

    if not results:
        results.append(_result("plat_general", "Platform checks", "platform", status=CheckStatus.SKIPPED))
    return results


def run_all_quality_checks(ins: RunInspection) -> list[QualityCheckResult]:
    checks: list[QualityCheckResult] = []
    checks.extend(run_core_file_checks(ins))
    checks.extend(run_video_render_checks(ins))
    checks.extend(run_audio_checks(ins))
    checks.extend(run_visual_checks(ins))
    checks.extend(run_script_metadata_checks(ins))
    checks.extend(run_disclosure_truth_checks(ins))
    checks.extend(run_safety_secret_checks(ins))
    checks.extend(run_platform_checks(ins))
    return checks
