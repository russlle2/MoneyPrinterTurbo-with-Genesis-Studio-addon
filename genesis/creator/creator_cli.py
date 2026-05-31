"""
Genesis Studio — Master creator CLI.

Usage:
    python -m genesis.creator.creator_cli create "idea" --template affiliate_product --platform tiktok --brand bold_viral
    python -m genesis.creator.creator_cli templates
    python -m genesis.creator.creator_cli template-info affiliate_product
    python -m genesis.creator.creator_cli rerender <job_id> --platform tiktok --brand bold_viral
    python -m genesis.creator.creator_cli status <job_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_RUNS_BASE = _REPO / "assets" / "runs"

from genesis.creator.pipeline_runner import run_creator_pipeline  # noqa: E402
from genesis.video.render_run import render_run_video  # noqa: E402


def _print(msg: str) -> None:
    print(msg)


def _header(title: str) -> None:
    bar = "─" * min(len(title) + 4, 72)
    _print(f"\n{bar}")
    _print(f"  {title}")
    _print(f"{bar}")


# ─── create ───────────────────────────────────────────────────────────────────

def cmd_create(args: argparse.Namespace) -> int:
    from genesis.creator.creator_models import CreatorRunRequest
    from genesis.creator.project_templates import get_template_or_default

    tmpl = get_template_or_default(args.template)
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    exports_base = Path(args.exports_base) if getattr(args, "exports_base", "") else None

    req = CreatorRunRequest(
        idea=args.idea,
        job_id=getattr(args, "job_id", "") or "",
        template=args.template,
        primary_platform=getattr(args, "platform", "tiktok") or "tiktok",
        brand_preset=getattr(args, "brand", None) or tmpl.brand_preset,
        media_path=getattr(args, "media", "") or "",
        music_path=getattr(args, "music", "") or "",
        narration_enabled=not getattr(args, "no_narration", False),
        render_enabled=not getattr(args, "no_render", False),
        export_enabled=getattr(args, "export", False),
        options={
            "ai_visual_fill": getattr(args, "ai_visual_fill", False),
            "visual_provider": getattr(args, "visual_provider", "prompt_card_only"),
            "visual_asset_type": getattr(args, "visual_asset_type", ""),
        },
        content_format=getattr(args, "content_format", "") or "",
        audience=getattr(args, "audience", "") or "",
        tone=getattr(args, "tone", "") or "",
        cta=getattr(args, "cta", "") or "",
    )

    _header(f"Genesis Creator — {req.template}")
    _print(f"  Idea:     {req.idea[:70]}")
    _print(f"  Platform: {req.primary_platform}")
    _print(f"  Brand:    {req.brand_preset}")

    kw: dict = {}
    if runs_base:
        kw["runs_base"] = runs_base
    if exports_base:
        kw["exports_base"] = exports_base

    result = run_creator_pipeline(req, **kw)

    _print(f"\n  Status:  {result.status}")
    _print(f"  Job ID:  {result.job_id}")
    _print(f"  Run dir: {result.run_dir}")
    if result.draft_video_path:
        _print(f"  Video:   {result.draft_video_path}")
    if result.export_dir:
        _print(f"  Export:  {result.export_dir}")
    if result.review_html_path:
        _print(f"  Review:  {result.review_html_path}")

    _print("\n  Steps:")
    for s in result.steps:
        mark = "✓" if s.status == "complete" else ("~" if s.status in ("partial", "skipped") else "✗")
        _print(f"    {mark} {s.step_name:<22} {s.status}")
    if result.warnings:
        _print("\n  Warnings:")
        for w in result.warnings[:5]:
            _print(f"    ! {w}")
    return 0 if result.status in ("complete", "partial") else 1


# ─── templates ────────────────────────────────────────────────────────────────

def cmd_templates(args: argparse.Namespace) -> int:
    from genesis.creator.project_templates import TEMPLATES
    _header("Available templates")
    for name, tmpl in TEMPLATES.items():
        _print(f"  {name:<28} {tmpl.brand_preset:<16} {tmpl.content_format}")
    return 0


# ─── template-info ────────────────────────────────────────────────────────────

def cmd_template_info(args: argparse.Namespace) -> int:
    from genesis.creator.project_templates import get_template
    tmpl = get_template(args.template_name)
    if not tmpl:
        _print(f"Template not found: {args.template_name}")
        return 1
    _header(f"Template: {tmpl.name}")
    _print(f"  Format:      {tmpl.content_format}")
    _print(f"  Brand:       {tmpl.brand_preset}")
    _print(f"  Audience:    {tmpl.audience}")
    _print(f"  Tone:        {tmpl.tone}")
    _print(f"  CTA style:   {tmpl.cta_style}")
    _print(f"  Music:       {tmpl.music_style}")
    _print(f"  Disclosure:  {tmpl.disclosure_expectation}")
    _print(f"  Platforms:   {', '.join(tmpl.platform_defaults)}")
    _print("\n  Suggested filenames:")
    for f in tmpl.suggested_filenames:
        _print(f"    • {f}")
    if tmpl.notes:
        _print(f"\n  Notes: {tmpl.notes}")
    return 0


# ─── rerender ─────────────────────────────────────────────────────────────────

def cmd_rerender(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else None
    kw: dict = dict(
        target_platform=getattr(args, "platform", "tiktok") or "tiktok",
        brand_preset=getattr(args, "brand", "clean_creator") or "clean_creator",
        audio_mix_enabled=bool(getattr(args, "music", "")),
        music_path=getattr(args, "music", "") or None,
        music_volume=float(getattr(args, "music_volume", 0.18) or 0.18),
        render_enabled=True,
        transition_preset=getattr(args, "transition_preset", "auto") or "auto",
        beat_sync_enabled=not getattr(args, "no_beat_sync", False),
        motion_effects_enabled=not getattr(args, "no_motion_effects", False),
    )
    if runs_base:
        kw["runs_base"] = runs_base

    if getattr(args, "ai_visual_fill", False):
        from genesis.ai_visuals.visual_fill import run_visual_fill_for_run
        run_visual_fill_for_run(
            args.job_id,
            runs_base=runs_base,
            provider_mode=getattr(args, "visual_provider", "prompt_card_only"),
        )

    _header(f"Rerender: {args.job_id}")
    result = render_run_video(args.job_id, **kw)
    _print(f"  Status:  {result.status}")
    if result.output_path:
        _print(f"  Output:  {result.output_path}")
    for w in result.warnings[:3]:
        _print(f"  ! {w}")
    return 0 if result.status in ("complete", "partial") else 1


# ─── status ───────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    run_dir = runs_base / args.job_id
    summary_path = run_dir / "creator_run_summary.json"

    if summary_path.is_file():
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        _header(f"Status: {args.job_id}")
        _print(f"  Status:  {data.get('status')}")
        _print(f"  Video:   {data.get('draft_video_path') or 'not rendered'}")
        _print(f"  Export:  {data.get('export_dir') or 'not exported'}")
        _print(f"  Steps:")
        for s in data.get("steps", []):
            mark = "✓" if s["status"] == "complete" else ("~" if s["status"] in ("partial", "skipped") else "✗")
            _print(f"    {mark} {s['step_name']:<22} {s['status']}")
        return 0

    # Fallback to review summary
    from genesis.review.run_loader import load_review_package
    pkg = load_review_package(args.job_id, runs_base=runs_base)
    rs = pkg.run_summary
    _header(f"Status: {args.job_id}")
    _print(f"  Status:  {rs.status}")
    _print(f"  Video:   {'yes' if rs.has_draft_video else 'no'}")
    return 0 if pkg.status != "failed" else 1


# ─── CLI wiring ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="genesis.creator.creator_cli",
                                description="Genesis Studio master creator CLI")
    p.add_argument("--runs-base", dest="runs_base", default="")
    p.add_argument("--exports-base", dest="exports_base", default="")
    sub = p.add_subparsers(dest="command")

    cr = sub.add_parser("create", help="Run full creator pipeline")
    cr.add_argument("idea")
    cr.add_argument("--template", default="affiliate_product")
    cr.add_argument("--job-id", dest="job_id", default="")
    cr.add_argument("--platform", default="tiktok")
    cr.add_argument("--brand", default="")
    cr.add_argument("--media", default="")
    cr.add_argument("--music", default="")
    cr.add_argument("--content-format", dest="content_format", default="")
    cr.add_argument("--audience", default="")
    cr.add_argument("--tone", default="")
    cr.add_argument("--cta", default="")
    cr.add_argument("--no-narration", action="store_true")
    cr.add_argument("--no-render", action="store_true")
    cr.add_argument("--export", action="store_true")
    cr.add_argument("--ai-visual-fill", dest="ai_visual_fill", action="store_true")
    cr.add_argument("--visual-provider", dest="visual_provider", default="prompt_card_only")
    cr.add_argument("--visual-asset-type", dest="visual_asset_type", default="")

    sub.add_parser("templates", help="List available templates")

    ti = sub.add_parser("template-info", help="Show template defaults")
    ti.add_argument("template_name")

    rr = sub.add_parser("rerender", help="Rerender an existing run")
    rr.add_argument("job_id")
    rr.add_argument("--platform", default="tiktok")
    rr.add_argument("--brand", default="clean_creator")
    rr.add_argument("--music", default="")
    rr.add_argument("--music-volume", dest="music_volume", type=float, default=0.18)
    rr.add_argument("--transition-preset", dest="transition_preset", default="auto")
    rr.add_argument("--no-beat-sync", action="store_true")
    rr.add_argument("--no-motion-effects", action="store_true")
    rr.add_argument("--ai-visual-fill", dest="ai_visual_fill", action="store_true")
    rr.add_argument("--visual-provider", dest="visual_provider", default="prompt_card_only")

    st = sub.add_parser("status", help="Show run status")
    st.add_argument("job_id")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "create": cmd_create,
        "templates": cmd_templates,
        "template-info": cmd_template_info,
        "rerender": cmd_rerender,
        "status": cmd_status,
    }
    if not args.command:
        parser.print_help()
        return 0
    handler = commands.get(args.command)
    if not handler:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
