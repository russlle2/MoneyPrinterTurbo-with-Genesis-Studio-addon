"""
Genesis Studio — UI launcher.

Usage:
    python -m genesis.ui.launch_ui
    python -m genesis.ui.launch_ui --port 8502
    python -m genesis.ui.launch_ui --no-browser
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path
import time

_REPO = Path(__file__).resolve().parents[2]
_UI_MODULE = Path(__file__).resolve().parent / "creator_ui.py"


def _find_streamlit() -> str | None:
    """Return path to streamlit executable or None."""
    venv_scripts = _REPO / ".venv" / "Scripts"
    for name in ("streamlit.exe", "streamlit"):
        p = venv_scripts / name
        if p.is_file():
            return str(p)
    # Fallback: system PATH
    import shutil
    return shutil.which("streamlit")


def launch(
    *,
    port: int = 8501,
    open_browser: bool = True,
    host: str = "localhost",
) -> None:
    streamlit_bin = _find_streamlit()
    if not streamlit_bin:
        print("ERROR: Streamlit not found.")
        print("Install it with: pip install streamlit")
        sys.exit(1)

    url = f"http://{host}:{port}"
    print(f"\n{'='*50}")
    print("  Genesis Studio Creator UI")
    print(f"{'='*50}")
    print(f"  URL:  {url}")
    print(f"  File: {_UI_MODULE}")
    print(f"{'='*50}\n")

    cmd = [
        streamlit_bin,
        "run",
        str(_UI_MODULE),
        "--server.port", str(port),
        "--server.headless", "true",
        "--server.address", host,
        "--browser.gatherUsageStats", "false",
    ]

    proc = subprocess.Popen(cmd)

    if open_browser:
        # Wait briefly for server startup
        time.sleep(2)
        try:
            webbrowser.open(url)
            print(f"Browser opened: {url}")
        except Exception:
            print(f"Could not open browser automatically.")
            print(f"Open manually: {url}")

    print("Press Ctrl+C to stop the UI.\n")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\nGenesis Studio UI stopped.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Launch Genesis Studio Creator UI",
        prog="genesis.ui.launch_ui",
    )
    p.add_argument("--port", type=int, default=8501, help="Port to run on (default: 8501)")
    p.add_argument("--host", default="localhost", help="Host to bind to (default: localhost)")
    p.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = p.parse_args(argv)
    launch(port=args.port, host=args.host, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
