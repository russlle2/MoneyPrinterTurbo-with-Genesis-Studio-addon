"""
Genesis Forge — Creator bridge.

Connects the Creator pipeline (natural-language idea -> script) to the Forge
video engine (genesis.forge.core). Two responsibilities:

  1. plan_forge_video(): turn a natural-language idea into a robust, high-quality
     *advanced video prompt plan* (per-scene cinematic prompts) with NO API calls.
     This is what the UI previews before any video is generated.

  2. render_forge_video(): take a (possibly user-edited) plan and produce the
     final draft_video.mp4 via Forge — AI image/video generation + animation.

No captions. No voiceover. No paid TTS. Script generation stays in the Creator
pipeline; this module only handles the *visual* prompt + render side.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Callable

from genesis.utils.logger import get_logger

logger = get_logger("forge.creator_bridge")

_PLAN_FILENAME = "forge_plan.json"

# ---------------------------------------------------------------------------
# Style mapping: brand preset -> (forge style key, descriptive prefix, lighting)
# ---------------------------------------------------------------------------

_BRAND_STYLE: dict[str, tuple[str, str, str]] = {
    "clean_creator": ("photorealistic", "clean, bright, modern, social-native", "natural daylight"),
    "cinematic_dark": ("cinematic", "cinematic, moody, dramatic", "low-key dramatic lighting"),
    "wellness_soft": ("photorealistic", "soft, serene, calming, pastel tones", "soft diffused light"),
    "bold_viral": ("vibrant", "bold, vibrant, high-energy, punchy colors", "bright high-contrast lighting"),
    "minimal_white": ("photorealistic", "minimal, clean, white background, elegant", "bright even studio light"),
    "auto": ("cinematic", "cinematic, polished, social-native", "natural cinematic lighting"),
    "clean": ("photorealistic", "clean, bright, modern, social-native", "natural daylight"),
}

# Mood keywords detected in the idea -> lighting / style modifiers.
_MOOD_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bwarm|cozy|heart\w*|kind|love|family|gentle\b", re.I), "warm golden-hour lighting"),
    (re.compile(r"\bdark|moody|noir|dramatic|intense|gritty\b", re.I), "dark dramatic lighting"),
    (re.compile(r"\bcalm|serene|peaceful|relax|wellness|meditat|soothing\b", re.I), "soft diffused light"),
    (re.compile(r"\bvibrant|energetic|fun|exciting|hype|bold|colorful\b", re.I), "bright vibrant colors"),
    (re.compile(r"\bcinematic|epic|film|movie|sweeping\b", re.I), "cinematic film lighting"),
    (re.compile(r"\bnight|evening|sunset|dusk\b", re.I), "golden sunset light"),
]

# Cinematic beat framings cycled across scenes (read naturally even with
# imperfect subjects from arbitrary natural-language input).
_BEAT_FRAMINGS: list[str] = [
    "Establishing wide shot of {subj}",
    "Emotional close-up of {subj}",
    "Candid documentary moment of {subj}",
    "Dynamic medium shot of {subj}",
    "Intimate detail shot of {subj}",
    "Cinematic reveal of {subj}",
    "Slow-motion moment of {subj}",
    "Closing hero shot of {subj}",
]

_CINEMATIC_SUFFIX = (
    "vertical 9:16 composition, professional color grading, "
    "highly detailed, sharp focus, 4k, no text, no watermark"
)

# Phrases that are *direction to the editor*, not visual subjects.
_DIRECTION_LEAD = re.compile(
    r"^(?:and\s+)?(?:please\s+)?(?:use|using|with|in|make\s+it|keep\s+it|"
    r"set\s+it\s+in|add|include|give\s+it|have\s+a?)\b",
    re.I,
)
_SHOW_SCENES_OF = re.compile(
    r"\b(?:show(?:ing)?|with|include|feature)\s+(?:scenes?|shots?|clips?|footage|moments?)\s+of\s+",
    re.I,
)
# Comparison hooks ("X outlasted/beats/vs Y") -> two separate filmable subjects.
_COMPARISON_SPLIT = re.compile(
    r"\s+\b(?:outlast(?:ed|s)?|outperform(?:ed|s)?|beat(?:s|en)?|"
    r"destroy(?:ed|s)?|crush(?:ed|es)?|vs\.?|versus|compared\s+to|better\s+than)\b\s+",
    re.I,
)
# Leading demonstratives/possessives that are not part of the subject noun.
_LEADING_DEMO = re.compile(
    r"^(?:this|that|these|those|my|your|our|his|her|its|their)\s+",
    re.I,
)
# Technical production specs that are directives, not filmable subjects.
# e.g. "cinematic 9:16 aspect ratio", "4k", "60fps"
_TECH_SPEC_STRIP = re.compile(
    r"[,.]?\s*\b\d+:\d+\b\s*(?:aspect\s+ratio\b)?"   # "9:16" or "9:16 aspect ratio"
    r"|[,.]?\s*\baspect\s+ratio\b"                      # lone "aspect ratio"
    r"|[,.]?\s*\b(?:4k|8k|1080p|720p|2160p)\b"
    r"|[,.]?\s*\b\d+\s*fps\b",
    re.I,
)
# "stunning visual story / cinematic journey" narrative-framing openers —
# they describe the *format* of the video, not what should be in the frame.
_NARRATIVE_OPENER = re.compile(
    r"^(?:a\s+|an\s+)?(?:stunning|beautiful|breathtaking|epic|amazing|dramatic|"
    r"powerful|incredible)\s+"
    r"(?:(?:and\s+)?(?:cinematic|visual|immersive)\s+)?"
    r"(?:story|journey|narrative|sequence|experience|tale|montage)\s+"
    r"(?:(?:of|about|through|showing|featuring|that\s+)\s*)?"
    r"(?:transitioning\s+)?",
    re.I,
)
_LEADING_FILLER = re.compile(
    r"^(?:be|being|to\s+be|that\s+(?:show|shows|are|is)|how\s+to|the\s+importance\s+of)\s+",
    re.I,
)
_TRAILING_FILLER = re.compile(
    r"\s*[-—:]*\s*\b(?:here'?s\s+why|and\s+why|explained|and\s+more|in\s+\d+\s+\w+)\s*$",
    re.I,
)

# Words that describe *style/mood*, not a filmable subject. A phrase made up
# only of these is dropped (the mood is already captured in style/lighting).
_STYLE_WORDS = frozenset({
    "emotional", "cinematic", "warm", "cozy", "dark", "moody", "vibrant",
    "energetic", "calm", "serene", "peaceful", "dramatic", "epic", "fun",
    "colorful", "bold", "gritty", "soft", "bright", "aesthetic", "vibe",
    "atmosphere", "mood", "tone", "style", "vibes", "feel", "feeling",
    "beautiful", "stunning", "gorgeous", "nice", "cool", "amazing",
})


def _is_style_only(phrase: str) -> bool:
    words = [w for w in re.findall(r"[a-z']+", phrase.lower()) if w not in {"and", "a", "an", "the", "very", "really"}]
    return bool(words) and all(w in _STYLE_WORDS for w in words)


def _strip_directives(text: str) -> str:
    """Remove tech specs and narrative-framing openers so subjects are clean."""
    t = _TECH_SPEC_STRIP.sub("", text).strip()
    t = _NARRATIVE_OPENER.sub("", t).strip()
    return t


def _parse_location_transitions(text: str) -> list[str] | None:
    """
    Detect 'from X to Y (to Z …)' narrative-transition patterns and return
    the ordered list of environment/location subjects.

    Returns None if no clear multi-location transition is found.
    """
    m = re.search(r'(?:transitioning\s+)?from\s+(.+)', text, re.I)
    if not m:
        return None
    remainder = m.group(1).strip()
    parts = re.split(r'\s+to\s+', remainder, flags=re.I)
    subjects: list[str] = []
    for p in parts:
        p = p.strip()
        # Strip tech specs embedded in this part.
        p = _TECH_SPEC_STRIP.sub("", p).strip()
        # Take only the first sentence — anything after a period is usually
        # a style note ("sahara desert. cinematic" → "sahara desert").
        p = re.split(r'\.\s+', p)[0].rstrip('.,;:!?').strip()
        # Strip trailing lone style/mood words that bled in.
        words = p.split()
        while words and words[-1].lower() in _STYLE_WORDS:
            words.pop()
        p = " ".join(words).strip()
        if len(p.split()) >= 2 and not _is_style_only(p):
            subjects.append(p)
    return subjects if len(subjects) >= 2 else None


def _detect_mood_lighting(idea: str, default: str) -> str:
    for pat, lighting in _MOOD_HINTS:
        if pat.search(idea):
            return lighting
    return default


def _extract_scene_subjects(idea: str) -> list[str]:
    """
    Split a natural-language idea into filmable subject phrases, robustly.

    Priority order:
      1. "from X to Y to Z" transition → ordered environment list
      2. Generic sentence/clause splitting with direction/style-word filtering

    Tech-spec directives ("9:16 aspect ratio", "4k") and narrative-framing
    openers ("stunning visual story transitioning…") are stripped first so they
    never appear as subjects.
    """
    from genesis.creative.idea_normalizer import clean_topic_phrase

    # Strip production directives before any other processing.
    clean_idea = _strip_directives(idea)
    text = clean_topic_phrase(clean_idea)
    text = _strip_directives(text)          # catch anything clean_topic_phrase exposed
    text = _SHOW_SCENES_OF.sub("", text).strip()

    # --- Priority 1: "from X to Y (to Z)" ordered-location transitions ---
    transition = _parse_location_transitions(text)
    if transition:
        return transition

    # --- Priority 2: generic clause splitting ---
    raw_parts = re.split(r"[.;\n]+|\s+\band\b\s+|,\s+", text)
    # Expand comparison hooks so each compared item becomes its own subject.
    expanded: list[str] = []
    for part in raw_parts:
        expanded.extend(_COMPARISON_SPLIT.split(part))
    subjects: list[str] = []
    for part in expanded:
        p = part.strip()
        if not p:
            continue
        # Drop "because ..." style trailing reasoning.
        p = re.split(r"\s+\b(?:because|since|so that|in order to)\b\s+", p, maxsplit=1)[0].strip()
        # Drop pure editor-direction clauses (e.g. "use a warm atmosphere").
        if _DIRECTION_LEAD.match(p):
            continue
        p = _LEADING_FILLER.sub("", p).strip()
        p = _LEADING_DEMO.sub("", p).strip()
        p = _TRAILING_FILLER.sub("", p).strip()
        # Drop phrases that are only style/mood words (captured separately).
        if _is_style_only(p):
            continue
        if len(p) < 3 or len(p.split()) > 14:
            # Too short or a whole run-on; still usable but trim very long ones.
            if len(p.split()) > 14:
                p = " ".join(p.split()[:14])
            else:
                continue
        subjects.append(p)

    # Dedupe (case-insensitive) preserving order.
    seen: set[str] = set()
    unique = []
    for s in subjects:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            unique.append(s)

    if not unique:
        # Fall back to the lightly cleaned idea / raw idea.
        fallback = text.strip() or idea.strip()
        unique = [" ".join(fallback.split()[:14])] if fallback else ["the main subject"]
    return unique


def _aspect_ratio_for_platform(platform: str) -> str:
    # All supported short-form platforms are vertical.
    return "9:16"


def plan_forge_video(
    idea: str,
    *,
    target_platform: str = "tiktok",
    brand_preset: str = "clean_creator",
    duration_seconds: float = 30.0,
    n_scenes: int | None = None,
) -> dict[str, Any]:
    """
    Build an advanced video prompt plan from a natural-language idea.

    Pure/deterministic — no network or API calls. Safe to call for preview.

    Returns a dict:
        {
          "idea", "style_key", "style_desc", "lighting", "aspect_ratio",
          "duration_seconds", "scene_duration",
          "scenes": [{"index", "beat", "subject", "prompt", "duration", "animation"}],
          "master_prompt"
        }
    """
    idea = (idea or "").strip()
    style_key, style_desc, base_light = _BRAND_STYLE.get(
        brand_preset, _BRAND_STYLE["auto"]
    )
    lighting = _detect_mood_lighting(idea, base_light)
    aspect = _aspect_ratio_for_platform(target_platform)

    subjects = _extract_scene_subjects(idea)

    duration_seconds = max(5.0, float(duration_seconds or 30.0))
    if n_scenes is None:
        # Scale cap with duration: ~4 s/scene, max 15 for longer videos.
        n_scenes = max(3, min(15, round(duration_seconds / 4.0)))
    n_scenes = max(1, int(n_scenes))
    scene_duration = round(duration_seconds / n_scenes, 2)

    # Narrative-arc mode: when subjects come from an ordered transition
    # ("from X to Y to Z"), distribute scenes in sequential blocks so the
    # video actually journeys through each environment in order.
    _stripped = _strip_directives(idea)
    _is_arc = len(subjects) >= 2 and _parse_location_transitions(_stripped) is not None

    animations = ["ken_burns", "zoom_in", "pan_right", "zoom_out", "pan_left"]
    scenes: list[dict[str, Any]] = []
    for i in range(n_scenes):
        if _is_arc:
            # Proportional block: subject 0 fills first slice, subject 1 the next, etc.
            subj_idx = min(int(i * len(subjects) / n_scenes), len(subjects) - 1)
            subject = subjects[subj_idx]
        else:
            subject = subjects[i % len(subjects)]
        beat_tmpl = _BEAT_FRAMINGS[i % len(_BEAT_FRAMINGS)]
        beat = beat_tmpl.format(subj=subject)
        prompt = (
            f"{style_desc}. {beat}. {lighting}, {_CINEMATIC_SUFFIX}"
        )
        scenes.append({
            "index": i,
            "beat": beat_tmpl.split(" of ")[0],
            "subject": subject,
            "prompt": prompt,
            "duration": scene_duration,
            "animation": animations[i % len(animations)],
        })

    master_subject = subjects[0] if subjects else "the main subject"
    master_prompt = (
        f"{style_desc}. {master_subject}. {lighting}, {_CINEMATIC_SUFFIX}"
    )

    return {
        "idea": idea,
        "style_key": style_key,
        "style_desc": style_desc,
        "lighting": lighting,
        "aspect_ratio": aspect,
        "duration_seconds": duration_seconds,
        "scene_duration": scene_duration,
        "scenes": scenes,
        "master_prompt": master_prompt,
    }


def write_forge_plan(run_dir: Path, plan: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / _PLAN_FILENAME
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return path


def load_forge_plan(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / _PLAN_FILENAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _collect_uploaded_images(run_dir: Path) -> list[str]:
    """Return uploaded still images in the run's media folder (videos ignored here)."""
    media = run_dir / "media"
    if not media.is_dir():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    return [str(p) for p in sorted(media.iterdir()) if p.suffix.lower() in exts]


def render_forge_video(
    job_id: str,
    *,
    run_dir: Path,
    plan: dict[str, Any] | None = None,
    idea: str = "",
    target_platform: str = "tiktok",
    brand_preset: str = "clean_creator",
    duration_seconds: float = 30.0,
    transition_style: str = "fade",
    progress_cb: Callable[[str, float], None] | None = None,
) -> dict[str, Any]:
    """
    Render the final draft_video.mp4 via the Forge engine using the plan.

    Resolution order for the plan:
      1. explicit ``plan`` argument
      2. an existing forge_plan.json in the run dir (user-edited in preview)
      3. a freshly built plan from ``idea``

    Returns dict: {"status", "output_path", "engine_used", "warnings", "scene_count"}.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    if plan is None:
        plan = load_forge_plan(run_dir)
    if plan is None:
        plan = plan_forge_video(
            idea,
            target_platform=target_platform,
            brand_preset=brand_preset,
            duration_seconds=duration_seconds,
        )
        write_forge_plan(run_dir, plan)

    aspect = plan.get("aspect_ratio", "9:16")
    output_path = run_dir / "draft_video.mp4"
    warnings: list[str] = []

    try:
        from genesis.forge import core as forge_core
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed", "output_path": "", "engine_used": "none",
            "warnings": [f"forge engine import failed: {exc}"], "scene_count": 0,
        }

    images = _collect_uploaded_images(run_dir)
    scenes = plan.get("scenes") or []

    try:
        if images:
            # User supplied real images — animate those (Ken Burns / AI animate).
            per = max(2.0, float(plan.get("scene_duration", 4.0)))
            result = forge_core.images_to_video(
                images,
                duration_per_image=per,
                aspect_ratio=aspect,
                transition_style=transition_style,
                output_dir=run_dir,
                progress_cb=progress_cb,
            )
        elif scenes:
            hybrid_scenes = [
                forge_core.HybridScene(
                    kind="prompt",
                    content=s.get("prompt", ""),
                    duration_seconds=float(s.get("duration", 4.0)),
                    style=plan.get("style_key", "cinematic"),
                    animation=s.get("animation", "ken_burns"),
                )
                for s in scenes if s.get("prompt")
            ]
            result = forge_core.hybrid_video(
                hybrid_scenes,
                transition_style=transition_style,
                aspect_ratio=aspect,
                output_dir=run_dir,
                progress_cb=progress_cb,
            )
        else:
            result = forge_core.text_to_video(
                plan.get("master_prompt", idea or "a cinematic short video"),
                style=plan.get("style_key", "cinematic"),
                duration_seconds=float(plan.get("duration_seconds", 30.0)),
                aspect_ratio=aspect,
                output_dir=run_dir,
                progress_cb=progress_cb,
            )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed", "output_path": "", "engine_used": "none",
            "warnings": [f"forge render error: {exc}"], "scene_count": len(scenes),
        }

    warnings.extend(result.warnings or [])

    if not result.success or not result.output_path:
        return {
            "status": "failed", "output_path": "", "engine_used": result.engine_used,
            "warnings": warnings or [result.error or "forge produced no output"],
            "scene_count": len(scenes),
        }

    # Normalize output to run_dir/draft_video.mp4
    src = Path(result.output_path)
    try:
        if src.resolve() != output_path.resolve():
            shutil.copy2(src, output_path)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"could not move forge output: {exc}")
        output_path = src

    logger.info(
        "forge render job=%s engine=%s scenes=%d -> %s",
        job_id, result.engine_used, len(scenes), output_path,
    )
    return {
        "status": "complete",
        "output_path": str(output_path),
        "engine_used": result.engine_used,
        "warnings": warnings,
        "scene_count": len(scenes),
    }
