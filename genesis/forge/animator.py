"""
Genesis Forge — Animator

Produces animated video frames from still images using cv2 + numpy.
No moviepy required. Effects: Ken Burns, zoom-in, zoom-out, pan-left,
pan-right, fade-in, fade-out, dissolve transitions.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Generator

import cv2
import numpy as np

FPS = 30

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

ANIMATION_STYLES = ("ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right", "static")
TRANSITION_STYLES = ("fade", "cut", "dissolve")


def frames_for_image(
    image_path: str | Path,
    *,
    duration_seconds: float = 4.0,
    animation: str = "ken_burns",
    width: int = 1080,
    height: int = 1920,
    fps: int = FPS,
) -> Generator[np.ndarray, None, None]:
    """
    Yield BGR frames animating a single still image.

    Args:
        image_path:        Source image file.
        duration_seconds:  How long this image occupies in the video.
        animation:         One of ANIMATION_STYLES.
        width/height:      Output frame resolution.
        fps:               Frames per second.

    Yields:
        numpy arrays (H, W, 3) dtype uint8 in BGR order.
    """
    img = _load_and_fit(str(image_path), width, height)
    n_frames = max(1, round(duration_seconds * fps))

    if animation == "ken_burns":
        yield from _ken_burns(img, n_frames, width, height)
    elif animation == "zoom_in":
        yield from _zoom(img, n_frames, width, height, direction="in")
    elif animation == "zoom_out":
        yield from _zoom(img, n_frames, width, height, direction="out")
    elif animation == "pan_left":
        yield from _pan(img, n_frames, width, height, direction="left")
    elif animation == "pan_right":
        yield from _pan(img, n_frames, width, height, direction="right")
    else:  # static
        for _ in range(n_frames):
            yield img.copy()


def transition_frames(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    *,
    style: str = "fade",
    duration_seconds: float = 0.5,
    fps: int = FPS,
) -> Generator[np.ndarray, None, None]:
    """Yield blend frames transitioning from frame_a to frame_b."""
    n = max(2, round(duration_seconds * fps))
    for i in range(n):
        t = i / (n - 1)
        if style == "fade":
            yield _blend(frame_a, frame_b, t)
        elif style == "dissolve":
            alpha = _ease_in_out(t)
            yield _blend(frame_a, frame_b, alpha)
        else:  # cut — instant, just yield b
            yield frame_b.copy()
            return


def fade_in_frames(
    frame: np.ndarray,
    *,
    duration_seconds: float = 0.4,
    fps: int = FPS,
) -> Generator[np.ndarray, None, None]:
    """Yield frames fading from black to frame."""
    black = np.zeros_like(frame)
    n = max(2, round(duration_seconds * fps))
    for i in range(n):
        t = i / (n - 1)
        yield _blend(black, frame, _ease_in_out(t))


def fade_out_frames(
    frame: np.ndarray,
    *,
    duration_seconds: float = 0.4,
    fps: int = FPS,
) -> Generator[np.ndarray, None, None]:
    """Yield frames fading from frame to black."""
    black = np.zeros_like(frame)
    n = max(2, round(duration_seconds * fps))
    for i in range(n):
        t = i / (n - 1)
        yield _blend(frame, black, _ease_in_out(t))


# ---------------------------------------------------------------------------
# Animation implementations
# ---------------------------------------------------------------------------

def _ken_burns(
    img: np.ndarray,
    n_frames: int,
    width: int,
    height: int,
) -> Generator[np.ndarray, None, None]:
    """
    Classic Ken Burns effect: slow pan + slight zoom.
    Starts zoomed-in slightly at a random-ish corner and drifts to center.
    """
    h, w = img.shape[:2]
    # Start: slight zoom-in + offset toward top-left
    start_scale = 1.12
    end_scale = 1.0
    # drift from top-left toward center
    start_cx = w * 0.42
    start_cy = h * 0.42
    end_cx = w * 0.50
    end_cy = h * 0.50

    for i in range(n_frames):
        t = _ease_in_out(i / max(n_frames - 1, 1))
        scale = start_scale + (end_scale - start_scale) * t
        cx = start_cx + (end_cx - start_cx) * t
        cy = start_cy + (end_cy - start_cy) * t
        yield _crop_and_resize(img, cx, cy, scale, width, height)


def _zoom(
    img: np.ndarray,
    n_frames: int,
    width: int,
    height: int,
    direction: str = "in",
) -> Generator[np.ndarray, None, None]:
    start_scale = 1.0 if direction == "in" else 1.18
    end_scale = 1.18 if direction == "in" else 1.0
    h, w = img.shape[:2]
    cx, cy = w / 2, h / 2

    for i in range(n_frames):
        t = _ease_in_out(i / max(n_frames - 1, 1))
        scale = start_scale + (end_scale - start_scale) * t
        yield _crop_and_resize(img, cx, cy, scale, width, height)


def _pan(
    img: np.ndarray,
    n_frames: int,
    width: int,
    height: int,
    direction: str = "left",
) -> Generator[np.ndarray, None, None]:
    h, w = img.shape[:2]
    scale = 1.15  # slight over-scale so panning never shows black bars
    pan_amount = 0.08  # fraction of width to drift

    for i in range(n_frames):
        t = _ease_in_out(i / max(n_frames - 1, 1))
        if direction == "left":
            cx = w * (0.54 - pan_amount * t)
        else:
            cx = w * (0.46 + pan_amount * t)
        cy = h * 0.5
        yield _crop_and_resize(img, cx, cy, scale, width, height)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_and_fit(path: str, width: int, height: int) -> np.ndarray:
    """Load image and letterbox/scale to fit target size (cover, no black bars)."""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        return img
    return _cover_resize(img, width, height)


def _cover_resize(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Scale to cover the target dimensions (crop excess, no black bars)."""
    h, w = img.shape[:2]
    scale = max(width / w, height / h)
    nw, nh = int(math.ceil(w * scale)), int(math.ceil(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    # Centre-crop
    x0 = (nw - width) // 2
    y0 = (nh - height) // 2
    return resized[y0:y0 + height, x0:x0 + width]


def _crop_and_resize(
    img: np.ndarray,
    cx: float,
    cy: float,
    scale: float,
    out_w: int,
    out_h: int,
) -> np.ndarray:
    """Extract a scaled crop centred at (cx, cy) and resize to (out_w, out_h)."""
    h, w = img.shape[:2]
    crop_w = int(out_w / scale)
    crop_h = int(out_h / scale)

    x0 = int(cx - crop_w / 2)
    y0 = int(cy - crop_h / 2)
    x0 = max(0, min(x0, w - crop_w))
    y0 = max(0, min(y0, h - crop_h))
    x1 = x0 + crop_w
    y1 = y0 + crop_h

    crop = img[y0:y1, x0:x1]
    return cv2.resize(crop, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)


def _blend(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """Linear blend a→b at proportion t (0=a, 1=b)."""
    return cv2.addWeighted(a, 1.0 - t, b, t, 0)


def _ease_in_out(t: float) -> float:
    """Smoothstep easing."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)
