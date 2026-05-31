"""
Local JSON credit / rate-limit tracker for Genesis providers.

Tracks hourly and daily generation counts and optional manually entered balances.
Does not scrape or assume real Diffus.me credits unless explicitly set in the tracker file.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis.utils.config_loader import load_diffusme_config
from genesis.utils.logger import get_logger

logger = get_logger("credit_tracker")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_TRACKER_DIR = _REPO_ROOT / "genesis" / "config"

DEFAULT_LIMITS = {
    "hourly_max": 10,
    "daily_max": 50,
    "low_credit_threshold": 200,
    "estimated_cost_per_generation": 1,
}


def tracker_dir(path: Path | str | None = None) -> Path:
    return Path(path) if path else _DEFAULT_TRACKER_DIR


def _tracker_path(provider: str, root: Path) -> Path:
    safe = provider.strip().lower().replace(" ", "_")
    return root / f"credits_{safe}.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def default_tracker(
    provider: str,
    *,
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    limits = {**DEFAULT_LIMITS, **(limits or {})}
    now = _now_utc()
    return {
        "provider": provider,
        "estimated_credits_remaining": None,
        "hourly_count": 0,
        "daily_count": 0,
        "hourly_window_start": _iso(now),
        "daily_window_start": _iso(now.replace(hour=0, minute=0, second=0, microsecond=0)),
        "limits": limits,
        "metadata": {},
    }


def _provider_limits(provider: str) -> dict[str, Any]:
    if provider.lower() == "diffusme":
        cfg = load_diffusme_config()
        return {
            "hourly_max": int(cfg.get("max_generations_per_hour", 10)),
            "daily_max": int(cfg.get("max_generations_per_day", 50)),
            "low_credit_threshold": int(cfg.get("low_credit_threshold", 200)),
            "estimated_cost_per_generation": int(
                cfg.get("estimated_cost_per_generation", 1)
            ),
        }
    return dict(DEFAULT_LIMITS)


def reset_windows_if_needed(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Reset hourly/daily counters when their window has elapsed."""
    now = now or _now_utc()
    updated = deepcopy(data)

    hourly_start = _parse_iso(updated.get("hourly_window_start"))
    if hourly_start is None or (now - hourly_start).total_seconds() >= 3600:
        updated["hourly_count"] = 0
        updated["hourly_window_start"] = _iso(now)

    daily_start = _parse_iso(updated.get("daily_window_start"))
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if daily_start is None or daily_start.date() < now.date():
        updated["daily_count"] = 0
        updated["daily_window_start"] = _iso(day_start)

    return updated


def load_tracker(
    provider: str,
    *,
    tracker_root: Path | str | None = None,
) -> dict[str, Any]:
    root = tracker_dir(tracker_root)
    path = _tracker_path(provider, root)
    if not path.is_file():
        data = default_tracker(provider, limits=_provider_limits(provider))
        return reset_windows_if_needed(data)

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("tracker must be a JSON object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("resetting tracker %s due to read error: %s", path, exc)
        data = default_tracker(provider, limits=_provider_limits(provider))

    if "limits" not in data:
        data["limits"] = _provider_limits(provider)
    data["provider"] = provider
    return reset_windows_if_needed(data)


def save_tracker(
    provider: str,
    data: dict[str, Any],
    *,
    tracker_root: Path | str | None = None,
) -> None:
    root = tracker_dir(tracker_root)
    root.mkdir(parents=True, exist_ok=True)
    path = _tracker_path(provider, root)
    payload = deepcopy(data)
    payload["provider"] = provider
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def can_generate(
    provider: str,
    estimated_cost: int = 1,
    *,
    tracker_root: Path | str | None = None,
) -> tuple[bool, str]:
    """
    Return whether a generation is allowed under rate limits and optional manual balance.
    """
    if estimated_cost < 1:
        estimated_cost = 1

    data = load_tracker(provider, tracker_root=tracker_root)
    limits = data.get("limits", DEFAULT_LIMITS)
    hourly_max = int(limits.get("hourly_max", 10))
    daily_max = int(limits.get("daily_max", 50))
    low_threshold = int(limits.get("low_credit_threshold", 200))

    hourly_count = int(data.get("hourly_count", 0))
    daily_count = int(data.get("daily_count", 0))

    if hourly_count + estimated_cost > hourly_max:
        return False, (
            f"{provider}: hourly limit reached ({hourly_count}/{hourly_max}). "
            "Wait for the hourly window to reset."
        )

    if daily_count + estimated_cost > daily_max:
        return False, (
            f"{provider}: daily limit reached ({daily_count}/{daily_max}). "
            "Counters reset at UTC midnight."
        )

    remaining = data.get("estimated_credits_remaining")
    if remaining is not None:
        try:
            remaining_int = int(remaining)
        except (TypeError, ValueError):
            remaining_int = None
        if remaining_int is not None:
            if remaining_int < low_threshold:
                return False, (
                    f"{provider}: estimated credits ({remaining_int}) below threshold "
                    f"({low_threshold}). Update credits_{provider}.json manually if balance "
                    "was refreshed."
                )
            if remaining_int < estimated_cost:
                return False, (
                    f"{provider}: insufficient estimated credits "
                    f"({remaining_int} < {estimated_cost})."
                )

    return True, ""


def record_generation(
    provider: str,
    estimated_cost: int = 1,
    *,
    tracker_root: Path | str | None = None,
) -> None:
    """Increment counters and optionally decrement manually tracked credits."""
    if estimated_cost < 1:
        estimated_cost = 1

    data = load_tracker(provider, tracker_root=tracker_root)
    data["hourly_count"] = int(data.get("hourly_count", 0)) + estimated_cost
    data["daily_count"] = int(data.get("daily_count", 0)) + estimated_cost

    remaining = data.get("estimated_credits_remaining")
    if remaining is not None:
        try:
            data["estimated_credits_remaining"] = int(remaining) - estimated_cost
        except (TypeError, ValueError):
            pass

    save_tracker(provider, data, tracker_root=tracker_root)
