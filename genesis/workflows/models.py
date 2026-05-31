"""
Genesis Studio — Social media workflow dataclass models.

Pure dataclasses; no pydantic dependency. JSON-serializable via to_dict().
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

class WorkflowStatus:
    CREATED = "created"
    SCRIPT_READY = "script_ready"
    NARRATION_COMPLETE = "narration_complete"
    COMPLETE = "complete"
    PARTIAL = "partial"    # completed but some optional steps skipped
    FAILED = "failed"


class NarrationStatus:
    PENDING = "pending"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    FAILED = "failed"


SUPPORTED_PLATFORMS: tuple[str, ...] = (
    "instagram_reels",
    "tiktok",
    "clapper",
    "youtube_shorts",
    "x",
)

_PLATFORM_LABELS: dict[str, str] = {
    "instagram_reels": "Instagram Reels",
    "tiktok": "TikTok",
    "clapper": "Clapper",
    "youtube_shorts": "YouTube Shorts",
    "x": "X (Twitter)",
}

_PLATFORM_DEFAULTS: dict[str, dict[str, Any]] = {
    "instagram_reels": {
        "aspect_ratio": "9:16",
        "max_duration_sec": 90,
        "recommended_duration_sec": 30,
        "hashtag_limit": 30,
        "caption_limit": 2200,
    },
    "tiktok": {
        "aspect_ratio": "9:16",
        "max_duration_sec": 600,
        "recommended_duration_sec": 30,
        "hashtag_limit": 10,
        "caption_limit": 2200,
    },
    "clapper": {
        "aspect_ratio": "9:16",
        "max_duration_sec": 180,
        "recommended_duration_sec": 60,
        "hashtag_limit": 20,
        "caption_limit": 500,
    },
    "youtube_shorts": {
        "aspect_ratio": "9:16",
        "max_duration_sec": 60,
        "recommended_duration_sec": 45,
        "hashtag_limit": 5,
        "caption_limit": 5000,
    },
    "x": {
        "aspect_ratio": "16:9",
        "max_duration_sec": 140,
        "recommended_duration_sec": 60,
        "hashtag_limit": 3,
        "caption_limit": 280,
    },
}


def platform_label(platform_key: str) -> str:
    return _PLATFORM_LABELS.get(platform_key, platform_key)


def platform_defaults(platform_key: str) -> dict[str, Any]:
    return dict(_PLATFORM_DEFAULTS.get(platform_key, {}))


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class SocialContentBrief:
    """Structured creative brief capturing the content intent."""

    job_id: str
    idea: str
    platforms: list[str] = field(default_factory=list)
    audience: str = ""
    content_goal: str = ""
    tone: str = "engaging"
    offer: str = ""
    cta: str = ""
    created_at: str = ""
    # Optional truth fields (safe defaults — never assume retailer/sponsorship)
    marketplace: str = ""
    retailer: str = ""
    brand_name: str = ""
    product_name: str = ""
    affiliate_status: str = ""
    sponsorship_status: str = ""
    link_status: str = ""
    fundraiser_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "idea": self.idea,
            "platforms": self.platforms,
            "audience": self.audience,
            "content_goal": self.content_goal,
            "tone": self.tone,
            "offer": self.offer,
            "cta": self.cta,
            "created_at": self.created_at,
            "marketplace": self.marketplace,
            "retailer": self.retailer,
            "brand_name": self.brand_name,
            "product_name": self.product_name,
            "affiliate_status": self.affiliate_status,
            "sponsorship_status": self.sponsorship_status,
            "link_status": self.link_status,
            "fundraiser_status": self.fundraiser_status,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class GeneratedAssetReference:
    """Lightweight reference to a generated media asset (audio, video, image)."""

    asset_id: str
    path: str
    asset_type: str          # "audio", "video", "image"
    provider: str
    status: str              # NarrationStatus.*
    prompt_excerpt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "path": self.path,
            "asset_type": self.asset_type,
            "provider": self.provider,
            "status": self.status,
            "prompt_excerpt": self.prompt_excerpt,
            "metadata": self.metadata,
        }


@dataclass
class PlatformMetadata:
    """Per-platform content metadata for a single post."""

    platform: str            # key from SUPPORTED_PLATFORMS
    caption: str
    hashtags: list[str] = field(default_factory=list)
    cta: str = ""
    duration_hint: str = ""
    aspect_ratio: str = "9:16"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "platform_label": platform_label(self.platform),
            "caption": self.caption,
            "hashtags": self.hashtags,
            "cta": self.cta,
            "duration_hint": self.duration_hint,
            "aspect_ratio": self.aspect_ratio,
            "notes": self.notes,
        }


@dataclass
class PostingPackage:
    """Paths to all files in a completed run package."""

    job_id: str
    run_dir: str
    brief_path: str
    script_path: str
    visual_plan_path: str
    metadata_pack_path: str
    posting_checklist_path: str
    narration_path: str = ""
    script_package_path: str = ""
    overlay_captions_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_dir": self.run_dir,
            "brief_path": self.brief_path,
            "script_path": self.script_path,
            "visual_plan_path": self.visual_plan_path,
            "metadata_pack_path": self.metadata_pack_path,
            "posting_checklist_path": self.posting_checklist_path,
            "narration_path": self.narration_path,
            "script_package_path": self.script_package_path,
            "overlay_captions_path": self.overlay_captions_path,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class SocialWorkflowResult:
    """Top-level result of a complete social media content workflow run."""

    job_id: str
    status: str              # WorkflowStatus.*
    brief: SocialContentBrief
    script_text: str = ""
    script_source: str = ""  # "provided" | "local_llm" | "template_fallback" | "placeholder"
    script_package: Any = None  # ScriptPackage | None (avoid import cycle)
    metadata_package: Any = None  # MetadataPackage | None (avoid import cycle)
    narration: GeneratedAssetReference | None = None
    platform_metadata: list[PlatformMetadata] = field(default_factory=list)
    posting_package: PostingPackage | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        script_pkg_dict = None
        if self.script_package is not None:
            try:
                script_pkg_dict = self.script_package.to_dict()
            except Exception:  # noqa: BLE001
                script_pkg_dict = {"status": "unserializable"}
        return {
            "job_id": self.job_id,
            "status": self.status,
            "brief": self.brief.to_dict(),
            "script_text": self.script_text,
            "script_source": self.script_source,
            "script_package": script_pkg_dict,
            "metadata_package": (
                self.metadata_package.to_dict()
                if self.metadata_package is not None
                and hasattr(self.metadata_package, "to_dict")
                else None
            ),
            "narration": self.narration.to_dict() if self.narration else None,
            "platform_metadata": [p.to_dict() for p in self.platform_metadata],
            "posting_package": self.posting_package.to_dict() if self.posting_package else None,
            "errors": self.errors,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
