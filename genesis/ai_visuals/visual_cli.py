"""
Genesis Studio — AI visual fill CLI.

Usage:
    python -m genesis.ai_visuals.visual_cli detect <job_id>
    python -m genesis.ai_visuals.visual_cli prompts <job_id>
    python -m genesis.ai_visuals.visual_cli fill <job_id>
    python -m genesis.ai_visuals.visual_cli fill-and-render <job_id> --platform tiktok --brand bold_viral
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from genesis.ai_visuals.visual_fill import (  # noqa: E402
    detect_and_prompt_missing_scenes,
    detect_missing_scenes,
    run_visual_fill_for_run,
)
from genesis.ai_visuals.provider_router import generate_prompt_card_only  # noqa: E402
from genesis.utils.config_loader import load_ai_visuals_config  # noqa: E402

_RUNS_BASE = _REPO / "assets" / "runs"


def _print(msg: str) -> None:
    print(msg)


def _header(title: str) -> None:
    bar = "-" * min(len(title) + 4, 72)
    _print(f"\n{bar}\n  {title}\n{bar}")


def cmd_detect(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    run_dir = runs_base / args.job_id
    missing = detect_missing_scenes(run_dir, force=getattr(args, "force", False))
    _header(f"Missing scenes — {args.job_id}")
    _print(f"  Found: {len(missing)}")
    for m in missing:
        _print(f"    {m.scene_id:<16} {m.priority:<8} {m.fallback_type}")
    return 0


def cmd_prompts(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    run_dir = runs_base / args.job_id
    cfg = load_ai_visuals_config()
    missing, prompts = detect_and_prompt_missing_scenes(
        run_dir,
        brand_preset=getattr(args, "brand", "clean_creator") or "clean_creator",
        force=getattr(args, "force", False),
    )
    out_dir = run_dir / cfg.get("output_dir", "generated_visuals")
    for p in prompts:
        generate_prompt_card_only(p, out_dir)
    _header(f"Prompt cards — {args.job_id}")
    _print(f"  Missing: {len(missing)}  Written: {len(prompts)} → {out_dir}")
    return 0


def cmd_fill(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    result = run_visual_fill_for_run(
        args.job_id,
        runs_base=runs_base,
        provider_mode=getattr(args, "provider", None),
        asset_type=getattr(args, "asset_type", None),
        brand_preset=getattr(args, "brand", "clean_creator") or "clean_creator",
        platform=getattr(args, "platform", "tiktok") or "tiktok",
        force=getattr(args, "force", False),
    )
    _header(f"Visual fill — {args.job_id}")
    _print(f"  Status:   {result.status}")
    _print(f"  Missing:  {len(result.missing_scenes)}")
    _print(f"  Assets:   {len(result.generated_assets)}")
    _print(f"  Manifest: {result.manifest_path}")
    for w in result.warnings[:5]:
        _print(f"  ! {w}")
    return 0 if result.status != "failed" else 1


def cmd_fill_and_render(args: argparse.Namespace) -> int:
    runs_base = Path(args.runs_base) if getattr(args, "runs_base", "") else _RUNS_BASE
    fill = run_visual_fill_for_run(
        args.job_id,
        runs_base=runs_base,
        provider_mode=getattr(args, "provider", None),
        asset_type=getattr(args, "asset_type", None),
        brand_preset=getattr(args, "brand", "clean_creator") or "clean_creator",
        platform=getattr(args, "platform", "tiktok") or "tiktok",
        force=getattr(args, "force", False),
    )
    from genesis.video.render_run import render_run_video

    _header(f"Render — {args.job_id}")
    render = render_run_video(
        args.job_id,
        runs_base=runs_base,
        target_platform=getattr(args, "platform", "tiktok") or "tiktok",
        brand_preset=getattr(args, "brand", "clean_creator") or "clean_creator",
        render_enabled=True,
    )
    _print(f"  Fill:   {fill.status}")
    _print(f"  Render: {render.status}")
    if render.output_path:
        _print(f"  Video:  {render.output_path}")
    return 0 if render.status in ("complete", "partial") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="genesis.ai_visuals.visual_cli")
    p.add_argument("--runs-base", dest="runs_base", default="")
    p.add_argument("--brand", default="clean_creator")
    p.add_argument("--platform", default="tiktok")
    p.add_argument("--provider", default="")
    p.add_argument("--asset-type", dest="asset_type", default="")
    p.add_argument("--force", action="store_true")
    sub = p.add_subparsers(dest="command")

    d = sub.add_parser("detect", help="Detect missing scene media")
    d.add_argument("job_id")
    pr = sub.add_parser("prompts", help="Write prompt cards only")
    pr.add_argument("job_id")
    f = sub.add_parser("fill", help="Full visual fill pipeline")
    f.add_argument("job_id")
    fr = sub.add_parser("fill-and-render", help="Fill then render draft video")
    fr.add_argument("job_id")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    handlers = {
        "detect": cmd_detect,
        "prompts": cmd_prompts,
        "fill": cmd_fill,
        "fill-and-render": cmd_fill_and_render,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
