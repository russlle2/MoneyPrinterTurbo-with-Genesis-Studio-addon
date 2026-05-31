"""
Genesis Studio — MotionCtrl provider client.

Preferred for controlled camera motion: pans, pushes, zooms.
Routes generation through ComfyUI using motionctrl.json blueprint.
"""

from __future__ import annotations

from typing import Any

from genesis.integrations.video_provider_base import VideoProviderBase, ensure_output_dir
from genesis.utils.logger import get_logger

logger = get_logger("motionctrl_client")

_DEFAULTS = {
    "motion_type": "camera_pan",
    "strength": 0.7,
    "fps": 8,
    "frames": 14,
    "steps": 22,
    "seed": 0,
}

MOTION_TYPES = frozenset({
    "camera_pan",
    "camera_push",
    "camera_zoom",
    "object_move",
    "pan_right",
    "pan_left",
    "push_in",
    "pull_out",
})


class MotionCtrlClient(VideoProviderBase):
    provider_name = "motionctrl"
    workflow_file = "motionctrl.json"
    model_family = "motionctrl"
    model_placeholder = "MOTIONCTRL_MODEL_PATH"

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
        motion_type = kwargs.get("motion_type", _DEFAULTS["motion_type"])
        if motion_type not in MOTION_TYPES:
            logger.warning(
                "motionctrl: unknown motion_type '%s', using 'camera_pan'", motion_type
            )
            motion_type = "camera_pan"

        replacements = self._build_base_replacements(
            prompt=prompt,
            output_dir=str(out_dir),
            negative_prompt=kwargs.get("negative_prompt", ""),
            model_override=kwargs.get("motionctrl_model_path"),
        )
        sdxl = self._get_sdxl_model(kwargs)
        if sdxl:
            replacements["SDXL_OR_FLUX_MODEL_PATH"] = sdxl
        replacements["INPUT_IMAGE_PATH"] = kwargs.get("init_image", "")
        replacements["CAMERA_MOTION"] = motion_type

        result = self._run(
            replacements, str(out_dir),
            base_url=kwargs.get("base_url"),
            timeout_sec=int(kwargs.get("timeout_sec", 600)),
        )
        if not result.success:
            raise RuntimeError(
                f"MotionCtrl generation failed: {result.error}. "
                "Ensure MotionCtrl ComfyUI custom nodes are installed."
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
            raise RuntimeError("MotionCtrl generate_video_from_image: image_path is required.")
        kwargs.setdefault("init_image", image_path)
        return self.generate_video_from_prompt(prompt, output_path, **kwargs)


_client = MotionCtrlClient()


def generate_video_from_prompt(prompt: str, output_path: str, **kwargs: Any) -> str:
    return _client.generate_video_from_prompt(prompt, output_path, **kwargs)


def generate_video_from_image(
    image_path: str, prompt: str, output_path: str, **kwargs: Any
) -> str:
    return _client.generate_video_from_image(image_path, prompt, output_path, **kwargs)
