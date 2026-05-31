"""
Genesis Studio configuration loader.

Merge order (highest priority last):
  1. Built-in defaults
  2. Local JSON under genesis/config/ (gitignored, user-created)
  3. Environment variables

Never creates real credential files automatically.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from genesis.utils.logger import get_logger

logger = get_logger("config_loader")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_DIR = _REPO_ROOT / "genesis" / "config"

DEFAULT_ELEVENLABS: dict[str, Any] = {
    "api_key": "",
    "voice_id": "",
    "voice_name": "",
    "model_id": "eleven_multilingual_v2",
    "output_format": "mp3_44100_128",
    "base_url": "https://api.elevenlabs.io/v1",
}

DEFAULT_LOCAL_LLM: dict[str, Any] = {
    "enabled": False,
    "backend": "disabled",
    "endpoint_url": "",
    "model": "",
    "timeout_seconds": 120,
    "max_tokens": 1200,
    "temperature": 0.7,
    "system_prompt": (
        "You are Genesis Studio's local creative writing model "
        "for short-form social media content."
    ),
    "debug_prompts": False,
}

DEFAULT_DIFFUSME: dict[str, Any] = {
    "username": "",
    "password": "",
    "max_generations_per_hour": 10,
    "max_generations_per_day": 50,
    "low_credit_threshold": 200,
    "estimated_cost_per_generation": 1,
    "mode": "auto",
}

DEFAULT_GENESIS_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "log_level": "INFO",
    "comfyui_url": "http://127.0.0.1:8188",
    "default_mode": "local_first",
    "output_base_dir": "assets",
}

DEFAULT_AI_VISUALS_COMFYUI: dict[str, Any] = {
    "endpoint_url": "http://127.0.0.1:8188",
    "workflow_path": "genesis/config/comfyui_workflow.example.json",
    "timeout_seconds": 180,
    "poll_interval_seconds": 2,
    "output_subdir": "comfyui",
}

DEFAULT_AI_VISUALS: dict[str, Any] = {
    "enabled": False,
    "provider_mode": "prompt_card_only",
    "default_asset_type": "image",
    "aspect_ratio": "9:16",
    "duration_seconds": 4,
    "allow_local_comfyui": False,
    "allow_external_paid": False,
    "output_dir": "generated_visuals",
    "debug_prompts": False,
    "comfyui": DEFAULT_AI_VISUALS_COMFYUI,
}

_ENV_MAP_ELEVENLABS = {
    "GENESIS_ELEVENLABS_API_KEY": "api_key",
    "GENESIS_ELEVENLABS_VOICE_ID": "voice_id",
    "GENESIS_ELEVENLABS_VOICE_NAME": "voice_name",
    "GENESIS_ELEVENLABS_MODEL_ID": "model_id",
    "GENESIS_ELEVENLABS_OUTPUT_FORMAT": "output_format",
    "GENESIS_ELEVENLABS_BASE_URL": "base_url",
}

_ENV_MAP_LOCAL_LLM = {
    "GENESIS_LOCAL_LLM_ENABLED": "enabled",
    "GENESIS_LOCAL_LLM_BACKEND": "backend",
    "GENESIS_LOCAL_LLM_ENDPOINT_URL": "endpoint_url",
    "GENESIS_LOCAL_LLM_MODEL": "model",
    "GENESIS_LOCAL_LLM_TIMEOUT_SECONDS": "timeout_seconds",
    "GENESIS_LOCAL_LLM_MAX_TOKENS": "max_tokens",
    "GENESIS_LOCAL_LLM_TEMPERATURE": "temperature",
    "GENESIS_LOCAL_LLM_SYSTEM_PROMPT": "system_prompt",
    "GENESIS_LOCAL_LLM_DEBUG_PROMPTS": "debug_prompts",
}

_ENV_MAP_DIFFUSME = {
    "GENESIS_DIFFUSME_USERNAME": "username",
    "GENESIS_DIFFUSME_PASSWORD": "password",
    "GENESIS_DIFFUSME_MODE": "mode",
    "GENESIS_DIFFUSME_MAX_PER_HOUR": "max_generations_per_hour",
    "GENESIS_DIFFUSME_MAX_PER_DAY": "max_generations_per_day",
    "GENESIS_DIFFUSME_LOW_CREDIT_THRESHOLD": "low_credit_threshold",
}

_ENV_MAP_SETTINGS = {
    "GENESIS_STUDIO_ENABLED": "enabled",
    "GENESIS_LOG_LEVEL": "log_level",
    "GENESIS_COMFYUI_URL": "comfyui_url",
    "GENESIS_DEFAULT_MODE": "default_mode",
    "GENESIS_OUTPUT_BASE_DIR": "output_base_dir",
}

_ENV_MAP_AI_VISUALS = {
    "GENESIS_AI_VISUALS_ENABLED": "enabled",
    "GENESIS_AI_VISUALS_PROVIDER_MODE": "provider_mode",
    "GENESIS_AI_VISUALS_DEFAULT_ASSET_TYPE": "default_asset_type",
    "GENESIS_AI_VISUALS_ALLOW_LOCAL_COMFYUI": "allow_local_comfyui",
    "GENESIS_AI_VISUALS_ALLOW_EXTERNAL_PAID": "allow_external_paid",
    "GENESIS_AI_VISUALS_DEBUG_PROMPTS": "debug_prompts",
}


def config_dir(path: Path | str | None = None) -> Path:
    return Path(path) if path else _DEFAULT_CONFIG_DIR


def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _apply_env(
    config: dict[str, Any],
    env_map: dict[str, str],
    *,
    coerce_bools: set[str] | None = None,
) -> dict[str, Any]:
    coerce_bools = coerce_bools or set()
    merged = deepcopy(config)
    for env_name, key in env_map.items():
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        if key in coerce_bools:
            merged[key] = raw.strip().lower() in {"1", "true", "yes", "on"}
        elif key in {
            "max_generations_per_hour",
            "max_generations_per_day",
            "low_credit_threshold",
            "estimated_cost_per_generation",
        }:
            try:
                merged[key] = int(raw)
            except ValueError:
                logger.warning("invalid integer for %s: %r", env_name, raw)
        else:
            merged[key] = raw.strip()
    return merged


def load_merged_config(
    *,
    name: str,
    defaults: dict[str, Any],
    local_filename: str,
    env_map: dict[str, str],
    config_root: Path | str | None = None,
    coerce_bools: set[str] | None = None,
) -> dict[str, Any]:
    """
    Load config with defaults <- local JSON <- environment variables.
    """
    root = config_dir(config_root)
    merged = deepcopy(defaults)

    local_path = root / local_filename
    if local_path.is_file():
        try:
            merged.update(_read_json_file(local_path))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("failed to read %s: %s", local_path, exc)
    elif local_path.name.startswith("example"):
        pass
    else:
        logger.debug(
            "no local config at %s (copy from example_%s if needed)",
            local_path,
            name,
        )

    merged = _apply_env(merged, env_map, coerce_bools=coerce_bools)
    return merged


def missing_required_keys(config: dict[str, Any], required: list[str]) -> list[str]:
    missing = []
    for key in required:
        value = config.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
    return missing


def format_missing_config_message(
    profile: str,
    missing_keys: list[str],
    *,
    local_filename: str,
    env_hints: dict[str, str] | None = None,
) -> str:
    env_hints = env_hints or {}
    lines = [
        f"Genesis config '{profile}' is incomplete. Missing: {', '.join(missing_keys)}.",
        f"Provide values via environment variables or create {local_filename} "
        f"(never commit secrets).",
    ]
    for key in missing_keys:
        hint = env_hints.get(key)
        if hint:
            lines.append(f"  - {key}: set {hint}")
    lines.append(
        f"See genesis/config/example_{profile}.json for the expected structure."
    )
    return " ".join(lines)


def load_elevenlabs_config(config_root: Path | str | None = None) -> dict[str, Any]:
    return load_merged_config(
        name="elevenlabs",
        defaults=DEFAULT_ELEVENLABS,
        local_filename="elevenlabs.json",
        env_map=_ENV_MAP_ELEVENLABS,
        config_root=config_root,
    )


def load_local_llm_config(config_root: Path | str | None = None) -> dict[str, Any]:
    return load_merged_config(
        name="local_llm",
        defaults=DEFAULT_LOCAL_LLM,
        local_filename="local_llm.json",
        env_map=_ENV_MAP_LOCAL_LLM,
        config_root=config_root,
        coerce_bools={"enabled", "debug_prompts"},
    )


def load_diffusme_config(config_root: Path | str | None = None) -> dict[str, Any]:
    return load_merged_config(
        name="diffusme",
        defaults=DEFAULT_DIFFUSME,
        local_filename="diffusme.json",
        env_map=_ENV_MAP_DIFFUSME,
        config_root=config_root,
    )


def load_genesis_settings(config_root: Path | str | None = None) -> dict[str, Any]:
    return load_merged_config(
        name="genesis_settings",
        defaults=DEFAULT_GENESIS_SETTINGS,
        local_filename="genesis_settings.json",
        env_map=_ENV_MAP_SETTINGS,
        config_root=config_root,
        coerce_bools={"enabled"},
    )


def load_ai_visuals_config(config_root: Path | str | None = None) -> dict[str, Any]:
    merged = load_merged_config(
        name="ai_visuals",
        defaults=DEFAULT_AI_VISUALS,
        local_filename="ai_visuals.json",
        env_map=_ENV_MAP_AI_VISUALS,
        config_root=config_root,
        coerce_bools={"enabled", "allow_local_comfyui", "allow_external_paid", "debug_prompts"},
    )
    comfy = deepcopy(DEFAULT_AI_VISUALS_COMFYUI)
    if isinstance(merged.get("comfyui"), dict):
        comfy.update(merged["comfyui"])
    endpoint = os.getenv("GENESIS_AI_VISUALS_COMFYUI_ENDPOINT_URL")
    if endpoint:
        comfy["endpoint_url"] = endpoint.strip()
    workflow = os.getenv("GENESIS_AI_VISUALS_COMFYUI_WORKFLOW_PATH")
    if workflow:
        comfy["workflow_path"] = workflow.strip()
    timeout = os.getenv("GENESIS_AI_VISUALS_COMFYUI_TIMEOUT_SECONDS")
    if timeout:
        try:
            comfy["timeout_seconds"] = int(timeout)
        except ValueError:
            logger.warning("invalid GENESIS_AI_VISUALS_COMFYUI_TIMEOUT_SECONDS: %r", timeout)
    merged["comfyui"] = comfy
    return merged


def elevenlabs_ready(config: dict[str, Any] | None = None) -> tuple[bool, str]:
    cfg = config or load_elevenlabs_config()
    missing = missing_required_keys(cfg, ["api_key"])
    if missing:
        return False, format_missing_config_message(
            "elevenlabs",
            missing,
            local_filename="genesis/config/elevenlabs.json",
            env_hints={"api_key": "GENESIS_ELEVENLABS_API_KEY"},
        )
    return True, ""


def diffusme_ready(config: dict[str, Any] | None = None) -> tuple[bool, str]:
    cfg = config or load_diffusme_config()
    missing = missing_required_keys(cfg, ["username", "password"])
    if missing:
        return False, format_missing_config_message(
            "diffusme",
            missing,
            local_filename="genesis/config/diffusme.json",
            env_hints={
                "username": "GENESIS_DIFFUSME_USERNAME",
                "password": "GENESIS_DIFFUSME_PASSWORD",
            },
        )
    return True, ""
