"""
Genesis Studio — Social media content workflow orchestration.

Turns a single idea or script into a structured, file-backed content package.

Workflow spine:
  1.  Create a SocialContentBrief from the input idea + parameters.
  2.  Prepare script:
        a. Use provided script_text as-is (source = "provided").
        b. Generate via Script Engine → local LLM if enabled, else Viral Spine template.
  3.  Run post-script pipeline steps (narration via ElevenLabs).
  4.  Generate per-platform metadata (ScriptPackage-aware).
  5.  Write the posting package to assets/runs/<job_id>/.
  6.  Return a SocialWorkflowResult.

No web UI, no agents, no auto-posting, no platform API calls.
Full SEO metadata, hashtag intelligence, and video assembly are Phase 13+.
"""

from __future__ import annotations

import json
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.utils.logger import get_logger
from genesis.workflows.models import (
    SUPPORTED_PLATFORMS,
    GeneratedAssetReference,
    NarrationStatus,
    PlatformMetadata,
    PostingPackage,
    SocialContentBrief,
    SocialWorkflowResult,
    WorkflowStatus,
    platform_defaults,
    platform_label,
)

logger = get_logger("workflows.social_media")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"


# ---------------------------------------------------------------------------
# Brief
# ---------------------------------------------------------------------------

def create_social_content_brief(
    idea: str,
    *,
    job_id: str | None = None,
    platforms: list[str] | None = None,
    audience: str = "",
    content_goal: str = "",
    tone: str = "engaging",
    offer: str = "",
    cta: str = "",
    marketplace: str = "",
    retailer: str = "",
    brand_name: str = "",
    product_name: str = "",
    affiliate_status: str = "",
    sponsorship_status: str = "",
    link_status: str = "",
    fundraiser_status: str = "",
) -> SocialContentBrief:
    """
    Build a SocialContentBrief from raw creative inputs.

    Args:
        idea:         Core idea or topic for the content piece.
        job_id:       Unique run ID; generated if not provided.
        platforms:    Target platforms (default: all five).
        audience:     Target audience description.
        content_goal: e.g. "awareness", "conversion", "engagement".
        tone:         Tone of voice, e.g. "educational", "energetic".
        offer:        Specific offer, product, or value proposition.
        cta:          Call-to-action text.

    Returns:
        A populated SocialContentBrief.
    """
    return SocialContentBrief(
        job_id=job_id or uuid.uuid4().hex[:12],
        idea=idea.strip(),
        platforms=list(platforms or SUPPORTED_PLATFORMS),
        audience=audience.strip(),
        content_goal=content_goal.strip(),
        tone=tone.strip(),
        offer=offer.strip(),
        cta=cta.strip(),
        created_at=datetime.now(timezone.utc).isoformat(),
        marketplace=marketplace.strip(),
        retailer=retailer.strip(),
        brand_name=brand_name.strip(),
        product_name=product_name.strip(),
        affiliate_status=affiliate_status.strip(),
        sponsorship_status=sponsorship_status.strip(),
        link_status=link_status.strip(),
        fundraiser_status=fundraiser_status.strip(),
    )


# ---------------------------------------------------------------------------
# Script helpers
# ---------------------------------------------------------------------------

def _placeholder_script_from_idea(
    idea: str,
    *,
    tone: str = "engaging",
    cta: str = "",
    audience: str = "",
) -> str:
    """Minimal placeholder; only used if the script engine itself fails to import."""
    hook = f"[HOOK] {idea.strip()}"
    body = "[BODY] Explain why this matters to your audience."
    if audience:
        body = f"[BODY] Share the key insight that resonates with {audience}."
    cta_line = f"[CTA] {cta.strip()}" if cta.strip() else "[CTA] Follow for more."
    note = (
        "# EMERGENCY PLACEHOLDER SCRIPT — script engine unavailable.\n"
        f"# Tone: {tone}\n\n"
    )
    return note + "\n\n".join([hook, body, cta_line])


def _generate_script_with_engine(
    brief: SocialContentBrief,
    content_format: str,
) -> tuple[str, str, Any]:
    """
    Call the Phase 12 script engine for a full ScriptPackage.

    Returns:
        (script_text, script_source, script_package_or_None)
    """
    try:
        from genesis.creative.script_engine import generate_script_package

        pkg = generate_script_package(
            brief.idea,
            job_id=brief.job_id,
            audience=brief.audience,
            tone=brief.tone,
            content_goal=brief.content_goal,
            offer=brief.offer,
            cta=brief.cta,
            content_format=content_format,
            platforms=brief.platforms,
        )
        script_text = pkg.primary_script.full_text or pkg.primary_script.title
        logger.info(
            "job=%s: script engine → source=%s backend=%s",
            brief.job_id, pkg.script_source, pkg.llm_backend or "template",
        )
        return script_text, pkg.script_source, pkg

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "job=%s: script engine failed (%s) — using placeholder",
            brief.job_id, exc,
        )
        text = _placeholder_script_from_idea(
            brief.idea, tone=brief.tone, cta=brief.cta, audience=brief.audience,
        )
        return text, "placeholder", None


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

def _run_narration_step(
    script_text: str,
    *,
    job_id: str,
    narration_kwargs: dict[str, Any],
) -> GeneratedAssetReference:
    """
    Attempt to synthesize narration. Returns a GeneratedAssetReference.
    Exceptions are caught and converted to a FAILED reference so the workflow
    can continue.
    """
    try:
        from genesis.pipeline.narration import run_post_script_steps

        results = run_post_script_steps(
            script_text,
            job_id=job_id,
            **narration_kwargs,
        )
        asset = results.get("narration")
        if asset is None:
            return GeneratedAssetReference(
                asset_id=f"narration-{job_id}",
                path="",
                asset_type="audio",
                provider="elevenlabs",
                status=NarrationStatus.SKIPPED,
                metadata={"reason": "not_returned"},
            )
        return GeneratedAssetReference(
            asset_id=asset.id,
            path=asset.path or "",
            asset_type="audio",
            provider=asset.provider,
            status=str(asset.status.value) if hasattr(asset.status, "value") else str(asset.status),
            prompt_excerpt=asset.prompt[:120] if asset.prompt else "",
            metadata=dict(asset.metadata or {}),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("narration step failed for job %s: %s", job_id, exc)
        return GeneratedAssetReference(
            asset_id=f"narration-{job_id}",
            path="",
            asset_type="audio",
            provider="elevenlabs",
            status=NarrationStatus.FAILED,
            metadata={"error": str(exc)},
        )


# ---------------------------------------------------------------------------
# Platform metadata (Phase 13 SEO engine)
# ---------------------------------------------------------------------------

def _build_metadata_package(
    brief: SocialContentBrief,
    script_package: Any,
    *,
    content_format: str,
    narration: GeneratedAssetReference | None = None,
) -> Any:
    """Generate MetadataPackage via genesis.metadata engine."""
    from genesis.metadata.metadata_engine import generate_metadata_package

    affiliate_status = brief.affiliate_status or (
        "possible" if content_format == "affiliate_followup" else ""
    )
    fundraiser_status = brief.fundraiser_status or (
        "yes" if content_format == "fundraising_story" else ""
    )

    return generate_metadata_package(
        brief,
        script_package,
        platforms=brief.platforms,
        narration=narration,
        content_format=content_format,
        affiliate_status=affiliate_status,
        fundraiser_link_status=fundraiser_status,
        sponsorship_status=brief.sponsorship_status,
        link_status=brief.link_status,
        marketplace=brief.marketplace,
        retailer=brief.retailer,
        brand_name=brief.brand_name or "",
        product_name=brief.product_name or "",
    )


def _legacy_platform_metadata_from_package(metadata_package: Any) -> list[PlatformMetadata]:
    """Map MetadataPackage → workflow PlatformMetadata list (backward compatible)."""
    from genesis.metadata.metadata_engine import metadata_package_to_legacy_platform_list

    if metadata_package is None:
        return []

    legacy = metadata_package_to_legacy_platform_list(metadata_package)
    results: list[PlatformMetadata] = []
    for row in legacy:
        results.append(PlatformMetadata(
            platform=row["platform"],
            caption=row["caption"],
            hashtags=row.get("hashtags", []),
            cta=row.get("cta", ""),
            duration_hint=row.get("duration_hint", ""),
            aspect_ratio=row.get("aspect_ratio", "9:16"),
            notes=row.get("notes", ""),
        ))
    return results


def _build_storyboard_package(
    brief: SocialContentBrief,
    result: SocialWorkflowResult,
    *,
    content_format: str,
) -> Any:
    """Generate StoryboardPackage via genesis.visuals engine."""
    from genesis.visuals.storyboard_engine import generate_storyboard_package

    narration_path = ""
    if result.narration and result.narration.path:
        narration_path = result.narration.path

    return generate_storyboard_package(
        brief,
        result.script_package,
        metadata_package=result.metadata_package,
        script_text=result.script_text,
        narration_path=narration_path,
        content_format=content_format,
        platforms=brief.platforms,
    )


# ---------------------------------------------------------------------------
# Posting package writer
# ---------------------------------------------------------------------------

def write_posting_package(result: SocialWorkflowResult) -> PostingPackage:
    """
    Write all content package files to assets/runs/<job_id>/.

    Creates:
        brief.json              — SocialContentBrief as JSON
        script.txt              — Script text
        script_package.json     — Full ScriptPackage (hooks, sections, CTAs, …)
        overlay_captions.json   — Overlay caption list for video editing
        visual_plan.md          — Visual plan (from storyboard when available)
        storyboard.json         — Full storyboard package
        shot_plan.json          — Shot plan only
        visual_prompts.md       — Text-only AI/manual prompt cards
        filming_checklist.md    — On-set filming checklist
        metadata_pack.json      — Per-platform metadata array
        posting_checklist.md    — Manual posting checklist

    The narration MP3 lives in assets/audio/ and is referenced by path only;
    it is never duplicated here.

    Returns:
        A PostingPackage with all file paths populated.
    """
    run_dir = _RUNS_BASE / result.job_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # --- brief.json ---
    brief_path = run_dir / "brief.json"
    brief_path.write_text(result.brief.to_json(), encoding="utf-8")

    # --- script.txt ---
    script_path = run_dir / "script.txt"
    script_path.write_text(result.script_text or "", encoding="utf-8")

    # --- script_package.json ---
    script_pkg_path = run_dir / "script_package.json"
    if result.script_package is not None:
        try:
            pkg_json = result.script_package.to_json()
        except Exception:  # noqa: BLE001
            pkg_json = json.dumps({"status": "unserializable"}, indent=2)
    else:
        # Minimal marker for packages where script was provided externally
        pkg_json = json.dumps({
            "job_id": result.job_id,
            "script_source": result.script_source,
            "status": "not_generated",
            "note": "Script was provided externally; no ScriptPackage was generated.",
        }, indent=2)
    script_pkg_path.write_text(pkg_json, encoding="utf-8")

    # --- overlay_captions.json ---
    overlays_path = run_dir / "overlay_captions.json"
    if result.script_package is not None:
        try:
            captions = [c.to_dict() for c in getattr(result.script_package, "overlay_captions", [])]
        except Exception:  # noqa: BLE001
            captions = []
    else:
        captions = []
    overlays_json = json.dumps({"job_id": result.job_id, "captions": captions}, indent=2)
    overlays_path.write_text(overlays_json, encoding="utf-8")

    # --- storyboard outputs (Phase 14) ---
    storyboard_path = run_dir / "storyboard.json"
    shot_plan_path = run_dir / "shot_plan.json"
    visual_prompts_path = run_dir / "visual_prompts.md"
    filming_checklist_path = run_dir / "filming_checklist.md"

    if result.storyboard_package is not None and hasattr(result.storyboard_package, "to_json"):
        sb = result.storyboard_package
        storyboard_path.write_text(sb.to_json(), encoding="utf-8")
        shot_plan_path.write_text(
            json.dumps(sb.shot_plan.to_dict(), indent=2),
            encoding="utf-8",
        )
        from genesis.visuals.visual_prompt_engine import format_visual_prompts_md
        visual_prompts_path.write_text(
            format_visual_prompts_md(sb.visual_prompts, job_id=result.job_id),
            encoding="utf-8",
        )
        filming_lines = "\n".join(f"- [ ] {item}" for item in sb.filming_checklist)
        filming_checklist_path.write_text(
            f"# Filming Checklist — {result.job_id}\n\n{filming_lines}\n",
            encoding="utf-8",
        )
    else:
        storyboard_path.write_text(
            json.dumps({"job_id": result.job_id, "status": "skipped"}, indent=2),
            encoding="utf-8",
        )
        shot_plan_path.write_text(
            json.dumps({"job_id": result.job_id, "status": "skipped", "scenes": []}, indent=2),
            encoding="utf-8",
        )
        visual_prompts_path.write_text(
            f"# Visual Prompts — {result.job_id}\n\n_Storyboard not generated._\n",
            encoding="utf-8",
        )
        filming_checklist_path.write_text(
            f"# Filming Checklist — {result.job_id}\n\n- [ ] Run workflow with script package\n",
            encoding="utf-8",
        )

    # --- visual_plan.md (backward compatible) ---
    visual_plan_path = run_dir / "visual_plan.md"
    visual_plan_path.write_text(
        _build_visual_plan_md(result),
        encoding="utf-8",
    )

    # --- metadata_pack.json ---
    metadata_pack_path = run_dir / "metadata_pack.json"
    if result.metadata_package is not None and hasattr(result.metadata_package, "to_dict"):
        metadata_pack_body = result.metadata_package.to_dict()
        metadata_pack_body["generated_at"] = datetime.now(timezone.utc).isoformat()
        metadata_pack_body["platforms_legacy"] = [p.to_dict() for p in result.platform_metadata]
    else:
        metadata_pack_body = {
            "job_id": result.job_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "partial",
            "metadata_by_platform": {},
            "platforms_legacy": [p.to_dict() for p in result.platform_metadata],
        }
    metadata_pack_path.write_text(
        json.dumps(metadata_pack_body, indent=2),
        encoding="utf-8",
    )

    # --- posting_checklist.md ---
    checklist_path = run_dir / "posting_checklist.md"
    checklist_path.write_text(
        _build_posting_checklist_md(result),
        encoding="utf-8",
    )

    narration_path = ""
    if result.narration and result.narration.path:
        narration_path = result.narration.path

    package = PostingPackage(
        job_id=result.job_id,
        run_dir=str(run_dir),
        brief_path=str(brief_path),
        script_path=str(script_path),
        visual_plan_path=str(visual_plan_path),
        metadata_pack_path=str(metadata_pack_path),
        posting_checklist_path=str(checklist_path),
        narration_path=narration_path,
        script_package_path=str(script_pkg_path),
        overlay_captions_path=str(overlays_path),
        storyboard_path=str(storyboard_path),
        shot_plan_path=str(shot_plan_path),
        visual_prompts_path=str(visual_prompts_path),
        filming_checklist_path=str(filming_checklist_path),
    )

    logger.info("posting package written → %s", run_dir)
    return package


def _build_visual_plan_md(result: SocialWorkflowResult) -> str:
    if result.storyboard_package is not None and hasattr(result.storyboard_package, "shot_plan"):
        from genesis.visuals.filming_checklist import build_visual_plan_from_storyboard
        return build_visual_plan_from_storyboard(
            result.storyboard_package,
            script_source=result.script_source,
            platforms=result.brief.platforms,
        )

    brief = result.brief
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    platforms_str = ", ".join(platform_label(p) for p in brief.platforms)
    overlay_block = ""
    if result.script_package is not None:
        overlays = getattr(result.script_package, "overlay_captions", []) or []
        if overlays:
            rows = "\n".join(
                f"| {i+1} | {c.timing_hint} | {c.text} | {c.purpose} |"
                for i, c in enumerate(overlays)
            )
            overlay_block = (
                "\n## Overlay Captions\n\n| # | Timing | Text | Purpose |\n"
                "|---|--------|------|---------|\n" + rows + "\n"
            )
    return textwrap.dedent(f"""\
        # Visual Plan — {result.job_id}

        **Generated:** {ts}
        **Platforms:** {platforms_str}
        **Script source:** {result.script_source}

        ## Concept

        {brief.idea}
        {overlay_block}
        _Storyboard not generated — re-run with script package for full shot plan._
    """)


def _build_posting_checklist_md(result: SocialWorkflowResult) -> str:
    brief = result.brief
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    narration_line = (
        f"- Narration audio: `{result.narration.path}`"
        if result.narration and result.narration.path
        else "- Narration audio: not yet generated (run with narration_enabled=True)"
    )

    script_engine_line = (
        f"- Script engine: {result.script_source}"
        + (f" (model: {result.script_package.llm_model})"
           if result.script_package and getattr(result.script_package, "llm_model", None)
           else "")
    )

    platform_sections = []
    mp = result.metadata_package
    by_plat = getattr(mp, "metadata_by_platform", None) or {} if mp else {}

    for meta in result.platform_metadata:
        defs = platform_defaults(meta.platform)
        rec = defs.get("recommended_duration_sec", "?")
        label = platform_label(meta.platform)
        rich = by_plat.get(meta.platform) if isinstance(by_plat, dict) else None
        title_line = ""
        pinned_line = ""
        disc_line = ""
        warn_line = ""
        if rich is not None:
            if getattr(rich, "title", None):
                title_line = f"- [ ] Title: {rich.title}\n"
            if getattr(rich, "pinned_comment", None):
                pinned_line = f"- [ ] Pinned comment: {rich.pinned_comment}\n"
            if getattr(rich, "disclosure", None) and rich.disclosure.short_text:
                disc_line = f"- [ ] Disclosure: {rich.disclosure.short_text}\n"
            if getattr(rich, "warnings", None) and rich.warnings:
                warn_line = f"- [ ] Warnings: {'; '.join(rich.warnings[:3])}\n"
        platform_sections.append(textwrap.dedent(f"""\
            ### {label}

            {title_line}- [ ] Caption reviewed (see `metadata_pack.json`)
            - [ ] Hashtags: {', '.join(meta.hashtags[:5])}{'…' if len(meta.hashtags) > 5 else ''}
            {pinned_line}{disc_line}{warn_line}- [ ] Duration checked (~{rec}s recommended)
            - [ ] Aspect ratio: {meta.aspect_ratio}
            - [ ] Thumbnail / cover frame selected
            - [ ] Scheduled or posted
        """))

    platforms_block = "\n".join(platform_sections)

    return textwrap.dedent(f"""\
        # Posting Checklist — {result.job_id}

        **Generated:** {ts}
        {script_engine_line}

        ## Pre-Flight

        - [ ] Script reviewed and approved (`script.txt`)
            - [ ] Visual plan reviewed (`visual_plan.md`)
            - [ ] Storyboard reviewed (`storyboard.json`, `shot_plan.json`)
            - [ ] Filming checklist reviewed (`filming_checklist.md`)
            - [ ] Overlay captions reviewed (`overlay_captions.json`)
        - [ ] Script package reviewed (`script_package.json`)
        {narration_line}
        - [ ] All assets exported at correct resolution

        ## Per-Platform

        {platforms_block}
        ## Notes

        _Posting checklist generated by Genesis Studio Phase 13 metadata engine._
        _Trend lookup and auto-posting are reserved for a later phase._
    """)


# ---------------------------------------------------------------------------
# Main workflow entry point
# ---------------------------------------------------------------------------

def run_social_media_workflow(
    idea: str,
    *,
    script_text: str | None = None,
    job_id: str | None = None,
    narration_enabled: bool = True,
    platforms: list[str] | None = None,
    audience: str = "",
    content_goal: str = "",
    tone: str = "engaging",
    offer: str = "",
    cta: str = "",
    content_format: str = "product_demo",
    write_package: bool = True,
    narration_kwargs: dict[str, Any] | None = None,
) -> SocialWorkflowResult:
    """
    Run the full social media content workflow from idea to posting package.

    Args:
        idea:               Core idea or topic.
        script_text:        Pre-written script. If None the script engine runs.
        job_id:             Unique run ID; auto-generated if omitted.
        narration_enabled:  Whether to call generate_voice via pipeline narration.
        platforms:          Target platforms (default: all five).
        audience:           Target audience description.
        content_goal:       e.g. "awareness", "conversion", "affiliate follow-up".
        tone:               Tone of voice.
        offer:              Offer, product, or value proposition.
        cta:                Call-to-action text (ALL_CAPS keyword triggers comment CTA).
        content_format:     One of the CONTENT_FORMATS in genesis.creative.script_models.
        write_package:      Whether to write posting package files to disk.
        narration_kwargs:   Extra kwargs forwarded to run_post_script_steps().

    Returns:
        SocialWorkflowResult with all populated fields.
    """
    run_id = job_id or uuid.uuid4().hex[:12]
    logger.info("starting social media workflow job=%s idea=%.60s", run_id, idea)

    errors: list[str] = []

    # Step 1 — brief
    brief = create_social_content_brief(
        idea,
        job_id=run_id,
        platforms=platforms,
        audience=audience,
        content_goal=content_goal,
        tone=tone,
        offer=offer,
        cta=cta,
    )

    # Step 2 — script
    script_package = None
    if script_text and script_text.strip():
        final_script = script_text.strip()
        script_source = "provided"
        logger.info("job=%s: using provided script (%d chars)", run_id, len(final_script))
    else:
        final_script, script_source, script_package = _generate_script_with_engine(
            brief, content_format
        )
        if script_source == "placeholder":
            errors.append("script engine unavailable — placeholder script used")

    result = SocialWorkflowResult(
        job_id=run_id,
        status=WorkflowStatus.SCRIPT_READY,
        brief=brief,
        script_text=final_script,
        script_source=script_source,
        script_package=script_package,
    )

    # Step 3 — narration
    if narration_enabled:
        try:
            narration_ref = _run_narration_step(
                final_script,
                job_id=run_id,
                narration_kwargs=narration_kwargs or {},
            )
        except Exception as _narr_exc:  # noqa: BLE001
            logger.warning("job=%s: narration step raised: %s — continuing", run_id, _narr_exc)
            narration_ref = GeneratedAssetReference(
                asset_id=f"narration-{run_id}",
                path="",
                asset_type="audio",
                provider="elevenlabs",
                status=NarrationStatus.FAILED,
                metadata={"error": str(_narr_exc)},
            )
        result.narration = narration_ref
        if narration_ref.status == NarrationStatus.FAILED:
            errors.append(f"narration failed: {narration_ref.metadata.get('error', 'unknown')}")
            logger.warning("job=%s: narration failed — workflow continues", run_id)
    else:
        result.narration = GeneratedAssetReference(
            asset_id=f"narration-{run_id}",
            path="",
            asset_type="audio",
            provider="elevenlabs",
            status=NarrationStatus.SKIPPED,
            metadata={"reason": "narration_disabled"},
        )

    # Step 4 — platform metadata (Phase 13 SEO engine)
    try:
        result.metadata_package = _build_metadata_package(
            brief,
            result.script_package,
            content_format=content_format,
            narration=result.narration,
        )
        result.platform_metadata = _legacy_platform_metadata_from_package(
            result.metadata_package
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("job=%s: metadata engine failed: %s", run_id, exc)
        errors.append(f"metadata generation failed: {exc}")
        result.metadata_package = None
        result.platform_metadata = []

    # Step 4b — visual storyboard (Phase 14)
    try:
        result.storyboard_package = _build_storyboard_package(
            brief, result, content_format=content_format
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("job=%s: storyboard engine failed: %s", run_id, exc)
        errors.append(f"storyboard generation failed: {exc}")
        result.storyboard_package = None

    # Step 5 — write package
    if write_package:
        try:
            result.posting_package = write_posting_package(result)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"package write failed: {exc}")
            logger.warning("job=%s: package write failed: %s", run_id, exc)

    # Step 6 — final status
    result.errors = errors
    if errors:
        result.status = WorkflowStatus.PARTIAL
    else:
        result.status = WorkflowStatus.COMPLETE

    logger.info("workflow complete job=%s status=%s source=%s", run_id, result.status, script_source)
    return result
