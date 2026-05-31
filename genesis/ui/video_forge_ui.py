# -*- coding: utf-8 -*-
"""
Genesis Forge UI - Video generation from text, images, or both.
Three modes. No captions. No voiceover. No script generation.

Launch: python -m genesis.ui.video_forge_ui
     or: streamlit run genesis/ui/video_forge_ui.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path regardless of how Streamlit was launched
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import shutil
import tempfile
import threading
import uuid

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Genesis Forge",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background: #0d0d0d; }
    .main .block-container { padding-top: 1.5rem; max-width: 1100px; }
    h1 { color: #f0f0f0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.5px; }
    h2, h3 { color: #e0e0e0; }
    .stTabs [data-baseweb="tab-list"] { gap: 12px; background: #1a1a1a; padding: 8px 12px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { color: #888; font-weight: 600; font-size: 1rem; padding: 8px 20px; border-radius: 8px; }
    .stTabs [aria-selected="true"] { background: #e63946 !important; color: #fff !important; }
    .stButton > button {
        background: linear-gradient(135deg, #e63946, #c1121f);
        color: white; border: none; border-radius: 8px;
        font-size: 1.05rem; font-weight: 700; padding: 0.6rem 2rem;
        width: 100%; transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.88; }
    .stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background: #1e1e1e !important; color: #f0f0f0 !important;
        border: 1px solid #333 !important; border-radius: 8px !important;
    }
    .stSlider { color: #f0f0f0; }
    .status-box {
        background: #1a1a1a; border-left: 4px solid #e63946;
        padding: 0.8rem 1.2rem; border-radius: 0 8px 8px 0;
        margin: 0.5rem 0; color: #ddd;
    }
    .engine-badge {
        display: inline-block; background: #222; color: #aaa;
        font-size: 0.78rem; padding: 3px 10px; border-radius: 20px;
        border: 1px solid #333; margin-top: 4px;
    }
    .comfyui-badge-ok {
        display: inline-block; background: #1a3a1a; color: #4caf50;
        font-size: 0.8rem; padding: 4px 12px; border-radius: 20px;
        border: 1px solid #4caf50;
    }
    .comfyui-badge-off {
        display: inline-block; background: #2a1a1a; color: #ff7043;
        font-size: 0.8rem; padding: 4px 12px; border-radius: 20px;
        border: 1px solid #ff7043;
    }
    div[data-testid="stFileUploader"] {
        background: #1a1a1a; border: 2px dashed #444;
        border-radius: 10px; padding: 1rem;
    }
    .scene-card {
        background: #1a1a1a; border: 1px solid #333;
        border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------
def _init_state(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default

_init_state("t2v_result", None)
_init_state("i2v_result", None)
_init_state("hyb_result", None)
_init_state("t2v_running", False)
_init_state("i2v_running", False)
_init_state("hyb_running", False)
_init_state("hyb_scenes", [])


# ---------------------------------------------------------------------------
# ComfyUI status check (cached per session)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=10)
def _comfyui_status() -> tuple[bool, str]:
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2)
        return True, "ComfyUI connected — real AI video enabled"
    except Exception:
        return False, "ComfyUI offline — using Pollinations FLUX + animation"


def _comfyui_badge() -> str:
    ok, msg = _comfyui_status()
    if ok:
        return f'<span class="comfyui-badge-ok">&#9679; {msg}</span>'
    return f'<span class="comfyui-badge-off">&#9679; {msg}</span>'


def _save_uploads(uploaded_files, subdir: str) -> list[str]:
    """Save Streamlit UploadedFile objects to a temp directory and return paths."""
    out_dir = Path(tempfile.mkdtemp()) / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in uploaded_files:
        dest = out_dir / f.name
        dest.write_bytes(f.read())
        paths.append(str(dest))
    return paths


# ---------------------------------------------------------------------------
# Generation runners — defined before tab code so they are in scope on rerun
# ---------------------------------------------------------------------------

def _ar_key(ar_string: str) -> str:
    return ar_string.split(" ")[0]


def _run_t2v_generation(prompt, style, ar, duration, anim, transition):
    from genesis.forge.core import text_to_video

    progress_bar = st.progress(0.0)
    status = st.empty()

    def _cb(msg: str, frac: float):
        progress_bar.progress(min(frac, 1.0))
        status.markdown(f'<div class="status-box">{msg}</div>', unsafe_allow_html=True)

    try:
        result = text_to_video(
            prompt=prompt,
            style=style,
            duration_seconds=float(duration),
            aspect_ratio=_ar_key(ar),
            animation_style=anim,
            transition_style=transition,
            progress_cb=_cb,
        )
        st.session_state.t2v_result = {
            "success": result.success,
            "output_path": result.output_path,
            "engine": result.engine_used,
            "elapsed": result.elapsed_seconds,
            "error": result.error,
            "warnings": result.warnings,
        }
    except Exception as e:
        st.session_state.t2v_result = {
            "success": False, "error": str(e), "output_path": "",
            "engine": "", "elapsed": 0, "warnings": [],
        }
    finally:
        progress_bar.empty()
        status.empty()
        st.session_state.t2v_running = False
        st.rerun()


def _run_i2v_generation(uploaded_files, anim, transition, dur, ar, use_ai):
    from genesis.forge.core import images_to_video

    progress_bar = st.progress(0.0)
    status = st.empty()

    def _cb(msg: str, frac: float):
        progress_bar.progress(min(frac, 1.0))
        status.markdown(f'<div class="status-box">{msg}</div>', unsafe_allow_html=True)

    try:
        image_paths = _save_uploads(uploaded_files, "i2v_input")
        result = images_to_video(
            image_paths=image_paths,
            animation_style=anim,
            transition_style=transition,
            duration_per_image=float(dur),
            aspect_ratio=_ar_key(ar),
            use_ai_animation=use_ai,
            progress_cb=_cb,
        )
        st.session_state.i2v_result = {
            "success": result.success,
            "output_path": result.output_path,
            "engine": result.engine_used,
            "elapsed": result.elapsed_seconds,
            "error": result.error,
            "warnings": result.warnings,
        }
    except Exception as e:
        st.session_state.i2v_result = {
            "success": False, "error": str(e), "output_path": "",
            "engine": "", "elapsed": 0, "warnings": [],
        }
    finally:
        progress_bar.empty()
        status.empty()
        st.session_state.i2v_running = False
        st.rerun()


def _run_hyb_generation(transition, ar):
    from genesis.forge.core import hybrid_video, HybridScene

    progress_bar = st.progress(0.0)
    status = st.empty()

    def _cb(msg: str, frac: float):
        progress_bar.progress(min(frac, 1.0))
        status.markdown(f'<div class="status-box">{msg}</div>', unsafe_allow_html=True)

    try:
        scenes = []
        for s in st.session_state.hyb_scenes:
            if not s["content"].strip():
                continue
            scenes.append(HybridScene(
                kind=s["kind"],
                content=s["content"],
                duration_seconds=float(s["duration"]),
                style=s.get("style", "cinematic"),
                animation=s.get("animation", "ken_burns"),
            ))

        if not scenes:
            st.session_state.hyb_result = {
                "success": False, "error": "No valid scenes to generate.",
                "output_path": "", "engine": "", "elapsed": 0, "warnings": [],
            }
            return

        result = hybrid_video(
            scenes=scenes,
            transition_style=transition,
            aspect_ratio=_ar_key(ar),
            progress_cb=_cb,
        )
        st.session_state.hyb_result = {
            "success": result.success,
            "output_path": result.output_path,
            "engine": result.engine_used,
            "elapsed": result.elapsed_seconds,
            "error": result.error,
            "warnings": result.warnings,
        }
    except Exception as e:
        st.session_state.hyb_result = {
            "success": False, "error": str(e), "output_path": "",
            "engine": "", "elapsed": 0, "warnings": [],
        }
    finally:
        progress_bar.empty()
        status.empty()
        st.session_state.hyb_running = False
        st.rerun()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("# Genesis Forge")
st.markdown(_comfyui_badge(), unsafe_allow_html=True)
st.markdown("")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_t2v, tab_i2v, tab_hyb = st.tabs([
    "Text to Video",
    "Images to Video",
    "Hybrid",
])


# ============================================================
# TAB 1 — TEXT TO VIDEO
# ============================================================
with tab_t2v:
    st.markdown("### Describe your video")
    st.markdown("Type a prompt. Genesis generates AI images and animates them into a video.")
    st.markdown("")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        t2v_prompt = st.text_area(
            "Video prompt",
            placeholder="A lone wolf runs across a snow-covered mountain ridge at golden hour, cinematic slow motion...",
            height=140,
            label_visibility="collapsed",
            key="t2v_prompt",
        )

        col_style, col_ar = st.columns(2)
        with col_style:
            t2v_style = st.selectbox(
                "Visual style",
                ["cinematic", "photorealistic", "anime", "vibrant", "dark", "abstract"],
                key="t2v_style",
            )
        with col_ar:
            t2v_ar = st.selectbox(
                "Aspect ratio",
                ["9:16 (Vertical)", "16:9 (Landscape)", "1:1 (Square)"],
                key="t2v_ar",
            )

        col_dur, col_scenes = st.columns(2)
        with col_dur:
            t2v_duration = st.select_slider(
                "Duration",
                options=[5, 10, 15, 20, 30],
                value=10,
                format_func=lambda x: f"{x}s",
                key="t2v_duration",
            )
        with col_scenes:
            t2v_anim = st.selectbox(
                "Animation",
                ["ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right"],
                format_func=lambda x: x.replace("_", " ").title(),
                key="t2v_anim",
            )

        t2v_transition = st.radio(
            "Transition",
            ["fade", "dissolve", "cut"],
            horizontal=True,
            format_func=lambda x: x.title(),
            key="t2v_transition",
        )

        if st.button("Generate Video", key="t2v_go", disabled=st.session_state.t2v_running):
            if not t2v_prompt.strip():
                st.error("Enter a prompt first.")
            else:
                st.session_state.t2v_running = True
                st.session_state.t2v_result = None
                st.rerun()

    with col_right:
        if st.session_state.t2v_running:
            _run_t2v_generation(t2v_prompt, t2v_style, t2v_ar, t2v_duration, t2v_anim, t2v_transition)

        if st.session_state.t2v_result:
            r = st.session_state.t2v_result
            if r["success"]:
                st.success(f"Done in {r['elapsed']:.1f}s")
                st.video(r["output_path"])
                with open(r["output_path"], "rb") as f:
                    st.download_button(
                        "Download MP4",
                        f,
                        file_name=Path(r["output_path"]).name,
                        mime="video/mp4",
                    )
                st.markdown(f'<div class="engine-badge">Engine: {r["engine"]}</div>', unsafe_allow_html=True)
                if r.get("warnings"):
                    for w in r["warnings"]:
                        st.info(w)
            else:
                st.error(f"Generation failed: {r['error']}")
        elif not st.session_state.t2v_running:
            st.markdown("""
            <div style="background:#1a1a1a;border-radius:10px;padding:2rem;text-align:center;color:#555;min-height:300px;display:flex;align-items:center;justify-content:center;">
                <div>
                    <div style="font-size:3rem;margin-bottom:0.5rem;">🎬</div>
                    <div>Your video will appear here</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ============================================================
# TAB 2 — IMAGES TO VIDEO
# ============================================================
with tab_i2v:
    st.markdown("### Animate your images")
    st.markdown("Upload images and choose an animation style. Each image becomes a living scene.")
    st.markdown("")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        i2v_files = st.file_uploader(
            "Upload images",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="i2v_files",
            label_visibility="collapsed",
        )

        if i2v_files:
            st.markdown(f"**{len(i2v_files)} image(s) loaded**")
            preview_cols = st.columns(min(4, len(i2v_files)))
            for idx, f in enumerate(i2v_files[:4]):
                with preview_cols[idx]:
                    st.image(f, use_container_width=True)
            if len(i2v_files) > 4:
                st.caption(f"+ {len(i2v_files) - 4} more")

        col_a, col_t = st.columns(2)
        with col_a:
            i2v_anim = st.selectbox(
                "Animation style",
                ["ken_burns", "zoom_in", "zoom_out", "pan_left", "pan_right", "static"],
                format_func=lambda x: x.replace("_", " ").title(),
                key="i2v_anim",
            )
        with col_t:
            i2v_transition = st.selectbox(
                "Transition",
                ["fade", "dissolve", "cut"],
                format_func=lambda x: x.title(),
                key="i2v_transition",
            )

        col_d, col_ar = st.columns(2)
        with col_d:
            i2v_dur = st.select_slider(
                "Seconds per image",
                options=[2, 3, 4, 5, 6, 8],
                value=4,
                format_func=lambda x: f"{x}s",
                key="i2v_dur",
            )
        with col_ar:
            i2v_ar = st.selectbox(
                "Aspect ratio",
                ["9:16 (Vertical)", "16:9 (Landscape)", "1:1 (Square)"],
                key="i2v_ar",
            )

        comfyui_ok, _ = _comfyui_status()
        i2v_ai = st.toggle(
            "AI animate with AnimateDiff/SVD (requires ComfyUI)",
            value=False,
            disabled=not comfyui_ok,
            key="i2v_ai",
            help="Real AI motion from your images. Only available when ComfyUI is running." if not comfyui_ok
                 else "Uses AnimateDiff or SVD to generate real motion from your images.",
        )

        if st.button("Animate", key="i2v_go", disabled=st.session_state.i2v_running or not i2v_files):
            st.session_state.i2v_running = True
            st.session_state.i2v_result = None
            st.rerun()

    with col_right:
        if st.session_state.i2v_running and i2v_files:
            _run_i2v_generation(i2v_files, i2v_anim, i2v_transition, i2v_dur, i2v_ar, i2v_ai)

        if st.session_state.i2v_result:
            r = st.session_state.i2v_result
            if r["success"]:
                st.success(f"Done in {r['elapsed']:.1f}s")
                st.video(r["output_path"])
                with open(r["output_path"], "rb") as f:
                    st.download_button(
                        "Download MP4",
                        f,
                        file_name=Path(r["output_path"]).name,
                        mime="video/mp4",
                    )
                st.markdown(f'<div class="engine-badge">Engine: {r["engine"]}</div>', unsafe_allow_html=True)
                if r.get("warnings"):
                    for w in r["warnings"]:
                        st.info(w)
            else:
                st.error(f"Animation failed: {r['error']}")
        elif not st.session_state.i2v_running:
            st.markdown("""
            <div style="background:#1a1a1a;border-radius:10px;padding:2rem;text-align:center;color:#555;min-height:300px;display:flex;align-items:center;justify-content:center;">
                <div>
                    <div style="font-size:3rem;margin-bottom:0.5rem;">🖼️</div>
                    <div>Animated video will appear here</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ============================================================
# TAB 3 — HYBRID
# ============================================================
with tab_hyb:
    st.markdown("### Build a hybrid video")
    st.markdown("Mix AI-generated scenes with your own images. Arrange them in any order.")
    st.markdown("")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        col_add_prompt, col_add_image = st.columns(2)

        with col_add_prompt:
            if st.button("+ Add AI Scene", key="hyb_add_prompt", use_container_width=True):
                st.session_state.hyb_scenes.append({
                    "kind": "prompt",
                    "content": "",
                    "duration": 4.0,
                    "style": "cinematic",
                    "animation": "ken_burns",
                    "id": uuid.uuid4().hex[:6],
                })
                st.rerun()

        with col_add_image:
            hyb_upload = st.file_uploader(
                "Add image scene",
                type=["jpg", "jpeg", "png", "webp"],
                key="hyb_upload",
                label_visibility="collapsed",
            )
            if hyb_upload:
                tmp = Path(tempfile.mkdtemp()) / hyb_upload.name
                tmp.write_bytes(hyb_upload.read())
                st.session_state.hyb_scenes.append({
                    "kind": "image",
                    "content": str(tmp),
                    "duration": 4.0,
                    "style": "cinematic",
                    "animation": "ken_burns",
                    "id": uuid.uuid4().hex[:6],
                })
                st.rerun()

        st.markdown("")

        if not st.session_state.hyb_scenes:
            st.markdown("""
            <div style="background:#1a1a1a;border:1px dashed #333;border-radius:8px;
                        padding:2rem;text-align:center;color:#555;">
                No scenes yet. Add AI scenes or upload images above.
            </div>
            """, unsafe_allow_html=True)
        else:
            to_remove = []
            for i, scene in enumerate(st.session_state.hyb_scenes):
                with st.container():
                    st.markdown(f'<div class="scene-card">', unsafe_allow_html=True)
                    s_col1, s_col2, s_col3 = st.columns([1, 3, 1])
                    with s_col1:
                        icon = "AI" if scene["kind"] == "prompt" else "IMG"
                        badge_color = "#e63946" if scene["kind"] == "prompt" else "#4caf50"
                        st.markdown(
                            f'<div style="background:{badge_color};color:white;text-align:center;'
                            f'border-radius:6px;padding:4px;font-weight:700;font-size:0.85rem;margin-top:8px;">{icon}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(f'<div style="text-align:center;color:#888;font-size:0.75rem;margin-top:2px;">Scene {i+1}</div>', unsafe_allow_html=True)
                    with s_col2:
                        if scene["kind"] == "prompt":
                            new_content = st.text_input(
                                "Prompt",
                                value=scene["content"],
                                key=f"hyb_p_{scene['id']}",
                                placeholder="Describe this scene...",
                                label_visibility="collapsed",
                            )
                            st.session_state.hyb_scenes[i]["content"] = new_content
                            new_style = st.selectbox(
                                "Style",
                                ["cinematic", "photorealistic", "anime", "vibrant", "dark", "abstract"],
                                index=["cinematic", "photorealistic", "anime", "vibrant", "dark", "abstract"].index(scene["style"]),
                                key=f"hyb_s_{scene['id']}",
                                label_visibility="collapsed",
                            )
                            st.session_state.hyb_scenes[i]["style"] = new_style
                        else:
                            st.markdown(
                                f'<div style="color:#aaa;font-size:0.85rem;padding:8px 0;">{Path(scene["content"]).name}</div>',
                                unsafe_allow_html=True,
                            )
                        new_dur = st.slider(
                            "Duration",
                            1.0, 10.0,
                            float(scene["duration"]),
                            0.5,
                            format="%.1fs",
                            key=f"hyb_d_{scene['id']}",
                            label_visibility="collapsed",
                        )
                        st.session_state.hyb_scenes[i]["duration"] = new_dur
                    with s_col3:
                        if st.button("Remove", key=f"hyb_rm_{scene['id']}"):
                            to_remove.append(i)
                    st.markdown("</div>", unsafe_allow_html=True)

            if to_remove:
                for i in reversed(to_remove):
                    st.session_state.hyb_scenes.pop(i)
                st.rerun()

        st.markdown("")
        col_tr, col_ar_h = st.columns(2)
        with col_tr:
            hyb_transition = st.selectbox(
                "Transition style",
                ["fade", "dissolve", "cut"],
                format_func=lambda x: x.title(),
                key="hyb_transition",
            )
        with col_ar_h:
            hyb_ar = st.selectbox(
                "Aspect ratio",
                ["9:16 (Vertical)", "16:9 (Landscape)", "1:1 (Square)"],
                key="hyb_ar",
            )

        n_scenes = len(st.session_state.hyb_scenes)
        n_ai = sum(1 for s in st.session_state.hyb_scenes if s["kind"] == "prompt")
        n_img = n_scenes - n_ai
        if n_scenes > 0:
            st.caption(f"{n_scenes} scene(s) total — {n_ai} AI-generated, {n_img} from images")

        if st.button(
            "Generate Hybrid Video",
            key="hyb_go",
            disabled=st.session_state.hyb_running or n_scenes == 0,
        ):
            st.session_state.hyb_running = True
            st.session_state.hyb_result = None
            st.rerun()

    with col_right:
        if st.session_state.hyb_running:
            _run_hyb_generation(hyb_transition, hyb_ar)

        if st.session_state.hyb_result:
            r = st.session_state.hyb_result
            if r["success"]:
                st.success(f"Done in {r['elapsed']:.1f}s")
                st.video(r["output_path"])
                with open(r["output_path"], "rb") as f:
                    st.download_button(
                        "Download MP4",
                        f,
                        file_name=Path(r["output_path"]).name,
                        mime="video/mp4",
                    )
                st.markdown(f'<div class="engine-badge">Engine: {r["engine"]}</div>', unsafe_allow_html=True)
                if r.get("warnings"):
                    for w in r["warnings"]:
                        st.info(w)
            else:
                st.error(f"Generation failed: {r['error']}")
        elif not st.session_state.hyb_running:
            st.markdown("""
            <div style="background:#1a1a1a;border-radius:10px;padding:2rem;text-align:center;color:#555;min-height:300px;display:flex;align-items:center;justify-content:center;">
                <div>
                    <div style="font-size:3rem;margin-bottom:0.5rem;">🎞️</div>
                    <div>Hybrid video will appear here</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


