"""
Shared Genesis Studio schema models.

JSON-serializable Pydantic models for agents, integrations, pipeline, captions,
and the MoneyPrinterTurbo bridge. Import-safe: no side effects on import.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field


class GenesisModel(BaseModel):
    """Base model with dict/JSON helpers for pipeline and logging."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls.model_validate(data)


class SceneType(str, Enum):
    HERO = "hero"
    BROLL = "broll"
    TRANSITION = "transition"
    TALKING_HEAD = "talking_head"
    TEXT_ONLY = "text_only"
    PRODUCT = "product"
    ABSTRACT = "abstract"


class AssetType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"


class TrackType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    CAPTION = "caption"


class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Scene(GenesisModel):
    id: str
    type: SceneType
    description: str = ""
    duration_sec: float = Field(default=0.0, ge=0.0)
    priority: int = 0
    visual_style: str = ""
    generator_hint: str = ""
    needs_image_first: bool = False
    reference_image: str | None = None
    status: JobStatus = JobStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetRequest(GenesisModel):
    id: str
    scene_id: str
    asset_type: AssetType
    prompt: str = ""
    provider_hint: str = ""
    output_dir: str = ""
    status: JobStatus = JobStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneratedAsset(GenesisModel):
    id: str
    request_id: str
    scene_id: str
    asset_type: AssetType
    path: str = ""
    provider: str = ""
    prompt: str = ""
    status: JobStatus = JobStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)


class CaptionSegment(GenesisModel):
    id: str
    text: str = ""
    start_sec: float = Field(default=0.0, ge=0.0)
    end_sec: float = Field(default=0.0, ge=0.0)
    emphasized_words: list[str] = Field(default_factory=list)
    style: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineTrackItem(GenesisModel):
    id: str
    track_type: TrackType
    path: str = ""
    start_sec: float = Field(default=0.0, ge=0.0)
    end_sec: float = Field(default=0.0, ge=0.0)
    duration_sec: float = Field(default=0.0, ge=0.0)
    layer: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Timeline(GenesisModel):
    resolution: str = "1080x1920"
    fps: float = Field(default=30.0, gt=0.0)
    video: list[TimelineTrackItem] = Field(default_factory=list)
    audio: list[TimelineTrackItem] = Field(default_factory=list)
    captions: list[TimelineTrackItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderJob(GenesisModel):
    id: str
    timeline: Timeline
    output_path: str = ""
    platform: str = ""
    mode: str = "local_first"
    status: JobStatus = JobStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderResult(GenesisModel):
    provider: str
    success: bool = False
    output_paths: list[str] = Field(default_factory=list)
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Public export list for stable imports.
__all__: ClassVar[tuple[str, ...]] = (
    "GenesisModel",
    "SceneType",
    "AssetType",
    "TrackType",
    "JobStatus",
    "Scene",
    "AssetRequest",
    "GeneratedAsset",
    "CaptionSegment",
    "TimelineTrackItem",
    "Timeline",
    "RenderJob",
    "ProviderResult",
)
