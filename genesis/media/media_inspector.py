"""
Genesis Studio — Media file inspection and metadata extraction.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from genesis.media.media_models import MediaAsset

_VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".webm"}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_AUDIO_EXT = {".mp3", ".wav", ".m4a"}

# Keyword → role mapping for filename inference
_ROLE_KEYWORDS: list[tuple[list[str], str]] = [
    (["closeup", "close-up", "close_up", "macro", "detail"], "product_closeup"),
    (["demo", "demonstrate", "demonstration", "showing", "show"], "demonstration"),
    (["broll", "b-roll", "b_roll", "background", "ambient"], "broll"),
    (["hook", "intro", "opening", "start"], "hook"),
    (["cta", "outro", "end", "final", "conclusion"], "cta"),
    (["walking", "walk", "store", "street", "outdoor", "outside"], "walk_talk"),
    (["bowl", "sound", "meditation", "breath", "wellness", "relax", "calm", "grounding"], "wellness"),
    (["donation", "fundrais", "charity", "support", "help", "medical"], "fundraiser"),
    (["reaction", "react", "response", "reply"], "reaction"),
    (["unbox", "unboxing", "package", "delivery"], "unboxing"),
    (["tutorial", "howto", "how-to", "how_to", "guide", "steps"], "tutorial"),
    (["product", "item", "gadget", "device", "tool"], "product_demo"),
    (["girlfriend", "boyfriend", "partner", "friend", "family", "person"], "social_proof"),
    (["sun", "solar", "light", "fire", "flame"], "product_demo"),
    (["screen", "phone", "comment", "proof", "screenshot"], "social_proof"),
]


def get_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _VIDEO_EXT:
        return "video"
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _AUDIO_EXT:
        return "audio"
    return "unknown"


def infer_orientation(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    ratio = width / height
    if ratio < 0.8:
        return "vertical"
    if ratio > 1.25:
        return "horizontal"
    return "square"


def infer_aspect_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    from math import gcd
    g = gcd(width, height)
    return f"{width // g}:{height // g}"


def infer_asset_tags(filename: str, media_type: str) -> list[str]:
    """Derive keyword tags from filename stem."""
    stem = re.sub(r"[_\-\s\.]+", " ", Path(filename).stem).lower()
    words = stem.split()
    tags: list[str] = list(set(w for w in words if len(w) >= 3))
    if media_type == "video":
        tags.append("video")
    elif media_type == "image":
        tags.append("image")
    return tags


def _infer_role_from_tags(tags: list[str]) -> str:
    tag_str = " ".join(tags).lower()
    for keywords, role in _ROLE_KEYWORDS:
        if any(kw in tag_str for kw in keywords):
            return role
    return ""


def safe_get_video_metadata(path: Path) -> tuple[float, int, int, list[str]]:
    """Returns (duration, width, height, warnings). Never raises."""
    warnings: list[str] = []
    try:
        from moviepy import VideoFileClip
        clip = VideoFileClip(str(path), audio=False)
        dur = clip.duration or 0.0
        w, h = (clip.size or (0, 0))
        clip.close()
        return float(dur), int(w), int(h), warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"video metadata unavailable: {exc}")
    return 0.0, 0, 0, warnings


def safe_get_image_metadata(path: Path) -> tuple[int, int, list[str]]:
    """Returns (width, height, warnings). Never raises."""
    warnings: list[str] = []
    try:
        from PIL import Image
        with Image.open(path) as img:
            w, h = img.size
        return int(w), int(h), warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"image metadata unavailable: {exc}")
    return 0, 0, warnings


def _asset_id(path: Path) -> str:
    """Short stable ID from filename + size."""
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    raw = f"{path.name}:{size}"
    return hashlib.md5(raw.encode()).hexdigest()[:10]


def inspect_media_file(
    path: Path,
    *,
    stored_path: str = "",
    source_path: str = "",
) -> MediaAsset:
    """
    Inspect a media file and return a MediaAsset. Never raises.
    """
    warnings: list[str] = []
    media_type = get_media_type(path)
    ext = path.suffix.lower()

    if media_type == "unknown":
        warnings.append(f"unsupported file type: {ext}")

    duration = 0.0
    width = height = 0
    extra_warns: list[str] = []

    if media_type == "video":
        duration, width, height, extra_warns = safe_get_video_metadata(path)
        warnings.extend(extra_warns)
    elif media_type == "image":
        width, height, extra_warns = safe_get_image_metadata(path)
        warnings.extend(extra_warns)

    tags = infer_asset_tags(path.name, media_type)
    role = _infer_role_from_tags(tags)
    orientation = infer_orientation(width, height)
    aspect_ratio = infer_aspect_ratio(width, height)

    try:
        size_bytes = path.stat().st_size
    except OSError:
        size_bytes = 0

    return MediaAsset(
        asset_id=_asset_id(path),
        source_path=source_path or str(path),
        stored_path=stored_path or str(path),
        filename=path.name,
        media_type=media_type,
        extension=ext,
        size_bytes=size_bytes,
        duration_seconds=round(duration, 3),
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        orientation=orientation,
        tags=tags,
        inferred_role=role,
        warnings=warnings,
    )
