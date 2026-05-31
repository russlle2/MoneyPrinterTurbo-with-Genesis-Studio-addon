"""
Genesis Studio — Hashtag generation and validation (no live trend lookup).
"""

from __future__ import annotations

import re
from typing import Any

from genesis.metadata.platform_profiles import PlatformProfile, get_platform_profile
from genesis.metadata.seo_models import HashtagSet
from genesis.metadata.truth_context import (
    MARKETPLACE_HASHTAG_STEMS,
    MetadataTruthContext,
    build_truth_context,
    filter_hashtags_for_truth,
)

# Broad discovery tags by content format (generic pools — not niche-specific products)
_BROAD_BY_FORMAT: dict[str, list[str]] = {
    "product_demo": ["ProductDemo", "GearReview", "UsefulFinds", "TechGadgets"],
    "affiliate_followup": ["ViralFind", "MustHave", "HonestReview", "CreatorFinds"],
    "wellness_teaching": ["WellnessTips", "SelfMastery", "Mindfulness", "HealthyHabits"],
    "personal_story": ["RealTalk", "StoryTime", "CreatorLife", "Authentic"],
    "controversial_take": ["HotTake", "ThinkDifferent", "Debate", "RealTalk"],
    "tutorial": ["HowTo", "LearnOnTikTok", "Tutorial", "TipsAndTricks"],
    "fundraising_story": ["MutualAid", "CommunitySupport", "GiveBack", "HelpOthers"],
    "motivational_walkthrough": ["Motivation", "DailyHabits", "Mindset", "GetItDone"],
}

# Neutral product discovery — no retailer names unless truth context allows
_NEUTRAL_PRODUCT_NICHE: list[str] = [
    "UsefulGadgets",
    "OutdoorGear",
    "SurvivalGadget",
    "EcoGadget",
    "ProductDemo",
    "GearReview",
    "WorthIt",
    "EverydayCarry",
]

_NICHE_KEYWORDS_BY_FORMAT: dict[str, list[str]] = {
    "product_demo": ["UsefulGadgets", "EverydayCarry", "GearTok"],
    "affiliate_followup": list(_NEUTRAL_PRODUCT_NICHE),
    "wellness_teaching": ["NervousSystem", "Breathwork", "Grounding", "Somatic"],
    "fundraising_story": ["AnimalRescue", "RescueStory", "CommunityHelp"],
    "tutorial": ["StepByStep", "BeginnerFriendly", "QuickTips"],
    "motivational_walkthrough": ["ActionSteps", "SelfImprovement", "Discipline"],
}

_SPAMMY_TAGS = frozenset({
    "fyp", "foryou", "foryoupage", "viral", "trending", "money", "lifehacks",
    "followme", "like4like", "subscribe", "clicklink", "free", "giveaway",
})

_BANNED_CLAIM_TAGS = frozenset({
    "sponsored", "officialpartner", "fdaapproved", "cure", "guaranteed",
})


def normalize_hashtag(text: str) -> str | None:
    """Return a normalized #Tag or None if invalid."""
    t = text.strip()
    if not t:
        return None
    if t.startswith("#"):
        t = t[1:]
    t = re.sub(r"[^\w]", "", t, flags=re.UNICODE)
    if not t or len(t) < 2 or len(t) > 40:
        return None
    if t[0].isdigit():
        return None
    return "#" + t[:1].upper() + t[1:]


def dedupe_hashtags(tags: list[str]) -> list[str]:
    """Case-insensitive dedupe preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        norm = normalize_hashtag(raw) if not raw.startswith("#") else normalize_hashtag(raw)
        if not norm:
            continue
        key = norm.lower()
        if key not in seen:
            seen.add(key)
            out.append(norm)
    return out


def validate_hashtags(
    tags: list[str],
    *,
    platform: str = "",
    max_count: int | None = None,
) -> tuple[list[str], list[str]]:
    """
    Validate and filter hashtags. Returns (valid_tags, warnings).
    """
    warnings: list[str] = []
    valid: list[str] = []
    profile = get_platform_profile(platform) if platform else None
    limit = max_count or (profile.hashtag_limit if profile else 30)

    for raw in tags:
        tag = normalize_hashtag(raw.lstrip("#"))
        if not tag:
            warnings.append(f"dropped invalid hashtag: {raw!r}")
            continue
        core = tag[1:].lower()
        if core in _SPAMMY_TAGS:
            warnings.append(f"dropped spammy hashtag: {tag}")
            continue
        if core in _BANNED_CLAIM_TAGS:
            warnings.append(f"dropped risky claim hashtag: {tag}")
            continue
        valid.append(tag)

    valid = dedupe_hashtags(valid)
    if len(valid) > limit:
        warnings.append(f"trimmed hashtags to platform limit ({limit})")
        valid = valid[:limit]
    return valid, warnings


def _tokens_from_text(*parts: str) -> list[str]:
    words: list[str] = []
    for p in parts:
        if not p:
            continue
        for w in re.findall(r"[A-Za-z][A-Za-z0-9]*", p):
            if len(w) > 2 and w.lower() not in {
                "the", "and", "for", "that", "this", "with", "from", "your", "about",
            }:
                words.append(w)
    return words


def _primary_from_subject(clean_subject: str, product_name: str = "") -> list[str]:
    """Build subject-derived primary hashtags without hard-coded product names."""
    tags: list[str] = []
    subject = product_name or clean_subject
    words = _tokens_from_text(subject)
    if not words:
        return tags
    if len(words) >= 2:
        combined = "".join(w.capitalize() for w in words[:4])
        if len(combined) >= 4:
            tags.append(f"#{combined}")
    for w in words[:4]:
        if len(w) >= 4:
            tags.append(f"#{w.capitalize()}")
    return dedupe_hashtags(tags)


def _marketplace_niche_tags(ctx: MetadataTruthContext) -> list[str]:
    if not ctx.marketplace:
        return []
    stems = MARKETPLACE_HASHTAG_STEMS.get(ctx.marketplace, [])
    return [f"#{s}" for s in stems]


def _niche_from_audience(
    audience: str,
    content_format: str,
    *,
    truth: MetadataTruthContext | None = None,
) -> list[str]:
    tags: list[str] = list(_NICHE_KEYWORDS_BY_FORMAT.get(content_format, []))
    if content_format in ("product_demo", "affiliate_followup") and truth:
        tags = _marketplace_niche_tags(truth) + list(_NEUTRAL_PRODUCT_NICHE)
    if truth and content_format == "wellness_teaching" and not truth.has_product_offer:
        tags = [t for t in tags if t.lower() not in {
            s.lower() for s in _NEUTRAL_PRODUCT_NICHE
        }]
    for w in _tokens_from_text(audience)[:6]:
        if len(w) >= 5:
            tags.append(f"#{w.capitalize()}")
    return dedupe_hashtags(tags)


def _broad_from_format(content_format: str, *, truth: MetadataTruthContext | None = None) -> list[str]:
    stems = list(_BROAD_BY_FORMAT.get(content_format, ["CreatorContent", "ShortForm"]))
    if truth and not truth.allow_fundraising_tags:
        stems = [
            s for s in stems
            if s.lower() not in {"mutualaid", "giveback", "helpothers", "communitysupport"}
        ]
    return [f"#{t}" for t in stems]


def generate_hashtag_set(
    *,
    clean_subject: str = "",
    content_format: str = "product_demo",
    audience: str = "",
    content_goal: str = "",
    product_type: str = "",
    topic_keywords: list[str] | None = None,
    location: str = "",
    brand_name: str = "",
    product_name: str = "",
    idea: str = "",
    offer: str = "",
    cta: str = "",
    truth: MetadataTruthContext | None = None,
    marketplace: str = "",
    retailer: str = "",
    affiliate_status: str = "",
    sponsorship_status: str = "",
    fundraiser_status: str = "",
) -> HashtagSet:
    """Generate categorized hashtags from normalized creative context."""
    if truth is None:
        truth = build_truth_context(
            idea=idea,
            offer=offer,
            cta=cta,
            content_goal=content_goal,
            content_format=content_format,
            marketplace=marketplace,
            retailer=retailer,
            affiliate_status=affiliate_status,
            sponsorship_status=sponsorship_status,
            fundraiser_status=fundraiser_status,
        )

    warnings: list[str] = list(truth.warnings)
    primary = _primary_from_subject(clean_subject, product_name or product_type)
    niche = _niche_from_audience(audience, content_format, truth=truth)
    broad = _broad_from_format(content_format, truth=truth)

    if topic_keywords:
        for kw in topic_keywords:
            t = normalize_hashtag(kw)
            if t:
                primary.append(t)

    branded: list[str] = []
    if brand_name:
        t = normalize_hashtag(brand_name.replace(" ", ""))
        if t:
            branded.append(t)

    location_tags: list[str] = []
    if location:
        for part in location.split(","):
            t = normalize_hashtag(part.strip().replace(" ", ""))
            if t:
                location_tags.append(t)

    # Fundraising: bias niche toward support language from goal/subject tokens
    if content_format == "fundraising_story":
        for w in _tokens_from_text(clean_subject, content_goal)[:5]:
            if w.lower() in ("rescue", "cat", "dog", "fund", "surgery", "community"):
                niche.insert(0, f"#{w.capitalize()}Rescue" if w.lower() != "fund" else "#CommunityFundraiser")

    primary, w = validate_hashtags(primary, max_count=12)
    warnings.extend(w)
    niche, w = validate_hashtags(niche, max_count=10)
    warnings.extend(w)
    broad, w = validate_hashtags(broad, max_count=8)
    warnings.extend(w)
    branded, w = validate_hashtags(branded, max_count=3)
    warnings.extend(w)
    location_tags, w = validate_hashtags(location_tags, max_count=3)
    warnings.extend(w)

    primary, tw = filter_hashtags_for_truth(primary, truth)
    warnings.extend(tw)
    niche, tw = filter_hashtags_for_truth(niche, truth)
    warnings.extend(tw)
    broad, tw = filter_hashtags_for_truth(broad, truth)
    warnings.extend(tw)
    branded, tw = filter_hashtags_for_truth(branded, truth)
    warnings.extend(tw)

    return HashtagSet(
        primary=primary,
        niche=niche,
        broad=broad,
        branded=branded,
        location=location_tags,
        warnings=list(dict.fromkeys(warnings)),
    )


def select_platform_hashtags(
    hashtag_set: HashtagSet,
    profile: PlatformProfile,
    *,
    truth: MetadataTruthContext | None = None,
) -> list[str]:
    """Pick hashtags for one platform respecting limits and style."""
    pool: list[str] = []
    if truth and truth.allowed_marketplace_stems:
        for tag in hashtag_set.niche:
            if _hashtag_stem(tag) in truth.allowed_marketplace_stems:
                pool.append(tag)
    pool.extend(hashtag_set.primary)
    pool.extend(hashtag_set.niche)
    pool.extend(hashtag_set.broad)
    pool.extend(hashtag_set.branded)
    if profile.platform_name.lower().startswith("youtube"):
        # YouTube: fewer hashtags in description
        count = min(profile.default_hashtag_count, profile.hashtag_limit, 3)
    elif profile.platform_name == "X":
        count = min(2, profile.hashtag_limit)
    else:
        count = min(profile.default_hashtag_count, profile.hashtag_limit)

    tags, _ = validate_hashtags(pool, max_count=count)
    if truth:
        tags = apply_truth_to_hashtag_list(tags, truth)
    return tags


def _hashtag_stem(tag: str) -> str:
    return tag.lstrip("#").lower()


def apply_truth_to_hashtag_list(
    tags: list[str],
    truth: MetadataTruthContext,
) -> list[str]:
    """Filter a flat hashtag list (e.g. after platform selection)."""
    filtered, _ = filter_hashtags_for_truth(tags, truth)
    return filtered
