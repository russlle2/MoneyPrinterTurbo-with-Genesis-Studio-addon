"""
Read-only filesystem scanner for Genesis Studio.

Detects local tools, caches, environments, workflows, and model files.
Does not copy, move, delete, rename, or modify any discovered paths.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

logger = logging.getLogger(__name__)

MODEL_EXTENSIONS = frozenset({".ckpt", ".safetensors", ".pth", ".pt", ".bin", ".gguf"})

DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    r"C:\Users\chris\Desktop\AI command center.lnk",
    r"C:\Users\chris\Desktop\Genesis Studio.lnk",
    r"C:\Users\chris\Desktop\Autonomous Ad Video Studio.lnk",
    r"C:\Users\chris\AppData\Local",
    r"C:\Users\chris\Documents",
    r"C:\AI",
    r"D:\AI",
    r"E:\AI",
)

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        "$recycle.bin",
        "recycle.bin",
        "system volume information",
        "windows",
        "program files",
        "program files (x86)",
        "winsxs",
        "appdata",  # when encountered as subdir name under non-Local roots
    }
)

# Browser / heavy cache folder names (matched case-insensitively).
SKIP_DIR_SUBSTRINGS = (
    "cache",
    "gpu cache",
    "code cache",
    "service worker",
    "shadercache",
    "grshadercache",
    "browsermetrics",
    "inetcache",
    "temp",
    "tmp",
)

MODEL_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cogvideox": ("cogvideox", "cog-video", "cog_video"),
    "svd": ("svd", "stable-video", "stable_video", "svd_xt"),
    "animatediff": ("animatediff", "animate_diff", "animate-diff"),
    "hotshotxl": ("hotshot-xl", "hotshotxl", "hotshot_xl"),
    "motionctrl": ("motionctrl", "motion-ctrl", "motion_ctrl"),
    "sdxl": ("sdxl", "stable-diffusion-xl", "stable_diffusion_xl"),
    "flux": ("flux", "flux1"),
}

COMFYUI_MARKERS = frozenset(
    {
        "comfyui",
        "comfy",
        "custom_nodes",
        "models",
        "input",
        "output",
    }
)

FFMPEG_NAMES = frozenset({"ffmpeg.exe", "ffmpeg", "ffprobe.exe", "ffprobe"})

HF_CACHE_MARKERS = (
    "huggingface",
    "hf_hub",
    "transformers",
    "diffusers",
)

WORKFLOW_JSON_HINTS = (
    "workflow",
    "comfyui_workflows",
    "workflows",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_output_dir() -> Path:
    return _repo_root() / "genesis" / "config"


def _normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _unique_sorted(paths: Iterable[str]) -> list[str]:
    return sorted({p for p in paths if p})


@dataclass
class ScanPaths:
    comfyui_roots: list[str] = field(default_factory=list)
    ffmpeg_bins: list[str] = field(default_factory=list)
    huggingface_caches: list[str] = field(default_factory=list)
    python_envs: list[str] = field(default_factory=list)
    conda_envs: list[str] = field(default_factory=list)
    model_dirs: list[str] = field(default_factory=list)
    workflow_dirs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "comfyui_roots": _unique_sorted(self.comfyui_roots),
            "ffmpeg_bins": _unique_sorted(self.ffmpeg_bins),
            "huggingface_caches": _unique_sorted(self.huggingface_caches),
            "python_envs": _unique_sorted(self.python_envs),
            "conda_envs": _unique_sorted(self.conda_envs),
            "model_dirs": _unique_sorted(self.model_dirs),
            "workflow_dirs": _unique_sorted(self.workflow_dirs),
        }


@dataclass
class ScanModels:
    cogvideox: list[str] = field(default_factory=list)
    svd: list[str] = field(default_factory=list)
    animatediff: list[str] = field(default_factory=list)
    hotshotxl: list[str] = field(default_factory=list)
    motionctrl: list[str] = field(default_factory=list)
    sdxl: list[str] = field(default_factory=list)
    flux: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "cogvideox": _unique_sorted(self.cogvideox),
            "svd": _unique_sorted(self.svd),
            "animatediff": _unique_sorted(self.animatediff),
            "hotshotxl": _unique_sorted(self.hotshotxl),
            "motionctrl": _unique_sorted(self.motionctrl),
            "sdxl": _unique_sorted(self.sdxl),
            "flux": _unique_sorted(self.flux),
            "other": _unique_sorted(self.other),
        }


@dataclass
class ScanState:
    paths: ScanPaths = field(default_factory=ScanPaths)
    models: ScanModels = field(default_factory=ScanModels)
    scanned_locations: list[str] = field(default_factory=list)
    skipped_locations: list[str] = field(default_factory=list)
    missing_locations: list[str] = field(default_factory=list)
    permission_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    files_inspected: int = 0
    _comfyui_seen: set[str] = field(default_factory=set, repr=False)
    _hf_cache_seen: set[str] = field(default_factory=set, repr=False)
    _model_dir_seen: set[str] = field(default_factory=set, repr=False)
    _workflow_dir_seen: set[str] = field(default_factory=set, repr=False)
    _python_env_seen: set[str] = field(default_factory=set, repr=False)
    _conda_env_seen: set[str] = field(default_factory=set, repr=False)


def resolve_scan_roots(raw_roots: Iterable[str | Path]) -> list[Path]:
    """Expand shortcuts and return concrete directories to scan."""
    resolved: list[Path] = []
    for raw in raw_roots:
        path = _normalize_path(raw)
        if not path.exists():
            continue
        if path.suffix.lower() == ".lnk":
            target = resolve_windows_lnk(path)
            if not target:
                continue
            target_path = _normalize_path(target)
            if target_path.is_file():
                resolved.append(target_path.parent)
            elif target_path.is_dir():
                resolved.append(target_path)
            else:
                parent = target_path.parent
                if parent.exists():
                    resolved.append(parent)
        elif path.is_file():
            resolved.append(path.parent)
        elif path.is_dir():
            resolved.append(path)
    # Preserve order while deduplicating.
    seen: set[str] = set()
    unique: list[Path] = []
    for item in resolved:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def resolve_windows_lnk(lnk_path: Path) -> str | None:
    """Resolve a Windows .lnk shortcut to its target path (read-only)."""
    if platform.system() != "Windows":
        return None
    if not lnk_path.is_file():
        return None
    escaped = str(lnk_path).replace("'", "''")
    command = (
        f"(New-Object -ComObject WScript.Shell)"
        f".CreateShortcut('{escaped}').TargetPath"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("lnk resolution failed for %s: %s", lnk_path, exc)
        return None
    if result.returncode != 0:
        logger.debug(
            "lnk resolution non-zero exit for %s: %s",
            lnk_path,
            (result.stderr or "").strip(),
        )
        return None
    target = (result.stdout or "").strip()
    return target or None


def should_skip_dir(dir_path: Path, scan_root: Path) -> bool:
    name = dir_path.name.lower()
    if name in SKIP_DIR_NAMES:
        return True
    # Allow AppData\Local as a scan root; skip nested AppData elsewhere.
    if name == "appdata" and scan_root.name.lower() != "local":
        return True
    # HuggingFace and tool caches commonly live under ".cache".
    if name == ".cache":
        return False
    for marker in SKIP_DIR_SUBSTRINGS:
        if marker in name:
            return True
    return False


def categorize_model(path: Path) -> str:
    text = str(path).lower()
    for category, keywords in MODEL_CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "other"


def is_workflow_json(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    parent_parts = [p.lower() for p in path.parent.parts]
    name_lower = path.name.lower()
    if "workflow" in name_lower:
        return True
    return any(hint in part for part in parent_parts for hint in WORKFLOW_JSON_HINTS)


def is_huggingface_cache_dir(dir_path: Path) -> bool:
    parts = [p.lower() for p in dir_path.parts]
    joined = "/".join(parts)
    if "huggingface" in joined and any(
        marker in joined for marker in ("hub", "cache", "transformers", "diffusers")
    ):
        return True
    return dir_path.name.lower() in {"hub", "transformers", "diffusers"} and any(
        "huggingface" in p.lower() or p.lower() == ".cache" for p in dir_path.parents
    )


def is_comfyui_root(dir_path: Path) -> bool:
    if not dir_path.is_dir():
        return False
    name = dir_path.name.lower()
    if "comfyui" in name or name == "comfy":
        return True
    try:
        children = {child.name.lower() for child in dir_path.iterdir() if child.is_dir()}
    except OSError:
        return False
    if "custom_nodes" in children and "models" in children:
        return True
    main_py = dir_path / "main.py"
    if main_py.is_file() and children.intersection(COMFYUI_MARKERS):
        return True
    return False


def _record_comfyui(dir_path: Path, state: ScanState) -> None:
    key = str(dir_path)
    if key in state._comfyui_seen:
        return
    state._comfyui_seen.add(key)
    state.paths.comfyui_roots.append(key)


def _record_hf_cache(dir_path: Path, state: ScanState) -> None:
    key = str(dir_path)
    if key in state._hf_cache_seen:
        return
    state._hf_cache_seen.add(key)
    state.paths.huggingface_caches.append(key)


def _record_model_dir(dir_path: Path, state: ScanState) -> None:
    key = str(dir_path)
    if key in state._model_dir_seen:
        return
    state._model_dir_seen.add(key)
    state.paths.model_dirs.append(key)


def _record_workflow_dir(dir_path: Path, state: ScanState) -> None:
    key = str(dir_path)
    if key in state._workflow_dir_seen:
        return
    state._workflow_dir_seen.add(key)
    state.paths.workflow_dirs.append(key)


def _record_python_env(dir_path: Path, state: ScanState) -> None:
    key = str(dir_path)
    if key in state._python_env_seen:
        return
    state._python_env_seen.add(key)
    state.paths.python_envs.append(key)


def _record_conda_env(dir_path: Path, state: ScanState) -> None:
    key = str(dir_path)
    if key in state._conda_env_seen:
        return
    state._conda_env_seen.add(key)
    state.paths.conda_envs.append(key)


def _record_model_file(file_path: Path, state: ScanState) -> None:
    category = categorize_model(file_path)
    bucket = getattr(state.models, category)
    bucket.append(str(file_path))
    _record_model_dir(file_path.parent, state)


def inspect_entry(
    entry: os.DirEntry[str],
    *,
    depth: int,
    max_depth: int,
    scan_root: Path,
    state: ScanState,
    verbose: bool,
) -> Iterator[tuple[Path, int]]:
    """Inspect one directory entry; yield subdirectories to recurse into."""
    state.files_inspected += 1
    path = Path(entry.path)

    if entry.is_symlink():
        if verbose:
            logger.debug("skip symlink: %s", path)
        state.skipped_locations.append(str(path))
        return

    if entry.is_file(follow_symlinks=False):
        name_lower = entry.name.lower()
        if name_lower in FFMPEG_NAMES:
            state.paths.ffmpeg_bins.append(str(path))
        elif path.suffix.lower() in MODEL_EXTENSIONS:
            _record_model_file(path, state)
        elif is_workflow_json(path):
            _record_workflow_dir(path.parent, state)
        elif name_lower == "pyvenv.cfg":
            _record_python_env(path.parent, state)
        return

    if not entry.is_dir(follow_symlinks=False):
        return

    if should_skip_dir(path, scan_root):
        state.skipped_locations.append(str(path))
        if verbose:
            logger.debug("skip dir: %s", path)
        return

    if is_comfyui_root(path):
        _record_comfyui(path, state)

    if is_huggingface_cache_dir(path):
        _record_hf_cache(path, state)

    if (path / "conda-meta").is_dir():
        _record_conda_env(path, state)

    if depth < max_depth:
        yield path, depth + 1


def walk_scan_root(
    scan_root: Path,
    *,
    max_depth: int,
    state: ScanState,
    verbose: bool,
) -> None:
    """Walk a single resolved root with depth limit (read-only)."""
    stack: list[tuple[Path, int]] = [(scan_root, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            with os.scandir(current) as entries:
                child_dirs: list[tuple[Path, int]] = []
                for entry in entries:
                    for child_path, child_depth in inspect_entry(
                        entry,
                        depth=depth,
                        max_depth=max_depth,
                        scan_root=scan_root,
                        state=state,
                        verbose=verbose,
                    ):
                        child_dirs.append((child_path, child_depth))
                stack.extend(reversed(child_dirs))
        except PermissionError as exc:
            msg = f"{current}: {exc}"
            state.permission_errors.append(msg)
            logger.warning("permission denied: %s", current)
        except OSError as exc:
            msg = f"{current}: {exc}"
            state.permission_errors.append(msg)
            state.warnings.append(msg)
            logger.warning("os error while scanning %s: %s", current, exc)


def build_scan_report(
    state: ScanState,
    *,
    start_time: datetime,
    end_time: datetime,
    max_depth: int,
    dry_run: bool,
) -> dict[str, Any]:
    paths_dict = state.paths.to_dict()
    models_dict = state.models.to_dict()
    model_count = sum(len(v) for v in models_dict.values())
    tool_count = (
        len(paths_dict["comfyui_roots"])
        + len(paths_dict["ffmpeg_bins"])
        + len(paths_dict["huggingface_caches"])
        + len(paths_dict["python_envs"])
        + len(paths_dict["conda_envs"])
        + len(paths_dict["workflow_dirs"])
    )
    return {
        "scan_start_time": start_time.isoformat(),
        "scan_end_time": end_time.isoformat(),
        "max_depth": max_depth,
        "dry_run": dry_run,
        "scanned_locations": _unique_sorted(state.scanned_locations),
        "skipped_locations": _unique_sorted(state.skipped_locations),
        "missing_locations": _unique_sorted(state.missing_locations),
        "permission_errors": _unique_sorted(state.permission_errors),
        "files_inspected": state.files_inspected,
        "models_found": model_count,
        "tools_found": tool_count,
        "warnings": _unique_sorted(state.warnings),
        "paths_summary": {key: len(value) for key, value in paths_dict.items()},
        "models_summary": {key: len(value) for key, value in models_dict.items()},
    }


def write_scan_outputs(
    state: ScanState,
    report: dict[str, Any],
    output_dir: Path,
    *,
    dry_run: bool,
) -> None:
    if dry_run:
        logger.info("dry-run: skipping write to %s", output_dir)
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "paths.json": state.paths.to_dict(),
        "models.json": state.models.to_dict(),
        "scan_report.json": report,
    }
    for filename, payload in outputs.items():
        target = output_dir / filename
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        logger.info("wrote %s", target)


def run_scan(
    *,
    scan_roots: Iterable[str | Path] | None = None,
    max_depth: int = 5,
    dry_run: bool = False,
    verbose: bool = False,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Run a read-only scan. Safe to call from tests with temporary roots.
    Does not run automatically on import.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(message)s", force=True)

    raw_roots = list(scan_roots) if scan_roots is not None else list(DEFAULT_SCAN_ROOTS)
    out_dir = _normalize_path(output_dir) if output_dir else _default_output_dir()

    start_time = datetime.now(timezone.utc)
    state = ScanState()

    for raw in raw_roots:
        path = _normalize_path(raw)
        if not path.exists():
            state.missing_locations.append(str(path))
            logger.warning("missing location: %s", path)
            continue

    resolved_roots = resolve_scan_roots(raw_roots)
    if not resolved_roots:
        state.warnings.append("no scan roots resolved; nothing to walk")

    for root in resolved_roots:
        state.scanned_locations.append(str(root))
        logger.info("scanning %s (max_depth=%s)", root, max_depth)
        walk_scan_root(root, max_depth=max_depth, state=state, verbose=verbose)

    end_time = datetime.now(timezone.utc)
    report = build_scan_report(
        state,
        start_time=start_time,
        end_time=end_time,
        max_depth=max_depth,
        dry_run=dry_run,
    )
    write_scan_outputs(state, report, out_dir, dry_run=dry_run)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Genesis Studio filesystem scanner."
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=5,
        help="Maximum directory depth to recurse (default: 5).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan without writing genesis/config/*.json outputs.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_depth < 0:
        logger.error("--max-depth must be >= 0")
        return 2
    run_scan(
        max_depth=args.max_depth,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
