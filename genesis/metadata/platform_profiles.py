"""
Genesis Studio — Platform posting profiles (configurable defaults).

These limits and capabilities are NOT fetched live from platforms.
Update this file when platform rules change.
"""

from __future__ import annotations

from dataclasses import dataclass

# Supported platform keys (aligned with genesis.workflows.models.SUPPORTED_PLATFORMS)
PLATFORM_KEYS: tuple[str, ...] = (
    "instagram_reels",
    "tiktok",
    "clapper",
    "youtube_shorts",
    "x",
)


@dataclass(frozen=True)
class PlatformProfile:
    platform_name: str
    caption_limit: int
    title_limit: int
    description_limit: int
    hashtag_limit: int
    recommended_caption_style: str
    supports_title: bool
    supports_description: bool
    supports_hashtags: bool
    supports_tags: bool
    supports_pinned_comment: bool
    supports_link_in_caption: bool
    preferred_cta_style: str
    notes: str
    aspect_ratio: str = "9:16"
    recommended_duration_sec: int = 30
    default_hashtag_count: int = 5


# Configurable defaults — may need updating as platforms evolve.
PLATFORM_PROFILES: dict[str, PlatformProfile] = {
    "instagram_reels": PlatformProfile(
        platform_name="Instagram Reels",
        caption_limit=2200,
        title_limit=0,
        description_limit=0,
        hashtag_limit=30,
        recommended_caption_style="hook_first_with_context",
        supports_title=False,
        supports_description=False,
        supports_hashtags=True,
        supports_tags=False,
        supports_pinned_comment=True,
        supports_link_in_caption=False,
        preferred_cta_style="comment_or_bio",
        notes="Reels: hook in first line; hashtags often in caption or first comment.",
        aspect_ratio="9:16",
        recommended_duration_sec=30,
        default_hashtag_count=5,
    ),
    "tiktok": PlatformProfile(
        platform_name="TikTok",
        caption_limit=2200,
        title_limit=0,
        description_limit=0,
        hashtag_limit=10,
        recommended_caption_style="short_hook_cta",
        supports_title=False,
        supports_description=False,
        supports_hashtags=True,
        supports_tags=False,
        supports_pinned_comment=True,
        supports_link_in_caption=False,
        preferred_cta_style="comment_keyword",
        notes="TikTok: shorter captions perform well; use pinned comment for links.",
        aspect_ratio="9:16",
        recommended_duration_sec=30,
        default_hashtag_count=5,
    ),
    "clapper": PlatformProfile(
        platform_name="Clapper",
        caption_limit=500,
        title_limit=0,
        description_limit=0,
        hashtag_limit=20,
        recommended_caption_style="direct_conversational",
        supports_title=False,
        supports_description=False,
        supports_hashtags=True,
        supports_tags=False,
        supports_pinned_comment=True,
        supports_link_in_caption=False,
        preferred_cta_style="comment_keyword",
        notes="Clapper: keep captions tight and conversational.",
        aspect_ratio="9:16",
        recommended_duration_sec=60,
        default_hashtag_count=5,
    ),
    "youtube_shorts": PlatformProfile(
        platform_name="YouTube Shorts",
        caption_limit=5000,
        title_limit=100,
        description_limit=5000,
        hashtag_limit=5,
        recommended_caption_style="title_plus_description",
        supports_title=True,
        supports_description=True,
        supports_hashtags=True,
        supports_tags=True,
        supports_pinned_comment=True,
        supports_link_in_caption=True,
        preferred_cta_style="description_link",
        notes="Shorts: title visible in feed; description for context and links.",
        aspect_ratio="9:16",
        recommended_duration_sec=45,
        default_hashtag_count=3,
    ),
    "x": PlatformProfile(
        platform_name="X",
        caption_limit=280,
        title_limit=0,
        description_limit=0,
        hashtag_limit=3,
        recommended_caption_style="standalone_post",
        supports_title=False,
        supports_description=False,
        supports_hashtags=True,
        supports_tags=False,
        supports_pinned_comment=False,
        supports_link_in_caption=True,
        preferred_cta_style="inline_link_or_reply",
        notes="X: one strong sentence; minimal hashtags.",
        aspect_ratio="16:9",
        recommended_duration_sec=60,
        default_hashtag_count=2,
    ),
}


def get_platform_profile(platform_key: str) -> PlatformProfile | None:
    return PLATFORM_PROFILES.get(platform_key)


def require_platform_profile(platform_key: str) -> PlatformProfile:
    profile = get_platform_profile(platform_key)
    if profile is None:
        raise ValueError(f"unknown platform: {platform_key!r}")
    return profile
