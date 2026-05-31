"""Genesis Studio — Project templates providing content defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectTemplate:
    name: str
    content_format: str
    audience: str
    content_goal: str
    tone: str
    cta_style: str
    brand_preset: str
    platform_defaults: list[str]
    music_style: str
    disclosure_expectation: str
    suggested_filenames: list[str]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content_format": self.content_format,
            "audience": self.audience,
            "content_goal": self.content_goal,
            "tone": self.tone,
            "cta_style": self.cta_style,
            "brand_preset": self.brand_preset,
            "platform_defaults": self.platform_defaults,
            "music_style": self.music_style,
            "disclosure_expectation": self.disclosure_expectation,
            "suggested_filenames": self.suggested_filenames,
            "notes": self.notes,
        }


TEMPLATES: dict[str, ProjectTemplate] = {
    "affiliate_product": ProjectTemplate(
        name="affiliate_product",
        content_format="affiliate_followup",
        audience="buyers, gadget fans, deal seekers",
        content_goal="affiliate follow-up",
        tone="curious, practical, viral",
        cta_style="Comment keyword / check pinned link",
        brand_preset="bold_viral",
        platform_defaults=["tiktok", "instagram_reels", "clapper"],
        music_style="upbeat light energy",
        disclosure_expectation="affiliate-safe: mark clearly when approved",
        suggested_filenames=[
            "product-closeup.mp4", "demo.mp4", "result-shot.mp4",
            "proof-comments.mp4", "girlfriend-demo.mp4",
        ],
        notes="Affiliate follow-up. Use hook-first structure. Include disclosure.",
    ),
    "product_demo": ProjectTemplate(
        name="product_demo",
        content_format="product_demo",
        audience="general buyers, curious viewers",
        content_goal="product demonstration",
        tone="enthusiastic, direct",
        cta_style="Link in bio / comment DEMO",
        brand_preset="bold_viral",
        platform_defaults=["tiktok", "instagram_reels", "youtube_shorts"],
        music_style="energetic background",
        disclosure_expectation="paid partnership if sponsored",
        suggested_filenames=[
            "product-closeup.mp4", "unboxing.mp4", "demo.mp4",
            "reaction.mp4", "cta-end.mp4",
        ],
    ),
    "wellness_teaching": ProjectTemplate(
        name="wellness_teaching",
        content_format="wellness_teaching",
        audience="wellness seekers, meditation practitioners, breathwork students",
        content_goal="educational wellness content",
        tone="calm, grounded, supportive",
        cta_style="Save this and try it",
        brand_preset="wellness_soft",
        platform_defaults=["instagram_reels", "tiktok", "youtube_shorts"],
        music_style="calm ambient or no music",
        disclosure_expectation="educational note when appropriate; no medical claims",
        suggested_filenames=[
            "talking-head.mp4", "practice-demo.mp4", "calm-broll.mp4",
            "sound-bowl-closeup.mp4", "breathwork.mp4",
        ],
        notes="No solar/lighter content. Avoid medical claims.",
    ),
    "fundraising_story": ProjectTemplate(
        name="fundraising_story",
        content_format="fundraising_story",
        audience="community supporters, empathetic viewers",
        content_goal="awareness and donation support",
        tone="honest, heartfelt, respectful",
        cta_style="Support / donate / share",
        brand_preset="clean_creator",
        platform_defaults=["tiktok", "instagram_reels", "clapper"],
        music_style="gentle emotional",
        disclosure_expectation="fundraising transparency required — no fake donation claims",
        suggested_filenames=[
            "context.mp4", "cause-broll.mp4", "support-cta.mp4",
            "story-clip.mp4",
        ],
        notes="Include truthful fundraising disclosure. Do not imply guaranteed donations.",
    ),
    "tutorial": ProjectTemplate(
        name="tutorial",
        content_format="tutorial",
        audience="learners, how-to seekers",
        content_goal="teach a skill or process",
        tone="clear, helpful, step-by-step",
        cta_style="Save / follow for more",
        brand_preset="minimal_white",
        platform_defaults=["youtube_shorts", "tiktok", "instagram_reels"],
        music_style="light background or silent",
        disclosure_expectation="none unless sponsored",
        suggested_filenames=[
            "step-01.mp4", "step-02.mp4", "step-03.mp4",
            "result.mp4", "talking-head.mp4",
        ],
    ),
    "motivational_walkthrough": ProjectTemplate(
        name="motivational_walkthrough",
        content_format="motivational_teaching",
        audience="self-improvement followers",
        content_goal="inspire and motivate",
        tone="energetic, authentic",
        cta_style="Follow / share if this helped you",
        brand_preset="clean_creator",
        platform_defaults=["tiktok", "instagram_reels", "clapper"],
        music_style="upbeat motivational",
        disclosure_expectation="none unless sponsored",
        suggested_filenames=[
            "walking-store.mp4", "talking-head.mp4", "broll-outdoor.mp4",
        ],
    ),
    "controversial_take": ProjectTemplate(
        name="controversial_take",
        content_format="reaction_commentary",
        audience="opinion followers, niche community",
        content_goal="drive engagement via strong opinion",
        tone="bold, direct, confident",
        cta_style="Comment your take / agree or disagree",
        brand_preset="bold_viral",
        platform_defaults=["tiktok", "clapper", "x"],
        music_style="tense or minimal",
        disclosure_expectation="none unless sponsored",
        suggested_filenames=[
            "talking-head.mp4", "reaction.mp4", "proof-screen.mp4",
        ],
        notes="Avoid harmful misinformation. Use opinion framing.",
    ),
    "personal_story": ProjectTemplate(
        name="personal_story",
        content_format="personal_story",
        audience="general audiences, empathy seekers",
        content_goal="connect through story",
        tone="personal, relatable",
        cta_style="Follow / share your story in comments",
        brand_preset="clean_creator",
        platform_defaults=["tiktok", "instagram_reels", "clapper"],
        music_style="emotional light background",
        disclosure_expectation="none unless sponsored",
        suggested_filenames=[
            "talking-head.mp4", "broll-personal.mp4", "context.mp4",
        ],
    ),
    "local_business_promo": ProjectTemplate(
        name="local_business_promo",
        content_format="product_demo",
        audience="local community, potential customers",
        content_goal="drive foot traffic or calls",
        tone="friendly, local, authentic",
        cta_style="Visit us / call now / link in bio",
        brand_preset="clean_creator",
        platform_defaults=["instagram_reels", "tiktok", "clapper"],
        music_style="light friendly background",
        disclosure_expectation="mark clearly if paid/sponsored",
        suggested_filenames=[
            "storefront.mp4", "product-demo.mp4", "staff.mp4", "customer.mp4",
        ],
    ),
}


def get_template(name: str) -> ProjectTemplate | None:
    return TEMPLATES.get(name)


def get_template_or_default(name: str) -> ProjectTemplate:
    return TEMPLATES.get(name) or TEMPLATES["affiliate_product"]


def list_template_names() -> list[str]:
    return list(TEMPLATES.keys())
