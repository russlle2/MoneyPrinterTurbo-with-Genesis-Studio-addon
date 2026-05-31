"""
Genesis Studio — Platform SEO metadata engine.

Turns SocialContentBrief + ScriptPackage (+ optional NormalizedIdeaContext)
into per-platform post metadata. No live web lookup.
"""

from __future__ import annotations

import re
from typing import Any

from genesis.metadata.disclosure_engine import (
    generate_disclosure_block,
    infer_disclosure_need,
    place_disclosure_for_platform,
)
from genesis.metadata.hashtag_engine import (
    apply_truth_to_hashtag_list,
    generate_hashtag_set,
    select_platform_hashtags,
    validate_hashtags,
)
from genesis.metadata.platform_profiles import (
    PLATFORM_KEYS,
    PlatformProfile,
    get_platform_profile,
)
from genesis.metadata.seo_models import (
    DisclosureBlock,
    HashtagSet,
    MetadataPackage,
    MetadataStatus,
    PlatformPostMetadata,
)
from genesis.metadata.truth_context import (
    MetadataTruthContext,
    build_truth_context,
    sanitize_metadata_text,
)

# Re-export for tests
__all__ = [
    "generate_metadata_package",
    "generate_platform_metadata",
    "build_caption_for_platform",
    "build_title_for_platform",
    "build_description_for_platform",
    "build_pinned_comment",
    "trim_to_limit",
    "validate_platform_metadata",
    "generate_youtube_tags",
    "metadata_package_to_legacy_platform_list",
]


def trim_to_limit(text: str, limit: int, *, suffix: str = "…") -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= len(suffix):
        return text[:limit]
    return text[: limit - len(suffix)].rstrip() + suffix


def _primary_hook_from_script(script_package: Any | None, idea: str) -> str:
    if script_package is not None:
        hooks = getattr(script_package, "hooks", None) or []
        if hooks:
            return str(hooks[0].text).strip()
    return idea.strip()[:200]


def _cta_text(script_package: Any | None, brief_cta: str) -> str:
    if brief_cta.strip():
        return brief_cta.strip()
    if script_package is not None:
        opts = getattr(script_package, "cta_options", None) or []
        if opts:
            return str(opts[0].text).strip()
    return ""


def _context_line(norm: Any | None, script_package: Any | None) -> str:
    if norm is not None:
        mech = getattr(norm, "mechanism", "") or ""
        if mech:
            return mech.rstrip(".") + "."
    if script_package is not None:
        notes = getattr(script_package, "notes", None) or []
        if notes:
            return str(notes[0])
    return ""


def _overlay_notes(script_package: Any | None) -> list[str]:
    if script_package is None:
        return []
    overlays = getattr(script_package, "overlay_captions", None) or []
    return [f"{c.text} ({c.timing_hint})" for c in overlays[:4] if getattr(c, "text", "")]


def build_title_for_platform(
    primary_hook: str,
    clean_subject: str,
    profile: PlatformProfile,
) -> str | None:
    if not profile.supports_title:
        return None
    # YouTube: 40–60 chars when possible
    base = clean_subject or primary_hook
    if len(base) > 55:
        base = trim_to_limit(base, 55)
    title = base if len(base) >= 20 else f"{base} — quick demo"
    return trim_to_limit(title, profile.title_limit or 100)


def build_description_for_platform(
    hook: str,
    context: str,
    cta: str,
    disclosure_text: str,
    profile: PlatformProfile,
) -> str | None:
    if not profile.supports_description:
        return None
    parts = [hook]
    if context:
        parts.append(context)
    if cta:
        parts.append(cta)
    if disclosure_text:
        parts.append(disclosure_text)
    body = " ".join(parts)
    return trim_to_limit(body, min(profile.description_limit, 500))


def build_pinned_comment(
    cta: str,
    *,
    link_placeholder: str = "",
    needs_link: bool = False,
) -> str | None:
    if link_placeholder:
        return f"Link: {link_placeholder}"
    if needs_link and cta:
        if "comment" in cta.lower() and "link" not in cta.lower():
            return f"{cta} — link will be pinned here when ready."
        return cta
    if needs_link:
        return "Link will be pinned here when available."
    return None


def build_caption_for_platform(
    *,
    profile: PlatformProfile,
    primary_hook: str,
    context_line: str,
    cta: str,
    disclosure_text: str,
    hashtags: list[str],
    style: str = "",
) -> str:
    """Assemble caption for a platform profile."""
    style = style or profile.recommended_caption_style
    parts: list[str] = []

    if style == "standalone_post":
        line = primary_hook
        if cta and cta not in line:
            line = f"{line} {cta}"
        parts.append(trim_to_limit(line, profile.caption_limit - 40))
        if disclosure_text:
            parts.append(disclosure_text)
        if hashtags and profile.supports_hashtags:
            parts.append(" ".join(hashtags[: profile.hashtag_limit]))
        return "\n\n".join(p for p in parts if p).strip()

    if style == "short_hook_cta":
        parts.append(trim_to_limit(primary_hook, 180))
        if cta:
            parts.append(cta)
        if disclosure_text:
            parts.append(disclosure_text)
        if hashtags:
            parts.append(" ".join(hashtags))
        return "\n\n".join(parts).strip()

    if style == "direct_conversational":
        core = primary_hook
        if context_line and len(context_line) < 120:
            core = f"{primary_hook}\n{context_line}"
        parts.append(trim_to_limit(core, profile.caption_limit - 80))
        if cta:
            parts.append(cta)
        if disclosure_text:
            parts.append(disclosure_text)
        if hashtags:
            parts.append(" ".join(hashtags))
        return "\n\n".join(parts).strip()

    if style == "title_plus_description":
        # Shorts often use description field; caption can mirror hook
        parts.append(primary_hook)
        if cta:
            parts.append(cta)
        if disclosure_text:
            parts.append(disclosure_text)
        return "\n\n".join(parts).strip()

    # hook_first_with_context (Instagram default)
    parts.append(primary_hook)
    if context_line:
        parts.append(context_line)
    if cta:
        parts.append(cta)
    if disclosure_text:
        parts.append(disclosure_text)
    if hashtags:
        parts.append(" ".join(hashtags))

    caption = "\n\n".join(parts).strip()
    tag_block = " ".join(hashtags) if hashtags else ""
    reserve = len(tag_block) + 8
    return trim_to_limit(caption, profile.caption_limit - reserve) + (
        ("\n\n" + tag_block) if tag_block else ""
    )


def generate_youtube_tags(
    clean_subject: str,
    product_name: str = "",
    *,
    extra_keywords: list[str] | None = None,
) -> list[str]:
    """
    Spelling / name variants for YouTube tags — not broad discovery keywords.
    """
    base = (product_name or clean_subject).lower().strip()
    tags: list[str] = []
    if base:
        tags.append(base)

    words = re.findall(r"[a-z0-9]+", base)
    if words:
        joined = " ".join(words)
        if joined != base:
            tags.append(joined)
        no_hyphen = "".join(words)
        if no_hyphen and no_hyphen != base.replace(" ", ""):
            tags.append(" ".join(words))  # already have joined

    # Hyphen / spacing variants
    raw = (product_name or clean_subject).strip()
    if "-" in raw:
        tags.append(raw.replace("-", " ").lower())
        tags.append(raw.replace("-", "").lower())

    # Spelling variants: duplicate trailing consonant, drop one letter on long tokens
    words = re.findall(r"[a-z0-9]+", base)
    if len(words) >= 2:
        phrase = " ".join(words)
        if phrase not in tags:
            tags.append(phrase)
        last = words[-1]
        if len(last) > 5:
            tags.append(" ".join(words[:-1] + [last + last[-1]]))
            tags.append(" ".join(words[:-1] + [last[:-1]]))

    if extra_keywords:
        for kw in extra_keywords:
            k = kw.lower().strip()
            if k and k not in tags and len(k) < 50:
                tags.append(k)

    # Remove spammy generic tags
    banned = {"viral", "fyp", "trending", "money", "life hacks", "lifehacks", "shorts"}
    out: list[str] = []
    seen: set[str] = set()
    for t in tags:
        key = t.lower()
        if key in seen or key in banned:
            continue
        seen.add(key)
        out.append(t)
    return out[:15]


def validate_platform_metadata(meta: PlatformPostMetadata, profile: PlatformProfile) -> list[str]:
    warnings: list[str] = []
    if meta.caption and len(meta.caption) > profile.caption_limit:
        warnings.append(f"caption exceeds {profile.caption_limit} chars for {meta.platform}")
    if meta.title and profile.title_limit and len(meta.title) > profile.title_limit:
        warnings.append(f"title exceeds limit for {meta.platform}")
    if meta.hashtags:
        _, w = validate_hashtags(meta.hashtags, platform=meta.platform)
        warnings.extend(w)
    meta.warnings.extend(warnings)
    return warnings


def generate_platform_metadata(
    platform_key: str,
    *,
    brief: Any,
    script_package: Any | None = None,
    norm: Any | None = None,
    hashtag_set: HashtagSet | None = None,
    disclosure_blocks: dict[str, DisclosureBlock] | None = None,
    narration_provider: str = "",
    location: str = "",
    brand_name: str = "",
    link_placeholder: str = "",
    affiliate_status: str = "",
    fundraiser_link_status: str = "",
    sponsorship_claimed: bool = False,
    truth: MetadataTruthContext | None = None,
) -> PlatformPostMetadata:
    profile = get_platform_profile(platform_key)
    if profile is None:
        return PlatformPostMetadata(
            platform=platform_key,
            caption="",
            warnings=[f"unknown platform: {platform_key}"],
        )

    content_format = (
        getattr(script_package, "content_format", None)
        or getattr(norm, "content_format", None)
        or "product_demo"
    )
    clean_subject = getattr(norm, "clean_subject", "") if norm else ""
    if not clean_subject and script_package:
        clean_subject = getattr(script_package, "idea", brief.idea)[:80]
    product_name = getattr(brief, "product_name", "") or ""
    if norm and not product_name:
        product_name = getattr(norm, "product_name", "") or ""

    if truth is None:
        truth = build_truth_context(
            idea=brief.idea,
            offer=brief.offer,
            cta=brief.cta,
            content_goal=brief.content_goal,
            content_format=content_format,
            marketplace=getattr(brief, "marketplace", "") or "",
            retailer=getattr(brief, "retailer", "") or "",
            affiliate_status=affiliate_status,
            sponsorship_status=getattr(brief, "sponsorship_status", "") or "",
            link_status=getattr(brief, "link_status", "") or "",
            fundraiser_status=fundraiser_link_status,
            link_placeholder=link_placeholder,
            norm=norm,
        )

    hook = _primary_hook_from_script(script_package, brief.idea)
    cta = _cta_text(script_package, brief.cta)
    context_line = _context_line(norm, script_package)

    if hashtag_set is None:
        hashtag_set = generate_hashtag_set(
            clean_subject=clean_subject,
            content_format=content_format,
            audience=brief.audience,
            content_goal=brief.content_goal,
            product_type=getattr(norm, "product_type", "") if norm else "",
            location=location,
            brand_name=brand_name or getattr(brief, "brand_name", ""),
            product_name=product_name,
            idea=brief.idea,
            offer=brief.offer,
            cta=brief.cta,
            truth=truth,
            marketplace=getattr(brief, "marketplace", "") or "",
            retailer=getattr(brief, "retailer", "") or "",
            affiliate_status=affiliate_status,
            sponsorship_status=getattr(brief, "sponsorship_status", "") or "",
            fundraiser_status=fundraiser_link_status,
        )

    hashtags = apply_truth_to_hashtag_list(
        select_platform_hashtags(hashtag_set, profile, truth=truth),
        truth,
    )

    disclosures = disclosure_blocks or {}
    disc_text = ""
    primary_disc: DisclosureBlock | None = None
    _priority = ("affiliate", "fundraising", "sponsored", "gifted", "medical_wellness")
    for dt in _priority:
        if dt in disclosures:
            primary_disc = disclosures[dt]
            disc_text = place_disclosure_for_platform(primary_disc, profile)
            break

    needs_link = bool(
        link_placeholder
        or affiliate_status in ("pending", "yes", "possible")
        or fundraiser_link_status in ("yes", "pending")
        or "affiliate" in content_format
        or "fundraising" in content_format
    )

    pinned = None
    if profile.supports_pinned_comment and needs_link:
        pinned = build_pinned_comment(cta, link_placeholder=link_placeholder, needs_link=True)

    title = build_title_for_platform(hook, clean_subject, profile)
    description = build_description_for_platform(
        hook, context_line, cta, disc_text, profile
    )

    caption = build_caption_for_platform(
        profile=profile,
        primary_hook=hook,
        context_line=context_line,
        cta=cta,
        disclosure_text=disc_text,
        hashtags=hashtags if profile.platform_name != "YouTube Shorts" else [],
    )

    tags: list[str] = []
    if profile.supports_tags:
        tags = generate_youtube_tags(clean_subject, product_name)

    posting_notes: list[str] = []
    if narration_provider == "elevenlabs":
        posting_notes.append("Narration uses ElevenLabs voice (internal note).")
    posting_notes.append(profile.notes)

    meta = PlatformPostMetadata(
        platform=platform_key,
        title=sanitize_metadata_text(title or "", truth) if title else None,
        caption=trim_to_limit(
            sanitize_metadata_text(caption, truth),
            profile.caption_limit,
        ),
        description=sanitize_metadata_text(description or "", truth) if description else None,
        hashtags=hashtags if profile.supports_hashtags else [],
        tags=tags,
        pinned_comment=sanitize_metadata_text(pinned or "", truth) if pinned else None,
        cta=sanitize_metadata_text(cta, truth),
        disclosure=primary_disc,
        overlay_caption_notes=_overlay_notes(script_package),
        posting_notes=posting_notes,
    )
    # Disclosure text is authored for compliance; do not strip conditional "if approved" wording.

    # YouTube: hashtags often in description
    if platform_key == "youtube_shorts" and hashtags:
        desc_parts = [meta.description or "", " ".join(hashtags)]
        meta.description = trim_to_limit("\n\n".join(p for p in desc_parts if p), profile.description_limit)

    validate_platform_metadata(meta, profile)
    return meta


def generate_metadata_package(
    brief: Any,
    script_package: Any | None = None,
    *,
    norm: Any | None = None,
    platforms: list[str] | None = None,
    narration: Any | None = None,
    location: str = "",
    brand_name: str = "",
    link_placeholder: str = "",
    affiliate_status: str = "",
    fundraiser_link_status: str = "",
    sponsorship_claimed: bool = False,
    gifted_claimed: bool = False,
    content_format: str = "",
    sponsorship_status: str = "",
    link_status: str = "",
    marketplace: str = "",
    retailer: str = "",
    product_name: str = "",
) -> MetadataPackage:
    """Build full MetadataPackage for all requested platforms."""
    target = list(platforms or brief.platforms or list(PLATFORM_KEYS))
    fmt = content_format or (
        getattr(script_package, "content_format", None) or "product_demo"
    )
    hook = _primary_hook_from_script(script_package, brief.idea)

    if norm is None:
        try:
            from genesis.creative.idea_normalizer import normalize_idea_context
            norm = normalize_idea_context(
                brief.idea,
                audience=brief.audience,
                content_goal=brief.content_goal,
                offer=brief.offer,
                cta=brief.cta,
                content_format=fmt,
            )
        except Exception:  # noqa: BLE001
            norm = None

    clean_subject = getattr(norm, "clean_subject", "") if norm else brief.idea[:60]
    truth = build_truth_context(
        idea=brief.idea,
        offer=brief.offer,
        cta=brief.cta,
        content_goal=brief.content_goal,
        content_format=fmt,
        marketplace=marketplace or getattr(brief, "marketplace", "") or "",
        retailer=retailer or getattr(brief, "retailer", "") or "",
        affiliate_status=affiliate_status,
        sponsorship_status=sponsorship_status or getattr(brief, "sponsorship_status", "") or "",
        link_status=link_status or getattr(brief, "link_status", "") or "",
        fundraiser_status=fundraiser_link_status,
        link_placeholder=link_placeholder,
        norm=norm,
    )

    disc_types = infer_disclosure_need(
        content_format=fmt,
        content_goal=brief.content_goal,
        offer=brief.offer,
        cta=brief.cta,
        affiliate_status=affiliate_status,
        fundraiser_link_status=fundraiser_link_status,
        sponsorship_status=sponsorship_status or getattr(brief, "sponsorship_status", "") or "",
        sponsorship_claimed=sponsorship_claimed,
        gifted_claimed=gifted_claimed,
        wellness_teaching=(fmt == "wellness_teaching"),
    )
    disclosures: dict[str, DisclosureBlock] = {}
    for dt in disc_types:
        disclosures[dt] = generate_disclosure_block(
            dt, official_approved=truth.affiliate_approved
        )

    hashtag_set = generate_hashtag_set(
        clean_subject=clean_subject,
        content_format=fmt,
        audience=brief.audience,
        content_goal=brief.content_goal,
        product_type=getattr(norm, "product_type", "") if norm else "",
        location=location,
        brand_name=brand_name or getattr(brief, "brand_name", ""),
        product_name=product_name or getattr(brief, "product_name", "") or (
            getattr(norm, "product_name", "") if norm else ""
        ),
        idea=brief.idea,
        offer=brief.offer,
        cta=brief.cta,
        truth=truth,
        marketplace=truth.marketplace,
        retailer=truth.retailer,
        affiliate_status=affiliate_status,
        sponsorship_status=sponsorship_status or getattr(brief, "sponsorship_status", "") or "",
        fundraiser_status=fundraiser_link_status,
    )

    narration_provider = ""
    if narration is not None:
        narration_provider = str(getattr(narration, "provider", "") or "")

    metadata_by_platform: dict[str, PlatformPostMetadata] = {}
    warnings_all: list[str] = []
    for plat in target:
        if plat not in PLATFORM_KEYS:
            warnings_all.append(f"skipped unknown platform: {plat}")
            continue
        meta = generate_platform_metadata(
            plat,
            brief=brief,
            script_package=script_package,
            norm=norm,
            hashtag_set=hashtag_set,
            disclosure_blocks=disclosures,
            narration_provider=narration_provider,
            location=location,
            brand_name=brand_name,
            link_placeholder=link_placeholder,
            affiliate_status=affiliate_status,
            fundraiser_link_status=fundraiser_link_status,
            sponsorship_claimed=sponsorship_claimed,
            truth=truth,
        )
        metadata_by_platform[plat] = meta
        warnings_all.extend(meta.warnings)

    status = MetadataStatus.COMPLETE if metadata_by_platform else MetadataStatus.PARTIAL

    return MetadataPackage(
        job_id=brief.job_id,
        idea=brief.idea,
        content_format=fmt,
        content_goal=brief.content_goal,
        platforms=target,
        primary_hook=hook,
        metadata_by_platform=metadata_by_platform,
        hashtag_sets={plat: hashtag_set for plat in metadata_by_platform},
        disclosures=disclosures,
        status=status,
        notes=list(dict.fromkeys(warnings_all)),
    )


def metadata_package_to_legacy_platform_list(
    package: MetadataPackage,
) -> list[dict[str, Any]]:
    """Convert to legacy workflow PlatformMetadata-compatible dicts."""
    from genesis.workflows.models import platform_defaults, platform_label

    out: list[dict[str, Any]] = []
    for key, meta in package.metadata_by_platform.items():
        defs = platform_defaults(key)
        notes_parts = list(meta.posting_notes)
        if meta.disclosure and meta.disclosure.short_text:
            notes_parts.append(f"Disclosure: {meta.disclosure.short_text}")
        if meta.pinned_comment:
            notes_parts.append(f"Pinned comment: {meta.pinned_comment}")
        if meta.warnings:
            notes_parts.extend(meta.warnings)
        out.append({
            "platform": key,
            "platform_label": platform_label(key),
            "caption": meta.caption,
            "hashtags": meta.hashtags,
            "cta": meta.cta,
            "duration_hint": f"{defs.get('recommended_duration_sec', 30)}s recommended",
            "aspect_ratio": defs.get("aspect_ratio", "9:16"),
            "notes": " ".join(notes_parts),
            "title": meta.title,
            "description": meta.description,
            "tags": meta.tags,
            "pinned_comment": meta.pinned_comment,
        })
    return out
