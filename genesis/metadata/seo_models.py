"""
Genesis Studio — SEO / platform post metadata dataclasses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class MetadataStatus:
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class HashtagSet:
    primary: list[str] = field(default_factory=list)
    niche: list[str] = field(default_factory=list)
    broad: list[str] = field(default_factory=list)
    branded: list[str] = field(default_factory=list)
    location: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary,
            "niche": self.niche,
            "broad": self.broad,
            "branded": self.branded,
            "location": self.location,
            "warnings": self.warnings,
        }


@dataclass
class DisclosureBlock:
    required: bool = False
    disclosure_type: str = "none"
    short_text: str = ""
    long_text: str = ""
    placement_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "disclosure_type": self.disclosure_type,
            "short_text": self.short_text,
            "long_text": self.long_text,
            "placement_note": self.placement_note,
        }


@dataclass
class PlatformPostMetadata:
    platform: str
    title: str | None = None
    caption: str = ""
    description: str | None = None
    hashtags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    pinned_comment: str | None = None
    cta: str = ""
    disclosure: DisclosureBlock | None = None
    overlay_caption_notes: list[str] = field(default_factory=list)
    posting_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "title": self.title,
            "caption": self.caption,
            "description": self.description,
            "hashtags": self.hashtags,
            "tags": self.tags,
            "pinned_comment": self.pinned_comment,
            "cta": self.cta,
            "disclosure": self.disclosure.to_dict() if self.disclosure else None,
            "overlay_caption_notes": self.overlay_caption_notes,
            "posting_notes": self.posting_notes,
            "warnings": self.warnings,
        }


@dataclass
class MetadataPackage:
    job_id: str
    idea: str
    content_format: str = "product_demo"
    content_goal: str = ""
    platforms: list[str] = field(default_factory=list)
    primary_hook: str = ""
    metadata_by_platform: dict[str, PlatformPostMetadata] = field(default_factory=dict)
    hashtag_sets: dict[str, HashtagSet] = field(default_factory=dict)
    disclosures: dict[str, DisclosureBlock] = field(default_factory=dict)
    status: str = MetadataStatus.COMPLETE
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "idea": self.idea,
            "content_format": self.content_format,
            "content_goal": self.content_goal,
            "platforms": self.platforms,
            "primary_hook": self.primary_hook,
            "metadata_by_platform": {
                k: v.to_dict() for k, v in self.metadata_by_platform.items()
            },
            "hashtag_sets": {k: v.to_dict() for k, v in self.hashtag_sets.items()},
            "disclosures": {k: v.to_dict() for k, v in self.disclosures.items()},
            "status": self.status,
            "notes": self.notes,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
