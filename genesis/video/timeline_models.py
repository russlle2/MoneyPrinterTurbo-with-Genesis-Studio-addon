"""
Genesis Studio — Video timeline dataclass models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class TimelineStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class TimelineClip:
    clip_id: str
    scene_id: str
    source_path: str
    media_type: str
    start_time: float
    duration: float
    visual_role: str = "scene"
    crop_mode: str = "cover"
    caption_text: str = ""
    notes: str = ""
    warnings: list[str] = field(default_factory=list)
    source_start: float = 0.0
    source_end: float = 0.0
    playback_speed: float = 1.0
    trim_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "clip_id": self.clip_id,
            "scene_id": self.scene_id,
            "source_path": self.source_path,
            "media_type": self.media_type,
            "start_time": self.start_time,
            "duration": self.duration,
            "visual_role": self.visual_role,
            "crop_mode": self.crop_mode,
            "caption_text": self.caption_text,
            "notes": self.notes,
            "warnings": self.warnings,
        }
        if self.source_end > self.source_start:
            d["source_start"] = self.source_start
            d["source_end"] = self.source_end
        if self.playback_speed != 1.0:
            d["playback_speed"] = self.playback_speed
        if self.trim_reason:
            d["trim_reason"] = self.trim_reason
        return d


@dataclass
class TimelineAudio:
    source_path: str
    start_time: float = 0.0
    duration: float = 0.0
    audio_role: str = "narration"
    volume: float = 1.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "start_time": self.start_time,
            "duration": self.duration,
            "audio_role": self.audio_role,
            "volume": self.volume,
            "notes": self.notes,
        }


@dataclass
class CaptionCue:
    cue_id: str
    scene_id: str
    text: str
    start_time: float
    end_time: float
    placement: str = "bottom_safe"
    style: str = "default"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cue_id": self.cue_id,
            "scene_id": self.scene_id,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "placement": self.placement,
            "style": self.style,
            "warnings": self.warnings,
        }


@dataclass
class VideoTimeline:
    job_id: str
    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    fps: int = 30
    duration: float = 0.0
    clips: list[TimelineClip] = field(default_factory=list)
    audio_tracks: list[TimelineAudio] = field(default_factory=list)
    captions: list[CaptionCue] = field(default_factory=list)
    scenes: list[dict[str, Any]] = field(default_factory=list)
    status: str = TimelineStatus.COMPLETE
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "fps": self.fps,
            "duration": self.duration,
            "clips": [c.to_dict() for c in self.clips],
            "audio_tracks": [a.to_dict() for a in self.audio_tracks],
            "captions": [c.to_dict() for c in self.captions],
            "scenes": self.scenes,
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class RenderResult:
    job_id: str
    output_path: str
    timeline_path: str
    caption_timing_path: str
    manifest_path: str
    status: str = TimelineStatus.COMPLETE
    renderer: str = "none"
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "output_path": self.output_path,
            "timeline_path": self.timeline_path,
            "caption_timing_path": self.caption_timing_path,
            "manifest_path": self.manifest_path,
            "status": self.status,
            "renderer": self.renderer,
            "warnings": self.warnings,
            "notes": self.notes,
        }
