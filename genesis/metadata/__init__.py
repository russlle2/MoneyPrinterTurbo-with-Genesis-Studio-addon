"""
Genesis Studio — Platform SEO and metadata engine.

Import-safe: no network calls on import.
"""

from genesis.metadata.metadata_engine import (
    build_caption_for_platform,
    build_description_for_platform,
    build_pinned_comment,
    build_title_for_platform,
    generate_metadata_package,
    generate_platform_metadata,
    generate_youtube_tags,
    metadata_package_to_legacy_platform_list,
    trim_to_limit,
    validate_platform_metadata,
)
from genesis.metadata.hashtag_engine import (
    dedupe_hashtags,
    generate_hashtag_set,
    normalize_hashtag,
    select_platform_hashtags,
    validate_hashtags,
)
from genesis.metadata.disclosure_engine import (
    generate_disclosure_block,
    infer_disclosure_need,
    place_disclosure_for_platform,
)

__all__ = [
    "generate_metadata_package",
    "generate_platform_metadata",
    "generate_hashtag_set",
    "normalize_hashtag",
    "infer_disclosure_need",
    "generate_youtube_tags",
    "metadata_package_to_legacy_platform_list",
]
