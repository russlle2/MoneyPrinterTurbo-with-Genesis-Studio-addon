"""
Genesis Studio — CogVideoX provider client.

Preferred for hero shots and narrative image-to-video scenes.
Routes generation through ComfyUI using cogvideox.json blueprint.
"""

from __future__ import annotations

from typing import Any

from genesis.integrations.video_provider_base import VideoProviderBase, ensure_output_dir
from genesis.utils.logger import get_logger

logger = get_logger("cogvideox_client")

_DEFAULTS = {
    "frames": 16,
    "fps": 12,
    "guidance_scale": 4.0,
    "steps": 30,
    "seed": 0,
}


class CogVideoXClient(VideoProviderBase):
    provider_name = "cogvideox"
    workflow_file = "cogvideox.json"
    model_family = "cogvideox"
    model_placeholder = "COGVIDEOX_MODEL_PATH"

    def generate_video_from_prompt(
        self,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        out_dir = ensure_output_dir(output_path)
        replacements = self._build_base_replacements(
            prompt=prompt,
            output_dir=str(out_dir),
            negative_prompt=kwargs.get("negative_prompt", ""),
            model_override=kwargs.get("model_path"),
        )
        # No image — use blank/placeholder so workflow can handle prompt-only mode
        replacements["INPUT_IMAGE_PATH"] = kwargs.get("init_image", "")
        _apply_extra_settings(replacements, kwargs)
        result = self._run(
            replacements, str(out_dir),
            base_url=kwargs.get("base_url"),
            timeout_sec=int(kwargs.get("timeout_sec", 600)),
        )
        if not result.success:
            raise RuntimeError(
                f"CogVideoX generation failed: {result.error}. "
                "Ensure CogVideoX ComfyUI nodes are installed and a model is available at "
                f"{self.model_placeholder}."
            )
        return result.output_paths[0] if result.output_paths else str(out_dir)

    def generate_video_from_image(
        self,
        image_path: str,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        if not image_path:
            raise RuntimeError("CogVideoX generate_video_from_image: image_path is required.")
        out_dir = ensure_output_dir(output_path)
        replacements = self._build_base_replacements(
            prompt=prompt,
            output_dir=str(out_dir),
            negative_prompt=kwargs.get("negative_prompt", ""),
            image_path=image_path,
            model_override=kwargs.get("model_path"),
        )
        _apply_extra_settings(replacements, kwargs)
        result = self._run(
            replacements, str(out_dir),
            base_url=kwargs.get("base_url"),
            timeout_sec=int(kwargs.get("timeout_sec", 600)),
        )
        if not result.success:
            raise RuntimeError(
                f"CogVideoX generation failed: {result.error}. "
                "Ensure CogVideoX ComfyUI nodes are installed and a model is discoverable."
            )
        return result.output_paths[0] if result.output_paths else str(out_dir)


def _apply_extra_settings(replacements: dict[str, str], kwargs: dict[str, Any]) -> None:
    """Inject numeric overrides as string replacements (informational; workflow uses defaults)."""
    if "frames" in kwargs:
        replacements["_frames"] = str(kwargs["frames"])
    if "guidance_scale" in kwargs:
        replacements["_cfg"] = str(kwargs["guidance_scale"])


# Module-level convenience functions
_client = CogVideoXClient()


def generate_video_from_prompt(prompt: str, output_path: str, **kwargs: Any) -> str:
    return _client.generate_video_from_prompt(prompt, output_path, **kwargs)


def generate_video_from_image(
    image_path: str, prompt: str, output_path: str, **kwargs: Any
) -> str:
    return _client.generate_video_from_image(image_path, prompt, output_path, **kwargs)
