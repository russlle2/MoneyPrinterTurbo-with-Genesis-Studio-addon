"""
Genesis Studio pipeline — orchestration after script and scene planning.

Import-safe: no API calls on import.
"""

from genesis.pipeline.narration import (
    generate_narration_from_script,
    run_post_script_steps,
)

__all__ = [
    "generate_narration_from_script",
    "run_post_script_steps",
]
