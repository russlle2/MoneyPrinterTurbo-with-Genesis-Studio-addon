"""
Genesis Studio — Pollinations.ai free image generation client.

Generates high-quality AI images using FLUX via the Pollinations.ai public API.
No API key required. Free to use. Requires internet connection.

API: https://image.pollinations.ai/prompt/{text}?width=W&height=H&model=flux&nologo=true
"""

from __future__ import annotations

import hashlib
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from genesis.utils.logger import get_logger

logger = get_logger("integrations.pollinations")

_BASE_URL = "https://image.pollinations.ai/prompt"
_MODELS = ("flux", "flux-realism", "flux-pro", "turbo")

# Default 9:16 vertical for social short-form
_DEFAULT_WIDTH = 576
_DEFAULT_HEIGHT = 1024


def pollinations_available() -> tuple[bool, str]:
    """Check if Pollinations.ai is reachable."""
    try:
        req = urllib.request.Request(
            "https://image.pollinations.ai/",
            method="HEAD",
            headers={"User-Agent": "GenesisStudio/1.0"},
        )
        urllib.request.urlopen(req, timeout=5)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"Pollinations.ai not reachable: {exc}"


def build_pollinations_url(
    prompt: str,
    *,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
    model: str = "flux",
    seed: int | None = None,
    enhance: bool = True,
    nologo: bool = True,
) -> str:
    """Build a Pollinations.ai image URL for the given prompt."""
    encoded = urllib.parse.quote(prompt, safe="")
    params: list[str] = [
        f"width={width}",
        f"height={height}",
        f"model={model}",
    ]
    if seed is not None:
        params.append(f"seed={seed}")
    if enhance:
        params.append("enhance=true")
    if nologo:
        params.append("nologo=true")
    return f"{_BASE_URL}/{encoded}?{'&'.join(params)}"


def _deterministic_seed(prompt: str) -> int:
    """Generate a consistent seed from the prompt for reproducible images."""
    h = hashlib.md5(prompt.encode()).hexdigest()
    return int(h[:8], 16) % 2147483647


def generate_image(
    prompt: str,
    out_path: Path,
    *,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
    model: str = "flux",
    style_suffix: str = "",
    max_retries: int = 2,
    timeout: int = 90,
) -> dict[str, Any]:
    """
    Generate an image via Pollinations.ai and save to out_path.

    Args:
        prompt:       Scene description / visual prompt.
        out_path:     Where to save the resulting image (JPG).
        width/height: Output dimensions (default 576×1024 = 9:16 vertical).
        model:        Generation model ('flux', 'flux-realism', 'turbo').
        style_suffix: Optional style suffix appended to prompt (e.g. 'cinematic, 4K').
        max_retries:  Number of retry attempts on failure.
        timeout:      HTTP timeout in seconds.

    Returns:
        dict with keys: success (bool), path (str), error (str), model (str), url (str)
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    full_prompt = prompt.strip()
    if style_suffix:
        full_prompt = f"{full_prompt}, {style_suffix.strip()}"

    seed = _deterministic_seed(full_prompt)
    url = build_pollinations_url(
        full_prompt, width=width, height=height, model=model, seed=seed,
    )

    logger.info("pollinations image request → model=%s prompt=%.80s", model, full_prompt)

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GenesisStudio/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "image" not in content_type:
                    raise ValueError(f"unexpected content type: {content_type}")
                data = resp.read()
                if len(data) < 1000:
                    raise ValueError(f"response too small ({len(data)} bytes) — likely an error")
                out_path.write_bytes(data)
                logger.info(
                    "pollinations image saved → %s (%d bytes)", out_path.name, len(data)
                )
                return {
                    "success": True,
                    "path": str(out_path),
                    "model": model,
                    "url": url,
                    "error": "",
                    "bytes": len(data),
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pollinations attempt %d/%d failed: %s", attempt + 1, max_retries + 1, exc
            )
            if attempt < max_retries:
                time.sleep(2)
            else:
                return {
                    "success": False,
                    "path": "",
                    "model": model,
                    "url": url,
                    "error": str(exc),
                    "bytes": 0,
                }

    return {"success": False, "path": "", "model": model, "url": url, "error": "max retries exceeded", "bytes": 0}


def generate_scene_image(
    scene_description: str,
    out_path: Path,
    *,
    brand_preset: str = "cinematic_dark",
    content_format: str = "personal_story",
    aspect_ratio: str = "9:16",
    timeout: int = 90,
) -> dict[str, Any]:
    """
    High-level helper: generate a single scene image with style context baked in.

    Automatically applies cinematic style instructions based on brand_preset and content_format.
    """
    # Style suffix by brand/content type
    style_map = {
        "cinematic_dark": "cinematic lighting, moody atmosphere, film grain, dramatic shadows, 4K",
        "wellness_soft": "soft natural light, warm tones, calming atmosphere, lifestyle photography",
        "bold_viral": "high contrast, vibrant colors, dynamic composition, social media ready",
        "clean_creator": "clean professional look, good lighting, authentic, vertical video frame",
        "minimal_white": "minimalist, clean white background, editorial style, bright",
        "auto": "cinematic, high quality, social media vertical format, 9:16",
    }
    content_style_map = {
        "personal_story": "authentic documentary style, real human emotion, golden hour lighting",
        "motivational_walkthrough": "energetic, inspiring, bold typography, dynamic movement",
        "wellness_teaching": "peaceful, natural light, zen atmosphere, clean",
        "product_demo": "product photography, clean studio, sharp focus",
        "controversial_take": "editorial, bold, contrasting elements, thought-provoking",
        "fundraising_story": "heartfelt, community, warmth, genuine emotion",
        "tutorial": "clear, instructional, well-lit, professional",
    }

    style = style_map.get(brand_preset, style_map["auto"])
    content_style = content_style_map.get(content_format, "")
    style_suffix = f"{style}, {content_style}" if content_style else style

    # Aspect ratio → dimensions
    w, h = (576, 1024)  # 9:16 default
    if aspect_ratio == "16:9":
        w, h = 1024, 576
    elif aspect_ratio == "1:1":
        w, h = 768, 768

    return generate_image(
        scene_description,
        out_path,
        width=w,
        height=h,
        model="flux",
        style_suffix=style_suffix,
        timeout=timeout,
    )
