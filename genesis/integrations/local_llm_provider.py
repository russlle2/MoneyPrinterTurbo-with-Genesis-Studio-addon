"""
Genesis Studio — Local LLM provider abstraction.

Connects to locally-hosted language model servers over HTTP.
Never loads model weights directly; never calls paid hosted APIs.
All generation is through local HTTP endpoints only.

Supported backends:
    disabled           — default; all calls return skipped/unavailable
    ollama             — http://localhost:11434/api/generate
    lmstudio           — OpenAI-compatible, http://localhost:1234/v1/chat/completions
    llama_cpp_server   — http://localhost:8080/completion
    text_generation_webui — http://localhost:5000/api/v1/generate
    custom_http        — user-defined endpoint, tries multiple response formats

Response shapes supported:
    Ollama:      {"response": "..."}
    OpenAI-compat: {"choices": [{"message": {"content": "..."}}]}
    TGWUI:       {"results": [{"text": "..."}]}
    llama.cpp:   {"content": "..."}
    Custom:      {"text": "..."} or any of the above
"""

from __future__ import annotations

from typing import Any

from genesis.utils.logger import get_logger

logger = get_logger("integrations.local_llm")

SUPPORTED_BACKENDS: tuple[str, ...] = (
    "disabled",
    "ollama",
    "lmstudio",
    "llama_cpp_server",
    "text_generation_webui",
    "custom_http",
)

_DEFAULT_SYSTEM_PROMPT = (
    "You are Genesis Studio's local creative writing model for short-form "
    "social media content. Output only valid JSON as requested."
)


# ---------------------------------------------------------------------------
# Config loading (lazy — avoids circular import at module level)
# ---------------------------------------------------------------------------

def load_local_llm_config(config_root=None) -> dict[str, Any]:
    """Load local LLM config from JSON file and environment variables."""
    from genesis.utils.config_loader import load_local_llm_config as _load
    return _load(config_root=config_root)


# ---------------------------------------------------------------------------
# Readiness check (config-only, no network call)
# ---------------------------------------------------------------------------

def local_llm_ready(config: dict[str, Any] | None = None) -> tuple[bool, str]:
    """
    Check whether local LLM is configured and nominally ready.

    Does NOT make a network call — that happens in generate_local_text().
    Returns (True, "") when ready; (False, reason) otherwise.
    """
    cfg = config or load_local_llm_config()
    if not cfg.get("enabled"):
        return False, (
            "local LLM disabled. Set enabled=true in "
            "genesis/config/local_llm.json or GENESIS_LOCAL_LLM_ENABLED=true."
        )
    backend = cfg.get("backend", "disabled")
    if backend == "disabled" or not backend:
        return False, "local LLM backend is 'disabled'."
    if backend not in SUPPORTED_BACKENDS:
        return False, f"unknown local LLM backend: {backend!r}. Supported: {', '.join(SUPPORTED_BACKENDS)}"
    endpoint = cfg.get("endpoint_url", "").strip()
    if not endpoint:
        return False, "no endpoint_url configured for local LLM."
    return True, ""


# ---------------------------------------------------------------------------
# Request builders per backend
# ---------------------------------------------------------------------------

def _build_payload(prompt: str, config: dict[str, Any]) -> dict[str, Any]:
    """Build the HTTP request payload for the configured backend."""
    backend = config.get("backend", "custom_http")
    model = config.get("model", "")
    max_tokens = int(config.get("max_tokens", 1200))
    temperature = float(config.get("temperature", 0.7))
    system_prompt = config.get("system_prompt", _DEFAULT_SYSTEM_PROMPT)

    if backend == "ollama":
        return {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }

    if backend == "lmstudio":
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

    if backend == "llama_cpp_server":
        return {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": [],
        }

    if backend == "text_generation_webui":
        return {
            "prompt": prompt,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "do_sample": True,
        }

    # custom_http — send a generic payload; server decides what to do with it
    return {
        "prompt": prompt,
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


# ---------------------------------------------------------------------------
# Response extractors per backend
# ---------------------------------------------------------------------------

def _extract_text(response_json: dict, backend: str) -> str | None:
    """Extract the generated text from the backend-specific response shape."""
    if backend == "ollama":
        return response_json.get("response")

    if backend in ("lmstudio",):
        choices = response_json.get("choices", [])
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message", {})
            return msg.get("content") if isinstance(msg, dict) else None

    if backend == "llama_cpp_server":
        return response_json.get("content")

    if backend == "text_generation_webui":
        results = response_json.get("results", [])
        if results and isinstance(results[0], dict):
            return results[0].get("text")

    # custom_http — try every known shape
    for extractor in [
        lambda r: r.get("text"),
        lambda r: r.get("response"),
        lambda r: r.get("content"),
        lambda r: (r.get("choices", [{}])[0] or {}).get("message", {}).get("content"),
        lambda r: ((r.get("results") or [{}])[0] or {}).get("text"),
    ]:
        try:
            val = extractor(response_json)
            if val:
                return str(val)
        except Exception:  # noqa: BLE001
            continue

    return None


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_local_text(
    prompt: str,
    *,
    config: dict[str, Any] | None = None,
    task: str | None = None,
) -> dict[str, Any]:
    """
    Send a prompt to the configured local LLM and return the response.

    Args:
        prompt: The full prompt text.
        config: Optional pre-loaded config dict.
        task:   Optional task hint (informational, not sent to model).

    Returns:
        dict with keys:
            success  (bool)
            text     (str)  — generated text when success=True
            backend  (str)
            model    (str)
            error    (str)  — error description when success=False
    """
    try:
        import requests  # already a project dependency
    except ImportError:
        return {"success": False, "error": "requests not installed", "text": "", "backend": "unknown", "model": "unknown"}

    cfg = config or load_local_llm_config()
    backend = cfg.get("backend", "disabled")
    model = cfg.get("model", "")
    endpoint = cfg.get("endpoint_url", "").strip()
    timeout = int(cfg.get("timeout_seconds", 120))
    debug = cfg.get("debug_prompts", False)

    if debug:
        logger.debug("local LLM prompt (task=%s, backend=%s): %.200s...", task or "?", backend, prompt)

    ready, reason = local_llm_ready(cfg)
    if not ready:
        return {"success": False, "error": reason, "text": "", "backend": backend, "model": model}

    payload = _build_payload(prompt, cfg)

    try:
        resp = requests.post(
            endpoint,
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        response_json = resp.json()
    except requests.exceptions.ConnectionError as exc:
        return {
            "success": False,
            "error": f"cannot connect to local LLM endpoint {endpoint}: {exc}",
            "text": "", "backend": backend, "model": model,
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"local LLM request timed out after {timeout}s",
            "text": "", "backend": backend, "model": model,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "error": f"local LLM request failed: {type(exc).__name__}: {str(exc)[:120]}",
            "text": "", "backend": backend, "model": model,
        }

    text = _extract_text(response_json, backend)
    if text is None:
        # Show a redacted preview of the unknown response shape
        raw_preview = str(response_json)[:120]
        return {
            "success": False,
            "error": f"unrecognised response format from {backend}: {raw_preview!r}",
            "text": "", "backend": backend, "model": model,
        }

    text = _repair_json_response(text)
    return {"success": True, "text": text, "backend": backend, "model": model}


# ---------------------------------------------------------------------------
# JSON repair — handles truncated / markdown-wrapped responses
# ---------------------------------------------------------------------------

def _repair_json_response(text: str) -> str:
    """
    Attempt to repair common LLM JSON output issues:
      1. Strip markdown code fences (```json ... ```)
      2. Return as-is if already valid
      3. Auto-close truncated JSON objects and arrays
    Returns the repaired string, or the original if repair fails.
    """
    import re
    import json as _json

    cleaned = text.strip()

    # Strip markdown fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    elif cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip().rstrip("`").strip()

    # Already valid
    try:
        _json.loads(cleaned)
        return cleaned
    except _json.JSONDecodeError:
        pass

    # Auto-close truncated JSON by tracking open braces/brackets and strings
    repaired = _auto_close_json(cleaned)
    try:
        _json.loads(repaired)
        logger.debug("JSON auto-repair succeeded (%d → %d chars)", len(cleaned), len(repaired))
        return repaired
    except _json.JSONDecodeError:
        pass

    return cleaned  # return best-effort cleaned text even if not valid JSON


def _auto_close_json(s: str) -> str:
    """Close any unclosed JSON brackets/braces/strings in a truncated response."""
    stack = []
    in_string = False
    escape_next = False

    for ch in s:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()

    closing = ""
    if in_string:
        closing += '"'
    closing += "".join(reversed(stack))
    return s + closing


# ---------------------------------------------------------------------------
# Prompt builder for social script generation
# ---------------------------------------------------------------------------

def build_social_script_prompt(
    *,
    idea: str,
    audience: str = "",
    tone: str = "engaging",
    content_goal: str = "",
    offer: str = "",
    cta: str = "",
    content_format: str = "product_demo",
    platforms: list[str] | None = None,
) -> str:
    """
    Build a structured JSON-output prompt for social media script generation.

    The prompt instructs the local model to return a JSON object matching
    the ScriptPackage shape.  It embeds the Viral Spine framework so that
    any instruction-following model can produce a structured result.
    """
    platforms_str = ", ".join(platforms or ["tiktok", "instagram_reels", "clapper", "youtube_shorts"])
    audience_line = f"Target audience: {audience}" if audience else "Target audience: general social media viewers"
    offer_line = f"Product / offer: {offer}" if offer else ""
    cta_line = f"Requested CTA: {cta}" if cta else ""
    goal_line = f"Content goal: {content_goal}" if content_goal else ""

    return f"""You are a social media script writer. Output ONLY a JSON object — no prose, no markdown, no explanation.

CREATIVE BRIEF
--------------
Idea: {idea}
{audience_line}
Tone: {tone}
{goal_line}
{offer_line}
{cta_line}
Content format: {content_format}
Target platforms: {platforms_str}

FRAMEWORK: Viral Spine
----------------------
Every script must follow this 5-section structure:
1. Pattern Interrupt — stop the scroll
2. Proof — establish credibility in 1–2 sentences
3. Demonstration / Teaching — deliver the core value
4. Meaning — explain why it matters to the viewer
5. CTA — one clear next action

REQUIRED JSON OUTPUT SHAPE
---------------------------
{{
  "hooks": [
    {{"text": "...", "style": "curiosity", "reason": "...", "score": 0.9}},
    {{"text": "...", "style": "proof_based", "reason": "...", "score": 0.85}},
    {{"text": "...", "style": "practical", "reason": "...", "score": 0.8}},
    {{"text": "...", "style": "emotional", "reason": "...", "score": 0.75}},
    {{"text": "...", "style": "contrarian", "reason": "...", "score": 0.7}}
  ],
  "primary_script": {{
    "title": "...",
    "duration_target": "30s",
    "platform_fit": ["{(platforms or ['tiktok', 'instagram_reels'])[0]}"],
    "sections": [
      {{"name": "Pattern Interrupt", "text": "...", "purpose": "Stop the scroll"}},
      {{"name": "Proof", "text": "...", "purpose": "Give credibility"}},
      {{"name": "Demonstration / Teaching", "text": "...", "purpose": "Deliver core value"}},
      {{"name": "Meaning", "text": "...", "purpose": "Explain why it matters"}},
      {{"name": "CTA", "text": "...", "purpose": "Next action"}}
    ],
    "full_text": "..."
  }},
  "alternate_scripts": [
    {{
      "title": "Short version",
      "duration_target": "15s",
      "platform_fit": ["clapper", "tiktok"],
      "sections": [],
      "full_text": "..."
    }}
  ],
  "overlay_captions": [
    {{"text": "...", "timing_hint": "0–2s", "purpose": "Hook echo"}},
    {{"text": "...", "timing_hint": "3–6s", "purpose": "Proof point"}},
    {{"text": "...", "timing_hint": "7–20s", "purpose": "Key action"}},
    {{"text": "...", "timing_hint": "end", "purpose": "CTA reminder"}}
  ],
  "cta_options": [
    {{"text": "...", "type": "comment_keyword", "platform_fit": ["tiktok", "clapper"]}},
    {{"text": "...", "type": "link_in_bio", "platform_fit": ["instagram_reels", "youtube_shorts"]}}
  ],
  "notes": ["..."]
}}

OUTPUT ONLY THE JSON. Nothing else."""


# ---------------------------------------------------------------------------
# Convenience: generate script package via local LLM (used by script_engine)
# ---------------------------------------------------------------------------

def generate_social_script_with_local_llm(
    idea: str,
    *,
    audience: str = "",
    tone: str = "engaging",
    content_goal: str = "",
    offer: str = "",
    cta: str = "",
    content_format: str = "product_demo",
    platforms: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    High-level wrapper: build prompt → call local LLM → return raw response dict.

    Returns the same shape as generate_local_text():
        {"success": bool, "text": str, "backend": str, "model": str, ...}
    """
    prompt = build_social_script_prompt(
        idea=idea, audience=audience, tone=tone,
        content_goal=content_goal, offer=offer, cta=cta,
        content_format=content_format, platforms=platforms,
    )
    return generate_local_text(prompt, config=config, task="social_script")
