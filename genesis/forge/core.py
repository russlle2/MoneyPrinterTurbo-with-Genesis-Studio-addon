"""
Genesis Forge — Core

Three generation modes:
  1. text_to_video   — prompt → AI images (FLUX) → animated MP4
                       upgrades to ComfyUI CogVideoX when available
  2. images_to_video — uploaded images → animated/Ken-Burns MP4
                       upgrades to ComfyUI AnimateDiff/SVD when available
  3. hybrid_video    — mix of AI-generated scenes + uploaded images → MP4

All three return a ForgeResult dataclass.
No captions. No voiceover. No script generation.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

STYLE_PROMPTS: dict[str, str] = {
    "cinematic": "cinematic lighting, dramatic composition, film grain, 4K, hyperrealistic",
    "anime": "anime art style, vibrant colors, cel shading, studio ghibli quality",
    "photorealistic": "photorealistic, sharp focus, professional photography, 8K detail",
    "abstract": "abstract art, fluid motion, vivid colors, surreal, artistic",
    "dark": "dark moody atmosphere, deep shadows, noir, dramatic lighting",
    "vibrant": "vibrant saturated colors, high energy, bold composition, dynamic",
}

RESOLUTION_MAP: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}

FPS = 30

# Wan2.1-1.3B is a native 480p model. Generating above this is exponentially
# slower (≈45 s/step at 1080p vs ≈3 s/step at 480p on a 5090) with no quality
# gain — the extra detail is hallucinated. We generate at the model's native
# resolution and Lanczos-upscale to the delivery resolution afterwards.
WAN_NATIVE_LONG_SIDE = 832
WAN_FPS = 16
# Max frames per Wan clip. Must be 4n+1. 81 frames ≈ 5s at 16fps — long enough
# to avoid excessive model reloads while staying within VRAM.
WAN_MAX_FRAMES_PER_CLIP = 81
WAN_MAX_CLIPS = 4


def _wan_gen_dims(width: int, height: int) -> tuple[int, int]:
    """Scale the requested aspect ratio down to Wan's native budget.

    Returns (gen_width, gen_height) with both dimensions multiples of 16 and
    the long side capped at WAN_NATIVE_LONG_SIDE.
    """
    long_side = WAN_NATIVE_LONG_SIDE

    def _round16(v: float) -> int:
        return max(16, int(round(v / 16)) * 16)

    if width >= height:
        gw = long_side
        gh = _round16(long_side * height / width)
    else:
        gh = long_side
        gw = _round16(long_side * width / height)
    return gw, gh


def _wan_clip_plan(duration_seconds: float) -> tuple[int, int]:
    """Return (num_clips, frames_per_clip) for a target duration.

    Prefers a single long clip; only splits into multiple clips when the target
    exceeds one clip's frame budget. Each clip length is forced to 4n+1.
    """
    total_frames = max(WAN_FPS, int(round(duration_seconds * WAN_FPS)))
    num_clips = max(1, math.ceil(total_frames / WAN_MAX_FRAMES_PER_CLIP))
    num_clips = min(num_clips, WAN_MAX_CLIPS)
    frames_per_clip = math.ceil(total_frames / num_clips)
    # Force to nearest valid 4n+1 within bounds.
    frames_per_clip = min(WAN_MAX_FRAMES_PER_CLIP, max(17, frames_per_clip))
    frames_per_clip = ((frames_per_clip - 1) // 4) * 4 + 1
    return num_clips, frames_per_clip


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ForgeResult:
    success: bool
    output_path: str = ""
    engine_used: str = ""         # "comfyui", "pollinations+animation", "animation_only"
    duration_seconds: float = 0.0
    frame_count: int = 0
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# 1. Text → Video
# ---------------------------------------------------------------------------

def text_to_video(
    prompt: str,
    *,
    style: str = "cinematic",
    duration_seconds: float = 10.0,
    aspect_ratio: str = "9:16",
    n_scenes: int | None = None,
    output_dir: str | Path | None = None,
    animation_style: str = "ken_burns",
    transition_style: str = "fade",
    progress_cb: Callable[[str, float], None] | None = None,
) -> ForgeResult:
    """
    Generate a video from a text prompt.

    Flow:
      1. Try ComfyUI CogVideoX (if running at localhost:8188)
      2. Fall back to Pollinations FLUX images + Ken Burns animation

    Args:
        prompt:           What the video should look like / be about.
        style:            Visual style preset (cinematic, anime, etc.)
        duration_seconds: Target video length.
        aspect_ratio:     "9:16", "16:9", or "1:1".
        n_scenes:         Number of AI images to generate (auto-calculated if None).
        output_dir:       Where to save output (defaults to assets/forge_output/).
        animation_style:  Ken Burns effect for each image.
        transition_style: Transition between images.
        progress_cb:      Optional callback(status_message, fraction_0_to_1).

    Returns:
        ForgeResult with output_path set on success.
    """
    t0 = time.time()
    out_dir = _resolve_output_dir(output_dir)
    width, height = RESOLUTION_MAP.get(aspect_ratio, (1080, 1920))
    job_id = uuid.uuid4().hex[:8]
    output_path = out_dir / f"text_to_video_{job_id}.mp4"

    _progress(progress_cb, "Checking ComfyUI...", 0.02)

    # --- Try ComfyUI first ---
    comfyui_ok, comfyui_msg = _check_comfyui()
    if comfyui_ok:
        _progress(progress_cb, "ComfyUI detected — generating real AI video...", 0.05)
        result = _text_to_video_comfyui(
            prompt=prompt,
            style=style,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            output_path=output_path,
            progress_cb=progress_cb,
        )
        if result.success:
            result.elapsed_seconds = time.time() - t0
            return result

    # --- Pollinations fallback ---
    _progress(progress_cb, "Generating AI images via Pollinations FLUX...", 0.05)
    style_suffix = STYLE_PROMPTS.get(style, STYLE_PROMPTS["cinematic"])

    if n_scenes is None:
        n_scenes = max(3, min(12, int(duration_seconds / 3)))

    scene_duration = duration_seconds / n_scenes

    image_paths = _generate_pollinations_scenes(
        prompt=prompt,
        style_suffix=style_suffix,
        n_scenes=n_scenes,
        width=width,
        height=height,
        out_dir=out_dir / f"frames_{job_id}",
        progress_cb=progress_cb,
        progress_start=0.05,
        progress_end=0.75,
    )

    if not image_paths:
        return ForgeResult(
            success=False,
            error="Image generation failed — check internet connection for Pollinations.ai.",
            elapsed_seconds=time.time() - t0,
        )

    _progress(progress_cb, "Animating scenes...", 0.78)
    result = _animate_images_to_mp4(
        image_paths=image_paths,
        output_path=output_path,
        width=width,
        height=height,
        scene_duration=scene_duration,
        animation_style=animation_style,
        transition_style=transition_style,
        fps=FPS,
        progress_cb=progress_cb,
        progress_start=0.78,
        progress_end=0.98,
    )
    result.engine_used = "pollinations+animation"
    result.elapsed_seconds = time.time() - t0

    if not comfyui_ok:
        result.warnings.append(
            f"ComfyUI not running ({comfyui_msg}). "
            "Run SETUP_COMFYUI.md guide for real AI video generation."
        )
    return result


# ---------------------------------------------------------------------------
# 2. Images → Video
# ---------------------------------------------------------------------------

def images_to_video(
    image_paths: list[str | Path],
    *,
    animation_style: str = "ken_burns",
    transition_style: str = "fade",
    duration_per_image: float = 4.0,
    aspect_ratio: str = "9:16",
    use_ai_animation: bool = True,
    output_dir: str | Path | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
) -> ForgeResult:
    """
    Turn uploaded images into an animated video.

    Flow:
      1. If use_ai_animation and ComfyUI running: AnimateDiff / SVD per image
      2. Otherwise: Ken Burns / zoom / pan animation on each image

    Args:
        image_paths:       List of image file paths.
        animation_style:   "ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right", "static".
        transition_style:  "fade", "dissolve", "cut".
        duration_per_image: Seconds each image is shown.
        aspect_ratio:      Output aspect ratio.
        use_ai_animation:  Attempt AnimateDiff/SVD if ComfyUI available.
        output_dir:        Output directory.
        progress_cb:       Optional progress callback.

    Returns:
        ForgeResult with output_path set on success.
    """
    t0 = time.time()
    if not image_paths:
        return ForgeResult(success=False, error="No images provided.", elapsed_seconds=0.0)

    out_dir = _resolve_output_dir(output_dir)
    width, height = RESOLUTION_MAP.get(aspect_ratio, (1080, 1920))
    job_id = uuid.uuid4().hex[:8]
    output_path = out_dir / f"images_to_video_{job_id}.mp4"

    _progress(progress_cb, "Checking ComfyUI...", 0.02)
    comfyui_ok, comfyui_msg = _check_comfyui()

    if use_ai_animation and comfyui_ok:
        _progress(progress_cb, "ComfyUI detected — running AnimateDiff on each image...", 0.05)
        result = _images_to_video_comfyui(
            image_paths=[Path(p) for p in image_paths],
            output_path=output_path,
            width=width,
            height=height,
            duration_per_image=duration_per_image,
            progress_cb=progress_cb,
        )
        if result.success:
            result.elapsed_seconds = time.time() - t0
            return result

    _progress(progress_cb, "Animating your images...", 0.08)
    result = _animate_images_to_mp4(
        image_paths=[str(p) for p in image_paths],
        output_path=output_path,
        width=width,
        height=height,
        scene_duration=duration_per_image,
        animation_style=animation_style,
        transition_style=transition_style,
        fps=FPS,
        progress_cb=progress_cb,
        progress_start=0.08,
        progress_end=0.98,
    )
    result.engine_used = "animation_only"
    result.elapsed_seconds = time.time() - t0

    if use_ai_animation and not comfyui_ok:
        result.warnings.append(
            f"ComfyUI not running ({comfyui_msg}). "
            "See SETUP_COMFYUI.md for real AI image-to-video with AnimateDiff/SVD."
        )
    return result


# ---------------------------------------------------------------------------
# 3. Hybrid → Video
# ---------------------------------------------------------------------------

@dataclass
class HybridScene:
    """A single scene in a hybrid video."""
    kind: Literal["prompt", "image"]
    content: str            # prompt text or image file path
    duration_seconds: float = 4.0
    style: str = "cinematic"
    animation: str = "ken_burns"


def hybrid_video(
    scenes: list[HybridScene],
    *,
    transition_style: str = "fade",
    aspect_ratio: str = "9:16",
    output_dir: str | Path | None = None,
    progress_cb: Callable[[str, float], None] | None = None,
) -> ForgeResult:
    """
    Mix AI-generated scenes (from prompts) with uploaded images into one video.

    Args:
        scenes:            Ordered list of HybridScene items.
        transition_style:  Transition between all scenes.
        aspect_ratio:      Output aspect ratio.
        output_dir:        Output directory.
        progress_cb:       Optional progress callback.

    Returns:
        ForgeResult with output_path set on success.
    """
    t0 = time.time()
    if not scenes:
        return ForgeResult(success=False, error="No scenes provided.", elapsed_seconds=0.0)

    out_dir = _resolve_output_dir(output_dir)
    width, height = RESOLUTION_MAP.get(aspect_ratio, (1080, 1920))
    job_id = uuid.uuid4().hex[:8]
    output_path = out_dir / f"hybrid_video_{job_id}.mp4"
    frames_dir = out_dir / f"hybrid_frames_{job_id}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    comfyui_ok, _ = _check_comfyui()

    resolved_image_paths: list[str] = []
    scene_durations: list[float] = []
    scene_animations: list[str] = []
    warnings: list[str] = []

    total = len(scenes)
    for idx, scene in enumerate(scenes):
        frac_start = 0.05 + (idx / total) * 0.70
        frac_end = 0.05 + ((idx + 1) / total) * 0.70
        _progress(progress_cb, f"Processing scene {idx + 1}/{total}...", frac_start)

        if scene.kind == "image":
            p = Path(scene.content)
            if not p.exists():
                warnings.append(f"Scene {idx + 1}: image not found — {scene.content}")
                continue
            resolved_image_paths.append(str(p))
            scene_durations.append(scene.duration_seconds)
            scene_animations.append(scene.animation)

        elif scene.kind == "prompt":
            style_suffix = STYLE_PROMPTS.get(scene.style, STYLE_PROMPTS["cinematic"])
            img_path = frames_dir / f"scene_{idx:03d}.jpg"

            success = _generate_one_pollinations_image(
                prompt=scene.content,
                style_suffix=style_suffix,
                width=width,
                height=height,
                out_path=img_path,
            )
            if success:
                resolved_image_paths.append(str(img_path))
                scene_durations.append(scene.duration_seconds)
                scene_animations.append(scene.animation)
            else:
                warnings.append(f"Scene {idx + 1}: image generation failed for prompt.")

        _progress(progress_cb, f"Scene {idx + 1} ready.", frac_end)

    if not resolved_image_paths:
        return ForgeResult(
            success=False,
            error="All scenes failed to generate.",
            warnings=warnings,
            elapsed_seconds=time.time() - t0,
        )

    _progress(progress_cb, "Assembling final video...", 0.78)
    result = _animate_images_to_mp4_variable(
        image_paths=resolved_image_paths,
        output_path=output_path,
        width=width,
        height=height,
        scene_durations=scene_durations,
        animation_styles=scene_animations,
        transition_style=transition_style,
        fps=FPS,
        progress_cb=progress_cb,
        progress_start=0.78,
        progress_end=0.98,
    )
    result.engine_used = "comfyui+animation" if comfyui_ok else "pollinations+animation"
    result.warnings.extend(warnings)
    result.elapsed_seconds = time.time() - t0
    return result


# ---------------------------------------------------------------------------
# ComfyUI integration
# ---------------------------------------------------------------------------

def _check_comfyui() -> tuple[bool, str]:
    """Quick check if ComfyUI is reachable at localhost:8188."""
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2)
        return True, ""
    except Exception as e:
        return False, str(e)


def _text_to_video_comfyui(
    *,
    prompt: str,
    style: str,
    duration_seconds: float,
    width: int,
    height: int,
    output_path: Path,
    progress_cb: Callable | None,
) -> ForgeResult:
    """Text-to-video via Wan2.1 T2V workflow in ComfyUI."""
    try:
        import json
        import random
        import time
        import urllib.request

        _progress(progress_cb, "Sending Wan2.1 T2V job to ComfyUI...", 0.08)

        style_suffix = STYLE_PROMPTS.get(style, "")
        full_prompt = f"{prompt}, {style_suffix}" if style_suffix else prompt
        neg_prompt = "blurry, low quality, distorted, flickering, bad quality, worst quality"

        fps = WAN_FPS
        gen_w, gen_h = _wan_gen_dims(width, height)
        num_clips, frames_per_clip = _wan_clip_plan(duration_seconds)

        workflow_path = (
            Path(__file__).parent.parent
            / "integrations" / "comfyui_workflows" / "wan2_t2v.json"
        )

        clip_paths: list[Path] = []
        for clip_idx in range(num_clips):
            _progress(
                progress_cb,
                f"Wan2.1 T2V @ {gen_w}x{gen_h}: clip {clip_idx + 1}/{num_clips}...",
                0.08 + (clip_idx / num_clips) * 0.75,
            )
            with open(workflow_path, encoding="utf-8") as f:
                workflow = json.load(f)
            workflow.pop("genesis_metadata", None)

            clip_path = output_path.parent / f"_wan_t2v_{output_path.stem}_{clip_idx:03d}.mp4"
            _patch_node(workflow, "4", "text", full_prompt)
            _patch_node(workflow, "5", "text", neg_prompt)
            _patch_node(workflow, "6", "width", gen_w)
            _patch_node(workflow, "6", "height", gen_h)
            _patch_node(workflow, "6", "length", frames_per_clip)
            _patch_node(workflow, "7", "seed", random.randint(0, 2**31))
            _patch_node(workflow, "9", "filename_prefix", f"forge_t2v_{clip_idx:03d}")

            clip_result = _submit_and_wait_comfyui(workflow, clip_path, fps=fps, progress_cb=progress_cb)
            if clip_result.success:
                clip_paths.append(clip_path)

        if not clip_paths:
            return ForgeResult(success=False, error="No clips generated by ComfyUI")

        _progress(progress_cb, f"Upscaling to {width}x{height} and finalizing...", 0.9)
        from genesis.forge.video_assembler import assemble_segments
        segments: list[dict] = []
        for i, p in enumerate(clip_paths):
            seg: dict = {"video": str(p)}
            if i > 0:
                seg["transition"] = {"style": "fade", "duration": 0.3}
            segments.append(seg)
        assemble_segments(segments, output_path, fps=fps, target_size=(width, height))

        return ForgeResult(
            success=True,
            output_path=str(output_path),
            engine_used="comfyui_wan2_t2v",
            duration_seconds=duration_seconds,
        )

    except Exception as e:
        return ForgeResult(success=False, error=f"ComfyUI Wan2.1 T2V error: {e}")


def _images_to_video_comfyui(
    *,
    image_paths: list[Path],
    output_path: Path,
    width: int,
    height: int,
    duration_per_image: float,
    progress_cb: Callable | None,
) -> ForgeResult:
    """Image-to-video via Wan2.1 I2V workflow in ComfyUI — one clip per image, then stitch."""
    try:
        import json
        import random

        workflow_path = (
            Path(__file__).parent.parent
            / "integrations" / "comfyui_workflows" / "wan2_i2v.json"
        )
        with open(workflow_path, encoding="utf-8") as f:
            base_workflow = json.load(f)
        base_workflow.pop("genesis_metadata", None)

        fps = WAN_FPS
        gen_w, gen_h = _wan_gen_dims(width, height)
        frames = max(17, min(WAN_MAX_FRAMES_PER_CLIP, int(duration_per_image * fps / 4) * 4 + 1))
        animated_clips: list[Path] = []

        for i, img_path in enumerate(image_paths):
            _progress(
                progress_cb,
                f"Wan2.1 I2V @ {gen_w}x{gen_h}: image {i + 1}/{len(image_paths)}...",
                0.1 + (i / len(image_paths)) * 0.75,
            )
            import copy
            workflow = copy.deepcopy(base_workflow)
            clip_path = output_path.parent / f"wan_i2v_{i:03d}.mp4"

            # Upload image to ComfyUI then reference it
            img_name = _upload_image_to_comfyui(img_path)
            if not img_name:
                continue

            _patch_node(workflow, "1", "image", img_name)
            _patch_node(workflow, "5", "text", "cinematic motion, smooth animation, high quality")
            _patch_node(workflow, "6", "text", "blurry, distorted, flickering, bad quality")
            _patch_node(workflow, "7", "width", gen_w)
            _patch_node(workflow, "7", "height", gen_h)
            _patch_node(workflow, "7", "length", frames)
            _patch_node(workflow, "8", "seed", random.randint(0, 2**31))
            _patch_node(workflow, "10", "filename_prefix", f"forge_i2v_{i:03d}")

            result = _submit_and_wait_comfyui(workflow, clip_path, fps=fps, progress_cb=progress_cb)
            if result.success:
                animated_clips.append(clip_path)

        if not animated_clips:
            return ForgeResult(success=False, error="Wan2.1 I2V produced no clips")

        _progress(progress_cb, f"Upscaling to {width}x{height} and finalizing...", 0.9)
        from genesis.forge.video_assembler import assemble_segments
        segments = [
            {"video": str(p), "transition": {"style": "fade", "duration": 0.4}}
            for p in animated_clips
        ]
        assemble_segments(segments, output_path, fps=fps, target_size=(width, height))

        return ForgeResult(
            success=True,
            output_path=str(output_path),
            engine_used="comfyui_wan2_i2v",
        )
    except Exception as e:
        return ForgeResult(success=False, error=f"ComfyUI Wan2.1 I2V error: {e}")


# ---------------------------------------------------------------------------
# ComfyUI workflow helpers
# ---------------------------------------------------------------------------

def _patch_node(workflow: dict, node_id: str, key: str, value) -> None:
    if node_id in workflow and "inputs" in workflow[node_id]:
        workflow[node_id]["inputs"][key] = value


def _upload_image_to_comfyui(img_path: Path) -> str | None:
    """Upload a local image file to ComfyUI's input folder and return the filename."""
    try:
        import urllib.request
        import mimetypes
        boundary = "----FormBoundaryGenesis"
        mime = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
        with open(img_path, "rb") as f:
            img_data = f.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{img_path.name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            "http://127.0.0.1:8188/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        import json
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            return result.get("name")
    except Exception:
        return None


def _submit_and_wait_comfyui(
    workflow: dict,
    output_path: Path,
    *,
    fps: int = 16,
    timeout: int = 300,
    progress_cb: Callable | None,
) -> ForgeResult:
    """Submit a ComfyUI workflow, poll until done, copy output to output_path."""
    import json
    import time
    import urllib.request
    import uuid as _uuid

    client_id = _uuid.uuid4().hex
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()

    req = urllib.request.Request(
        "http://127.0.0.1:8188/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        prompt_id = resp.get("prompt_id")
        if not prompt_id:
            return ForgeResult(success=False, error=f"ComfyUI rejected workflow: {resp}")
    except Exception as e:
        return ForgeResult(success=False, error=f"ComfyUI submit failed: {e}")

    # Poll until complete
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(2)
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:8188/history/{prompt_id}", timeout=10
            ) as r:
                history = json.loads(r.read())
            if prompt_id in history:
                job = history[prompt_id]
                status_str = job.get("status", {}).get("status_str", "")
                outputs = job.get("outputs", {})
                video_file = _extract_video_from_outputs(outputs)
                if video_file:
                    comfyui_output = Path("C:/ComfyUI_windows_portable/ComfyUI/output") / video_file
                    if comfyui_output.exists():
                        import shutil
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(comfyui_output, output_path)
                        return ForgeResult(
                            success=True,
                            output_path=str(output_path),
                            engine_used="comfyui",
                        )
                    return ForgeResult(success=False, error=f"Output file not found: {comfyui_output}")
                # Job is in history but no video — it errored, return immediately
                err_msg = ""
                for msg in job.get("status", {}).get("messages", []):
                    if isinstance(msg, list) and msg[0] == "execution_error":
                        err_msg = msg[1].get("exception_message", "")[:200]
                        break
                return ForgeResult(success=False, error=f"ComfyUI job failed ({status_str}): {err_msg}")
        except Exception:
            pass
        if progress_cb:
            elapsed = int(time.time() - t0)
            _progress(progress_cb, f"ComfyUI generating... ({elapsed}s)", 0.3 + min(0.5, elapsed / timeout))

    return ForgeResult(success=False, error=f"ComfyUI timed out after {timeout}s")


def _extract_video_from_outputs(outputs: dict) -> str | None:
    """Find the first video filename in ComfyUI history outputs."""
    for node_output in outputs.values():
        for key in ("gifs", "videos", "images"):
            items = node_output.get(key, [])
            for item in items:
                fname = item.get("filename", "")
                if fname.endswith((".mp4", ".webm", ".gif")):
                    return fname
    return None


# ---------------------------------------------------------------------------
# Pollinations image generation helpers
# ---------------------------------------------------------------------------

def _generate_pollinations_scenes(
    *,
    prompt: str,
    style_suffix: str,
    n_scenes: int,
    width: int,
    height: int,
    out_dir: Path,
    progress_cb: Callable | None,
    progress_start: float,
    progress_end: float,
) -> list[str]:
    from genesis.integrations.pollinations_client import generate_image

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    # Build scene prompts: vary the angle/framing slightly per scene
    scene_variants = [
        "",
        "close-up detail shot",
        "wide establishing shot",
        "medium shot",
        "overhead aerial view",
        "low angle dramatic perspective",
        "golden hour lighting",
        "blue hour atmosphere",
        "extreme close-up",
        "silhouette against sky",
        "action shot",
        "environmental portrait",
    ]

    for i in range(n_scenes):
        frac = progress_start + (i / n_scenes) * (progress_end - progress_start)
        _progress(progress_cb, f"Generating scene {i + 1}/{n_scenes}...", frac)

        variant = scene_variants[i % len(scene_variants)]
        scene_prompt = f"{prompt}, {variant}, {style_suffix}" if variant else f"{prompt}, {style_suffix}"

        out_path = out_dir / f"scene_{i:03d}.jpg"
        result = generate_image(
            scene_prompt,
            out_path,
            width=width,
            height=height,
            model="flux",
            max_retries=2,
            timeout=90,
        )
        if result.get("success"):
            paths.append(str(out_path))
        else:
            # Don't fail the whole job for one scene
            pass

    return paths


def _generate_one_pollinations_image(
    *,
    prompt: str,
    style_suffix: str,
    width: int,
    height: int,
    out_path: Path,
) -> bool:
    from genesis.integrations.pollinations_client import generate_image
    result = generate_image(
        f"{prompt}, {style_suffix}",
        out_path,
        width=width,
        height=height,
        model="flux",
        max_retries=2,
        timeout=90,
    )
    return bool(result.get("success"))


# ---------------------------------------------------------------------------
# Animation assembly helpers
# ---------------------------------------------------------------------------

def _animate_images_to_mp4(
    *,
    image_paths: list[str],
    output_path: Path,
    width: int,
    height: int,
    scene_duration: float,
    animation_style: str,
    transition_style: str,
    fps: int,
    progress_cb: Callable | None,
    progress_start: float,
    progress_end: float,
) -> ForgeResult:
    return _animate_images_to_mp4_variable(
        image_paths=image_paths,
        output_path=output_path,
        width=width,
        height=height,
        scene_durations=[scene_duration] * len(image_paths),
        animation_styles=[animation_style] * len(image_paths),
        transition_style=transition_style,
        fps=fps,
        progress_cb=progress_cb,
        progress_start=progress_start,
        progress_end=progress_end,
    )


def _animate_images_to_mp4_variable(
    *,
    image_paths: list[str],
    output_path: Path,
    width: int,
    height: int,
    scene_durations: list[float],
    animation_styles: list[str],
    transition_style: str,
    fps: int,
    progress_cb: Callable | None,
    progress_start: float,
    progress_end: float,
) -> ForgeResult:
    from genesis.forge.animator import frames_for_image
    from genesis.forge.video_assembler import assemble_segments

    n = len(image_paths)
    segments: list[dict] = []
    for i, (img_path, dur, anim) in enumerate(zip(image_paths, scene_durations, animation_styles)):
        seg: dict = {
            "label": f"scene_{i}",
            "frames": frames_for_image(
                img_path,
                duration_seconds=dur,
                animation=anim,
                width=width,
                height=height,
                fps=fps,
            ),
        }
        if i > 0:
            seg["transition"] = {"style": transition_style, "duration": 0.5}
        segments.append(seg)

    total_frames = sum(int(d * fps) for d in scene_durations)
    written = [0]

    def _seg_progress(label: str, count: int) -> None:
        written[0] = count
        frac = progress_start + min(1.0, count / max(total_frames, 1)) * (progress_end - progress_start)
        _progress(progress_cb, f"Rendering {label}...", frac)

    try:
        assemble_segments(segments, output_path, fps=fps, progress_cb=_seg_progress)
        return ForgeResult(
            success=True,
            output_path=str(output_path),
            engine_used="animation_only",
            frame_count=written[0],
            duration_seconds=sum(scene_durations),
        )
    except Exception as e:
        return ForgeResult(success=False, error=f"Video assembly failed: {e}")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _resolve_output_dir(output_dir: str | Path | None) -> Path:
    if output_dir:
        p = Path(output_dir)
    else:
        p = Path("assets") / "forge_output"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _progress(cb: Callable | None, message: str, fraction: float) -> None:
    if cb:
        try:
            cb(message, fraction)
        except Exception:
            pass
