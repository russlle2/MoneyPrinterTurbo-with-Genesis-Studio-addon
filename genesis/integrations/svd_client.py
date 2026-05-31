"""
Genesis Studio — SVD (Stable Video Diffusion) provider client.

Preferred for smooth cinematic image-to-video b-roll.
Routes generation through ComfyUI using svd.json blueprint.
"""

from __future__ import annotations

from typing import Any

from genesis.integrations.video_provider_base import VideoProviderBase, ensure_output_dir
from genesis.utils.logger import get_logger

logger = get_logger("svd_client")

_DEFAULTS = {
    "frames": 16,
    "fps": 12,
    "motion_bucket_id": 127,
    "steps": 20,
    "seed": 0,
}


class SVDClient(VideoProviderBase):
    provider_name = "svd"
    workflow_file = "svd.json"
    model_family = "svd"
    model_placeholder = "SVD_MODEL_PATH"

    def generate_video_from_prompt(
        self,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        # SVD is image-conditioned; prompt-only mode requires an init image.
        init_image = kwargs.get("init_image", "")
        if not init_image:
            raise RuntimeError(
                "SVD generate_video_from_prompt: SVD requires an init image. "
                "Pass init_image=<path> or use generate_video_from_image() instead."
            )
        return self.generate_video_from_image(init_image, prompt, output_path, **kwargs)

    def generate_video_from_image(
        self,
        image_path: str,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        if not image_path:
            raise RuntimeError("SVD generate_video_from_image: image_path is required.")
        out_dir = ensure_output_dir(output_path)
        replacements = self._build_base_replacements(
            prompt=prompt,
            output_dir=str(out_dir),
            negative_prompt=kwargs.get("negative_prompt", ""),
            image_path=image_path,
            model_override=kwargs.get("model_path"),
        )
        result = self._run(
            replacements, str(out_dir),
            base_url=kwargs.get("base_url"),
            timeout_sec=int(kwargs.get("timeout_sec", 600)),
        )
        if not result.success:
            raise RuntimeError(
                f"SVD generation failed: {result.error}. "
                "Ensure SVD ComfyUI nodes (ImageOnlyCheckpointLoader, SVD_img2vid_Conditioning) "
                "are installed and an SVD model is available."
            )
        return result.output_paths[0] if result.output_paths else str(out_dir)


_client = SVDClient()


def generate_video_from_prompt(prompt: str, output_path: str, **kwargs: Any) -> str:
    return _client.generate_video_from_prompt(prompt, output_path, **kwargs)


def generate_video_from_image(
    image_path: str, prompt: str, output_path: str, **kwargs: Any
) -> str:
    return _client.generate_video_from_image(image_path, prompt, output_path, **kwargs)
