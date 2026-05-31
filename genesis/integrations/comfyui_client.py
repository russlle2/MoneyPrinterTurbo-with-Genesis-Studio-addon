"""
Genesis Studio — ComfyUI HTTP client.

Import-safe: no network calls on import. ComfyUI must be running separately.
All functions raise RuntimeError with clear messages on failure rather than
silently returning empty results.

Supports two workflow JSON shapes:
  1. Node-dict format  {"1": {"class_type": "...", "inputs": {...}}, ...}
  2. Nodes-list format {"nodes": [{"type": "...", ...}, ...], ...}
"""

from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import requests

from genesis.utils.config_loader import load_genesis_settings
from genesis.utils.logger import get_logger

logger = get_logger("comfyui_client")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_BASE_URL = "http://127.0.0.1:8188"
_RESOLVED_WORKFLOW_DIR = _REPO_ROOT / "assets" / "imports" / "resolved_workflows"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _base_url(override: str | None = None) -> str:
    if override:
        return override.rstrip("/")
    settings = load_genesis_settings()
    return settings.get("comfyui_url", _DEFAULT_BASE_URL).rstrip("/")


def _load_workflow_file(workflow_path: str) -> dict[str, Any]:
    path = Path(workflow_path)
    if not path.is_file():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow must be a JSON object, got: {type(data).__name__}")
    return data


def _extract_node_types(workflow: dict[str, Any]) -> list[str]:
    """
    Extract all class_type / type strings from a workflow regardless of shape.
    Returns a deduplicated sorted list.
    """
    found: set[str] = set()

    # Shape 1: {"1": {"class_type": "X", ...}, ...}
    for value in workflow.values():
        if isinstance(value, dict):
            ct = value.get("class_type")
            if isinstance(ct, str) and ct:
                found.add(ct)

    # Shape 2: {"nodes": [{"type": "X", ...}, ...], ...}
    nodes_list = workflow.get("nodes")
    if isinstance(nodes_list, list):
        for node in nodes_list:
            if isinstance(node, dict):
                t = node.get("type")
                if isinstance(t, str) and t:
                    found.add(t)

    return sorted(found)


def _apply_replacements(workflow: dict[str, Any], replacements: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively replace placeholder strings in a deep-copied workflow.
    Only string values are replaced; keys are not modified.
    """
    copy = deepcopy(workflow)

    def _walk(obj: Any) -> Any:
        if isinstance(obj, str):
            for placeholder, value in replacements.items():
                obj = obj.replace(placeholder, str(value))
            return obj
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        return obj

    return _walk(copy)  # type: ignore[return-value]


def _collect_output_paths(history_entry: dict[str, Any], output_dir: Path) -> list[str]:
    """
    Parse a ComfyUI history entry and return any output file paths that can be
    located under output_dir or the ComfyUI output directory recorded in the entry.
    """
    found: list[str] = []
    outputs = history_entry.get("outputs", {})

    for _node_id, node_out in outputs.items():
        if not isinstance(node_out, dict):
            continue
        # images / videos / audio keys all share the same list structure
        for _media_key, items in node_out.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename") or item.get("name")
                subfolder = item.get("subfolder", "")
                if not filename:
                    continue
                # Try output_dir first, then any absolute path in the item
                candidate = Path(output_dir) / subfolder / filename
                if candidate.is_file():
                    found.append(str(candidate))
                elif "abs_path" in item and Path(item["abs_path"]).is_file():
                    found.append(item["abs_path"])
                else:
                    # Log the reference even if we cannot resolve it locally
                    logger.warning(
                        "output file referenced but not found locally: %s/%s",
                        subfolder,
                        filename,
                    )
                    found.append(str(candidate))  # include path so caller can inspect

    return found


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_comfyui_available(base_url: str | None = None) -> bool:
    """
    Return True if ComfyUI is reachable at base_url.
    Never raises; logs the reason if unavailable.
    """
    url = _base_url(base_url)
    try:
        resp = requests.get(f"{url}/object_info", timeout=5)
        if resp.status_code == 200:
            logger.info("ComfyUI available at %s", url)
            return True
        logger.warning("ComfyUI at %s returned HTTP %s", url, resp.status_code)
        return False
    except requests.exceptions.ConnectionError:
        logger.warning("ComfyUI not reachable at %s (connection refused)", url)
        return False
    except requests.exceptions.Timeout:
        logger.warning("ComfyUI at %s timed out during availability check", url)
        return False
    except requests.exceptions.RequestException as exc:
        logger.warning("ComfyUI availability check failed: %s", exc)
        return False


def get_available_nodes(base_url: str | None = None) -> dict[str, Any]:
    """
    Fetch /object_info and return the raw dict of registered node class names.
    Raises RuntimeError if ComfyUI is not reachable or returns unexpected data.
    """
    url = _base_url(base_url)
    try:
        resp = requests.get(f"{url}/object_info", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError(
                f"ComfyUI /object_info returned unexpected type: {type(data).__name__}"
            )
        logger.info("fetched %d node types from ComfyUI at %s", len(data), url)
        return data
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"ComfyUI not reachable at {url}. "
            "Start ComfyUI first: python main.py (in your ComfyUI directory)."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"ComfyUI at {url} timed out fetching /object_info.") from exc
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(
            f"ComfyUI /object_info returned error: {exc.response.status_code}"
        ) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ComfyUI /object_info returned non-JSON response: {exc}") from exc


def validate_workflow(
    workflow_path: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    """
    Validate that every node type in the workflow is installed in ComfyUI.

    Returns a validation result dict with keys:
      ok, workflow_path, required_node_types, available_node_types_count,
      missing_node_types, warnings, errors
    """
    result: dict[str, Any] = {
        "ok": False,
        "workflow_path": workflow_path,
        "required_node_types": [],
        "available_node_types_count": 0,
        "missing_node_types": [],
        "warnings": [],
        "errors": [],
    }

    # Load workflow
    try:
        workflow = _load_workflow_file(workflow_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        result["errors"].append(str(exc))
        return result

    required = _extract_node_types(workflow)
    result["required_node_types"] = required

    if not required:
        result["warnings"].append(
            "No node types detected in workflow. "
            "Check that the workflow uses class_type (dict format) or type (nodes-list format)."
        )

    # Fetch available nodes
    try:
        available = get_available_nodes(base_url)
    except RuntimeError as exc:
        result["errors"].append(str(exc))
        return result

    result["available_node_types_count"] = len(available)
    missing = [n for n in required if n not in available]
    result["missing_node_types"] = missing

    if missing:
        result["errors"].append(
            f"Missing {len(missing)} custom node(s): {', '.join(missing)}. "
            "Install them via ComfyUI Manager before running this workflow."
        )
    else:
        result["ok"] = True
        logger.info(
            "workflow validation passed: %s (%d nodes, 0 missing)",
            workflow_path,
            len(required),
        )

    return result


def resolve_workflow_placeholders(
    workflow_path: str,
    replacements: dict[str, Any],
    output_path: str | None = None,
) -> dict[str, Any]:
    """
    Apply string replacements to a workflow blueprint and return the resolved dict.
    The original blueprint file is never modified.
    If output_path is given, the resolved workflow is also written there.
    """
    workflow = _load_workflow_file(workflow_path)
    resolved = _apply_replacements(workflow, replacements)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            json.dump(resolved, fh, indent=2)
            fh.write("\n")
        logger.info("resolved workflow written to %s", out)

    return resolved


def run_workflow(
    workflow_path: str,
    replacements: dict[str, Any],
    output_dir: str,
    base_url: str | None = None,
    timeout_sec: int = 600,
) -> list[str]:
    """
    Validate, resolve placeholders, submit to ComfyUI, poll until completion,
    and return a list of output file paths.

    Raises RuntimeError on:
      - ComfyUI unavailable
      - validation failure (missing nodes)
      - prompt submission failure
      - polling timeout
    """
    url = _base_url(base_url)

    # 1. Availability check
    if not check_comfyui_available(url):
        raise RuntimeError(
            f"ComfyUI is not available at {url}. "
            "Start ComfyUI before running a workflow."
        )

    # 2. Validation
    validation = validate_workflow(workflow_path, base_url=url)
    if not validation["ok"]:
        missing = validation["missing_node_types"]
        errors = validation["errors"]
        detail = "; ".join(errors) if errors else f"missing nodes: {missing}"
        raise RuntimeError(
            f"Workflow validation failed for {workflow_path}. {detail}"
        )

    # 3. Resolve placeholders
    stem = Path(workflow_path).stem
    resolved_dir = _RESOLVED_WORKFLOW_DIR
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_path = resolved_dir / f"{stem}_resolved_{uuid.uuid4().hex[:8]}.json"
    resolved = resolve_workflow_placeholders(
        workflow_path, replacements, output_path=str(resolved_path)
    )

    # 4. Submit prompt
    client_id = uuid.uuid4().hex
    payload = {"prompt": resolved, "client_id": client_id}

    try:
        resp = requests.post(f"{url}/prompt", json=payload, timeout=30)
        resp.raise_for_status()
        submit_data = resp.json()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Failed to submit prompt to ComfyUI: {exc}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ComfyUI /prompt returned non-JSON response: {exc}") from exc

    prompt_id = submit_data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(
            f"ComfyUI /prompt did not return a prompt_id. Response: {submit_data}"
        )

    logger.info("submitted prompt %s to ComfyUI at %s", prompt_id, url)

    # 5. Poll /history/{prompt_id}
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_sec
    poll_interval = 2.0

    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        try:
            hist_resp = requests.get(f"{url}/history/{prompt_id}", timeout=15)
            hist_resp.raise_for_status()
            history = hist_resp.json()
        except requests.exceptions.RequestException as exc:
            logger.warning("polling /history failed (will retry): %s", exc)
            continue
        except (ValueError, json.JSONDecodeError):
            logger.warning("polling /history returned non-JSON (will retry)")
            continue

        if prompt_id not in history:
            logger.debug("prompt %s not yet in history", prompt_id)
            continue

        entry = history[prompt_id]
        status = entry.get("status", {})
        status_str = status.get("status_str", "")

        if status_str in ("error", "cancelled"):
            messages = status.get("messages", [])
            raise RuntimeError(
                f"ComfyUI execution failed for prompt {prompt_id}. "
                f"Status: {status_str}. Messages: {messages}"
            )

        if status.get("completed", False) or status_str == "success":
            output_paths = _collect_output_paths(entry, out_dir)
            logger.info(
                "prompt %s completed with %d output(s)", prompt_id, len(output_paths)
            )
            return output_paths

    raise RuntimeError(
        f"ComfyUI workflow timed out after {timeout_sec}s for prompt {prompt_id}."
    )
