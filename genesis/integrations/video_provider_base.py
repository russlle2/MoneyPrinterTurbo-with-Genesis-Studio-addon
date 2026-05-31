"""
Shared base class and helpers for Genesis video provider clients.

All providers:
  - are import-safe (no CUDA, no ComfyUI, no model loading on import)
  - route generation through ComfyUI workflow execution
  - strip genesis_metadata before submitting to /prompt
  - load candidate model paths from genesis/config/models.json when present
  - return ProviderResult or raise RuntimeError with clear messages
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from genesis.schemas.core import ProviderResult
from genesis.utils.logger import get_logger

logger = get_logger("video_provider")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS_DIR = _REPO_ROOT / "genesis" / "integrations" / "comfyui_workflows"
_MODELS_JSON = _REPO_ROOT / "genesis" / "config" / "models.json"


# ---------------------------------------------------------------------------
# models.json loader (non-crashing)
# ---------------------------------------------------------------------------

def load_model_candidates(family: str) -> list[str]:
    """
    Return candidate model paths for a family from genesis/config/models.json.
    Returns an empty list silently if the file does not exist or is malformed.
    """
    if not _MODELS_JSON.is_file():
        return []
    try:
        with _MODELS_JSON.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        candidates = data.get(family, [])
        return [str(p) for p in candidates if p]
    except (OSError, json.JSONDecodeError, ValueError):
        return []


def first_candidate(family: str) -> str | None:
    """Return the first model candidate for a family, or None."""
    candidates = load_model_candidates(family)
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Workflow helper
# ---------------------------------------------------------------------------

def workflow_path(name: str) -> str:
    """Resolve a blueprint filename to its absolute path string."""
    return str(_WORKFLOWS_DIR / name)


def strip_metadata(workflow: dict[str, Any]) -> dict[str, Any]:
    """
    Remove genesis_metadata from a workflow dict before submission to /prompt.
    Returns a new dict; never mutates the original.
    """
    return {k: v for k, v in workflow.items() if k != "genesis_metadata"}


def output_prefix(provider_name: str) -> str:
    """Generate a short, unique output file prefix for a provider run."""
    return f"genesis_{provider_name}_{uuid.uuid4().hex[:8]}"


def ensure_output_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class VideoProviderBase:
    """
    Abstract base for ComfyUI-backed video providers.

    Subclasses must set:
      provider_name    str
      workflow_file    str  (filename inside comfyui_workflows/)
      model_family     str  (key in models.json)
      model_placeholder str (placeholder string in the workflow)
    """

    provider_name: str = "base"
    workflow_file: str = ""
    model_family: str = ""
    model_placeholder: str = ""

    def _get_model_path(self, override: str | None = None) -> str | None:
        if override:
            return override
        return first_candidate(self.model_family)

    def _build_base_replacements(
        self,
        prompt: str,
        output_dir: str,
        *,
        negative_prompt: str = "",
        image_path: str | None = None,
        model_override: str | None = None,
    ) -> dict[str, str]:
        prefix = output_prefix(self.provider_name)
        replacements: dict[str, str] = {
            "PROMPT_TEXT": prompt,
            "NEGATIVE_PROMPT_TEXT": negative_prompt or "blurry, low quality, watermark",
            "OUTPUT_PREFIX": f"{output_dir}/{prefix}",
        }
        if image_path:
            replacements["INPUT_IMAGE_PATH"] = image_path
        model = self._get_model_path(model_override)
        if model and self.model_placeholder:
            replacements[self.model_placeholder] = model
        return replacements

    def generate_video_from_prompt(
        self,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError(
            f"{self.provider_name}.generate_video_from_prompt() not implemented"
        )

    def generate_video_from_image(
        self,
        image_path: str,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError(
            f"{self.provider_name}.generate_video_from_image() not implemented"
        )

    def _run(
        self,
        replacements: dict[str, str],
        output_dir: str,
        *,
        base_url: str | None = None,
        timeout_sec: int = 600,
    ) -> ProviderResult:
        """Execute the workflow and return a ProviderResult."""
        from genesis.integrations.comfyui_client import run_workflow

        wf = workflow_path(self.workflow_file)
        logger.info(
            "%s: submitting workflow %s to ComfyUI",
            self.provider_name,
            self.workflow_file,
        )
        try:
            paths = run_workflow(
                wf,
                replacements,
                output_dir,
                base_url=base_url,
                timeout_sec=timeout_sec,
            )
            return ProviderResult(
                provider=self.provider_name,
                success=True,
                output_paths=paths,
            )
        except RuntimeError as exc:
            logger.warning("%s: workflow failed: %s", self.provider_name, exc)
            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error=str(exc),
            )
