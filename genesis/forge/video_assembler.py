"""
Genesis Forge — Video Assembler

Stitches animated frames and/or video clips into a final MP4
using imageio + ffmpeg. No moviepy dependency.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Generator, Iterable

import cv2
import imageio
import numpy as np

FPS = 30


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def frames_to_mp4(
    frames: Iterable[np.ndarray],
    output_path: str | Path,
    *,
    fps: int = FPS,
    quality: int = 8,
    progress_cb: Callable[[int], None] | None = None,
) -> Path:
    """
    Write an iterable of BGR numpy frames to an H.264 MP4 file.

    Args:
        frames:      Iterable of (H, W, 3) uint8 BGR arrays.
        output_path: Destination .mp4 path.
        fps:         Output frame rate.
        quality:     imageio quality 0-10 (higher = better, larger file).
        progress_cb: Optional callback called with frame count written so far.

    Returns:
        Path to the written file.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    writer = imageio.get_writer(
        str(out),
        fps=fps,
        quality=quality,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )
    count = 0
    try:
        for frame in frames:
            rgb = _bgr_to_rgb(frame)
            writer.append_data(rgb)
            count += 1
            if progress_cb and count % fps == 0:
                progress_cb(count)
    finally:
        writer.close()

    return out


def assemble_segments(
    segments: list[dict],
    output_path: str | Path,
    *,
    fps: int = FPS,
    target_size: tuple[int, int] | None = None,
    quality: int = 9,
    progress_cb: Callable[[str, int], None] | None = None,
) -> Path:
    """
    Assemble multiple segments into one MP4.

    Each segment dict has:
        "frames": Iterable[np.ndarray]  — pre-generated frames, OR
        "video":  str | Path            — existing video file to splice in

    A "transition" key (optional) on segments after the first:
        {"style": "fade"|"dissolve"|"cut", "duration": 0.5}

    Args:
        segments:    List of segment dicts.
        output_path: Destination .mp4 path.
        fps:         Frame rate.
        target_size: Optional (width, height). When set, every frame is
                     Lanczos-resized to this size before writing. Used to
                     upscale native-resolution AI clips (e.g. Wan 480p) to the
                     final delivery resolution (e.g. 1080p) in a single pass.
        quality:     imageio quality 0-10 (higher = better, larger file).
        progress_cb: Optional callback(segment_label, frame_count).

    Returns:
        Path to written file.
    """
    from genesis.forge.animator import transition_frames, fade_in_frames, fade_out_frames

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    writer = imageio.get_writer(
        str(out),
        fps=fps,
        quality=quality,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )

    last_frame: np.ndarray | None = None
    total = 0

    try:
        for idx, seg in enumerate(segments):
            label = seg.get("label", f"segment_{idx}")
            transition = seg.get("transition", {})

            frame_gen = _segment_frames(seg, fps)

            seg_frames: list[np.ndarray] = [
                _fit_frame(f, target_size) for f in frame_gen
            ]
            if not seg_frames:
                continue

            # Inter-segment transition
            if last_frame is not None and transition:
                t_style = transition.get("style", "fade")
                t_dur = float(transition.get("duration", 0.5))
                for tf in transition_frames(
                    last_frame, seg_frames[0], style=t_style, duration_seconds=t_dur, fps=fps
                ):
                    writer.append_data(_bgr_to_rgb(tf))
                    total += 1
            elif last_frame is None:
                # Fade in on first segment
                for ff in fade_in_frames(seg_frames[0], duration_seconds=0.3, fps=fps):
                    writer.append_data(_bgr_to_rgb(ff))
                    total += 1

            for frame in seg_frames:
                writer.append_data(_bgr_to_rgb(frame))
                total += 1
                last_frame = frame

            if progress_cb:
                progress_cb(label, total)

        # Fade out last frame
        if last_frame is not None:
            for ff in fade_out_frames(last_frame, duration_seconds=0.4, fps=fps):
                writer.append_data(_bgr_to_rgb(ff))

    finally:
        writer.close()

    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _segment_frames(seg: dict, fps: int) -> Generator[np.ndarray, None, None]:
    """Resolve a segment dict to its frame stream."""
    if "frames" in seg:
        yield from seg["frames"]
    elif "video" in seg:
        yield from _read_video_frames(seg["video"], fps)


def _read_video_frames(video_path: str | Path, fps: int) -> Generator[np.ndarray, None, None]:
    """Read frames from an existing video file, resampling to target fps."""
    reader = imageio.get_reader(str(video_path))
    meta = reader.get_meta_data()
    src_fps = meta.get("fps", fps) or fps
    step = max(1, round(src_fps / fps))
    try:
        for i, frame in enumerate(reader):
            if i % step == 0:
                # imageio reads RGB — convert to BGR for consistency
                yield frame[:, :, :3][..., ::-1].copy()
    finally:
        reader.close()


def _fit_frame(frame: np.ndarray, target_size: tuple[int, int] | None) -> np.ndarray:
    """Resize a frame to target_size (width, height) with high-quality Lanczos.

    Aspect ratio is preserved via cover-crop so AI clips generated at a slightly
    different native aspect (e.g. 832x464) fill the final frame with no bars.
    """
    if target_size is None:
        return frame
    tw, th = target_size
    h, w = frame.shape[:2]
    if w == tw and h == th:
        return frame
    scale = max(tw / w, th / h)
    nw, nh = max(tw, int(round(w * scale))), max(th, int(round(h * scale)))
    interp = cv2.INTER_LANCZOS4 if scale >= 1.0 else cv2.INTER_AREA
    resized = cv2.resize(frame, (nw, nh), interpolation=interp)
    x0 = (nw - tw) // 2
    y0 = (nh - th) // 2
    return resized[y0:y0 + th, x0:x0 + tw]


def _bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    """Convert BGR to RGB (imageio writes RGB)."""
    if frame.ndim == 3 and frame.shape[2] == 3:
        return frame[..., ::-1].copy()
    return frame
