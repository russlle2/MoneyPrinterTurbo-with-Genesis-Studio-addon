"""
Genesis Studio logging utilities.

Uses loguru when available (MoneyPrinterTurbo dependency); falls back to stdlib logging.
Import-safe: does not create log files until configure_genesis_logging() is called.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

_USE_LOGURU = False
_loguru_logger: Any = None

try:
    from loguru import logger as _loguru_logger  # type: ignore[no-redef]

    _USE_LOGURU = True
except ImportError:
    pass

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOG_DIR = _REPO_ROOT / "logs" / "genesis"
_configured = False

# Keys and patterns redacted from log messages.
_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|authorization|bearer)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


def repo_log_dir() -> Path:
    return _DEFAULT_LOG_DIR


def redact_secrets(message: str) -> str:
    """Mask likely secrets before writing logs."""
    if not message:
        return message
    redacted = _SECRET_KEY_RE.sub(r"\1=***", message)
    redacted = _BEARER_RE.sub("Bearer ***", redacted)
    redacted = _SK_RE.sub("sk-***", redacted)
    return redacted


def _redact_record(record: dict[str, Any]) -> bool:
    record["message"] = redact_secrets(str(record.get("message", "")))
    return True


def configure_genesis_logging(
    *,
    level: str = "INFO",
    log_dir: Path | str | None = None,
    console: bool = True,
) -> None:
    """
    Configure Genesis file + console logging under logs/genesis/ (or log_dir).
    Safe to call multiple times; reconfigures sinks/handlers.
    """
    global _configured
    target_dir = Path(log_dir) if log_dir else _DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    level_norm = level.upper()

    if _USE_LOGURU and _loguru_logger is not None:
        _loguru_logger.remove()
        if console:
            _loguru_logger.add(
                sys.stderr,
                level=level_norm,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{extra[module]}</cyan> - "
                    "<level>{message}</level>"
                ),
                filter=_redact_record,
            )
        _loguru_logger.add(
            target_dir / "genesis_{time:YYYY-MM-DD}.log",
            level=level_norm,
            rotation="10 MB",
            retention="14 days",
            encoding="utf-8",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[module]} | {message}"
            ),
            filter=_redact_record,
        )
    else:
        root = logging.getLogger("genesis")
        root.handlers.clear()
        root.setLevel(getattr(logging, level_norm, logging.INFO))
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )

        class _RedactingFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                record.msg = redact_secrets(str(record.msg))
                return super().format(record)

        redacting = _RedactingFormatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )

        if console:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setFormatter(redacting)
            root.addHandler(stream_handler)

        file_handler = logging.FileHandler(
            target_dir / "genesis.log", encoding="utf-8"
        )
        file_handler.setFormatter(redacting)
        root.addHandler(file_handler)

    _configured = True


def reset_genesis_logging() -> None:
    """Remove handlers/sinks so log files can be closed (useful in tests)."""
    global _configured
    if _USE_LOGURU and _loguru_logger is not None:
        _loguru_logger.remove()
    else:
        root = logging.getLogger("genesis")
        for handler in root.handlers[:]:
            handler.close()
            root.removeHandler(handler)
    _configured = False


def get_logger(module: str):
    """
    Return a module-scoped logger. Does not configure sinks on import.
    Call configure_genesis_logging() once at application startup for file logs.
    """
    if _USE_LOGURU and _loguru_logger is not None:
        return _loguru_logger.bind(module=module)
    return logging.getLogger(f"genesis.{module}")
