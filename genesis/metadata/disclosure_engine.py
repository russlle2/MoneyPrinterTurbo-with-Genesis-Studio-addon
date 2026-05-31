"""
Genesis Studio — Disclosure inference and placement (truth-aware).
"""

from __future__ import annotations

import re
from typing import Any

from genesis.metadata.platform_profiles import PlatformProfile
from genesis.metadata.seo_models import DisclosureBlock

_AFFILIATE_SIGNAL = re.compile(
    r"\b(?:affiliate|commission|referral\s+link|use\s+code|discount\s+code|"
    r"link\s+in\s+bio|pinned\s+link|official\s+link|buy\s+link)\b",
    re.I,
)
_SPONSOR_SIGNAL = re.compile(
    r"\b(?:sponsored\s+by|paid\s+partnership|brand\s+deal|#ad\b|#sponsored)\b",
    re.I,
)
_GIFTED_SIGNAL = re.compile(r"\b(?:gifted|pr\s+package|sent\s+by\s+the\s+brand)\b", re.I)
_FUNDRAISE_SIGNAL = re.compile(
    r"\b(?:donate|donation|gofundme|fundraiser|fundraising|venmo|paypal\s+me|"
    r"support\s+the\s+cause|help\s+fund)\b",
    re.I,
)
_MEDICAL_WELLNESS_SIGNAL = re.compile(
    r"\b(?:cure|treat|diagnos|prescri|medical\s+advice|heal\s+your|fda)\b",
    re.I,
)


def infer_disclosure_need(
    *,
    content_format: str = "",
    content_goal: str = "",
    offer: str = "",
    cta: str = "",
    affiliate_status: str = "",
    fundraiser_link_status: str = "",
    sponsorship_status: str = "",
    sponsorship_claimed: bool = False,
    gifted_claimed: bool = False,
    wellness_teaching: bool = False,
) -> list[str]:
    """
    Return list of disclosure type keys needed (may be empty).
    """
    combined = f"{content_format} {content_goal} {offer} {cta}".lower()
    types: list[str] = []

    if content_format == "fundraising_story":
        types.append("fundraising")
        if wellness_teaching:
            types.append("medical_wellness")
        return types

    sponsor_ok = sponsorship_status.strip().lower() == "sponsored" or sponsorship_claimed
    if sponsor_ok or _SPONSOR_SIGNAL.search(combined):
        types.append("sponsored")
    elif gifted_claimed or _GIFTED_SIGNAL.search(combined):
        types.append("gifted")
    elif (
        content_format == "affiliate_followup"
        or "affiliate" in combined
        or affiliate_status in ("pending", "possible", "yes")
        or _AFFILIATE_SIGNAL.search(combined)
    ):
        types.append("affiliate")

    if fundraiser_link_status in ("yes", "pending") or _FUNDRAISE_SIGNAL.search(combined):
        types.append("fundraising")

    if wellness_teaching or content_format == "wellness_teaching":
        if _MEDICAL_WELLNESS_SIGNAL.search(combined) or content_format == "wellness_teaching":
            types.append("medical_wellness")

    return list(dict.fromkeys(types))


def generate_disclosure_block(disclosure_type: str, *, official_approved: bool = False) -> DisclosureBlock:
    """Build disclosure text for a type. Does not claim approval unless flagged."""
    if disclosure_type == "affiliate":
        if official_approved:
            short = "Affiliate link — clearly marked."
            long = "This post may include an affiliate link. I may earn a small commission at no extra cost to you."
        else:
            short = "Affiliate link if approved — I'll clearly mark it."
            long = (
                "If I receive an affiliate link or code, I may earn a small commission. "
                "I'll mark it clearly when that happens."
            )
        return DisclosureBlock(
            required=True,
            disclosure_type="affiliate",
            short_text=short,
            long_text=long,
            placement_note="Place in caption, description, or pinned comment — not hidden.",
        )

    if disclosure_type == "sponsored":
        return DisclosureBlock(
            required=True,
            disclosure_type="sponsored",
            short_text="Paid partnership.",
            long_text="This content is part of a paid partnership. Opinions are my own.",
            placement_note="Visible in caption or first line of description.",
        )

    if disclosure_type == "gifted":
        return DisclosureBlock(
            required=True,
            disclosure_type="gifted",
            short_text="Product gifted by brand.",
            long_text="This product was gifted. My review is honest and unsponsored unless stated.",
            placement_note="Near the top of caption or description.",
        )

    if disclosure_type == "fundraising":
        return DisclosureBlock(
            required=True,
            disclosure_type="fundraising",
            short_text="Donation link in bio/pinned comment.",
            long_text=(
                "Funds are intended to support the person or cause described. "
                "Please review the fundraiser details before donating."
            ),
            placement_note="Pin fundraiser link; repeat disclosure in caption.",
        )

    if disclosure_type == "medical_wellness":
        return DisclosureBlock(
            required=False,
            disclosure_type="medical_wellness",
            short_text="Educational only — not medical advice.",
            long_text=(
                "This is educational wellness content, not medical advice. "
                "Consult a qualified professional for your situation."
            ),
            placement_note="Optional footer in caption or description.",
        )

    return DisclosureBlock(
        required=False,
        disclosure_type="none",
        short_text="",
        long_text="",
        placement_note="",
    )


def place_disclosure_for_platform(
    disclosure: DisclosureBlock,
    profile: PlatformProfile,
    *,
    use_short: bool = True,
) -> str:
    """Return disclosure string sized for platform caption style."""
    if not disclosure.required and disclosure.disclosure_type == "none":
        return ""
    text = disclosure.short_text if use_short else disclosure.long_text
    if profile.platform_name == "X" and len(text) > 80:
        return disclosure.short_text
    return text
