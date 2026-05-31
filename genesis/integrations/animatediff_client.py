"""
Genesis Studio — AnimateDiff provider client.

Preferred for stylized animated b-roll and cinematic ambience.
Routes generation through ComfyUI using animatediff.json blueprint.
"""

from __future__ import annotations

from typing import Any

from genesis.integrations.video_provider_base import VideoProviderBase, ensure_output_dir
from genesis.utils.logger import get_logger

logger = get_logger("animatediff_client")

_DEFAULTS = {
    "fps": 12,
    "frames": 16,
    "motion_scale": 1.0,
    "steps": 20,
    "seed": 0,
}


class AnimateDiffClient(VideoProviderBase):
    provider_name = "animatediff"
    workflow_file = "animatediff.json"
    model_family = "animatediff"
    model_placeholder = "ANIMATEDIFF_MODEL_PATH"

    def _get_sdxl_model(self, kwargs: dict[str, Any]) -> str | None:
        override = kwargs.get("sdxl_model_path") or kwargs.get("model_path")
        if override:
            return str(override)
        from genesis.integrations.video_provider_base import first_candidate
        return first_candidate("sdxl") or first_candidate("flux")

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
            model_override=kwargs.get("animatediff_model_path"),
        )
        sdxl = self._get_sdxl_model(kwargs)
        if sdxl:
            replacements["SDXL_OR_FLUX_MODEL_PATH"] = sdxl
        replacements["INPUT_IMAGE_PATH"] = kwargs.get("init_image", "")
        result = self._run(
            replacements, str(out_dir),
            base_url=kwargs.get("base_url"),
            timeout_sec=int(kwargs.get("timeout_sec", 600)),
        )
        if not result.success:
            raise RuntimeError(
                f"AnimateDiff generation failed: {result.error}. "
                "Ensure AnimateDiff-Evolved nodes are installed via ComfyUI Manager."
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
            raise RuntimeError("AnimateDiff generate_video_from_image: image_path is required.")
        kwargs.setdefault("init_image", image_path)
        return self.generate_video_from_prompt(prompt, output_path, **kwargs)


_client = AnimateDiffClient()


def generate_video_from_prompt(prompt: str, output_path: str, **kwargs: Any) -> str:
    return _client.generate_video_from_prompt(prompt, output_path, **kwargs)


def generate_video_from_image(
    image_path: str, prompt: str, output_path: str, **kwargs: Any
) -> str:
    return _client.generate_video_from_image(image_path, prompt, output_path, **kwargs)
