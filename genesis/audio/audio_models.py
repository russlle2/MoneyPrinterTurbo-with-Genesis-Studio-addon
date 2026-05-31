"""Genesis Studio — Audio mix dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AudioStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class AudioAsset:
    asset_id: str
    source_path: str
    stored_path: str
    filename: str
    audio_type: str
    extension: str
    size_bytes: int
    duration_seconds: float
    sample_rate: int
    channels: int
    volume_role: str = ""
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source_path": self.source_path,
            "stored_path": self.stored_path,
            "filename": self.filename,
            "audio_type": self.audio_type,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "volume_role": self.volume_role,
            "warnings": self.warnings,
            "notes": self.notes,
        }


@dataclass
class AudioMixSettings:
    narration_volume: float = 1.0
    music_volume: float = 0.18
    sfx_volume: float = 0.5
    fade_in_seconds: float = 1.0
    fade_out_seconds: float = 1.5
    duck_music_under_voice: bool = True
    ducking_level: float = 0.12
    normalize_output: bool = False
    target_lufs: float = -14.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "narration_volume": self.narration_volume,
            "music_volume": self.music_volume,
            "sfx_volume": self.sfx_volume,
            "fade_in_seconds": self.fade_in_seconds,
            "fade_out_seconds": self.fade_out_seconds,
            "duck_music_under_voice": self.duck_music_under_voice,
            "ducking_level": self.ducking_level,
            "normalize_output": self.normalize_output,
            "target_lufs": self.target_lufs,
            "notes": self.notes,
        }


@dataclass
class AudioTrackPlan:
    track_id: str
    source_path: str
    track_type: str
    start_time: float
    duration: float
    volume: float
    fade_in: float
    fade_out: float
    ducking_applied: bool
    notes: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "source_path": self.source_path,
            "track_type": self.track_type,
            "start_time": self.start_time,
            "duration": self.duration,
            "volume": self.volume,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "ducking_applied": self.ducking_applied,
            "notes": self.notes,
            "warnings": self.warnings,
        }


@dataclass
class AudioMixResult:
    job_id: str
    output_path: str
    track_plans: list[AudioTrackPlan]
    settings: AudioMixSettings
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "output_path": self.output_path,
            "track_plans": [t.to_dict() for t in self.track_plans],
            "settings": self.settings.to_dict(),
            "status": self.status,
            "warnings": self.warnings,
            "notes": self.notes,
        }
