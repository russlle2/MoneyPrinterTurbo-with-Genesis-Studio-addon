"""
Genesis Studio — Automatic1111 Stable Diffusion WebUI client.

Connects to a locally-running AUTOMATIC1111 / stable-diffusion-webui instance
via its REST API. Default port: 7860.

Start with: python launch.py --api --nowebui (or just --api for both)
"""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any

from genesis.utils.logger import get_logger

logger = get_logger("integrations.auto1111")

_DEFAULT_ENDPOINT = "http://127.0.0.1:7860"


def auto1111_available(endpoint: str = _DEFAULT_ENDPOINT) -> tuple[bool, str]:
    """Check if Automatic1111 API is reachable."""
    try:
        url = endpoint.rstrip("/") + "/sdapi/v1/sd-models"
        req = urllib.request.Request(url, headers={"User-Agent": "GenesisStudio/1.0"})
        urllib.request.urlopen(req, timeout=4)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"Automatic1111 not reachable at {endpoint}: {exc}"


def generate_image(
    prompt: str,
    out_path: Path,
    *,
    negative_prompt: str = "blurry, low quality, distorted, ugly, bad anatomy",
    width: int = 576,
    height: int = 1024,
    steps: int = 20,
    cfg_scale: float = 7.0,
    sampler: str = "DPM++ 2M Karras",
    seed: int = -1,
    endpoint: str = _DEFAULT_ENDPOINT,
    timeout: int = 120,
) -> dict[str, Any]:
    """Generate an image using Automatic1111 txt2img API."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler,
        "seed": seed,
        "batch_size": 1,
        "n_iter": 1,
        "save_images": False,
        "send_images": True,
    }

    url = endpoint.rstrip("/") + "/sdapi/v1/txt2img"
    logger.info("auto1111 image request → %s prompt=%.80s", url, prompt)

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "GenesisStudio/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())

        images = result.get("images", [])
        if not images:
            return {"success": False, "path": "", "error": "no images in response"}

        img_data = base64.b64decode(images[0])
        out_path.write_bytes(img_data)
        logger.info("auto1111 image saved → %s (%d bytes)", out_path.name, len(img_data))
        return {
            "success": True,
            "path": str(out_path),
            "error": "",
            "bytes": len(img_data),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto1111 generation failed: %s", exc)
        return {"success": False, "path": "", "error": str(exc)}
