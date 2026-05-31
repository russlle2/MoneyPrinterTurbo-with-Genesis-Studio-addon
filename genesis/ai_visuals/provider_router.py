"""Genesis Studio — Route visual generation to local/manual providers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from genesis.ai_visuals.visual_models import GeneratedVisualAsset, VisualFillStatus, VisualGenerationPrompt
from genesis.utils.config_loader import load_ai_visuals_config

_REPO_ROOT = Path(__file__).resolve().parents[2]
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_VIDEO_EXT = {".mp4", ".mov", ".webm"}


def visual_provider_ready(
    provider_mode: str,
    config: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    cfg = config or load_ai_visuals_config()
    mode = (provider_mode or cfg.get("provider_mode", "prompt_card_only")).lower()

    if mode in ("disabled", "prompt_card_only", "manual_chatgpt"):
        return True, ""
    if mode == "hero_shot_provider":
        return True, ""
    if mode == "local_comfyui":
        if not cfg.get("allow_local_comfyui"):
            return False, "allow_local_comfyui is false in config"
        return True, ""
    if mode == "auto":
        return True, ""
    return True, ""


def choose_visual_provider(
    *,
    provider_mode: str | None = None,
    config: dict[str, Any] | None = None,
    asset_type: str = "image",
) -> str:
    cfg = config or load_ai_visuals_config()
    mode = (provider_mode or cfg.get("provider_mode", "prompt_card_only")).lower()

    if not cfg.get("enabled") and mode == "auto":
        return "prompt_card_only"

    if mode == "auto":
        if asset_type == "video" and cfg.get("allow_local_comfyui"):
            return "hero_shot_provider"
        return "prompt_card_only"

    if mode == "local_comfyui" and not cfg.get("allow_local_comfyui"):
        return "prompt_card_only"

    if mode in ("openai", "external_paid") and not cfg.get("allow_external_paid"):
        return "prompt_card_only"

    return mode


def generate_prompt_card_only(
    prompt: VisualGenerationPrompt,
    out_dir: Path,
) -> GeneratedVisualAsset:
    out_dir.mkdir(parents=True, exist_ok=True)
    card = out_dir / f"{prompt.scene_id}_prompt.md"
    card.write_text(
        f"# Visual Prompt — {prompt.scene_id}\n\n"
        f"**Type:** {prompt.prompt_type}\n"
        f"**Aspect:** {prompt.aspect_ratio}\n"
        f"**Duration:** {prompt.duration_seconds}s\n\n"
        f"## Prompt\n\n{prompt.prompt_text}\n\n"
        f"## Negative\n\n{prompt.negative_prompt}\n\n"
        f"## Safety\n\n{prompt.safety_notes}\n\n"
        f"## Style\n\n{prompt.style_hint}\n",
        encoding="utf-8",
    )
    return GeneratedVisualAsset(
        asset_id=f"card_{prompt.scene_id}",
        scene_id=prompt.scene_id,
        prompt_id=prompt.prompt_id,
        asset_type="prompt_card",
        provider="prompt_card_only",
        path=str(card),
        width=1080,
        height=1920,
        duration_seconds=prompt.duration_seconds,
        status=VisualFillStatus.COMPLETE,
        notes=["manual generation required"],
    )


def generate_with_hero_shot_provider(
    prompt: VisualGenerationPrompt,
    output_path: Path,
    *,
    mode: str = "auto",
) -> GeneratedVisualAsset:
    warnings: list[str] = []
    try:
        from genesis.integrations.hero_shot_provider import generate_hero_shot

        result_path = generate_hero_shot(
            prompt.prompt_text,
            str(output_path),
            mode=mode if mode in ("auto", "local_cogvideox", "manual_chatgpt") else "auto",
            scene_id=prompt.scene_id,
            duration_seconds=int(prompt.duration_seconds or 4),
            aspect_ratio=prompt.aspect_ratio,
            style_notes=prompt.style_hint,
        )
        p = Path(result_path)
        is_video = p.suffix.lower() in _VIDEO_EXT and p.is_file()
        is_card = p.suffix.lower() == ".md"
        status = VisualFillStatus.COMPLETE if is_video else VisualFillStatus.PARTIAL
        if is_card:
            warnings.append("hero_shot returned prompt card — import video manually")
        return GeneratedVisualAsset(
            asset_id=f"gen_{prompt.scene_id}",
            scene_id=prompt.scene_id,
            prompt_id=prompt.prompt_id,
            asset_type="video" if is_video else "prompt_card",
            provider="hero_shot_provider",
            path=str(p),
            width=1080,
            height=1920,
            duration_seconds=prompt.duration_seconds,
            status=status,
            warnings=warnings,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(str(exc))
        card = generate_prompt_card_only(prompt, output_path.parent)
        card.warnings = warnings
        card.status = VisualFillStatus.PARTIAL
        return card


def generate_with_local_comfyui_if_available(
    prompt: VisualGenerationPrompt,
    output_path: Path,
) -> GeneratedVisualAsset | None:
    cfg = load_ai_visuals_config()
    if not cfg.get("allow_local_comfyui"):
        return None
    return generate_with_hero_shot_provider(
        prompt, output_path, mode="local_cogvideox",
    )


def validate_generated_asset(asset: GeneratedVisualAsset) -> list[str]:
    warnings: list[str] = []
    if asset.asset_type in ("image", "video") and asset.path:
        p = Path(asset.path)
        if not p.is_file():
            warnings.append(f"asset file missing: {asset.path}")
    return warnings


def generate_visual_asset(
    prompt: VisualGenerationPrompt,
    run_dir: Path,
    *,
    provider_mode: str | None = None,
    config: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> GeneratedVisualAsset:
    """Generate or write prompt card for one scene."""
    cfg = config or load_ai_visuals_config()
    repo_root = repo_root or _REPO_ROOT
    out_dir = run_dir / cfg.get("output_dir", "generated_visuals")
    mode = choose_visual_provider(provider_mode=provider_mode, config=cfg, asset_type=prompt.provider_hint)

    if mode == "disabled":
        return GeneratedVisualAsset(
            asset_id=f"skip_{prompt.scene_id}",
            scene_id=prompt.scene_id,
            prompt_id=prompt.prompt_id,
            asset_type="skipped",
            provider="disabled",
            path="",
            width=0,
            height=0,
            duration_seconds=0,
            status=VisualFillStatus.SKIPPED,
        )

    ext = ".mp4" if prompt.provider_hint == "video" or prompt.duration_seconds > 0 else ".png"
    out_path = out_dir / f"{prompt.scene_id}_generated{ext}"

    if mode in ("prompt_card_only", "manual_chatgpt"):
        return generate_prompt_card_only(prompt, out_dir)

    if mode == "hero_shot_provider":
        return generate_with_hero_shot_provider(prompt, out_path, mode="auto")

    if mode == "local_comfyui":
        asset = generate_with_local_comfyui_if_available(prompt, out_path)
        if asset:
            return asset
        return generate_prompt_card_only(prompt, out_dir)

    # auto / unknown — prompt card safe default
    return generate_prompt_card_only(prompt, out_dir)
