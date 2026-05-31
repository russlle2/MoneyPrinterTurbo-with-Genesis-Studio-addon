"""
Genesis Studio — Hero-shot video provider abstraction.

generate_hero_shot() selects the best available generation strategy:

  1. local_cogvideox     — ComfyUI/CogVideoX local GPU generation (preferred)
  2. manual_chatgpt      — Writes a Markdown prompt card; expects manual import
  3. openai_api_optional — Disabled unless GENESIS_OPENAI_VIDEO_PROVIDER_ENABLED=true

Auto mode priority: local_cogvideox → manual_chatgpt
(openai_api_optional is inserted between them only when explicitly enabled)

Design principles:
  - No cloud service dependencies.
  - ChatGPT Pro = manual import workflow, not API access.
  - Failures in lower-priority modes fall back cleanly in auto mode.
  - No ComfyUI or CUDA required on import.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any

from genesis.utils.logger import get_logger

logger = get_logger("hero_shot_provider")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANUAL_DIR = _REPO_ROOT / "assets" / "manual_hero_shots"
_MANUAL_IMPORTS_DIR = _MANUAL_DIR / "imports"


# ---------------------------------------------------------------------------
# Mode: local_cogvideox
# ---------------------------------------------------------------------------

def _try_cogvideox(prompt: str, output_path: str, **kwargs: Any) -> str | None:
    """
    Attempt CogVideoX generation via ComfyUI.

    Returns the output path string on success, None on any failure (so auto
    mode can fall back cleanly without propagating the error).
    """
    try:
        from genesis.integrations.cogvideox_client import CogVideoXClient
        client = CogVideoXClient()
        return client.generate_video_from_prompt(prompt, output_path, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("local_cogvideox unavailable (auto mode will fall back): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Mode: manual_chatgpt
# ---------------------------------------------------------------------------

def _manual_chatgpt(
    prompt: str,
    output_path: str,  # noqa: ARG001  kept for API symmetry
    *,
    scene_id: str | None = None,
    imported_file: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Create a Markdown prompt card for manual hero-shot generation.

    If the caller already provides an ``imported_file`` path that exists on
    disk, that path is returned directly (the import has already been done).

    Otherwise a prompt card is written to assets/manual_hero_shots/ and its
    path is returned.  The caller is responsible for surfacing the "manual
    import required" message to the user.
    """
    _MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    _MANUAL_IMPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if imported_file and Path(imported_file).is_file():
        logger.info("manual_chatgpt: using imported file %s", imported_file)
        return str(imported_file)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = scene_id or ts
    card_path = _MANUAL_DIR / f"hero_prompt_{slug}.md"

    duration = kwargs.get("duration_seconds", 5)
    aspect = kwargs.get("aspect_ratio", "16:9")
    style = kwargs.get("style_notes", "cinematic, photorealistic")
    import_target = _MANUAL_IMPORTS_DIR / f"{slug}.mp4"

    card_path.write_text(
        f"# Hero Shot Prompt Card\n\n"
        f"**Generated:** {datetime.datetime.now().isoformat()}\n"
        f"**Scene ID:** `{slug}`\n\n"
        f"## Prompt\n\n"
        f"{prompt}\n\n"
        f"## Generation Settings\n\n"
        f"- Duration: {duration}s\n"
        f"- Aspect ratio: {aspect}\n"
        f"- Style: {style}\n\n"
        f"## Instructions\n\n"
        f"1. Open ChatGPT (Sora) or your preferred video generation tool.\n"
        f"2. Use the prompt above to generate a {duration}s video clip.\n"
        f"3. Download the result and save it to:\n\n"
        f"   `{import_target}`\n\n"
        f"   (any `.mp4` / `.mov` file placed under "
        f"`assets/manual_hero_shots/imports/` also works)\n"
        f"4. Re-run Genesis Studio — it will detect the import automatically.\n",
        encoding="utf-8",
    )
    logger.info("manual_chatgpt: prompt card written → %s", card_path)
    return str(card_path)


# ---------------------------------------------------------------------------
# Mode: openai_api_optional
# ---------------------------------------------------------------------------

def _openai_api_optional(prompt: str, output_path: str, **kwargs: Any) -> str:  # noqa: ARG001
    """
    OpenAI video generation — disabled unless explicitly configured.

    Requires ALL of:
      GENESIS_OPENAI_VIDEO_PROVIDER_ENABLED=true
      OPENAI_API_KEY
      GENESIS_OPENAI_VIDEO_MODEL (or model= kwarg)

    Note: ChatGPT Pro does NOT provide an API for Sora video generation.
    This mode exists for future official API access only.
    """
    enabled = os.getenv("GENESIS_OPENAI_VIDEO_PROVIDER_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        raise RuntimeError(
            "openai_api_optional mode is disabled. "
            "Set GENESIS_OPENAI_VIDEO_PROVIDER_ENABLED=true to enable it. "
            "Note: ChatGPT Pro / Sora does not expose a public video generation API — "
            "use manual_chatgpt mode for Sora-based hero shots."
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Configure it before enabling openai_api_optional mode."
        )

    model = (kwargs.get("model") or os.getenv("GENESIS_OPENAI_VIDEO_MODEL", "")).strip()
    if not model:
        raise RuntimeError(
            "No OpenAI video model configured. "
            "Set GENESIS_OPENAI_VIDEO_MODEL or pass model= in kwargs."
        )

    raise RuntimeError(
        f"openai_api_optional: model={model!r} is configured, but video generation "
        "via the OpenAI API is not yet implemented in Genesis Studio. "
        "Use manual_chatgpt mode to generate hero shots with Sora/ChatGPT manually."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_hero_shot(
    prompt: str,
    output_path: str,
    mode: str = "auto",
    **kwargs: Any,
) -> str:
    """
    Generate a hero-shot video clip from a text prompt.

    Args:
        prompt:      Visual/narrative description for the hero shot.
        output_path: Desired output video path (used by local_cogvideox).
        mode:        Generation mode. One of:
                       "auto"                — tries local_cogvideox, then manual_chatgpt
                       "local_cogvideox"     — ComfyUI/CogVideoX local GPU generation
                       "manual_chatgpt"      — writes a Markdown prompt card
                       "openai_api_optional" — disabled unless explicitly configured
        **kwargs:    Mode-specific options:
                       scene_id          (str)  — slug used in prompt-card filename
                       imported_file     (str)  — path to already-downloaded video
                       duration_seconds  (int)  — target clip duration (default 5)
                       aspect_ratio      (str)  — e.g. "16:9" (default)
                       style_notes       (str)  — style guidance for the prompt card
                       model             (str)  — OpenAI model name (openai_api_optional)
                       model_path        (str)  — CogVideoX model override
                       base_url          (str)  — ComfyUI base URL override
                       timeout_sec       (int)  — ComfyUI timeout

    Returns:
        Path to the generated video file, or the path to the Markdown prompt card
        when in manual_chatgpt mode.

    Raises:
        RuntimeError: For invalid mode, explicit mode failures, or missing config.
    """
    mode = mode.strip().lower()

    if mode == "local_cogvideox":
        result = _try_cogvideox(prompt, output_path, **kwargs)
        if result is None:
            raise RuntimeError(
                "local_cogvideox generation failed. "
                "Ensure ComfyUI is running at the configured URL, that the "
                "CogVideoX custom nodes are installed, and that a model is "
                "available at COGVIDEOX_MODEL_PATH in genesis/config/models.json."
            )
        return result

    if mode == "manual_chatgpt":
        return _manual_chatgpt(prompt, output_path, **kwargs)

    if mode == "openai_api_optional":
        return _openai_api_optional(prompt, output_path, **kwargs)

    if mode == "auto":
        # Priority 1: local CogVideoX
        result = _try_cogvideox(prompt, output_path, **kwargs)
        if result is not None:
            return result

        # Priority 2: OpenAI API only if explicitly enabled
        openai_enabled = (
            os.getenv("GENESIS_OPENAI_VIDEO_PROVIDER_ENABLED", "").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        if openai_enabled:
            return _openai_api_optional(prompt, output_path, **kwargs)

        # Priority 3: Manual prompt card (always available)
        logger.info(
            "auto mode: local_cogvideox unavailable → generating manual_chatgpt prompt card"
        )
        return _manual_chatgpt(prompt, output_path, **kwargs)

    raise RuntimeError(
        f"Unknown hero-shot mode: {mode!r}. "
        "Valid modes: auto, local_cogvideox, manual_chatgpt, openai_api_optional"
    )
