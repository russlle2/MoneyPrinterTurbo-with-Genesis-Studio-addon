"""
Genesis Studio — Idea normalization for script generation.

Turns messy creator ideas into clean, reusable fields before hooks/scripts
are generated. Fully generic — no hard-coded niche examples in production logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from genesis.creative.script_models import CONTENT_FORMATS


# Narrative openers to strip from the start of an idea
_NARRATIVE_PREFIXES = re.compile(
    r"^(?:"
    r"my\s+(?:girlfriend|boyfriend|partner|wife|husband|friend|mom|dad|brother|sister)\s+"
    r"(?:demonstrates?|shows?|tried|uses?|found)\s+"
    r"|my\s+\w+\s+(?:demonstrates?|shows?)\s+"
    r"|watch\s+(?:as\s+)?(?:me|us|this)\s+"
    r"|here(?:'s| is)\s+(?:how|why)\s+"
    r"|i\s+(?:show|demonstrate|tried|found|discovered)\s+"
    r"|let\s+me\s+show\s+you\s+"
    r"|this\s+is\s+how\s+"
    r")",
    re.IGNORECASE,
)

# Trailing clauses to drop
_TRAILING_CLAUSE = re.compile(
    r"\s+(?:that|which|because|and)\s+(?:went\s+viral|got\s+viral|is\s+viral|blows?\s+up|trending).*$",
    re.IGNORECASE,
)

_VIRAL_SIGNAL = re.compile(
    r"\b(?:went\s+viral|gone\s+viral|getting\s+viral|viral\s+video|blew\s+up|trending|million\s+views|\d+k\s+views)\b",
    re.IGNORECASE,
)

_TESTING_DURATION_CLAIM = re.compile(
    r"\b(?:"
    r"tested\s+(?:.{0,40}?\s+)?for\s+(?:a\s+)?(?:full\s+)?week"
    r"|tested\s+(?:.{0,40}?\s+)?for\s+\d+\s+weeks?"
    r"|used\s+(?:for\s+)?\d+\s+days?"
    r"|for\s+two\s+weeks"
    r"|month\s+of\s+testing"
    r"|after\s+\d+\s+days?"
    r")\b",
    re.IGNORECASE,
)

_AFFILIATE_APPROVED_CLAIM = re.compile(
    r"\b(?:official\s+affiliate|approved\s+affiliate|my\s+code\s+is|use\s+code\s+\w+|sponsored\s+by\s+the\s+brand)\b",
    re.IGNORECASE,
)

_PRODUCT_MECHANISM_HINTS: list[tuple[re.Pattern[str], str, list[str]]] = [
    (re.compile(r"\bsolar[- ]?powered?\b", re.I), "uses sunlight instead of fuel or batteries",
     ["no fuel", "no battery", "works with direct sunlight"]),
    (re.compile(r"\bsound\s+bowl|singing\s+bowl|meditation\s+bowl\b", re.I),
     "uses vibration and resonance for relaxation",
     ["calming sound", "guided breath", "nervous-system reset"]),
    (re.compile(r"\bessential\s+oil|aromatherapy|diffuser\b", re.I),
     "uses scent and dilution for safe topical or ambient use",
     ["dilution matters", "patch test first", "small amount goes far"]),
    (re.compile(r"\b(cat|dog|kitten|puppy|rescue|shelter)\b", re.I),
     "community support changes outcomes for animals in need",
     ["donations help", "foster network", "every share reaches someone"]),
    (re.compile(r"\bbrain\s+training|memory\s+game|cognitive|puzzle\s+app\b", re.I),
     "builds focus and mental agility through short daily practice",
     ["daily reps", "measurable progress", "habit stacking"]),
    (re.compile(r"\bfundrais|donat|charity|gofundme\b", re.I),
     "collective giving moves the cause forward",
     ["transparent impact", "community rally", "one action matters"]),
]

_BAD_HOOK_FRAGMENTS = [
    re.compile(r"\bdemonstrates?\s+a\s*$", re.I),
    re.compile(r"\bI\s+tested\s+My\b", re.I),
    re.compile(r"\btalks\s+about\s+My\b", re.I),
    re.compile(r"\bNobody\s+talks\s+about\s+My\b", re.I),
    re.compile(r"\bMy\s+girlfriend\s+demonstrates\b", re.I),
    re.compile(r"\blike\s+this\s+—\s+until\s+now\b", re.I),
    re.compile(r"\bthis\s+topic\s+like\s+this\b", re.I),
    re.compile(r"\s{2,}"),
    re.compile(r"\b(?:a|an|the)\s+(?:a|an|the)\b", re.I),
]

_SAFE_FALLBACK_HOOK = (
    "This video went viral because the product looks fake until you see it work."
)


@dataclass
class NormalizedIdeaContext:
    """Structured, truth-aware context derived from a raw creator idea."""

    raw_idea: str
    clean_subject: str
    product_name: str = ""
    product_type: str = ""
    mechanism: str = ""
    proof_point: str = ""
    scene_context: str = ""
    audience_phrase: str = ""
    content_angle: str = ""
    content_format: str = "product_demo"
    cta_keyword: str = ""
    key_benefits: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    # Truthfulness flags — set from explicit brief text only
    claims_testing_duration: bool = False
    claims_affiliate_approved: bool = False
    claims_official_link: bool = False
    mentions_viral: bool = False

    def to_template_ctx(self) -> dict[str, str]:
        """Flat string dict for legacy template fill (brief_subject = clean_subject)."""
        subj = self.clean_subject or "this"
        benefits = self.key_benefits
        benefit_short = benefits[0] if benefits else ""
        benefit_pair = " · ".join(benefits[:2]) if len(benefits) >= 2 else benefit_short
        return {
            "raw_idea": self.raw_idea[:120],
            "clean_subject": subj,
            "brief_subject": subj,
            "product_name": self.product_name or subj,
            "product_type": self.product_type or subj,
            "mechanism": self.mechanism,
            "proof_point": self.proof_point,
            "scene_context": self.scene_context,
            "audience_phrase": self.audience_phrase,
            "audience_or_niche": self.audience_phrase,
            "content_angle": self.content_angle,
            "content_format": self.content_format,
            "cta_keyword": self.cta_keyword,
            "keyword": self.cta_keyword,
            "key_benefit": benefit_short,
            "key_benefits": benefit_pair,
            "benefit_one": benefits[0] if len(benefits) > 0 else "",
            "benefit_two": benefits[1] if len(benefits) > 1 else "",
            "benefit_three": benefits[2] if len(benefits) > 2 else "",
        }


def clean_topic_phrase(text: str) -> str:
    """Remove narrative noise and trailing viral clauses; collapse whitespace."""
    t = text.strip()
    t = _NARRATIVE_PREFIXES.sub("", t)
    t = _TRAILING_CLAUSE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_clean_subject(idea: str, offer: str = "") -> str:
    """
    Extract a short, speakable subject (product/topic name) from a messy idea.
    """
    if offer and len(offer.split()) <= 8 and not _looks_like_sentence(offer):
        return _title_case_phrase(offer.strip())

    t = clean_topic_phrase(idea)

    # Prefer "a/an/the <noun phrase>" capture
    m = re.search(
        r"\b(?:a|an|the)\s+([\w\-]+(?:\s+[\w\-]+){0,5})",
        t,
        re.IGNORECASE,
    )
    if m:
        phrase = m.group(1).strip()
        phrase = _trim_at_break(phrase)
        if _is_valid_subject(phrase):
            return _title_case_phrase(phrase)

    # "solar-powered lighter" style compound at start
    m2 = re.search(
        r"^([\w\-]+(?:\s+[\w\-]+){0,4}(?:lighter|gadget|tool|device|kit|app|course|bowl|oil|rescue|training|routine|hack|method|system|product))",
        t,
        re.IGNORECASE,
    )
    if m2:
        phrase = _trim_at_break(m2.group(1))
        if _is_valid_subject(phrase):
            return _title_case_phrase(phrase)

    # Last resort: first 4 meaningful tokens after cleaning
    tokens = [w for w in t.split() if w.lower() not in _STOPWORDS and len(w) > 1]
    if tokens:
        phrase = " ".join(tokens[:5])
        phrase = _trim_at_break(phrase)
        return _title_case_phrase(phrase) if phrase else "this topic"

    return "this topic"


def infer_product_context(
    idea: str,
    clean_subject: str,
) -> tuple[str, str, list[str]]:
    """
    Return (product_type, mechanism, key_benefits) inferred from keywords.
    Generic keyword rules only — no fixed product names.
    """
    combined = f"{idea} {clean_subject}".lower()
    product_type = clean_subject
    mechanism = ""
    benefits: list[str] = []

    for pattern, mech, bens in _PRODUCT_MECHANISM_HINTS:
        if pattern.search(combined):
            mechanism = mech
            benefits = list(bens)
            # Shorter product_type label from subject
            words = clean_subject.split()
            if len(words) > 3:
                product_type = " ".join(words[-2:]) if len(words) >= 2 else clean_subject
            break

    if not mechanism:
        if re.search(r"\b(?:demo|product|gadget|tool|device)\b", combined, re.I):
            mechanism = "works as shown in the demonstration"
            benefits = ["easy to see in action", "practical everyday use"]
        elif re.search(r"\b(?:meditat|wellness|breath|yoga|calm)\b", combined, re.I):
            mechanism = "supports calm and focus through guided practice"
            benefits = ["repeatable practice", "felt in the body", "no hype required"]
        elif re.search(r"\b(?:tutorial|how\s+to|step)\b", combined, re.I):
            mechanism = "a clear sequence you can follow"
            benefits = ["step-by-step", "beginner-friendly", "save and replay"]
        else:
            mechanism = "delivers what the video shows"
            benefits = ["worth a closer look", "easy to explain in 30 seconds"]

    return product_type, mechanism, benefits


def infer_proof_point(idea: str, content_goal: str = "") -> str:
    """Infer credibility proof from explicit signals — no invented metrics."""
    if _VIRAL_SIGNAL.search(idea):
        return "the video went viral"
    if re.search(r"\b(?:before\s+and\s+after|results|proof|review|honest)\b", idea, re.I):
        return "visible results people can judge for themselves"
    if re.search(r"\b(?:rescue|saved|survived|funded)\b", idea, re.I):
        return "a real outcome people rallied around"
    if "follow-up" in content_goal.lower() or "viral" in content_goal.lower():
        return "people kept asking about it after it spread"
    return ""


def infer_content_angle(content_format: str, idea: str, content_goal: str = "") -> str:
    """Map format + idea signals to a creator-facing angle label."""
    goal = content_goal.lower()
    if content_format == "affiliate_followup":
        return "viral product follow-up"
    if content_format == "fundraising_story":
        return "community support story"
    if content_format == "wellness_teaching":
        return "guided wellness practice"
    if content_format == "tutorial":
        return "how-to walkthrough"
    if content_format == "personal_story":
        return "personal experience"
    if content_format == "controversial_take":
        return "contrarian perspective"
    if content_format == "motivational_walkthrough":
        return "action-oriented motivation"
    if content_format == "product_demo":
        return "product demonstration"
    if "affiliate" in goal:
        return "buyer-interest follow-up"
    if "fund" in goal or "donat" in goal:
        return "fundraising appeal"
    if "teach" in goal or "wellness" in goal:
        return "educational wellness"
    return "short-form creator content"


def infer_content_angle_from_format(content_format: str) -> str:
    return infer_content_angle(content_format, "", "")


def _infer_scene_context(idea: str) -> str:
    if re.search(r"\b(?:demonstrat|shows?|watch|in\s+action|hands?-on)\b", idea, re.I):
        return "a real-life demonstration"
    if re.search(r"\b(?:class|session|workshop|studio)\b", idea, re.I):
        return "a guided session"
    if re.search(r"\b(?:story|journey|happened)\b", idea, re.I):
        return "a personal moment on camera"
    return "a short on-camera moment"


def _extract_cta_keyword(cta: str, content_format: str) -> str:
    if cta:
        matches = re.findall(r"\b[A-Z]{3,}\b", cta)
        if matches:
            return matches[0]
    return {
        "affiliate_followup": "LINK",
        "product_demo": "DEMO",
        "wellness_teaching": "LEARN",
        "tutorial": "STEPS",
        "motivational_walkthrough": "READY",
        "fundraising_story": "HELP",
        "personal_story": "SAME",
        "controversial_take": "THOUGHTS",
    }.get(content_format, "LINK")


def _truth_flags_from_brief(
    idea: str,
    cta: str,
    offer: str,
    content_goal: str,
) -> tuple[bool, bool, bool]:
    combined = f"{idea} {cta} {offer} {content_goal}"
    claims_duration = bool(_TESTING_DURATION_CLAIM.search(combined))
    claims_affiliate = bool(_AFFILIATE_APPROVED_CLAIM.search(combined))
    claims_link = bool(
        re.search(r"\bofficial\s+link\b", combined, re.I)
    )
    # "pinned link" / "link in bio" in CTA are intents, not proof the link is live yet
    return claims_duration, claims_affiliate, claims_link


def normalize_idea_context(
    idea: str,
    *,
    audience: str = "",
    content_goal: str = "",
    offer: str = "",
    cta: str = "",
    content_format: str = "product_demo",
) -> NormalizedIdeaContext:
    """
    Main entry: raw idea → NormalizedIdeaContext for hook/script generation.
    """
    fmt = content_format if content_format in CONTENT_FORMATS else "product_demo"
    clean = extract_clean_subject(idea, offer=offer)
    product_type, mechanism, benefits = infer_product_context(idea, clean)
    proof = infer_proof_point(idea, content_goal)
    angle = infer_content_angle(fmt, idea, content_goal)
    scene = _infer_scene_context(idea)
    keyword = _extract_cta_keyword(cta, fmt)
    claims_dur, claims_aff, claims_link = _truth_flags_from_brief(idea, cta, offer, content_goal)
    mentions_viral = bool(_VIRAL_SIGNAL.search(idea))

    aud_phrase = audience.strip() or _default_audience_for_format(fmt)

    risk_notes: list[str] = []
    if fmt == "affiliate_followup" and not claims_aff:
        risk_notes.append("Do not imply affiliate approval unless stated in brief.")
    if not claims_dur:
        risk_notes.append("Avoid inventing testing duration.")
    if fmt == "fundraising_story":
        risk_notes.append("Lead with the human story before the ask.")

    product_name = clean
    if len(clean.split()) > 4:
        # Shorter speakable name: last 2–3 words often the product noun
        parts = clean.split()
        product_name = " ".join(parts[-2:])

    return NormalizedIdeaContext(
        raw_idea=idea.strip(),
        clean_subject=clean,
        product_name=product_name,
        product_type=product_type,
        mechanism=mechanism,
        proof_point=proof,
        scene_context=scene,
        audience_phrase=aud_phrase,
        content_angle=angle,
        content_format=fmt,
        cta_keyword=keyword,
        key_benefits=benefits,
        risk_notes=risk_notes,
        claims_testing_duration=claims_dur,
        claims_affiliate_approved=claims_aff,
        claims_official_link=claims_link,
        mentions_viral=mentions_viral,
    )


def validate_hook_text(text: str, norm: NormalizedIdeaContext | None = None) -> bool:
    """
    Return False if hook contains known bad fragments or awkward raw-idea leakage.
    """
    if not text or len(text.strip()) < 12:
        return False
    for pat in _BAD_HOOK_FRAGMENTS:
        if pat.search(text):
            return False
    # Raw idea substring leaked (long prefix match)
    if norm and norm.raw_idea:
        raw_lower = norm.raw_idea.lower()
        # If hook contains 5+ consecutive words from raw narrative opener
        opener = raw_lower[:40]
        if len(opener) > 20 and opener in text.lower():
            return False
        if "demonstrates a" in text.lower() and "demonstrates" in raw_lower:
            return False
    # Subject should not be absurdly long in a hook
    if norm and norm.clean_subject:
        if norm.clean_subject.lower() in text.lower():
            pass  # good
        elif len(norm.raw_idea.split()) > 6 and norm.raw_idea.lower()[:30] in text.lower():
            return False
    # Incomplete sentence ending
    if text.rstrip().endswith((" a", " an", " the", " my", " this")):
        return False
    return True


def sanitize_hook(text: str, norm: NormalizedIdeaContext) -> str:
    """Return validated hook or a safe fallback tied to proof/mechanism."""
    t = re.sub(r"\s+", " ", text).strip()
    if validate_hook_text(t, norm):
        return t
    if norm.proof_point and "viral" in norm.proof_point:
        subj = norm.product_name or norm.clean_subject
        return f"This {subj} blew up because it looks fake until you see it work."
    if norm.mechanism and norm.key_benefits:
        b = norm.key_benefits[0]
        return f"{b.capitalize()}. Here's the {norm.product_name or norm.clean_subject}."
    return _SAFE_FALLBACK_HOOK


# --- private helpers ---

_STOPWORDS = frozenset({
    "a", "an", "the", "that", "which", "who", "my", "our", "your", "this", "it",
    "is", "are", "was", "were", "for", "and", "or", "but", "with", "from", "to",
    "in", "on", "at", "by", "of", "how", "why", "what", "when", "went", "viral",
    "demonstrates", "demonstrate", "shows", "show", "video", "watch",
})


def _looks_like_sentence(s: str) -> bool:
    return len(s.split()) > 10 or s.count(".") > 0


def _trim_at_break(phrase: str) -> str:
    phrase = re.split(r"\s+(?:that|which|because|and|or)\s+", phrase, maxsplit=1)[0]
    return phrase.strip()[:60]


def _is_valid_subject(phrase: str) -> bool:
    if not phrase or len(phrase) < 3:
        return False
    low = phrase.lower()
    if low.startswith(("demonstrates", "shows", "watch", "here")):
        return False
    if re.search(r"\bdemonstrates?\s+a\b", low):
        return False
    return len(phrase.split()) <= 7


def _title_case_phrase(phrase: str) -> str:
    """Title-case but keep small words and hyphenated parts sensible."""
    if not phrase:
        return phrase
    # Don't title-case every word for multi-word product names — use sentence case for hooks
    return phrase[0].upper() + phrase[1:] if phrase else phrase


def _default_audience_for_format(content_format: str) -> str:
    return {
        "affiliate_followup": "people who saw the viral clip and want the link",
        "product_demo": "people comparing gear before they buy",
        "wellness_teaching": "people investing in calm, focus, and daily practice",
        "personal_story": "people who relate to real stories on camera",
        "controversial_take": "people tired of generic advice",
        "tutorial": "people who want clear steps they can repeat",
        "fundraising_story": "people who support causes in their community",
        "motivational_walkthrough": "people ready to take one concrete step today",
    }.get(content_format, "your audience")
