"""Genesis Studio — AI visual fill orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from genesis.ai_visuals.generated_asset_manifest import (
    build_generated_visuals_manifest,
    load_generated_scene_assignments,
    update_media_manifest_with_generated_assets,
    write_generated_visuals_manifest,
)
from genesis.ai_visuals.missing_scene_detector import (
    detect_missing_scenes,
    read_storyboard_scenes,
)
from genesis.ai_visuals.prompt_builder import build_visual_generation_prompts
from genesis.ai_visuals.provider_router import generate_visual_asset, visual_provider_ready
from genesis.ai_visuals.visual_models import VisualFillResult, VisualFillStatus
from genesis.utils.config_loader import load_ai_visuals_config

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNS_BASE = _REPO_ROOT / "assets" / "runs"


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def write_visual_fill_report(
    run_dir: Path,
    result: VisualFillResult,
) -> Path:
    lines = [
        f"# AI Visual Fill Report — {result.job_id}",
        "",
        f"**Status:** {result.status}",
        f"**Missing scenes:** {len(result.missing_scenes)}",
        f"**Prompts:** {len(result.prompts)}",
        f"**Generated assets:** {len(result.generated_assets)}",
        "",
        "## Missing scenes",
        "",
    ]
    for m in result.missing_scenes:
        lines.append(f"- `{m.scene_id}` ({m.priority}) — {m.reason_missing} → {m.fallback_type}")
    lines.extend(["", "## Generated assets", ""])
    for a in result.generated_assets:
        lines.append(f"- `{a.scene_id}`: {a.asset_type} via {a.provider} — {a.status}")
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        for w in result.warnings:
            lines.append(f"- {w}")
    path = run_dir / "ai_visual_fill_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def detect_and_prompt_missing_scenes(
    run_dir: Path,
    *,
    brand_preset: str = "clean_creator",
    content_format: str = "",
    platform: str = "tiktok",
    force: bool = False,
    config: dict[str, Any] | None = None,
) -> tuple[list, list]:
    cfg = config or load_ai_visuals_config()
    missing = detect_missing_scenes(run_dir, force=force)
    scenes = read_storyboard_scenes(run_dir)
    by_id = {s.get("scene_id"): s for s in scenes if s.get("scene_id")}
    prompts = build_visual_generation_prompts(
        missing,
        by_id,
        brand_preset=brand_preset,
        content_format=content_format,
        platform=platform,
        default_asset_type=cfg.get("default_asset_type", "image"),
        duration_seconds=float(cfg.get("duration_seconds", 4)),
    )
    return missing, prompts


def generate_assets_for_missing_scenes(
    run_dir: Path,
    prompts: list,
    *,
    provider_mode: str | None = None,
    config: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> list:
    cfg = config or load_ai_visuals_config()
    repo_root = repo_root or _REPO_ROOT
    assets = []
    for prompt in prompts:
        try:
            asset = generate_visual_asset(
                prompt, run_dir,
                provider_mode=provider_mode,
                config=cfg,
                repo_root=repo_root,
            )
            assets.append(asset)
        except Exception as exc:  # noqa: BLE001
            from genesis.ai_visuals.provider_router import generate_prompt_card_only
            card = generate_prompt_card_only(prompt, run_dir / cfg.get("output_dir", "generated_visuals"))
            card.warnings.append(str(exc))
            card.status = VisualFillStatus.PARTIAL
            assets.append(card)
    return assets


def integrate_generated_assets_with_run(
    run_dir: Path,
    generated_assets: list,
    *,
    repo_root: Path | None = None,
) -> dict[str, str]:
    repo_root = repo_root or _REPO_ROOT
    assignments: dict[str, str] = {}
    for a in generated_assets:
        if a.asset_type in ("image", "video") and a.path:
            p = Path(a.path)
            if p.is_file():
                try:
                    assignments[a.scene_id] = str(p.resolve().relative_to(repo_root.resolve()))
                except ValueError:
                    assignments[a.scene_id] = str(p)
    if assignments:
        update_media_manifest_with_generated_assets(run_dir, assignments, repo_root=repo_root)
    return assignments


def run_visual_fill_for_run(
    job_id: str,
    *,
    runs_base: Path | None = None,
    repo_root: Path | None = None,
    provider_mode: str | None = None,
    asset_type: str | None = None,
    brand_preset: str = "clean_creator",
    content_format: str = "",
    platform: str = "tiktok",
    force: bool = False,
    generate_assets: bool = True,
) -> VisualFillResult:
    runs_base = runs_base or _RUNS_BASE
    repo_root = repo_root or _REPO_ROOT
    run_dir = runs_base / job_id
    cfg = load_ai_visuals_config()
    if asset_type:
        cfg = {**cfg, "default_asset_type": asset_type}
    # Forward brand/content context so providers (e.g. Pollinations) apply correct style
    cfg = {**cfg, "brand_preset": brand_preset, "content_format": content_format}

    warnings: list[str] = []
    if not run_dir.is_dir():
        return VisualFillResult(
            job_id=job_id,
            missing_scenes=[],
            prompts=[],
            generated_assets=[],
            manifest_path="",
            status=VisualFillStatus.FAILED,
            warnings=[f"run folder not found: {run_dir}"],
        )

    brief = _safe_json(run_dir / "brief.json")
    content_format = content_format or brief.get("content_format", "")
    brand_preset = brand_preset or brief.get("brand_preset", "clean_creator")

    mode = provider_mode or cfg.get("provider_mode", "prompt_card_only")
    ready, msg = visual_provider_ready(mode, cfg)
    if not ready:
        warnings.append(msg)

    missing, prompts = detect_and_prompt_missing_scenes(
        run_dir,
        brand_preset=brand_preset,
        content_format=content_format,
        platform=platform,
        force=force,
        config=cfg,
    )

    if not missing:
        manifest = build_generated_visuals_manifest(
            job_id, missing_scenes=[], prompts=[], generated_assets=[],
            status=VisualFillStatus.SKIPPED,
            notes=["no missing scenes detected"],
        )
        mpath = write_generated_visuals_manifest(run_dir, manifest)
        result = VisualFillResult(
            job_id=job_id,
            missing_scenes=[],
            prompts=[],
            generated_assets=[],
            manifest_path=str(mpath),
            status=VisualFillStatus.SKIPPED,
            warnings=warnings,
        )
        write_visual_fill_report(run_dir, result)
        return result

    generated: list = []
    if generate_assets and (
        cfg.get("enabled")
        or mode in (
            "prompt_card_only", "manual_chatgpt", "hero_shot_provider",
            "auto", "local_comfyui",
        )
    ):
        generated = generate_assets_for_missing_scenes(
            run_dir, prompts, provider_mode=mode, config=cfg, repo_root=repo_root,
        )
        integrate_generated_assets_with_run(run_dir, generated, repo_root=repo_root)
    else:
        from genesis.ai_visuals.provider_router import generate_prompt_card_only
        out_dir = run_dir / cfg.get("output_dir", "generated_visuals")
        for p in prompts:
            generated.append(generate_prompt_card_only(p, out_dir))

    status = VisualFillStatus.COMPLETE
    if any(a.status == VisualFillStatus.FAILED for a in generated):
        status = VisualFillStatus.PARTIAL
    if any(a.status == VisualFillStatus.PARTIAL for a in generated):
        status = VisualFillStatus.PARTIAL

    manifest = build_generated_visuals_manifest(
        job_id,
        missing_scenes=missing,
        prompts=prompts,
        generated_assets=generated,
        status=status,
        warnings=warnings,
    )
    mpath = write_generated_visuals_manifest(run_dir, manifest)
    result = VisualFillResult(
        job_id=job_id,
        missing_scenes=missing,
        prompts=prompts,
        generated_assets=generated,
        manifest_path=str(mpath),
        status=status,
        warnings=warnings,
        notes=[f"provider_mode={mode}"],
    )
    write_visual_fill_report(run_dir, result)
    return result
