"""
Genesis Studio — Script + Hook Engine.

Turns a rough idea into a structured short-form video script package using
the Viral Spine framework:

  1. Pattern Interrupt  — stop the scroll
  2. Proof              — establish credibility
  3. Demonstration / Teaching — deliver core value
  4. Meaning            — explain why it matters
  5. CTA                — single clear next action

When a local LLM is configured and reachable, the engine attempts local
generation first.  On any failure or when LLM is disabled, the deterministic
Viral Spine template fallback is used — high-quality enough to publish as-is.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from typing import Any

from genesis.creative.script_models import (
    CONTENT_FORMATS,
    CTAOption,
    HookOption,
    OverlayCaption,
    ScriptPackage,
    ScriptSection,
    ScriptSource,
    ScriptStatus,
    ScriptVariant,
)
from genesis.creative.idea_normalizer import (
    NormalizedIdeaContext,
    normalize_idea_context,
    sanitize_hook,
    validate_hook_text,
)
from genesis.utils.logger import get_logger

logger = get_logger("creative.script_engine")

# Re-export normalization API for tests and callers
__all_exports__ = (
    "normalize_idea_context",
    "validate_hook_text",
    "extract_clean_subject",
    "infer_content_angle",
    "infer_product_context",
    "infer_proof_point",
    "clean_topic_phrase",
)

def extract_clean_subject(idea: str, offer: str = "") -> str:
    from genesis.creative.idea_normalizer import extract_clean_subject as _ecs
    return _ecs(idea, offer=offer)

def infer_content_angle(content_format: str, idea: str = "", content_goal: str = "") -> str:
    from genesis.creative.idea_normalizer import infer_content_angle as _ica
    return _ica(content_format, idea, content_goal)

def infer_product_context(idea: str, clean_subject: str):
    from genesis.creative.idea_normalizer import infer_product_context as _ipc
    return _ipc(idea, clean_subject)

def infer_proof_point(idea: str, content_goal: str = "") -> str:
    from genesis.creative.idea_normalizer import infer_proof_point as _ipp
    return _ipp(idea, content_goal)

def clean_topic_phrase(text: str) -> str:
    from genesis.creative.idea_normalizer import clean_topic_phrase as _ctp
    return _ctp(text)


# ---------------------------------------------------------------------------
# Format profiles
# ---------------------------------------------------------------------------

_FORMAT_PROFILES: dict[str, dict[str, Any]] = {
    "product_demo": {
        "hook_styles": ["practical", "proof_based", "curiosity", "shock"],
        "primary_cta_type": "link_in_bio",
        "notes": ["Show the product in action within first 3 seconds.",
                  "Demonstrate one clear benefit — do not feature-dump."],
    },
    "wellness_teaching": {
        "hook_styles": ["curiosity", "emotional", "practical", "contrarian"],
        "primary_cta_type": "save_for_later",
        "notes": ["Lead with outcome, not method.",
                  "Keep advice actionable and specific."],
    },
    "personal_story": {
        "hook_styles": ["story_open_loop", "emotional", "shock", "curiosity"],
        "primary_cta_type": "comment_engage",
        "notes": ["Name the tension in the first sentence.",
                  "Resolve the story before the CTA — do not leave it hanging."],
    },
    "affiliate_followup": {
        "hook_styles": ["proof_based", "practical", "curiosity", "story_open_loop"],
        "primary_cta_type": "comment_keyword",
        "notes": ["Reference the original viral moment to borrow credibility.",
                  "Include any required FTC disclosure: 'Link may be affiliate'."],
    },
    "controversial_take": {
        "hook_styles": ["contrarian", "shock", "curiosity", "emotional"],
        "primary_cta_type": "comment_engage",
        "notes": ["State the counterintuitive position clearly in the hook.",
                  "Back with evidence or experience — not just opinion."],
    },
    "tutorial": {
        "hook_styles": ["practical", "curiosity", "proof_based", "contrarian"],
        "primary_cta_type": "save_for_later",
        "notes": ["Promise the outcome in the hook, deliver it in the body.",
                  "Number the steps on-screen for scroll-friendly skimming."],
    },
    "fundraising_story": {
        "hook_styles": ["emotional", "story_open_loop", "shock", "proof_based"],
        "primary_cta_type": "donate_share",
        "notes": ["Lead with the human, not the ask.",
                  "Make the impact of one action concrete and specific."],
    },
    "motivational_walkthrough": {
        "hook_styles": ["emotional", "contrarian", "story_open_loop", "practical"],
        "primary_cta_type": "save_for_later",
        "notes": ["Give a real actionable step, not just inspiration.",
                  "Let the viewer picture themselves completing the action."],
    },
}

# ---------------------------------------------------------------------------
# Hook templates  (8 styles × 4 options = 32 hooks)
# ---------------------------------------------------------------------------

_HOOK_TEMPLATES: dict[str, list[str]] = {
    "curiosity": [
        "Nobody talks about {brief_subject} like this — until now.",
        "I didn't believe {brief_subject} was real until I actually tried it.",
        "The thing about {brief_subject} that the algorithm keeps hiding.",
        "What if everything you've been told about {brief_subject} is backwards?",
    ],
    "shock": [
        "This {offer_or_thing} actually works — and I have the proof.",
        "I bought {brief_subject} on a whim. I can't believe what happened next.",
        "{brief_subject} just went viral for a very real reason.",
        "I almost missed this. Don't make the same mistake I did.",
    ],
    "proof_based": [
        "I tested {brief_subject} for a full week. Here's the honest breakdown.",
        "Real results. No filter. No brand deal (not yet). Here's {brief_subject}.",
        "I've tried every version of {brief_subject}. This one actually delivers.",
        "Before and after — {brief_subject} — and the numbers don't lie.",
    ],
    "emotional": [
        "This one hit different. Let me tell you about {brief_subject}.",
        "I wasn't prepared for how {brief_subject} would change things.",
        "If you're struggling with {audience_or_niche}, this is for you.",
        "The moment I discovered {brief_subject}, everything shifted.",
    ],
    "contrarian": [
        "Stop doing {brief_subject} the old way. Seriously.",
        "Everyone gets {brief_subject} wrong — including most experts.",
        "The popular advice on {brief_subject} is actually keeping you stuck.",
        "Unpopular opinion: {brief_subject} doesn't work the way you think.",
    ],
    "practical": [
        "Here's exactly how {brief_subject} works in 30 seconds.",
        "Save this. You'll want to come back to {brief_subject} later.",
        "Three things nobody tells you before trying {brief_subject}.",
        "If you're going to do {brief_subject}, do it this way.",
    ],
    "story_open_loop": [
        "My {story_connector} showed me {brief_subject} and I couldn't stop thinking about it.",
        "A year ago I had no idea {brief_subject} would end up here.",
        "It started with {brief_subject}. It ended with something I didn't expect.",
        "The strangest thing happened when I first tried {brief_subject}.",
    ],
    "monetization": [
        "This {brief_subject} paid for itself in {timeframe}.",
        "I'm making {outcome} with {brief_subject} — here's exactly how.",
        "If you haven't looked at {brief_subject} as an income stream, read this.",
        "{brief_subject} — the quiet money move most people overlook.",
    ],
}

# ---------------------------------------------------------------------------
# Section templates by content format
# Each format × 5 Viral Spine sections × 3 template options
# ---------------------------------------------------------------------------

_SECTION_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "affiliate_followup": {
        "Pattern Interrupt": [
            "You saw it go viral. Before you order — here's my full breakdown.",
            "Everyone's asking about {brief_subject}. Here's what the original video didn't show you.",
            "Before you spend a dollar on {brief_subject}, watch the next 30 seconds.",
        ],
        "Proof": [
            "I got mine {days_ago}. I tested it for real. Here's what I actually found.",
            "I was sceptical. Then I tried it. Here's the honest truth — no edits.",
            "Real talk — this is my unsponsored, unfiltered take on {brief_subject}.",
        ],
        "Demonstration / Teaching": [
            "Here's exactly how it works: {demo_or_idea}. Watch closely.",
            "This is the part the viral video didn't show you: {demo_or_idea}.",
            "Let me walk you through it step by step: {demo_or_idea}.",
        ],
        "Meaning": [
            "If you're into {audience_or_niche}, this is genuinely worth your time.",
            "Here's why this went viral and why it actually matters for {audience_or_niche}.",
            "This isn't just a gadget. For {audience_or_niche}, it's a real upgrade.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Comment {keyword} below and I'll send you the exact link I used.",
            "Link is in my bio. Don't sleep on this one.",
        ],
    },
    "product_demo": {
        "Pattern Interrupt": [
            "I've been using {brief_subject} for a month and I need to talk about it.",
            "This is {brief_subject} — and it does exactly what it claims.",
            "Watch this. {brief_subject} in action — no edits, no cuts.",
        ],
        "Proof": [
            "Here's the evidence: {demo_or_idea}. Consistent results every time.",
            "I've tested the competition. {brief_subject} wins on every single metric.",
            "Real use case, real results. This is what {brief_subject} actually does.",
        ],
        "Demonstration / Teaching": [
            "Step one: {demo_or_idea}. It really is that straightforward.",
            "Here's the part people always ask me about: {demo_or_idea}.",
            "Watch how {brief_subject} handles {demo_or_idea} — in real time.",
        ],
        "Meaning": [
            "For {audience_or_niche}, this solves a problem that's been ignored for too long.",
            "This is why {brief_subject} is worth every penny for {audience_or_niche}.",
            "The reason this matters: {content_goal_or_value}.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Link in bio to grab yours. I'll also answer any questions in the comments.",
            "Want to see more? Save this and follow for the full review series.",
        ],
    },
    "wellness_teaching": {
        "Pattern Interrupt": [
            "Most people approach {brief_subject} completely backwards.",
            "Here's the {brief_subject} truth that took me three years to learn.",
            "Stop ignoring {brief_subject}. Here's what it's actually doing to you.",
        ],
        "Proof": [
            "I've worked with {audience_or_niche} for years. Here's what actually works.",
            "The research backs this up — and my personal experience does too.",
            "Three months of testing {brief_subject}. These are the only results that matter.",
        ],
        "Demonstration / Teaching": [
            "Here's the exact method: {demo_or_idea}. Do this daily.",
            "The practice looks like this: {demo_or_idea}. Simple. Repeatable.",
            "Step one is the hardest: {demo_or_idea}. But it changes everything.",
        ],
        "Meaning": [
            "When you get {brief_subject} right, {content_goal_or_value} follows naturally.",
            "This matters because {audience_or_niche} deserve better than the generic advice.",
            "Your body and mind already know how to do this — you just need the right framework.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Save this post. Share it with someone who needs to hear it today.",
            "Follow for the full protocol — this is just part one.",
        ],
    },
    "personal_story": {
        "Pattern Interrupt": [
            "I almost didn't share this. But here's what happened with {brief_subject}.",
            "Six months ago I made a decision about {brief_subject}. This is the honest story.",
            "The thing nobody tells you when you're going through {brief_subject}.",
        ],
        "Proof": [
            "I'm not saying this to impress you. I'm saying it because it's true.",
            "I have the receipts. The timestamps. The screenshots. It happened.",
            "Ask anyone who was there. {brief_subject} changed the trajectory.",
        ],
        "Demonstration / Teaching": [
            "Here's exactly what I did: {demo_or_idea}. And why it worked.",
            "The turning point was when I tried {demo_or_idea} — everything shifted after that.",
            "What I learned from {brief_subject}: {demo_or_idea}.",
        ],
        "Meaning": [
            "I'm sharing this because I know {audience_or_niche} face the same thing.",
            "The point of this story isn't the outcome. It's what {brief_subject} taught me about myself.",
            "If {brief_subject} can happen for me, it can happen for you. That's the whole point.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Tell me in the comments — have you been through something similar?",
            "Follow if you want to see where this goes next.",
        ],
    },
    "controversial_take": {
        "Pattern Interrupt": [
            "Hot take: {brief_subject} is the one thing everyone in {audience_or_niche} gets wrong.",
            "I know this is going to upset some people. But {brief_subject} needs to be said.",
            "Unpopular opinion incoming. {brief_subject}. Here's why I believe it.",
        ],
        "Proof": [
            "Before you argue — here's the evidence: {demo_or_idea}.",
            "I didn't form this opinion overnight. Here's what changed my mind.",
            "The data, the experience, and the results all point to the same thing.",
        ],
        "Demonstration / Teaching": [
            "Here's the alternative approach that actually works: {demo_or_idea}.",
            "Instead of {brief_subject} the old way, try this: {demo_or_idea}.",
            "The counterintuitive truth is: {demo_or_idea}. Here's the breakdown.",
        ],
        "Meaning": [
            "This matters because the mainstream advice on {brief_subject} is actively holding {audience_or_niche} back.",
            "The stakes are higher than you think. {content_goal_or_value} is on the line.",
            "I'd rather say the uncomfortable thing than watch {audience_or_niche} stay stuck.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Agree or disagree — tell me in the comments. I read every one.",
            "Follow if you want more takes that the algorithm probably won't promote.",
        ],
    },
    "tutorial": {
        "Pattern Interrupt": [
            "Here's how to do {brief_subject} — the right way — in under a minute.",
            "I'm going to teach you {brief_subject} faster than any tutorial online.",
            "Stop making {brief_subject} harder than it is. This is all you need.",
        ],
        "Proof": [
            "I've done this hundreds of times. This method works every single time.",
            "My {audience_or_niche} students use this exact framework. The results speak for themselves.",
            "I tested every shortcut. This is the only one worth your time.",
        ],
        "Demonstration / Teaching": [
            "Step one: {demo_or_idea}. Step two follows naturally from there.",
            "The process: {demo_or_idea}. Follow this exactly and you won't need to Google it again.",
            "Watch closely: {demo_or_idea}. This is the step most people skip.",
        ],
        "Meaning": [
            "Once you know {brief_subject}, you'll wonder how you managed without it.",
            "This one skill saves {audience_or_niche} hours every single week.",
            "Mastering {brief_subject} is the highest-leverage thing you can do right now.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Save this so you have it when you need it. You will.",
            "Comment STEPS below for the written version with timestamps.",
        ],
    },
    "fundraising_story": {
        "Pattern Interrupt": [
            "This is {brief_subject}. And this story needs to be heard.",
            "I don't usually ask for anything. But {brief_subject} changed that.",
            "Meet {brief_subject}. One conversation. One decision. Everything changed.",
        ],
        "Proof": [
            "I've seen the impact firsthand. I've seen what happens when people show up.",
            "Every dollar raised so far has gone directly to {demo_or_idea}. No overhead. No spin.",
            "The numbers are real. The need is real. And this is the moment to act.",
        ],
        "Demonstration / Teaching": [
            "Here's exactly where the support goes: {demo_or_idea}. Tangible. Traceable.",
            "One contribution means {demo_or_idea}. That's the direct impact.",
            "Watch what happens when {brief_subject} gets the support it needs: {demo_or_idea}.",
        ],
        "Meaning": [
            "For {audience_or_niche}, this isn't abstract. This is someone's real life.",
            "The people we ignore the most are often the ones who need us the most.",
            "If not now, when? If not us, who? {brief_subject} is the reason.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Share this even if you can't give today. Reach matters as much as money right now.",
            "Link in bio. Every single contribution changes the outcome.",
        ],
    },
    "motivational_walkthrough": {
        "Pattern Interrupt": [
            "I need to show you exactly what {brief_subject} looks like when it works.",
            "This is what happens when {audience_or_niche} stop waiting and start moving.",
            "The version of you who already did {brief_subject} — let me introduce you.",
        ],
        "Proof": [
            "I've walked this exact path. Here's what no one told me at the start.",
            "Everyone who's done {brief_subject} said the same thing on the other side: 'I wish I'd started sooner.'",
            "The people in {audience_or_niche} who followed this system changed everything in under 90 days.",
        ],
        "Demonstration / Teaching": [
            "Here's the walkthrough: {demo_or_idea}. Do this today. Not tomorrow.",
            "The move is simple: {demo_or_idea}. The discipline is what separates the people who do from the people who watch.",
            "Step one, and the only step that matters today: {demo_or_idea}.",
        ],
        "Meaning": [
            "This isn't about motivation. It's about building a system that works even when you don't feel like it.",
            "{brief_subject} is how {audience_or_niche} reclaim the time and energy they've been handing to the wrong things.",
            "The difference between where you are and where you want to be is one decision. This is that decision.",
        ],
        "CTA": [
            "{cta_or_default}",
            "Save this and come back to it when you need the reminder.",
            "Comment READY below if you're starting today. I'll hold you to it.",
        ],
    },
}

# ---------------------------------------------------------------------------
# CTA templates by content format
# ---------------------------------------------------------------------------

_CTA_TEMPLATES: dict[str, list[CTAOption]] = {
    "affiliate_followup": [
        CTAOption("Comment {keyword} below and I'll drop the link.", "comment_keyword", ["tiktok", "instagram_reels", "clapper"]),
        CTAOption("Link in my bio — it's the first one.", "link_in_bio", ["instagram_reels", "youtube_shorts", "x"]),
        CTAOption("Save this video and check the pinned comment for the link.", "pinned_comment", ["tiktok", "instagram_reels"]),
    ],
    "product_demo": [
        CTAOption("Link in bio to grab yours.", "link_in_bio", ["instagram_reels", "youtube_shorts", "x"]),
        CTAOption("Comment DEMO below for the product link.", "comment_keyword", ["tiktok", "clapper"]),
        CTAOption("Save this review. You'll want to revisit it before you buy.", "save_for_later", ["instagram_reels", "youtube_shorts"]),
    ],
    "wellness_teaching": [
        CTAOption("Save this so you have it when you need it.", "save_for_later", ["instagram_reels", "tiktok", "clapper"]),
        CTAOption("Follow for the full protocol — this is part one of many.", "follow", ["tiktok", "instagram_reels", "youtube_shorts"]),
        CTAOption("Share this with someone in your life who needs to hear it.", "share", ["x", "instagram_reels", "clapper"]),
    ],
    "personal_story": [
        CTAOption("Tell me your version in the comments — I read every one.", "comment_engage", ["tiktok", "instagram_reels", "clapper"]),
        CTAOption("Follow to see what happened next.", "follow", ["tiktok", "youtube_shorts", "clapper"]),
        CTAOption("Share if this hit close to home.", "share", ["x", "instagram_reels"]),
    ],
    "controversial_take": [
        CTAOption("Agree or disagree — drop it in the comments.", "comment_engage", ["tiktok", "instagram_reels", "clapper", "x"]),
        CTAOption("Follow if you want more takes the algorithm won't push.", "follow", ["tiktok", "clapper"]),
        CTAOption("Share this with the person who needs to hear it.", "share", ["x", "instagram_reels"]),
    ],
    "tutorial": [
        CTAOption("Save this. You'll need it.", "save_for_later", ["instagram_reels", "tiktok", "youtube_shorts"]),
        CTAOption("Comment STEPS for the written version.", "comment_keyword", ["tiktok", "instagram_reels", "clapper"]),
        CTAOption("Follow for the next step in the series.", "follow", ["youtube_shorts", "tiktok"]),
    ],
    "fundraising_story": [
        CTAOption("Link in bio. Every contribution matters.", "link_in_bio", ["instagram_reels", "youtube_shorts", "x"]),
        CTAOption("Share this even if you can't give today — reach is everything right now.", "share", ["x", "instagram_reels", "tiktok", "clapper"]),
        CTAOption("Comment HELP below to show you're with us.", "comment_keyword", ["tiktok", "clapper"]),
    ],
    "motivational_walkthrough": [
        CTAOption("Comment READY below if you're starting today.", "comment_keyword", ["tiktok", "instagram_reels", "clapper"]),
        CTAOption("Save this for the days when you need the push.", "save_for_later", ["instagram_reels", "tiktok", "youtube_shorts"]),
        CTAOption("Follow — I post the next step every week.", "follow", ["tiktok", "youtube_shorts", "clapper"]),
    ],
}

# Fallback CTA for unknown formats
_DEFAULT_CTA_OPTIONS = [
    CTAOption("Follow for more content like this.", "follow", ["tiktok", "instagram_reels", "clapper"]),
    CTAOption("Save this and share it with someone who needs it.", "save_for_later", ["instagram_reels", "youtube_shorts"]),
    CTAOption("Drop a comment — what do you think?", "comment_engage", ["tiktok", "clapper", "x"]),
]

# ---------------------------------------------------------------------------
# Overlay caption templates  (timing slot → template options)
# ---------------------------------------------------------------------------

_OVERLAY_TIMING_SLOTS = [
    ("0–2s", "hook_echo", "Stop the scroll — mirror spoken hook"),
    ("3–6s", "proof_point", "Reinforce credibility"),
    ("7–20s", "demo_caption", "Annotate key action"),
    ("end", "cta_text", "Repeat CTA on screen"),
]

_OVERLAY_TEMPLATES: dict[str, list[str]] = {
    "hook_echo": [
        "{brief_subject}",
        "Wait — {brief_subject}?",
        "🔥 {brief_subject}",
    ],
    "proof_point": [
        "I tested this for real",
        "No brand deal. Honest review.",
        "Real results ↓",
    ],
    "demo_caption": [
        "Watch what happens here 👇",
        "This is the part everyone skips",
        "Step {step}: {demo_or_idea}",
    ],
    "cta_text": [
        "{cta_or_default}",
        "Comment {keyword} for the link 👇",
        "Save this post ↑",
    ],
}

# ---------------------------------------------------------------------------
# Context-aware hook / section / CTA builders (Phase 12.1)
# ---------------------------------------------------------------------------

def _hooks_for_context(
    norm: NormalizedIdeaContext,
    *,
    seed: int,
    n_hooks: int = 5,
) -> list[tuple[str, str, str]]:
    """
    Return list of (style, text, reason) hook candidates from normalized context.
    """
    s = norm.clean_subject
    pn = norm.product_name or s
    pt = norm.product_type or s
    b1 = norm.key_benefits[0] if norm.key_benefits else ""
    b2 = norm.key_benefits[1] if len(norm.key_benefits) > 1 else ""
    proof = norm.proof_point
    mech = norm.mechanism
    fmt = norm.content_format

    candidates: list[tuple[str, str, str]] = []

    if fmt == "affiliate_followup":
        if proof:
            candidates.append((
                "proof_based",
                f"This {pn} got attention because people thought it was fake.",
                "Borrow viral proof without inventing view counts.",
            ))
        candidates.append((
            "shock",
            f"This little {pt} looks fake until you see it work.",
            "Pattern interrupt with scepticism.",
        ))
        if b1 and b2:
            candidates.append((
                "practical",
                f"{b1.capitalize()}. {b2.capitalize()}.",
                "Lead with concrete benefits.",
            ))
        elif b1:
            candidates.append(("practical", f"{b1.capitalize()}.", "Single sharp benefit."))
        candidates.append((
            "curiosity",
            f"People kept asking where to buy this {s}.",
            "Buyer-interest without claiming a live code.",
        ))
        if not norm.claims_official_link:
            candidates.append((
                "story_open_loop",
                f"I'm trying to get the official link for this {s}.",
                "Honest uncertainty about link status.",
            ))
        else:
            candidates.append((
                "story_open_loop",
                f"Pinned comment has the link people asked for.",
                "Uses brief-confirmed link language.",
            ))
        if mech:
            candidates.append((
                "curiosity",
                f"It {mech.rstrip('.')}.",
                "Mechanism-led curiosity.",
            ))

    elif fmt == "product_demo":
        candidates.extend([
            ("practical", f"Watch how {s} works in under 30 seconds.", "Direct demonstration promise."),
            ("proof_based", f"Here's {s} in action — no cuts, no fluff.", "Show-don't-tell proof."),
            ("curiosity", f"Most people skip this step with {pn}.", "Teaching gap hook."),
        ])
        if mech:
            candidates.append(("practical", f"Quick demo: {mech.rstrip('.')}.", "Mechanism in demo hook."))
        if norm.claims_testing_duration:
            candidates.append((
                "proof_based",
                f"I've had time with {s} — here's what actually holds up.",
                "Duration claim allowed by brief.",
            ))
        else:
            candidates.append((
                "proof_based",
                f"First impressions of {s} — what stood out immediately.",
                "Soft proof without invented timeline.",
            ))

    elif fmt == "fundraising_story":
        candidates.extend([
            ("emotional", f"This story about {s} needs more eyes.", "Human-first framing."),
            ("story_open_loop", f"We almost lost this — then the community showed up.", "Open loop without product CTA tone."),
            ("proof_based", f"Every share puts {s} in front of someone who can help.", "Reach as proof of impact."),
            ("practical", "One donation. One share. Both matter today.", "Dual low-friction actions."),
        ])

    elif fmt == "wellness_teaching":
        candidates.extend([
            ("practical", f"A simple practice with {s} you can try today.", "Teaching-forward."),
            ("emotional", f"If your body feels wired, this {pt} approach may help.", "Relatable wellness entry."),
            ("curiosity", f"The part most people rush in {s}.", "Curiosity on technique."),
        ])
        if mech:
            candidates.append(("practical", mech.capitalize() + ".", "Mechanism as teaching hook."))

    elif fmt == "tutorial":
        candidates.extend([
            ("practical", f"How to use {s} — step by step.", "Clear tutorial promise."),
            ("curiosity", f"The mistake everyone makes with {s}.", "Error-correction hook."),
            ("proof_based", f"Follow along — you'll have this working by the end.", "Outcome proof."),
        ])

    elif fmt == "personal_story":
        candidates.extend([
            ("story_open_loop", f"I didn't expect {s} to go this way.", "Personal open loop."),
            ("emotional", f"This moment with {s} still stays with me.", "Emotional anchor."),
            ("proof_based", f"Here's what actually happened — no polish.", "Authenticity proof."),
        ])

    elif fmt == "controversial_take":
        candidates.extend([
            ("contrarian", f"Hot take: most advice about {s} is backwards.", "Contrarian frame."),
            ("curiosity", f"Why {s} works differently than you've been told.", "Reframe curiosity."),
            ("shock", f"I stopped doing {s} the popular way — here's why.", "Pattern interrupt."),
        ])

    elif fmt == "motivational_walkthrough":
        candidates.extend([
            ("practical", f"One move with {s} you can do before the video ends.", "Embodied action."),
            ("emotional", f"You don't need motivation for {s} — you need a system.", "Systems over hype."),
            ("story_open_loop", f"I almost skipped this step. Glad I didn't.", "Relatable resistance."),
        ])

    else:
        candidates.append((
            "curiosity",
            f"Here's why {s} is worth 30 seconds of your time.",
            "Generic clean-subject hook.",
        ))

    # Dedupe by text, cap length
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for style, text, reason in candidates:
        key = text.lower()
        if key not in seen:
            seen.add(key)
            unique.append((style, text, reason))

    if not unique:
        unique.append(("curiosity", sanitize_hook("", norm), "Safe fallback."))

    # Deterministic pick order with seed
    ordered = sorted(unique, key=lambda x: (x[0], x[1]))
    result: list[tuple[str, str, str]] = []
    for i in range(min(n_hooks, len(ordered))):
        idx = (seed + i * 7) % len(ordered)
        result.append(ordered[idx])
    # Fill if needed (bounded — avoid infinite loop when all candidates dedupe)
    i = 0
    max_attempts = max(n_hooks * 3, len(ordered) * 2)
    while len(result) < n_hooks and ordered and i < max_attempts:
        style, text, reason = ordered[(seed + i) % len(ordered)]
        if text.lower() not in {r[1].lower() for r in result}:
            result.append((style, text, reason))
        i += 1
    return result[:n_hooks]


def _section_text_for_context(
    norm: NormalizedIdeaContext,
    section_name: str,
    *,
    seed: int,
    offset: int,
    cta_text: str,
) -> str:
    """Build one Viral Spine section from normalized context (truth-aware)."""
    s = norm.clean_subject
    pn = norm.product_name or s
    aud = norm.audience_phrase
    proof = norm.proof_point
    mech = norm.mechanism
    fmt = norm.content_format
    kw = norm.cta_keyword

    pools: dict[str, list[str]] = {}

    if fmt == "affiliate_followup":
        pools = {
            "Pattern Interrupt": [
                "You saw the clip blow up. Before you buy anything — watch this.",
                f"Everyone's asking about {s}. Here's what the viral video didn't show.",
            ],
            "Proof": [
                f"{proof.capitalize()} — so people had reason to pay attention." if proof
                else f"Real {norm.scene_context} — not a studio mock-up.",
                "I'm not sponsored yet — this is my honest follow-up.",
            ],
            "Demonstration / Teaching": [
                f"Here's how it actually works: {mech.rstrip('.')}." if mech
                else f"Watch the core move with {pn}.",
                f"This is the part people replay: {norm.scene_context}.",
            ],
            "Meaning": [
                f"If you're in {aud}, this solves a real annoyance.",
                f"It's not hype — {s} is practical gear when you see it work.",
            ],
            "CTA": [
                cta_text,
                f"Comment {kw} and I'll send the link when it's ready.",
                "Check the pinned comment — link will be marked if it's affiliate.",
            ],
        }
    elif fmt == "fundraising_story":
        pools = {
            "Pattern Interrupt": [f"This is about {s} — and it matters right now."],
            "Proof": ["I've seen what happens when people show up."],
            "Demonstration / Teaching": ["Here's exactly where support goes."],
            "Meaning": [f"For {aud}, one action changes someone's week."],
            "CTA": [
                cta_text or "Share this — reach helps as much as money today.",
                "Link in bio if you're ready to give.",
            ],
        }
    elif fmt == "wellness_teaching":
        pools = {
            "Pattern Interrupt": [f"Try this with {s} before you scroll away."],
            "Proof": ["Short daily practice beats one perfect session."],
            "Demonstration / Teaching": [
                mech.capitalize() + "." if mech else f"Walk through {s} slowly with me.",
            ],
            "Meaning": [f"Your nervous system responds when {aud} commit to the reps."],
            "CTA": [cta_text or "Save this and practice it tonight."],
        }
    elif fmt == "product_demo":
        pools = {
            "Pattern Interrupt": [f"Quick look at {s} — does it do what it claims?"],
            "Proof": [
                "I've had time with this — here's what holds up." if norm.claims_testing_duration
                else f"First honest look at {pn} on camera.",
            ],
            "Demonstration / Teaching": [
                f"Step by step: {mech.rstrip('.')}." if mech else f"Watch {pn} in use.",
            ],
            "Meaning": [f"Worth it for {aud} if you need this daily."],
            "CTA": [cta_text or f"Comment {kw} for questions."],
        }
    else:
        # Generic pools using clean subject only
        pools = {
            "Pattern Interrupt": [f"Let's talk about {s} — quickly."],
            "Proof": [proof.capitalize() + "." if proof else "Here's what I actually saw."],
            "Demonstration / Teaching": [mech.capitalize() + "." if mech else f"The core of {s}."],
            "Meaning": [f"This matters for {aud}."],
            "CTA": [cta_text or "Follow for part two."],
        }

    options = pools.get(section_name, [f"[{section_name}]"])
    return _pick(options, seed=seed, offset=offset) or options[0]


def _cta_options_for_context(
    norm: NormalizedIdeaContext,
    cta: str,
    platforms: list[str] | None,
) -> list[CTAOption]:
    """Truth-aware CTA options per content format."""
    plats = list(platforms or ["tiktok", "instagram_reels", "clapper"])
    kw = norm.cta_keyword
    options: list[CTAOption] = []

    if cta.strip():
        options.append(CTAOption(cta.strip(), "custom", plats))

    fmt = norm.content_format
    if fmt == "affiliate_followup":
        options.extend([
            CTAOption(
                f"Comment {kw} and I'll send you the link when it's ready.",
                "comment_keyword",
                ["tiktok", "clapper"],
            ),
            CTAOption(
                "Check the pinned comment for the official link.",
                "pinned_comment",
                ["tiktok", "instagram_reels"],
            ),
            CTAOption(
                "If I get a code from the company, I'll pin it here.",
                "comment_engage",
                plats,
            ),
        ])
        if not norm.claims_affiliate_approved:
            options.append(CTAOption(
                "Affiliate link will be clearly marked if they approve one.",
                "disclosure",
                plats,
            ))
    elif fmt == "fundraising_story":
        options.extend([
            CTAOption("Share this — reach helps the cause today.", "share", plats),
            CTAOption("Link in bio to donate if you can.", "link_in_bio", ["instagram_reels", "youtube_shorts"]),
            CTAOption(f"Comment {kw} to show you're with us.", "comment_keyword", ["tiktok", "clapper"]),
        ])
    elif fmt == "wellness_teaching":
        options.extend([
            CTAOption("Save this and try the practice tonight.", "save_for_later", plats),
            CTAOption("Follow for the full guided series.", "follow", plats),
        ])
    elif fmt == "product_demo":
        options.extend([
            CTAOption(f"Comment {kw} if you want the product link.", "comment_keyword", ["tiktok", "clapper"]),
            CTAOption("Save before you buy — compare later.", "save_for_later", plats),
        ])
    else:
        options.extend(list(_CTA_TEMPLATES.get(fmt, _DEFAULT_CTA_OPTIONS)))

    # Dedupe by text
    seen: set[str] = set()
    out: list[CTAOption] = []
    for o in options:
        if o.text.lower() not in seen:
            seen.add(o.text.lower())
            out.append(o)
    return out[:4]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _compute_seed(idea: str, audience: str = "") -> int:
    """Deterministic DJB2 hash → always same output for same input."""
    h = 5381
    for c in (idea + audience):
        h = ((h << 5) + h + ord(c)) & 0x7FFFFFFF
    return h


def _pick(items: list, seed: int, offset: int = 0) -> Any:
    """Pick deterministically from a list using seed."""
    if not items:
        return None
    return items[(seed + offset) % len(items)]


def _fill(template: str, **ctx: str) -> str:
    """Fill a template string; missing keys become [key]."""
    class _Safe(defaultdict):
        def __missing__(self, key: str) -> str:
            return f"[{key}]"
    try:
        return template.format_map(_Safe(str, ctx))
    except Exception:
        return template


def _brief_subject(idea: str, words: int = 6) -> str:
    """Legacy helper — prefer extract_clean_subject / normalize_idea_context."""
    return extract_clean_subject(idea)


def _cta_keyword(cta: str, content_format: str) -> str:
    if cta:
        matches = re.findall(r'\b[A-Z]{3,}\b', cta)
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


def _default_audience(content_format: str) -> str:
    return {
        "affiliate_followup": "people who follow viral product content",
        "product_demo": "people looking for honest reviews",
        "wellness_teaching": "people investing in their health and energy",
        "personal_story": "people who've been through something similar",
        "controversial_take": "people tired of generic advice",
        "tutorial": "people who want to learn faster",
        "fundraising_story": "people who believe in community support",
        "motivational_walkthrough": "people ready to make a change",
    }.get(content_format, "your audience")


def _default_goal(content_format: str) -> str:
    return {
        "affiliate_followup": "drive affiliate clicks and trusted recommendations",
        "product_demo": "build product awareness and drive purchase intent",
        "wellness_teaching": "educate and build authority in wellness",
        "personal_story": "create connection and earn followers through authenticity",
        "controversial_take": "generate discussion and grow engaged following",
        "tutorial": "provide practical value and establish expertise",
        "fundraising_story": "drive donations and shares for the cause",
        "motivational_walkthrough": "inspire action and grow a committed community",
    }.get(content_format, "create engaging content")


def _make_ctx(
    idea: str,
    audience: str,
    offer: str,
    cta: str,
    tone: str,
    content_goal: str,
    content_format: str,
    seed: int,
    norm: NormalizedIdeaContext | None = None,
) -> dict[str, str]:
    """Build template context from normalized idea (Phase 12.1)."""
    if norm is None:
        norm = normalize_idea_context(
            idea,
            audience=audience,
            content_goal=content_goal,
            offer=offer,
            cta=cta,
            content_format=content_format,
        )
    ctx = norm.to_template_ctx()
    goal = content_goal or _default_goal(content_format)
    cta_text = cta or f"Follow for more {content_format.replace('_', ' ')} content."
    ctx.update({
        "idea": idea[:100],
        "brief_idea": idea[:80],
        "tone": tone,
        "content_goal": goal,
        "content_goal_or_value": goal,
        "cta": cta_text,
        "cta_or_default": cta_text,
        "offer": offer or norm.clean_subject,
        "offer_or_thing": offer or norm.product_name or "this",
        "demo_or_idea": offer or norm.mechanism or norm.clean_subject,
        "step": "one",
    })
    if norm.claims_testing_duration:
        days_options = ["after a few days", "this week", "recently"]
        ctx["days_ago"] = _pick(days_options, seed=seed, offset=3)
    else:
        ctx["days_ago"] = "recently"
    return ctx


# ---------------------------------------------------------------------------
# Core generation functions
# ---------------------------------------------------------------------------

def generate_hook_bank(
    idea: str,
    *,
    audience: str = "",
    tone: str = "engaging",
    content_format: str = "product_demo",
    offer: str = "",
    cta: str = "",
    platforms: list[str] | None = None,
    n_hooks: int = 5,
    seed: int | None = None,
) -> list[HookOption]:
    """
    Generate a diverse hook bank for the given idea.

    Returns ``n_hooks`` hooks with at least one per priority style for the format.
    """
    _seed = seed if seed is not None else _compute_seed(idea, audience)
    norm = normalize_idea_context(
        idea,
        audience=audience,
        offer=offer,
        cta=cta,
        content_format=content_format,
    )
    profile = _FORMAT_PROFILES.get(content_format, _FORMAT_PROFILES["product_demo"])
    priority_styles: list[str] = profile["hook_styles"]

    raw_hooks = _hooks_for_context(norm, seed=_seed, n_hooks=max(n_hooks, 6))
    hooks: list[HookOption] = []
    for i, (style, text, reason) in enumerate(raw_hooks[:n_hooks]):
        clean_text = sanitize_hook(text, norm)
        score = 0.9 - (i * 0.04) if style in priority_styles else 0.75 - (i * 0.03)
        hooks.append(HookOption(
            text=clean_text,
            style=style,
            reason=reason,
            score=round(max(0.4, score), 2),
        ))

    return hooks[:n_hooks]


def _build_spine_sections(
    idea: str,
    audience: str,
    offer: str,
    cta: str,
    tone: str,
    content_goal: str,
    content_format: str,
    seed: int,
    offset: int = 0,
) -> list[ScriptSection]:
    """Build the 5-section Viral Spine for a given format."""
    norm = normalize_idea_context(
        idea,
        audience=audience,
        content_goal=content_goal,
        offer=offer,
        cta=cta,
        content_format=content_format,
    )
    cta_text = cta or f"Follow for more {content_format.replace('_', ' ')} content."

    spine_purposes = {
        "Pattern Interrupt": "Stop the scroll — grab immediate attention",
        "Proof": "Establish credibility and trust",
        "Demonstration / Teaching": "Deliver the core value",
        "Meaning": "Create emotional resonance — explain why it matters",
        "CTA": "Single, clear next action",
    }

    sections: list[ScriptSection] = []
    for section_offset, name in enumerate(
        ["Pattern Interrupt", "Proof", "Demonstration / Teaching", "Meaning", "CTA"]
    ):
        text = _section_text_for_context(
            norm, name, seed=seed, offset=offset + section_offset, cta_text=cta_text,
        )
        sections.append(ScriptSection(
            name=name,
            text=text,
            purpose=spine_purposes.get(name, ""),
        ))

    return sections


def generate_short_form_script(
    idea: str,
    *,
    audience: str = "",
    tone: str = "engaging",
    content_goal: str = "",
    offer: str = "",
    cta: str = "",
    content_format: str = "product_demo",
    platforms: list[str] | None = None,
    duration: str = "30s",
    seed: int | None = None,
    variant_offset: int = 0,
) -> ScriptVariant:
    """Generate a single ScriptVariant following the Viral Spine."""
    _seed = seed if seed is not None else _compute_seed(idea, audience)
    target_platforms = list(platforms or ["tiktok", "instagram_reels", "clapper"])
    sections = _build_spine_sections(
        idea, audience, offer, cta, tone, content_goal,
        content_format, _seed, offset=variant_offset,
    )
    full_text = "\n\n".join(s.text for s in sections)
    profile = _FORMAT_PROFILES.get(content_format, {})
    notes = profile.get("notes", [])
    title_suffixes = ["— Viral Spine", "— Hook Version", "— Story Version", "— Short Cut"]
    norm = normalize_idea_context(
        idea, audience=audience, content_goal=content_goal,
        offer=offer, cta=cta, content_format=content_format,
    )
    title = norm.clean_subject + " " + _pick(title_suffixes, seed=_seed, offset=variant_offset)

    return ScriptVariant(
        title=title,
        duration_target=duration,
        platform_fit=target_platforms,
        sections=sections,
        full_text=full_text,
    )


def generate_overlay_captions(
    idea: str,
    hooks: list[HookOption],
    primary_script: ScriptVariant,
    *,
    cta: str = "",
    content_format: str = "product_demo",
    seed: int | None = None,
    n_captions: int = 4,
) -> list[OverlayCaption]:
    """Generate on-screen text overlay captions keyed to timing slots."""
    _seed = seed if seed is not None else _compute_seed(idea)
    norm = normalize_idea_context(idea, cta=cta, content_format=content_format)
    cta_text = cta or "Follow for more."
    subj = norm.product_name or norm.clean_subject

    captions: list[OverlayCaption] = []
    for i, (timing, slot_key, purpose) in enumerate(_OVERLAY_TIMING_SLOTS[:n_captions]):
        if slot_key == "hook_echo" and hooks:
            text = hooks[0].text[:60]
        elif slot_key == "proof_point":
            text = (
                norm.proof_point.capitalize()[:50] if norm.proof_point
                else "Honest follow-up ↓"
            )
        elif slot_key == "demo_caption":
            text = (norm.key_benefits[0][:40].capitalize() if norm.key_benefits
                    else f"Watch {subj}")
        elif slot_key == "cta_text":
            text = cta_text[:50]
        else:
            text = subj[:40]
        captions.append(OverlayCaption(text=text, timing_hint=timing, purpose=purpose))

    return captions


def generate_cta_options(
    cta: str,
    content_format: str,
    platforms: list[str] | None = None,
    *,
    idea: str = "",
    audience: str = "",
    offer: str = "",
) -> list[CTAOption]:
    """
    Return a list of platform-appropriate, truth-aware CTA options.
    """
    norm = normalize_idea_context(
        idea or "content",
        audience=audience,
        offer=offer,
        cta=cta,
        content_format=content_format,
    )
    return _cta_options_for_context(norm, cta, platforms)


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

def _extract_json_from_markdown(text: str) -> str | None:
    """Extract JSON from a markdown ```json ... ``` code block."""
    pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return None


def _extract_json_object(text: str) -> str | None:
    """Find the first JSON-looking object { ... } in the text."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_llm_json_response(raw: str) -> dict | None:
    """
    Tolerant JSON parser for local LLM output.
    Tries 4 strategies before giving up.
    """
    candidates: list[str | None] = [
        raw,
        _extract_json_from_markdown(raw),
        _extract_json_object(raw),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _build_package_from_llm_data(
    data: dict,
    *,
    idea: str,
    job_id: str,
    audience: str,
    tone: str,
    content_goal: str,
    offer: str,
    content_format: str,
    platforms: list[str],
    backend: str,
    model: str,
    seed: int,
) -> ScriptPackage:
    """Convert a parsed LLM JSON dict into a ScriptPackage."""
    # Hooks
    hooks: list[HookOption] = []
    for h in data.get("hooks", []):
        if isinstance(h, dict) and h.get("text"):
            hooks.append(HookOption(
                text=str(h.get("text", "")),
                style=str(h.get("style", "curiosity")),
                reason=str(h.get("reason", "")),
                score=float(h.get("score", 0.8)),
            ))

    def _parse_sections(raw_sections: list) -> list[ScriptSection]:
        sections = []
        for s in raw_sections:
            if isinstance(s, dict) and s.get("text"):
                sections.append(ScriptSection(
                    name=str(s.get("name", "Section")),
                    text=str(s.get("text", "")),
                    purpose=str(s.get("purpose", "")),
                ))
        return sections

    def _parse_variant(raw: dict | None, title_fallback: str) -> ScriptVariant:
        if not raw or not isinstance(raw, dict):
            return ScriptVariant(title=title_fallback)
        secs = _parse_sections(raw.get("sections", []))
        full = str(raw.get("full_text", "") or "\n\n".join(s.text for s in secs))
        return ScriptVariant(
            title=str(raw.get("title", title_fallback)),
            duration_target=str(raw.get("duration_target", "30s")),
            platform_fit=list(raw.get("platform_fit", platforms)),
            sections=secs,
            full_text=full,
        )

    primary = _parse_variant(data.get("primary_script"), _brief_subject(idea))
    alts = [_parse_variant(a, f"Variant {i+1}") for i, a in enumerate(data.get("alternate_scripts", []))]

    overlays: list[OverlayCaption] = []
    for c in data.get("overlay_captions", []):
        if isinstance(c, dict) and c.get("text"):
            overlays.append(OverlayCaption(
                text=str(c.get("text", "")),
                timing_hint=str(c.get("timing_hint", "")),
                purpose=str(c.get("purpose", "")),
            ))

    ctas: list[CTAOption] = []
    for c in data.get("cta_options", []):
        if isinstance(c, dict) and c.get("text"):
            ctas.append(CTAOption(
                text=str(c.get("text", "")),
                type=str(c.get("type", "")),
                platform_fit=list(c.get("platform_fit", [])),
            ))

    # Fill in missing required fields with template fallback
    if not hooks:
        hooks = generate_hook_bank(idea, audience=audience, content_format=content_format,
                                    offer=offer, cta="", seed=seed)
    if not primary.sections:
        primary = generate_short_form_script(idea, audience=audience, tone=tone,
                                              content_goal=content_goal, offer=offer,
                                              content_format=content_format, seed=seed)
    if not overlays:
        overlays = generate_overlay_captions(idea, hooks, primary, content_format=content_format, seed=seed)
    if not ctas:
        ctas = generate_cta_options(
            "", content_format, platforms, idea=idea, audience=audience, offer=offer,
        )

    return ScriptPackage(
        job_id=job_id,
        idea=idea,
        audience=audience,
        tone=tone,
        content_goal=content_goal,
        offer=offer,
        content_format=content_format,
        hooks=hooks,
        primary_script=primary,
        alternate_scripts=alts,
        overlay_captions=overlays,
        cta_options=ctas,
        notes=list(data.get("notes", [])),
        status=ScriptStatus.COMPLETE,
        script_source=ScriptSource.LOCAL_LLM,
        llm_backend=backend,
        llm_model=model,
    )


# ---------------------------------------------------------------------------
# Deterministic template package
# ---------------------------------------------------------------------------

def _generate_template_package(
    idea: str,
    *,
    job_id: str,
    audience: str,
    tone: str,
    content_goal: str,
    offer: str,
    cta: str,
    content_format: str,
    platforms: list[str],
    fallback_reason: str | None = None,
    seed: int | None = None,
) -> ScriptPackage:
    _seed = seed if seed is not None else _compute_seed(idea, audience)

    hooks = generate_hook_bank(
        idea, audience=audience, tone=tone, content_format=content_format,
        offer=offer, cta=cta, platforms=platforms, n_hooks=5, seed=_seed,
    )
    primary = generate_short_form_script(
        idea, audience=audience, tone=tone, content_goal=content_goal,
        offer=offer, cta=cta, content_format=content_format,
        platforms=platforms, duration="30s", seed=_seed, variant_offset=0,
    )
    alternate = generate_short_form_script(
        idea, audience=audience, tone=tone, content_goal=content_goal,
        offer=offer, cta=cta, content_format=content_format,
        platforms=platforms, duration="15s", seed=_seed, variant_offset=10,
    )
    overlays = generate_overlay_captions(
        idea, hooks, primary, cta=cta, content_format=content_format, seed=_seed,
    )
    cta_opts = generate_cta_options(
        cta, content_format, platforms, idea=idea, audience=audience, offer=offer,
    )
    profile = _FORMAT_PROFILES.get(content_format, {})
    notes = list(profile.get("notes", []))

    return ScriptPackage(
        job_id=job_id,
        idea=idea,
        audience=audience,
        tone=tone,
        content_goal=content_goal,
        offer=offer,
        content_format=content_format,
        hooks=hooks,
        primary_script=primary,
        alternate_scripts=[alternate],
        overlay_captions=overlays,
        cta_options=cta_opts,
        notes=notes,
        status=ScriptStatus.COMPLETE,
        script_source=ScriptSource.TEMPLATE_FALLBACK,
        llm_backend=None,
        llm_model=None,
        fallback_reason=fallback_reason,
    )


# ---------------------------------------------------------------------------
# Local LLM integration (lazy import to stay import-safe)
# ---------------------------------------------------------------------------

def _try_local_llm_generation(
    idea: str,
    *,
    job_id: str,
    audience: str,
    tone: str,
    content_goal: str,
    offer: str,
    cta: str,
    content_format: str,
    platforms: list[str],
    seed: int,
    llm_config: dict | None,
) -> ScriptPackage | None:
    """
    Attempt generation via local LLM.

    Returns ScriptPackage on success, None if LLM is unavailable or output
    cannot be parsed.
    """
    try:
        from genesis.integrations.local_llm_provider import (
            build_social_script_prompt,
            generate_local_text,
            local_llm_ready,
            load_local_llm_config,
        )
        cfg = dict(llm_config if llm_config is not None else load_local_llm_config())
        ready, reason = local_llm_ready(cfg)
        if not ready:
            logger.debug("local LLM not ready: %s", reason)
            return None
        # Cap wait so offline endpoints fail fast and tests/workflows do not stall
        cfg["timeout_seconds"] = min(int(cfg.get("timeout_seconds", 120)), 8)

        prompt = build_social_script_prompt(
            idea=idea, audience=audience, tone=tone,
            content_goal=content_goal, offer=offer, cta=cta,
            content_format=content_format, platforms=platforms,
        )
        response = generate_local_text(prompt, config=cfg)
        if not response.get("success"):
            logger.warning("local LLM call failed: %s", response.get("error", "unknown"))
            return None

        raw_text = response.get("text", "")
        data = _parse_llm_json_response(raw_text)
        if data is None:
            logger.warning("local LLM output could not be parsed as JSON — using template fallback")
            return None

        pkg = _build_package_from_llm_data(
            data,
            idea=idea, job_id=job_id, audience=audience, tone=tone,
            content_goal=content_goal, offer=offer, content_format=content_format,
            platforms=platforms,
            backend=str(cfg.get("backend", "unknown")),
            model=str(cfg.get("model", "unknown")),
            seed=seed,
        )
        logger.info("local LLM script generated for job %s", job_id)
        return pkg

    except Exception as exc:  # noqa: BLE001
        logger.warning("local LLM generation exception: %s — falling back to template", exc)
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_script_package(
    idea: str,
    *,
    job_id: str | None = None,
    audience: str = "",
    tone: str = "engaging",
    content_goal: str = "",
    offer: str = "",
    cta: str = "",
    content_format: str = "product_demo",
    platforms: list[str] | None = None,
    llm_config: dict | None = None,
) -> ScriptPackage:
    """
    Generate a complete ScriptPackage for the given idea.

    Tries local LLM first (if configured and reachable).
    Falls back to deterministic Viral Spine templates on any failure.

    Args:
        idea:           Core idea or topic.
        job_id:         Unique run ID; auto-generated if omitted.
        audience:       Target audience description.
        tone:           Tone of voice.
        content_goal:   e.g. "affiliate follow-up", "awareness".
        offer:          Product, service, or value proposition.
        cta:            Call-to-action text (include keyword in ALL_CAPS for comments).
        content_format: One of CONTENT_FORMATS.
        platforms:      Target platform list.
        llm_config:     Override local LLM config dict (useful in tests).

    Returns:
        ScriptPackage with hooks, primary script, alternate script,
        overlay captions, and CTA options.
    """
    run_id = job_id or uuid.uuid4().hex[:12]
    fmt = content_format if content_format in CONTENT_FORMATS else "product_demo"
    target_platforms = list(platforms or ["tiktok", "instagram_reels", "clapper", "youtube_shorts", "x"])
    _seed = _compute_seed(idea, audience)

    # Try local LLM
    llm_pkg = _try_local_llm_generation(
        idea, job_id=run_id, audience=audience, tone=tone,
        content_goal=content_goal, offer=offer, cta=cta,
        content_format=fmt, platforms=target_platforms,
        seed=_seed, llm_config=llm_config,
    )
    if llm_pkg is not None:
        return llm_pkg

    # Deterministic fallback
    return _generate_template_package(
        idea, job_id=run_id, audience=audience, tone=tone,
        content_goal=content_goal, offer=offer, cta=cta,
        content_format=fmt, platforms=target_platforms,
        seed=_seed,
    )
