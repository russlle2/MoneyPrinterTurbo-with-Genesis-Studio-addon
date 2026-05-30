# Genesis Studio Build Notes
**Phase 0 — Repo Safety & Baseline Inspection**
_Date: 2026-05-30_

---

## 1. Current Repo Structure Summary

```
MoneyPrinterTurbo-with-Genesis-Studio-addon-main/
├── main.py                         ← FastAPI backend entry point
├── config.example.toml             ← Config template (gitignored: config.toml)
├── pyproject.toml                  ← uv-managed deps (Python 3.11–3.12)
├── requirements.txt                ← Legacy pip fallback (same deps)
├── webui.bat / webui.sh            ← Streamlit launchers
│
├── app/                            ← Core MoneyPrinterTurbo backend
│   ├── asgi.py                     ← FastAPI app factory + CORS + static mounts
│   ├── router.py                   ← Registers v1/video and v1/llm routers
│   ├── config/
│   │   └── config.py               ← Loads config.toml, exposes module-level vars
│   ├── controllers/
│   │   ├── v1/video.py             ← REST routes: task start/stop/query, upload
│   │   └── v1/llm.py               ← REST routes: LLM script/term generation
│   ├── models/
│   │   ├── schema.py               ← Pydantic: VideoParams, MaterialInfo, enums
│   │   └── const.py                ← Task state constants, file type lists
│   └── services/
│       ├── task.py                 ← MASTER pipeline: script→terms→audio→subs→materials→render
│       ├── video.py                ← MoviePy/FFmpeg combine + subtitle burn
│       ├── llm.py                  ← LLM script & terms generation (multi-provider)
│       ├── voice.py                ← TTS (edge_tts, Azure, whisper alignment)
│       ├── material.py             ← Pexels/Pixabay download + local media processing
│       ├── subtitle.py             ← SRT generation + correction (whisper)
│       ├── state.py                ← Task state management (memory or Redis)
│       └── upload_post.py          ← Optional TikTok/Instagram cross-post
│
├── webui/
│   ├── Main.py                     ← Streamlit UI (single-page, ~800+ lines)
│   ├── .streamlit/config.toml      ← Streamlit browser settings
│   └── i18n/                       ← Language JSON files (zh, en, de, pt, ru, tr, vi)
│
├── resource/
│   ├── fonts/                      ← .ttf/.ttc fonts for subtitle burn-in
│   └── songs/                      ← Background music .mp3 files
│
├── storage/                        ← Created at runtime, gitignored
│   ├── tasks/{uuid}/               ← Per-task outputs (audio, subs, combined/final .mp4)
│   └── cache_videos/               ← Downloaded Pexels/Pixabay clips
│
├── logs/                           ← Gitignored, created at runtime
│
├── test/                           ← Existing pytest suite
│   └── services/                   ← Tests for llm, material, state, task, video, voice
│
├── docs/                           ← Documentation + Jupyter notebook
└── CURSOR_GENESIS_MASTER_PLAN.md/  ← NOTE: Windows made this a directory; contains .txt inside
```

**Note:** `CURSOR_GENESIS_MASTER_PLAN.md` was created by Windows as a directory with a `.txt` file inside (`CURSOR_GENESIS_MASTER_PLAN.md.txt`). The Read tool sees it as a directory. Use `Get-Content` to read it. This does not affect the build.

---

## 2. MoneyPrinterTurbo Pipeline — How It Actually Works

Understanding the exact flow is critical before adding any Genesis layer.

### 2a. Two Entry Points (they are independent)

| Entry Point | Runtime | Purpose |
|---|---|---|
| `main.py` | uvicorn/FastAPI on `:8080` | REST API backend |
| `webui/Main.py` | Streamlit on `:8501` | Browser UI |

The Streamlit UI talks to the FastAPI backend via HTTP (`http://127.0.0.1:8080`). Both must run simultaneously for the full UI experience.

### 2b. Task Pipeline (`app/services/task.start()`)

```
start(task_id, params: VideoParams)
  1. generate_script()    → LLM → video_script (str)
  2. generate_terms()     → LLM → video_terms (list[str])
  3. generate_audio()     → edge_tts or custom → audio.mp3 + sub_maker
  4. generate_subtitle()  → edge_tts subtitles or whisper → subtitle.srt
  5. get_video_materials() → Pexels/Pixabay download or local → list[str paths]
  6. generate_final_videos() → MoviePy combine + FFmpeg subtitle burn → final-N.mp4
  7. (optional) upload_post.cross_post_video()
```

The pipeline supports `stop_at` checkpoints: `"script"`, `"terms"`, `"audio"`, `"subtitle"`, `"materials"`, `"video"`.

### 2c. Config System

Config is loaded once at import from `config.toml` (auto-created from `config.example.toml`). Keys are exposed as module-level vars in `app/config/config.py`:

```python
from app.config import config
config.app.get("ffmpeg_path", "")      # dict of [app] section
config.listen_port                      # top-level key
config.ui.get("hide_log", False)       # dict of [ui] section
```

Sections in `config.example.toml`: `[app]`, `[whisper]`, `[proxy]`, `[azure]`, `[siliconflow]`, `[ui]`

### 2d. Storage Layout (created at runtime)

```python
utils.storage_dir()               → ./storage/
utils.storage_dir("tasks")        → ./storage/tasks/
utils.task_dir(task_id)           → ./storage/tasks/{uuid}/
utils.storage_dir("cache_videos") → ./storage/cache_videos/
utils.storage_dir("local_videos") → ./storage/local_videos/
utils.public_dir()                → ./resource/public/
```

### 2e. Existing Dependencies (already available to Genesis)

From `pyproject.toml`:
- `moviepy==2.1.2` + FFmpeg — video editing and rendering
- `faster-whisper==1.1.0` — local whisper STT (word-level timestamps)
- `loguru==0.7.3` — structured logging
- `pydantic` (via fastapi) — schema validation
- `openai==1.56.1` — OpenAI-compatible API client
- `requests==2.33.1` — HTTP client
- `pyyaml==6.0.3` — YAML parsing
- `streamlit==1.45.0` — WebUI framework

**Not yet installed (Genesis will need):**
- `playwright` — Diffus.me browser automation
- `elevenlabs` — voiceover API
- `toml` — already used by config.py (stdlib `tomllib` in 3.11+, or `toml` package)

---

## 3. Files That Must NOT Be Directly Edited

These files are the protected core. Genesis must never modify them unless a specific, justified edit is explicitly approved.

| File | Reason |
|---|---|
| `app/services/task.py` | Master pipeline orchestrator — all steps |
| `app/services/video.py` | MoviePy/FFmpeg assembly — complex, brittle |
| `app/services/llm.py` | Multi-provider LLM abstraction |
| `app/services/voice.py` | TTS + subtitle alignment |
| `app/services/material.py` | Pexels/Pixabay fetch + preprocessing |
| `app/services/subtitle.py` | Whisper subtitle creation |
| `app/services/state.py` | Task state machine (memory/Redis) |
| `app/asgi.py` | FastAPI app + CORS + static mounts |
| `app/models/schema.py` | Pydantic schemas used by all services |
| `app/models/const.py` | Task state constants |
| `webui/Main.py` | Single-file Streamlit UI |
| `main.py` | Backend entry point |
| `webui.bat` / `webui.sh` | Launchers |
| `pyproject.toml` | Dep versions (add only, never change existing) |
| `requirements.txt` | Legacy pip mirror of pyproject |
| `config.example.toml` | Config template (safe to add new section) |

**Minimal-touch files** (one line addition acceptable with care):
| File | Acceptable Change |
|---|---|
| `app/router.py` | **DO NOT TOUCH** until `genesis/api/__init__.py` exists, imports cleanly, and has been verified. Add `include_router` only after that gate passes. |
| `config.example.toml` | Append a `[genesis]` section at the bottom |
| `.gitignore` | Append new ignore patterns |

---

## 4. Proposed Advanced-Mode Integration Point

### Strategy: Streamlit Multi-Page App (Zero-Touch to Main.py)

Streamlit natively supports multi-page apps. Any `.py` file placed in a `pages/` subdirectory next to the main script automatically appears as a sidebar navigation entry — **with no modification to `webui/Main.py`**.

**This is the cleanest possible integration path.**

```
webui/
  Main.py                    ← UNCHANGED
  pages/
    Genesis_Studio.py        ← NEW: appears automatically in Streamlit sidebar
  i18n/
  .streamlit/
```

The Genesis Studio page loads independently. It can:
- Import from `genesis/` package freely
- Access `app.config.config` for shared config
- Call `genesis.mpt_bridge.run_genesis_from_mpt()` for pipeline execution
- Run its own task loop with no interference with existing tasks

### Strategy: FastAPI Router Extension (Deferred — Do Not Touch Yet)

`app/router.py` must not be modified until all of the following gates are met:

1. `genesis/api/__init__.py` exists and defines `genesis_router`
2. All imports inside `genesis/api/` are verified to not raise at import time
3. All Genesis dependencies required by the router are installed in the venv
4. The router has been manually import-tested in isolation: `python -c "from genesis.api import genesis_router; print('ok')"`

Only after all four gates pass, add one line to `app/router.py`:

```python
# app/router.py — add ONLY after genesis/api import gate passes
from genesis.api import genesis_router
root_api_router.include_router(genesis_router, prefix="/genesis")
```

All Genesis API routes live under `/genesis/` — completely separate namespace.

**Until that gate passes, Genesis has no REST presence and the existing backend is completely unaffected.**

### Strategy: Config Extension (Zero-Touch)

Append a `[genesis]` section to `config.example.toml`:

```toml
[genesis]
enabled = false
# ... genesis-specific settings
```

Read in `genesis/utils/config_loader.py` — Genesis manages its own config loading and never touches the existing `app/config/config.py` loader.

### Strategy: Feature Flag

Set `GENESIS_STUDIO_ENABLED=true` as an env var or `genesis.enabled = true` in `config.toml`. Genesis checks this flag at startup. If false, the page still shows but displays a "not enabled" message.

---

## 5. Proposed `genesis/` Root Package Structure

Based on the master plan and this codebase inspection, the `genesis/` package should be placed at repo root (sibling to `app/`, `webui/`):

```
genesis/
  __init__.py
  mpt_bridge.py              ← Bridge: exposes run_genesis_from_mpt()
  agents/
    __init__.py
    director_agent.py
    scene_agent.py
    asset_agent.py
    caption_agent.py
    timeline_agent.py
  integrations/
    __init__.py
    comfyui_client.py
    cogvideox_client.py
    svd_client.py
    animatediff_client.py
    hotshotxl_client.py
    motionctrl_client.py
    elevenlabs_client.py
    diffusme_playwright.py
    hero_shot_provider.py
    comfyui_workflows/        ← Blueprint JSONs (AnimateDiff, SVD, CogVideoX, etc.)
  pipeline/
    __init__.py
    ingest_transcript.py
    generate_assets.py
    generate_scenes.py
    generate_voiceover.py
    assemble_timeline.py
    render_video.py
    run_genesis.py            ← CLI entry: python -m genesis.pipeline.run_genesis
  captions/
    __init__.py
    whisper_align.py          ← Wraps faster-whisper (already installed)
    kinetic_captions.py
    caption_styles.json
  utils/
    __init__.py
    logger.py                 ← Loguru wrapper with genesis/ log dir
    config_loader.py          ← Reads [genesis] from config.toml + env vars
    file_scanner.py           ← Detects ComfyUI/FFmpeg/models (read-only)
    credit_tracker.py         ← Hourly/daily limit tracker for Diffus.me
  schemas/
    __init__.py
    core.py                   ← Pydantic: Scene, Timeline, Asset, RenderJob, etc.
  config/
    .gitkeep
    example_elevenlabs.json
    example_diffusme.json
    example_genesis_settings.json
  tests/
    __init__.py
    fixtures/
      sample_transcript.txt
    test_file_scanner.py
    test_config_loader.py
    test_credit_tracker.py
    test_timeline_schema.py
    test_agents_basic.py
    test_comfyui_validation.py
    test_pipeline_dry_run.py
  api/
    __init__.py               ← Exposes genesis_router (FastAPI APIRouter)
  README.md
  SETUP.md
  USAGE.md
  TROUBLESHOOTING.md

assets/
  images/
  videos/
  audio/
  renders/
    enhanced/
  imports/
    resolved_workflows/
    diffusme_manual_prompts/
    timeline.json
  manual_hero_shots/
    imports/
```

---

## 6. Critical Shared Resources Already in Repo

These MoneyPrinterTurbo utilities are safe for Genesis to import without modification:

| Import | What it provides |
|---|---|
| `from app.config import config` | Access to `config.toml` values |
| `from app.utils.utils import storage_dir, task_dir` | Standard storage paths |
| `from app.models.const import TASK_STATE_*` | Task state constants |
| `from loguru import logger` | Already configured by the app |

Genesis should use these when appropriate rather than reimplementing them.

The `faster-whisper` package is already installed — `genesis/captions/whisper_align.py` can use it directly.

MoviePy 2.x and FFmpeg are already configured — `genesis/pipeline/render_video.py` can use the same patterns as `app/services/video.py`.

---

## 7. Key Risks and Guard Rails

### Risk 1: `CURSOR_GENESIS_MASTER_PLAN.md` is a directory
Windows created this as a directory, not a file. Do not try to open it with the Read tool. Its content is in `CURSOR_GENESIS_MASTER_PLAN.md\CURSOR_GENESIS_MASTER_PLAN.md.txt`. This is a Windows quirk — does not affect any build file.

### Risk 2: config.toml is gitignored but required
The file `config.toml` is created automatically on first run from `config.example.toml`. Genesis must not assume it exists during CI or fresh clone. `genesis/utils/config_loader.py` must handle the missing file gracefully.

### Risk 3: Python env isolation
The project uses `uv` with `.venv`. Genesis dependencies (playwright, elevenlabs, etc.) must be added to `pyproject.toml` as optional extras — do not `pip install` directly or create a second venv. Command: `uv add --optional genesis <package>`.

### Risk 4: Streamlit session state
`webui/Main.py` uses `st.session_state` extensively. The Genesis Studio page in `webui/pages/Genesis_Studio.py` has its own isolated session state namespace — no interference possible.

### Risk 5: FFmpeg path
MoneyPrinterTurbo reads `ffmpeg_path` from `config.toml` and sets `IMAGEIO_FFMPEG_EXE`. Genesis must read the same env var or `genesis/config/paths.json` (from the file scanner) when calling FFmpeg directly, to avoid conflicts with whatever path was configured.

### Risk 6: `logs/` directory
`logs/` is gitignored. Genesis must create `logs/genesis/` under it programmatically — do not assume it exists.

---

## 8. Genesis-Exclusive Storage (No Collision with MPT)

| Path | Owner | Purpose |
|---|---|---|
| `storage/tasks/` | MoneyPrinterTurbo | Per-task render outputs |
| `storage/cache_videos/` | MoneyPrinterTurbo | Pexels/Pixabay cache |
| `genesis/config/` | Genesis | Scanned paths, models, settings |
| `assets/` | Genesis | Images, videos, audio, renders |
| `logs/genesis/` | Genesis | Structured logs |

Genesis never reads or writes inside `storage/tasks/` except via `mpt_bridge.py` which calls MPT's own `task.start()`.

---

## 9. Phase Execution Order

Per the master plan, proceed strictly in this order after Phase 0:

1. **Phase 1** — Create the `genesis/` folder structure and `assets/` folder. Add `.gitignore` entries.
2. **Phase 2** — `genesis/utils/file_scanner.py` — read-only scanner for tools/models.
3. **Phase 3** — `genesis/schemas/core.py` — Pydantic schemas.
4. **Phase 4** — `genesis/utils/logger.py` + `genesis/utils/config_loader.py`.
5. **Phase 5** — `genesis/integrations/comfyui_client.py`.
6. Continue per master plan...

**Do not start Phase 1 until this document is reviewed and Phase 0 is signed off.**

---

## 10. One-Line Summary

> MoneyPrinterTurbo is a FastAPI backend + Streamlit frontend connected via HTTP. The core pipeline in `app/services/task.py` must be treated as a black box. Genesis Studio can be added as a **Streamlit multi-page entry** (`webui/pages/Genesis_Studio.py`) and a **root-level `genesis/` package**, with a single bridge module (`genesis/mpt_bridge.py`) for MPT interop — all with zero modifications to any existing core file.
