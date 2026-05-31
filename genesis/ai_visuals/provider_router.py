"""Genesis Studio — Route visual generation to local/manual providers."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.ai_visuals.visual_models import GeneratedVisualAsset, VisualFillStatus, VisualGenerationPrompt
from genesis.utils.config_loader import load_ai_visuals_config

_REPO_ROOT = Path(__file__).resolve().parents[2]
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
_RENDERABLE_EXT = _IMAGE_EXT | _VIDEO_EXT
_SECRET_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9]{8,}", re.I),
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.I),
    re.compile(r"voice[_-]?id\s*[:=]\s*\S+", re.I),
)


def _comfy_cfg(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_ai_visuals_config()
    comfy = cfg.get("comfyui")
    return comfy if isinstance(comfy, dict) else {}


def _resolve_workflow_path(workflow_path: str) -> Path | None:
    if not workflow_path:
        return None
    p = Path(workflow_path)
    if p.is_file():
        return p
    candidate = _REPO_ROOT / workflow_path
    if candidate.is_file():
        return candidate
    return None


def _workflow_is_placeholder(workflow_path: Path) -> bool:
    try:
        text = workflow_path.read_text(encoding="utf-8")
    except OSError:
        return True
    return "PLACEHOLDER" in text or "__POSITIVE_PROMPT__" in text


def check_comfyui_available(
    config: dict[str, Any] | None = None,
    *,
    base_url: str | None = None,
) -> tuple[bool, str]:
    """
    Return (ready, message). Never raises.
    ComfyUI is only considered when allow_local_comfyui is true.
    """
    cfg = config or load_ai_visuals_config()
    if not cfg.get("allow_local_comfyui"):
        return False, "allow_local_comfyui is false in config"

    comfy = _comfy_cfg(cfg)
    url = (base_url or comfy.get("endpoint_url") or "http://127.0.0.1:8188").rstrip("/")

    workflow = _resolve_workflow_path(str(comfy.get("workflow_path", "")))
    if workflow is None:
        return False, "comfyui workflow_path not found — configure a real workflow JSON"
    if _workflow_is_placeholder(workflow):
        return False, "comfyui workflow is still a placeholder — copy example and replace node types"

    try:
        from genesis.integrations.comfyui_client import check_comfyui_available as _ping

        if _ping(url):
            return True, ""
        return False, f"ComfyUI not reachable at {url}"
    except Exception as exc:  # noqa: BLE001
        return False, f"ComfyUI check failed: {exc}"


def validate_comfyui_response(
    output_paths: list[str],
    *,
    expected_ext: str = ".png",
) -> tuple[bool, list[str]]:
    """Validate ComfyUI output paths exist and look like media."""
    warnings: list[str] = []
    if not output_paths:
        return False, ["ComfyUI returned no output paths"]
    found = False
    for raw in output_paths:
        p = Path(raw)
        if p.is_file() and p.suffix.lower() in _RENDERABLE_EXT:
            found = True
            if expected_ext and p.suffix.lower() != expected_ext.lower():
                warnings.append(f"expected {expected_ext}, got {p.suffix}")
        else:
            warnings.append(f"output not found or unsupported: {raw}")
    return found, warnings


def write_provider_debug_report(
    run_dir: Path,
    *,
    provider: str,
    status: str,
    details: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> Path:
    """Write debug report without secrets or full config blobs."""
    cfg = config or load_ai_visuals_config()
    out_dir = run_dir / cfg.get("output_dir", "generated_visuals")
    sub = _comfy_cfg(cfg).get("output_subdir", "comfyui")
    report_dir = out_dir / sub
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "provider_debug.md"

    safe: dict[str, Any] = {}
    for key, val in details.items():
        if key in ("api_key", "password", "token", "workflow_json", "config"):
            continue
        if isinstance(val, str):
            scrubbed = val
            for pat in _SECRET_PATTERNS:
                scrubbed = pat.sub("[redacted]", scrubbed)
            safe[key] = scrubbed
        elif isinstance(val, (int, float, bool)) or val is None:
            safe[key] = val
        elif isinstance(val, list) and all(isinstance(x, str) for x in val):
            scrubbed_list: list[str] = []
            for s in val[:20]:
                scrubbed = s
                for pat in _SECRET_PATTERNS:
                    scrubbed = pat.sub("[redacted]", scrubbed)
                scrubbed_list.append(scrubbed)
            safe[key] = scrubbed_list
        else:
            safe[key] = str(type(val).__name__)

    comfy = _comfy_cfg(cfg)
    lines = [
        f"# Provider debug — {provider}",
        "",
        f"**Status:** {status}",
        f"**Time:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Endpoint",
        "",
        f"- URL: {comfy.get('endpoint_url', 'http://127.0.0.1:8188')}",
        f"- Workflow configured: {bool(_resolve_workflow_path(str(comfy.get('workflow_path', ''))))}",
        "",
        "## Details",
        "",
        "```json",
        json.dumps(safe, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def check_pollinations_available() -> tuple[bool, str]:
    """Check if Pollinations.ai is reachable (requires internet)."""
    try:
        from genesis.integrations.pollinations_client import pollinations_available
        return pollinations_available()
    except Exception as exc:  # noqa: BLE001
        return False, f"pollinations import error: {exc}"


def check_auto1111_available(config: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Check if Automatic1111 SD WebUI is running."""
    cfg = config or load_ai_visuals_config()
    endpoint = cfg.get("auto1111", {}).get("endpoint_url", "http://127.0.0.1:7860") \
        if isinstance(cfg.get("auto1111"), dict) else "http://127.0.0.1:7860"
    try:
        from genesis.integrations.auto1111_client import auto1111_available
        return auto1111_available(endpoint)
    except Exception as exc:  # noqa: BLE001
        return False, f"auto1111 import error: {exc}"


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
        return check_comfyui_available(cfg)
    if mode == "pollinations":
        return check_pollinations_available()
    if mode == "auto1111":
        return check_auto1111_available(cfg)
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

    if mode == "auto":
        # Priority: ComfyUI (if configured) → Auto1111 (if running) → Pollinations (free, online)
        if cfg.get("allow_local_comfyui"):
            ready, _ = check_comfyui_available(cfg)
            if ready:
                return "local_comfyui"
        # Try Auto1111 (local Stable Diffusion)
        if cfg.get("allow_auto1111", True):
            ready, _ = check_auto1111_available(cfg)
            if ready:
                return "auto1111"
        # Try Pollinations (free, no API key, internet required)
        if cfg.get("allow_pollinations", True):
            ready, _ = check_pollinations_available()
            if ready:
                return "pollinations"
        # Last resort: cinematic placeholder cards
        return "prompt_card_only"

    if mode == "local_comfyui":
        if not cfg.get("allow_local_comfyui"):
            return "prompt_card_only"
        ready, _ = check_comfyui_available(cfg)
        if not ready:
            return "prompt_card_only"

    if mode == "auto1111":
        ready, _ = check_auto1111_available(cfg)
        if not ready:
            return "prompt_card_only"

    if mode == "pollinations":
        # Always return pollinations — it will fail gracefully if offline
        return "pollinations"

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
        source_type="prompt_card",
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
            source_type="generated",
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
    *,
    run_dir: Path | None = None,
    config: dict[str, Any] | None = None,
) -> GeneratedVisualAsset:
    """
    Attempt ComfyUI generation when explicitly enabled.
    Returns SKIPPED/PARTIAL asset with warnings on failure — never raises.
    """
    cfg = config or load_ai_visuals_config()
    comfy = _comfy_cfg(cfg)
    warnings: list[str] = []

    if not cfg.get("allow_local_comfyui"):
        return GeneratedVisualAsset(
            asset_id=f"skip_{prompt.scene_id}",
            scene_id=prompt.scene_id,
            prompt_id=prompt.prompt_id,
            asset_type="skipped",
            provider="local_comfyui",
            path="",
            width=0,
            height=0,
            duration_seconds=0,
            status=VisualFillStatus.SKIPPED,
            source_type="generated",
            warnings=["allow_local_comfyui is false"],
        )

    ready, msg = check_comfyui_available(cfg)
    if not ready:
        if run_dir:
            write_provider_debug_report(
                run_dir, provider="local_comfyui", status="skipped",
                details={"reason": msg},
                config=cfg,
            )
        return GeneratedVisualAsset(
            asset_id=f"skip_{prompt.scene_id}",
            scene_id=prompt.scene_id,
            prompt_id=prompt.prompt_id,
            asset_type="skipped",
            provider="local_comfyui",
            path="",
            width=0,
            height=0,
            duration_seconds=0,
            status=VisualFillStatus.SKIPPED,
            source_type="generated",
            warnings=[msg],
        )

    workflow = _resolve_workflow_path(str(comfy.get("workflow_path", "")))
    assert workflow is not None
    url = str(comfy.get("endpoint_url", "http://127.0.0.1:8188"))
    timeout = int(comfy.get("timeout_seconds", 180))
    out_sub = comfy.get("output_subdir", "comfyui")
    gen_dir = (run_dir or output_path.parent) / cfg.get("output_dir", "generated_visuals") / out_sub
    gen_dir.mkdir(parents=True, exist_ok=True)

    replacements = {
        "__POSITIVE_PROMPT__": prompt.prompt_text[:2000],
        "__NEGATIVE_PROMPT__": prompt.negative_prompt[:500],
        "__WIDTH__": "1080",
        "__HEIGHT__": "1920",
        "__SEED__": str(abs(hash(prompt.prompt_id)) % 2_147_483_647),
    }

    try:
        from genesis.integrations.comfyui_client import run_workflow

        outputs = run_workflow(
            str(workflow),
            replacements,
            str(gen_dir),
            base_url=url,
            timeout_sec=timeout,
        )
        ok, val_warn = validate_comfyui_response(outputs, expected_ext=output_path.suffix)
        warnings.extend(val_warn)
        if not ok:
            raise RuntimeError("ComfyUI produced no usable output files")

        src = next(
            (Path(p) for p in outputs if Path(p).is_file() and Path(p).suffix.lower() in _RENDERABLE_EXT),
            None,
        )
        if src is None:
            raise RuntimeError("no renderable ComfyUI output")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, output_path)
        asset_type = "video" if output_path.suffix.lower() in _VIDEO_EXT else "image"
        return GeneratedVisualAsset(
            asset_id=f"comfy_{prompt.scene_id}",
            scene_id=prompt.scene_id,
            prompt_id=prompt.prompt_id,
            asset_type=asset_type,
            provider="local_comfyui",
            path=str(output_path),
            width=1080,
            height=1920,
            duration_seconds=prompt.duration_seconds,
            status=VisualFillStatus.COMPLETE,
            source_type="generated",
            warnings=warnings,
            notes=[f"comfyui outputs={len(outputs)}"],
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(str(exc))
        if run_dir:
            write_provider_debug_report(
                run_dir, provider="local_comfyui", status="partial",
                details={"error": str(exc), "scene_id": prompt.scene_id},
                config=cfg,
            )
        card = generate_prompt_card_only(prompt, output_path.parent)
        card.provider = "local_comfyui"
        card.status = VisualFillStatus.PARTIAL
        card.warnings = warnings
        card.notes.append("ComfyUI failed — prompt card written")
        return card


def generate_with_pollinations(
    prompt: VisualGenerationPrompt,
    output_path: Path,
    *,
    brand_preset: str = "cinematic_dark",
    content_format: str = "",
    config: dict[str, Any] | None = None,
) -> GeneratedVisualAsset:
    """Generate an image via Pollinations.ai (free, no API key, FLUX model)."""
    warnings: list[str] = []
    try:
        from genesis.integrations.pollinations_client import generate_scene_image

        result = generate_scene_image(
            prompt.prompt_text,
            output_path.with_suffix(".jpg"),
            brand_preset=brand_preset,
            content_format=content_format,
            aspect_ratio=prompt.aspect_ratio or "9:16",
        )
        if result["success"]:
            p = Path(result["path"])
            return GeneratedVisualAsset(
                asset_id=f"poll_{prompt.scene_id}",
                scene_id=prompt.scene_id,
                prompt_id=prompt.prompt_id,
                asset_type="image",
                provider="pollinations",
                path=str(p),
                width=576,
                height=1024,
                duration_seconds=prompt.duration_seconds,
                status=VisualFillStatus.COMPLETE,
                source_type="generated",
                notes=["generated via Pollinations.ai / FLUX"],
            )
        warnings.append(result.get("error", "Pollinations generation failed"))
    except Exception as exc:  # noqa: BLE001
        warnings.append(str(exc))

    card = generate_prompt_card_only(prompt, output_path.parent)
    card.provider = "pollinations"
    card.status = VisualFillStatus.PARTIAL
    card.warnings = warnings
    return card


def generate_with_auto1111(
    prompt: VisualGenerationPrompt,
    output_path: Path,
    *,
    config: dict[str, Any] | None = None,
) -> GeneratedVisualAsset:
    """Generate an image via Automatic1111 Stable Diffusion WebUI."""
    cfg = config or load_ai_visuals_config()
    a1111_cfg = cfg.get("auto1111", {}) if isinstance(cfg.get("auto1111"), dict) else {}
    endpoint = a1111_cfg.get("endpoint_url", "http://127.0.0.1:7860")
    warnings: list[str] = []
    try:
        from genesis.integrations.auto1111_client import generate_image

        result = generate_image(
            prompt.prompt_text,
            output_path.with_suffix(".png"),
            negative_prompt=prompt.negative_prompt or "blurry, low quality, distorted",
            width=576,
            height=1024,
            endpoint=endpoint,
        )
        if result["success"]:
            p = Path(result["path"])
            return GeneratedVisualAsset(
                asset_id=f"a1111_{prompt.scene_id}",
                scene_id=prompt.scene_id,
                prompt_id=prompt.prompt_id,
                asset_type="image",
                provider="auto1111",
                path=str(p),
                width=576,
                height=1024,
                duration_seconds=prompt.duration_seconds,
                status=VisualFillStatus.COMPLETE,
                source_type="generated",
                notes=["generated via Automatic1111"],
            )
        warnings.append(result.get("error", "Auto1111 generation failed"))
    except Exception as exc:  # noqa: BLE001
        warnings.append(str(exc))

    card = generate_prompt_card_only(prompt, output_path.parent)
    card.provider = "auto1111"
    card.status = VisualFillStatus.PARTIAL
    card.warnings = warnings
    return card


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
    mode = choose_visual_provider(
        provider_mode=provider_mode, config=cfg, asset_type=prompt.provider_hint,
    )

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
            source_type="generated",
        )

    ext = ".mp4" if prompt.provider_hint == "video" or prompt.duration_seconds > 0 else ".png"
    out_path = out_dir / f"{prompt.scene_id}_generated{ext}"

    if mode in ("prompt_card_only", "manual_chatgpt"):
        return generate_prompt_card_only(prompt, out_dir)

    if mode == "hero_shot_provider":
        return generate_with_hero_shot_provider(prompt, out_path, mode="auto")

    if mode == "local_comfyui":
        return generate_with_local_comfyui_if_available(
            prompt, out_path, run_dir=run_dir, config=cfg,
        )

    if mode == "pollinations":
        # Extract brand/content info from config if available
        brand_preset = cfg.get("brand_preset", "cinematic_dark")
        content_format = cfg.get("content_format", "")
        return generate_with_pollinations(
            prompt, out_path, brand_preset=brand_preset, content_format=content_format, config=cfg,
        )

    if mode == "auto1111":
        return generate_with_auto1111(prompt, out_path, config=cfg)

    return generate_prompt_card_only(prompt, out_dir)
