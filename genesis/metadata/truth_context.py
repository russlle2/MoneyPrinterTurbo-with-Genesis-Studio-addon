"""
Genesis Studio — Metadata truth guards for hashtags, captions, and disclosures.

Marketplace, sponsorship, affiliate approval, and fundraising claims must be
supported by the brief or explicit optional fields — never assumed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Hashtag stems (without #) gated by marketplace / status
MARKETPLACE_HASHTAG_STEMS: dict[str, list[str]] = {
    "amazon": ["AmazonFinds"],
    "tiktok_shop": ["TikTokShop", "TikTokMadeMeBuyIt"],
    "etsy": ["EtsyFinds"],
    "walmart": ["WalmartFinds"],
    "target": ["TargetFinds"],
    "shopmy": ["ShopMy"],
}

_MARKETPLACE_FROM_TEXT: list[tuple[str, re.Pattern[str]]] = [
    ("amazon", re.compile(r"\bamazon\b", re.I)),
    ("tiktok_shop", re.compile(r"\b(?:tiktok\s+shop|tiktok\s+made\s+me\s+buy)\b", re.I)),
    ("etsy", re.compile(r"\betsy\b", re.I)),
    ("walmart", re.compile(r"\bwalmart\b", re.I)),
    ("target", re.compile(r"\btarget\b", re.I)),
    ("shopmy", re.compile(r"\bshop\s*my\b", re.I)),
]

_SPONSORSHIP_HASHTAG_STEMS = frozenset({
    "paidpartnership", "sponsored", "ad",
})

_FUNDRAISING_HASHTAG_STEMS = frozenset({
    "gofundme", "mutualaid", "giveback", "helpothers", "communitysupport",
    "communityfundraiser", "communityfund",
})

_PRODUCT_BUYING_HASHTAG_STEMS = frozenset({
    "amazonfinds", "tiktokshop", "tiktokmademebuyit", "etsyfinds",
    "walmartfinds", "targetfinds", "shopmy", "musthave", "viralfind",
})

_PRODUCT_OFFER_SIGNAL = re.compile(
    r"\b(?:buy|shop|discount|code|link|affiliate|product|gear|gadget|available)\b",
    re.I,
)

_GOFUNDME_SIGNAL = re.compile(r"\bgofundme\b", re.I)


@dataclass
class MetadataTruthContext:
    """Truth flags derived from brief + normalized context."""

    marketplace: str = ""
    retailer: str = ""
    affiliate_status: str = ""
    sponsorship_status: str = ""
    link_status: str = ""
    fundraiser_status: str = ""
    content_format: str = ""
    has_product_offer: bool = False
    allow_fundraising_tags: bool = False
    allow_sponsorship_tags: bool = False
    allow_gofundme_mention: bool = False
    affiliate_approved: bool = False
    official_link_claim: bool = False
    allowed_marketplace_stems: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)


def _normalize_marketplace_key(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "tiktok": "tiktok_shop",
        "tiktokshop": "tiktok_shop",
        "tik_tok_shop": "tiktok_shop",
    }
    return aliases.get(key, key)


def infer_marketplace_from_text(*parts: str) -> str:
    combined = " ".join(p for p in parts if p)
    for key, pattern in _MARKETPLACE_FROM_TEXT:
        if pattern.search(combined):
            return key
    return ""


def build_truth_context(
    *,
    idea: str = "",
    offer: str = "",
    cta: str = "",
    content_goal: str = "",
    content_format: str = "product_demo",
    marketplace: str = "",
    retailer: str = "",
    affiliate_status: str = "",
    sponsorship_status: str = "",
    link_status: str = "",
    fundraiser_status: str = "",
    link_placeholder: str = "",
    norm: object | None = None,
) -> MetadataTruthContext:
    """Build truth context; explicit fields override inference from text."""
    inferred = infer_marketplace_from_text(idea, offer, cta, content_goal, retailer)
    market = _normalize_marketplace_key(marketplace) if marketplace else inferred
    if retailer and not market:
        market = infer_marketplace_from_text(retailer) or _normalize_marketplace_key(retailer)

    combined = f"{idea} {offer} {cta} {content_goal}".lower()
    fmt = content_format or "product_demo"

    fund_status = fundraiser_status.strip().lower()
    allow_fund = fmt == "fundraising_story" or fund_status in ("yes", "pending", "active")
    if not allow_fund and _GOFUNDME_SIGNAL.search(combined):
        allow_fund = True  # brief explicitly names GoFundMe

    sponsor_status = sponsorship_status.strip().lower()
    allow_sponsor = sponsor_status == "sponsored" or bool(
        re.search(r"\b(?:sponsored\s+by|paid\s+partnership|#ad\b|#sponsored)\b", combined, re.I)
    )

    aff_status = affiliate_status.strip().lower()
    affiliate_approved = aff_status == "approved"

    link_stat = link_status.strip().lower()
    official_link = link_stat == "official" or bool(
        getattr(norm, "claims_official_link", False) if norm else False
    )
    if re.search(r"\bofficial\s+link\b", combined, re.I):
        official_link = True

    has_product_offer = bool(offer.strip()) and bool(_PRODUCT_OFFER_SIGNAL.search(offer))
    if fmt in ("product_demo", "affiliate_followup") and not has_product_offer:
        has_product_offer = True  # format implies product angle
    if fmt == "wellness_teaching":
        has_product_offer = bool(offer.strip()) and bool(
            _PRODUCT_OFFER_SIGNAL.search(f"{offer} {cta}")
        )

    allowed: set[str] = set()
    if market:
        for stem in MARKETPLACE_HASHTAG_STEMS.get(market, []):
            allowed.add(stem.lower())

    ctx = MetadataTruthContext(
        marketplace=market,
        retailer=retailer,
        affiliate_status=aff_status,
        sponsorship_status=sponsor_status,
        link_status=link_stat,
        fundraiser_status=fund_status,
        content_format=fmt,
        has_product_offer=has_product_offer,
        allow_fundraising_tags=allow_fund,
        allow_sponsorship_tags=allow_sponsor,
        allow_gofundme_mention=allow_fund and (
            fund_status in ("yes", "pending", "active") or _GOFUNDME_SIGNAL.search(combined)
        ),
        affiliate_approved=affiliate_approved,
        official_link_claim=official_link,
        allowed_marketplace_stems=allowed,
    )
    return ctx


def _hashtag_stem(tag: str) -> str:
    return tag.lstrip("#").lower()


def filter_hashtags_for_truth(
    tags: list[str],
    ctx: MetadataTruthContext,
) -> tuple[list[str], list[str]]:
    """Remove hashtags that imply unsupported marketplace, sponsorship, or fundraising."""
    warnings: list[str] = []
    out: list[str] = []

    for tag in tags:
        stem = _hashtag_stem(tag)
        if not stem:
            continue

        if stem in _SPONSORSHIP_HASHTAG_STEMS and not ctx.allow_sponsorship_tags:
            warnings.append(f"dropped sponsorship hashtag (not supported): {tag}")
            continue

        if stem in _FUNDRAISING_HASHTAG_STEMS and not ctx.allow_fundraising_tags:
            warnings.append(f"dropped fundraising hashtag (not supported): {tag}")
            continue

        if stem == "gofundme" and not ctx.allow_gofundme_mention:
            warnings.append(f"dropped GoFundMe hashtag (not in brief): {tag}")
            continue

        marketplace_gated = False
        for market_key, stems in MARKETPLACE_HASHTAG_STEMS.items():
            if stem in {s.lower() for s in stems}:
                marketplace_gated = True
                if stem in ctx.allowed_marketplace_stems:
                    out.append(tag)
                else:
                    warnings.append(
                        f"dropped marketplace hashtag (no {market_key} support): {tag}"
                    )
                break
        if marketplace_gated:
            continue

        if (
            ctx.content_format == "wellness_teaching"
            and stem in _PRODUCT_BUYING_HASHTAG_STEMS
            and not ctx.has_product_offer
        ):
            warnings.append(f"dropped product-buying hashtag from wellness content: {tag}")
            continue

        if (
            ctx.content_format not in ("product_demo", "affiliate_followup", "tutorial")
            and stem in _PRODUCT_BUYING_HASHTAG_STEMS
            and not ctx.has_product_offer
        ):
            warnings.append(f"dropped product-buying hashtag: {tag}")
            continue

        out.append(tag)

    return out, warnings


def sanitize_metadata_text(text: str, ctx: MetadataTruthContext) -> str:
    """Strip or soften retailer/sponsorship claims not supported by context."""
    if not text:
        return text
    out = text

    if not ctx.marketplace or ctx.marketplace != "amazon":
        if not re.search(r"\bamazon\b", f"{ctx.retailer} {ctx.marketplace}", re.I):
            out = re.sub(r"\bAmazon\b", "", out, flags=re.I)

    if not ctx.allow_gofundme_mention:
        out = re.sub(r"\bGoFundMe\b", "fundraiser", out, flags=re.I)

    if not ctx.allow_sponsorship_tags:
        out = re.sub(r"\b(?:#ad|#sponsored|paid partnership|sponsored by)\b", "", out, flags=re.I)

    if not ctx.affiliate_approved:
        out = re.sub(r"\baffiliate\s+approved\b", "", out, flags=re.I)
        out = re.sub(r"\bofficial(?:ly)?\s+approved\b", "", out, flags=re.I)

    if not ctx.official_link_claim:
        out = re.sub(r"\bofficial\s+link\b", "link", out, flags=re.I)

    out = re.sub(r"  +", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
