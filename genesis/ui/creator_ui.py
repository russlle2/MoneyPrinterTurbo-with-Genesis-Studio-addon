"""
Genesis Studio — Local Creator UI (Streamlit).

Run with:
    python -m genesis.ui.launch_ui
    streamlit run genesis/ui/creator_ui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import streamlit as st
from genesis.ui.ui_helpers import (
    build_video_plan,
    create_video,
    export_package,
    generate_job_id,
    get_dashboard_path,
    import_visuals,
    ingest_media,
    list_run_ids,
    load_run_preview,
    match_clips,
    open_in_browser,
    prepare_run_uploads,
    rebuild_dashboard,
    render_video,
    run_quality_check,
    run_visual_fill,
    save_video_plan,
    select_thumbnail,
)
from genesis.ui.ui_models import UICreateRequest

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Genesis Studio Creator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Global CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
.block-container { max-width: 1100px; padding-top: 1.5rem; }
h1 { color: #f1f5f9; }
h2, h3 { color: #e2e8f0; }
.stButton > button { border-radius: 8px; font-weight: 600; }
.stButton > button[kind="primary"] { background: #3b82f6; border: none; }
.stTextArea textarea { font-size: 1rem; }
.success-box { background: #14532d; border-radius: 8px; padding: 12px 16px; color: #86efac; margin: 8px 0; }
.warn-box { background: #78350f; border-radius: 8px; padding: 12px 16px; color: #fde68a; margin: 8px 0; }
.error-box { background: #7f1d1d; border-radius: 8px; padding: 12px 16px; color: #fca5a5; margin: 8px 0; }
.info-box { background: #1e3a5f; border-radius: 8px; padding: 12px 16px; color: #93c5fd; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)

# ─── Constants ────────────────────────────────────────────────────────────────

TEMPLATES = [
    "affiliate_product", "product_demo", "wellness_teaching",
    "fundraising_story", "tutorial", "motivational_walkthrough",
    "controversial_take", "personal_story", "local_business_promo",
]
PLATFORMS = [
    "tiktok", "instagram_reels", "youtube_shorts", "clapper", "x",
]
BRANDS = [
    "auto", "clean_creator", "cinematic_dark", "wellness_soft",
    "bold_viral", "minimal_white",
]
DURATIONS = ["15 seconds", "30 seconds", "45 seconds", "60 seconds", "90 seconds"]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _status_box(result, *, label: str = "") -> None:
    prefix = f"**{label}:** " if label else ""
    if result.error:
        st.markdown(
            f'<div class="error-box">{prefix}⚠ {result.error}</div>',
            unsafe_allow_html=True,
        )
    elif result.success:
        st.markdown(
            f'<div class="success-box">{prefix}✓ {result.message}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="warn-box">{prefix}! {result.message}</div>',
            unsafe_allow_html=True,
        )
    for w in result.warnings[:6]:
        st.caption(f"⚠ {w}")


def _save_uploaded(uploaded_file, dest_dir: Path, *, filename: str = "") -> Path | None:
    """Save a Streamlit UploadedFile to disk; returns path."""
    if not uploaded_file:
        return None
    import re
    name = re.sub(r"[^\w.\-]+", "_", filename or uploaded_file.name)[:120]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


def _save_uploaded_list(files, dest_dir: Path) -> list[str]:
    paths = []
    for f in (files or []):
        p = _save_uploaded(f, dest_dir)
        if p:
            paths.append(str(p))
    return paths


_RUNS_BASE = _REPO / "assets" / "runs"
_UPLOADS_TMP = _REPO / "assets" / "_ui_uploads"

# ─── Title ───────────────────────────────────────────────────────────────────

st.title("🎬 Genesis Studio Creator")
st.caption("Local AI-powered short-form video creator. All data stays on your machine.")

# ─── Tabs ────────────────────────────────────────────────────────────────────

tab_create, tab_media, tab_review, tab_export, tab_dashboard, tab_settings = st.tabs([
    "✏️ Create Video",
    "🖼️ Media & Visuals",
    "👁️ Review",
    "📦 Export",
    "📊 Dashboard",
    "⚙️ Settings",
])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — CREATE VIDEO
# ═══════════════════════════════════════════════════════════════════════════
with tab_create:
    st.header("Create Video")
    st.caption("Fill in the fields below and click **Create Video** to run the full pipeline.")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        idea = st.text_area(
            "Video idea / concept *",
            placeholder="e.g. 'This $12 solar lighter outlasted my $80 BIC — here's why'",
            height=120,
            key="idea",
        )

        col_a, col_b = st.columns(2)
        with col_a:
            template = st.selectbox("Template", TEMPLATES, key="template")
            platform = st.selectbox("Platform", PLATFORMS, key="platform")
            brand = st.selectbox("Brand / Style", BRANDS, key="brand")
        with col_b:
            duration = st.selectbox("Target duration", DURATIONS, index=1, key="duration")
            audience = st.text_input("Target audience", placeholder="25-35 women interested in wellness", key="audience")
            cta = st.text_input("Call to action", placeholder="Link in bio for 20% off", key="cta")
            tone = st.text_input("Tone / style", placeholder="energetic, direct, inspiring", key="tone")

        job_id_input = st.text_input(
            "Job ID (leave blank to auto-generate)",
            placeholder="auto-generated",
            key="job_id_create",
        )

    with col_right:
        st.subheader("Options")
        narration = st.toggle(
            "Generate narration (voiceover paused)",
            value=False,
            key="narration",
            help="Voiceover/captions are temporarily disabled to avoid wasted API "
                 "tokens. Set GENESIS_ENABLE_VOICEOVER=1 to re-enable later.",
            disabled=True,
        )
        use_local_llm = st.toggle("Use local LLM if available", value=False, key="local_llm")
        ai_fill = st.toggle("AI visual fill for missing scenes", value=False, key="ai_fill")
        import_vis = st.toggle("Import manual visuals (Diffus.me etc)", value=False, key="import_vis")
        sel_thumb = st.toggle("Select thumbnail", value=True, key="sel_thumb")
        quality = st.toggle("Run quality check", value=True, key="quality")
        strict_q = st.toggle("Strict quality check", value=False, key="strict_q")
        do_export = st.toggle("Export package", value=True, key="do_export")
        use_music = st.toggle("Use music bed", value=False, key="use_music")
        transitions = st.toggle("Enable transitions", value=True, key="transitions")
        motion = st.toggle("Enable motion effects", value=True, key="motion")

        st.subheader("Uploads")
        clip_files = st.file_uploader(
            "Video clips / images",
            type=["mp4", "mov", "avi", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="clip_files",
        )
        music_file = st.file_uploader(
            "Music file (optional)",
            type=["mp3", "wav", "m4a", "aac"],
            key="music_file",
        )
        thumb_file = st.file_uploader(
            "Thumbnail image (optional)",
            type=["jpg", "jpeg", "png", "webp"],
            key="thumb_file",
        )
        manual_vis_files = st.file_uploader(
            "Manual AI visuals (Diffus.me / Midjourney etc)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="manual_vis_files",
        )

    st.divider()

    # ── Step 1: preview the suggested video prompt before generating ──────────
    st.subheader("Step 1 — Preview the suggested video prompt")
    st.caption("Generate the script + AI video prompt first. Review and edit it, "
               "then generate the video. No API tokens are spent on the preview.")
    btn_preview = st.button("🧠 Generate Script & Video Prompt (preview)", use_container_width=False)

    if btn_preview:
        if not idea.strip():
            st.error("Please enter a video idea before previewing.")
        else:
            jid_prev = job_id_input.strip() or generate_job_id(idea)
            with st.spinner("Building script and video prompt…"):
                plan_res = build_video_plan(
                    idea, platform=platform, brand=brand, duration=duration,
                    template=template, audience=audience, cta=cta, tone=tone,
                    job_id=jid_prev, use_local_llm=use_local_llm,
                )
            if plan_res.get("error"):
                st.error(f"Could not build plan: {plan_res['error']}")
            else:
                st.session_state["forge_plan"] = plan_res["plan"]
                st.session_state["plan_job_id"] = plan_res["job_id"]
                st.session_state["script_preview"] = plan_res.get("script_preview", "")
                for w in plan_res.get("warnings", []):
                    st.caption(f"⚠ {w}")

    plan = st.session_state.get("forge_plan")
    if plan:
        st.markdown(f"**Plan for job:** `{st.session_state.get('plan_job_id','')}`")
        if st.session_state.get("script_preview"):
            with st.expander("📝 Script preview", expanded=False):
                st.text(st.session_state["script_preview"])

        st.markdown(
            f"**Style:** {plan.get('style_desc','')} · **Lighting:** {plan.get('lighting','')} · "
            f"**Aspect:** {plan.get('aspect_ratio','9:16')} · "
            f"~{plan.get('scene_duration','?')}s/scene"
        )
        st.caption("Edit any scene prompt below. These exact prompts drive the AI video generation.")
        edited_scenes = []
        for i, scene in enumerate(plan.get("scenes", [])):
            new_prompt = st.text_area(
                f"Scene {i+1} — {scene.get('beat','')}",
                value=scene.get("prompt", ""),
                height=80,
                key=f"scene_prompt_{i}",
            )
            s2 = dict(scene)
            s2["prompt"] = new_prompt
            edited_scenes.append(s2)
        st.session_state["forge_plan"]["scenes"] = edited_scenes

    st.divider()
    st.subheader("Step 2 — Generate")

    col_btn1, col_btn2, col_btn3, _ = st.columns([2, 2, 2, 4])
    btn_create = col_btn1.button("▶ Generate Video", type="primary", use_container_width=True)
    btn_no_render = col_btn2.button("📝 Create (no render)", use_container_width=True)
    btn_quality = col_btn3.button("✅ Quality Check Only", use_container_width=True)

    if btn_create or btn_no_render:
        if not idea.strip():
            st.error("Please enter a video idea before creating.")
        else:
            # Reuse the previewed plan/job when available so the edited prompts drive render.
            plan_state = st.session_state.get("forge_plan")
            plan_jid = st.session_state.get("plan_job_id", "")
            jid = job_id_input.strip() or plan_jid or generate_job_id(idea)
            if plan_state and jid == plan_jid:
                save_video_plan(jid, plan_state)

            # Save uploads to temp area first, then copy to run folder
            tmp_dir = _UPLOADS_TMP / jid
            clips_paths = _save_uploaded_list(clip_files, tmp_dir / "media")
            music_path_str = ""
            if music_file:
                mp = _save_uploaded(music_file, tmp_dir / "music")
                if mp:
                    music_path_str = str(mp)
            thumb_path_str = ""
            if thumb_file:
                tp = _save_uploaded(thumb_file, tmp_dir / "thumbnails")
                if tp:
                    thumb_path_str = str(tp)
            manual_paths = _save_uploaded_list(manual_vis_files, tmp_dir / "manual_visuals")

            # Copy uploads into run folder
            prepare_run_uploads(
                jid,
                media_files=clips_paths,
                music_file=music_path_str or None,
                thumbnail_file=thumb_path_str or None,
                manual_visuals=manual_paths,
            )

            req = UICreateRequest(
                idea=idea,
                job_id=jid,
                template=template,
                platform=platform,
                brand=brand,
                duration=duration,
                audience=audience,
                cta=cta,
                tone=tone,
                media_path=str(_RUNS_BASE / jid / "media") if clips_paths else "",
                music_path=music_path_str,
                thumbnail_path=thumb_path_str,
                narration=narration,
                use_local_llm=use_local_llm,
                ai_visual_fill=ai_fill,
                import_visuals=import_vis,
                select_thumbnail=sel_thumb,
                quality_check=quality,
                strict_quality=strict_q,
                export=do_export,
                use_music=use_music,
                transitions=transitions,
                motion_effects=motion,
                render_enabled=not btn_no_render,
            )

            with st.spinner(f"Running pipeline for job `{jid}`… This may take a minute."):
                result = create_video(req)

            _status_box(result, label="Pipeline")
            st.session_state["last_job_id"] = result.job_id or jid

            if result.output_paths.get("draft_video"):
                vp = result.output_paths["draft_video"]
                st.success(f"Draft video: `{vp}`")
                try:
                    st.video(vp)
                except Exception:
                    st.caption(f"Open manually: {vp}")

            if result.output_paths.get("selected_thumbnail"):
                tp = result.output_paths["selected_thumbnail"]
                st.image(tp, caption="Selected thumbnail", width=280)

            if result.readiness_label:
                color = "green" if result.readiness_label == "READY_TO_POST" else (
                    "orange" if result.readiness_label == "NEEDS_REVIEW" else "red"
                )
                st.markdown(f"**Readiness:** :{color}[{result.readiness_label}] — {result.quality_score}/100")

            if result.output_paths.get("export_dir"):
                st.info(f"Export folder: `{result.output_paths['export_dir']}`")

    if btn_quality:
        jid = job_id_input.strip() or st.session_state.get("last_job_id", "")
        if not jid:
            st.warning("Enter a Job ID or create a video first.")
        else:
            with st.spinner("Running quality check…"):
                result = run_quality_check(jid, platform=platform, strict=strict_q)
            _status_box(result, label="Quality")

    # Render existing job
    st.divider()
    st.subheader("Render Existing Job")
    col_r1, col_r2, col_r3 = st.columns([2, 2, 2])
    with col_r1:
        render_jid = st.text_input("Job ID to render", key="render_jid")
    with col_r2:
        render_plat = st.selectbox("Platform", PLATFORMS, key="render_plat")
    with col_r3:
        render_brand = st.selectbox("Brand", [b for b in BRANDS if b != "auto"], key="render_brand")
    if st.button("🎥 Render Existing Job", key="btn_render_existing"):
        if not render_jid.strip():
            st.warning("Enter a Job ID.")
        else:
            with st.spinner("Rendering…"):
                result = render_video(render_jid.strip(), platform=render_plat, brand=render_brand)
            _status_box(result, label="Render")
            if result.output_paths.get("draft_video"):
                try:
                    st.video(result.output_paths["draft_video"])
                except Exception:
                    st.caption(result.output_paths["draft_video"])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — MEDIA & VISUALS
# ═══════════════════════════════════════════════════════════════════════════
with tab_media:
    st.header("Media & Visuals")
    st.caption("Add media, import AI visuals, or generate prompt cards for an existing job.")

    run_ids = list_run_ids()
    col_m1, col_m2 = st.columns([2, 4])
    with col_m1:
        media_jid = st.selectbox(
            "Job ID",
            options=[""] + run_ids,
            key="media_jid",
            help="Select an existing run or type a job ID",
        )
        if not media_jid:
            media_jid = st.text_input("Or type job ID", key="media_jid_text")

    with col_m2:
        clip_up2 = st.file_uploader(
            "Upload video clips / images",
            type=["mp4", "mov", "avi", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="clip_up2",
        )
        manual_vis2 = st.file_uploader(
            "Upload manual AI visuals",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="manual_vis2",
        )
        thumb_up2 = st.file_uploader(
            "Upload thumbnail",
            type=["jpg", "jpeg", "png", "webp"],
            key="thumb_up2",
        )

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    btn_ingest = c1.button("📥 Ingest Media", key="btn_ingest")
    btn_match = c2.button("🔗 Match Clips", key="btn_match")
    btn_import_vis = c3.button("🖼️ Import Visuals", key="btn_import_vis")
    btn_vis_fill = c4.button("✨ AI Visual Fill", key="btn_vis_fill")
    btn_sel_thumb2 = c5.button("🖼️ Select Thumbnail", key="btn_sel_thumb2")

    jid2 = str(media_jid or "").strip()

    if btn_ingest:
        if not jid2:
            st.warning("Select or enter a Job ID.")
        else:
            tmp_dir2 = _UPLOADS_TMP / jid2
            clips_p2 = _save_uploaded_list(clip_up2, tmp_dir2 / "media")
            if clips_p2:
                prepare_run_uploads(jid2, media_files=clips_p2)
                with st.spinner("Ingesting media…"):
                    result = ingest_media(jid2, str(_RUNS_BASE / jid2 / "media"))
                _status_box(result)
            else:
                st.info("Upload clips first to ingest.")

    if btn_match:
        if not jid2:
            st.warning("Select or enter a Job ID.")
        else:
            with st.spinner("Matching clips to scenes…"):
                result = match_clips(jid2)
            _status_box(result)

    if btn_import_vis:
        if not jid2:
            st.warning("Select or enter a Job ID.")
        else:
            tmp_dir2 = _UPLOADS_TMP / jid2
            vis_p = _save_uploaded_list(manual_vis2, tmp_dir2 / "manual_visuals")
            thumb_p2 = None
            if thumb_up2:
                tp2 = _save_uploaded(thumb_up2, tmp_dir2 / "thumbnails")
                thumb_p2 = str(tp2) if tp2 else None
            if vis_p or thumb_p2:
                prepare_run_uploads(
                    jid2,
                    manual_visuals=vis_p,
                    thumbnail_file=thumb_p2,
                )
            with st.spinner("Importing visuals…"):
                result = import_visuals(jid2)
            _status_box(result)

    if btn_vis_fill:
        if not jid2:
            st.warning("Select or enter a Job ID.")
        else:
            with st.spinner("Running AI visual fill…"):
                result = run_visual_fill(jid2)
            _status_box(result)

    if btn_sel_thumb2:
        if not jid2:
            st.warning("Select or enter a Job ID.")
        else:
            with st.spinner("Selecting thumbnail…"):
                result = select_thumbnail(jid2)
            _status_box(result)
            if result.preview_paths.get("thumbnail"):
                tp = result.preview_paths["thumbnail"]
                try:
                    st.image(tp, caption="Selected thumbnail", width=280)
                except Exception:
                    st.caption(f"Thumbnail: {tp}")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — REVIEW
# ═══════════════════════════════════════════════════════════════════════════
with tab_review:
    st.header("Review")
    st.caption("Preview a run's script, captions, thumbnail, video, and quality report.")

    run_ids_r = list_run_ids()
    col_rv1, col_rv2 = st.columns([2, 2])
    with col_rv1:
        review_jid = st.selectbox(
            "Job ID",
            options=[""] + run_ids_r,
            key="review_jid",
        )
        if not review_jid:
            review_jid = st.text_input("Or type job ID", key="review_jid_text")
    with col_rv2:
        review_plat = st.selectbox("Platform", PLATFORMS, key="review_plat")

    col_rb1, col_rb2, col_rb3, col_rb4 = st.columns(4)
    btn_load = col_rb1.button("🔍 Load Run", key="btn_load_run")
    btn_qc_review = col_rb2.button("✅ Quality Check", key="btn_qc_review")
    btn_strict_review = col_rb3.button("🔒 Strict Quality Check", key="btn_strict_review")
    btn_open_review = col_rb4.button("🌐 Open Review HTML", key="btn_open_review")

    jid_r = str(review_jid or "").strip()

    if btn_load and jid_r:
        preview = load_run_preview(jid_r)
        if not preview:
            st.warning(f"No data found for job `{jid_r}`.")
        else:
            col_p1, col_p2 = st.columns([2, 1])
            with col_p1:
                if preview.get("draft_video"):
                    st.subheader("Draft Video")
                    try:
                        st.video(preview["draft_video"])
                    except Exception:
                        st.caption(f"Video path: {preview['draft_video']}")

                if preview.get("script_preview"):
                    st.subheader("Script Preview")
                    st.text_area("Script", preview["script_preview"], height=200, disabled=True, key="rv_script")

                if preview.get("caption"):
                    st.subheader("Caption")
                    st.text_area("Caption", preview["caption"], height=120, disabled=True, key="rv_caption")

                if preview.get("hashtags"):
                    st.subheader("Hashtags")
                    st.code(preview["hashtags"])

            with col_p2:
                if preview.get("thumbnail"):
                    st.subheader("Thumbnail")
                    try:
                        st.image(preview["thumbnail"], caption="Thumbnail", use_container_width=True)
                    except Exception:
                        st.caption(preview["thumbnail"])

                if preview.get("quality_badge"):
                    st.subheader("Quality")
                    badge = preview["quality_badge"]
                    color = "green" if "READY" in badge else ("orange" if "REVIEW" in badge else "red")
                    st.markdown(f"**:{color}[{badge}]**")

    if btn_qc_review and jid_r:
        with st.spinner("Running quality check…"):
            result = run_quality_check(jid_r, platform=review_plat)
        _status_box(result, label="Quality")

    if btn_strict_review and jid_r:
        with st.spinner("Running strict quality check…"):
            result = run_quality_check(jid_r, platform=review_plat, strict=True)
        _status_box(result, label="Strict Quality")

    if btn_open_review and jid_r:
        html = _RUNS_BASE / jid_r / "review.html"
        if html.is_file():
            opened = open_in_browser(str(html))
            if not opened:
                st.info(f"Open manually: `{html}`")
        else:
            st.warning(f"review.html not found for job `{jid_r}`.")

    if not jid_r and (btn_load or btn_qc_review or btn_strict_review or btn_open_review):
        st.warning("Select or enter a Job ID first.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — EXPORT
# ═══════════════════════════════════════════════════════════════════════════
with tab_export:
    st.header("Export")
    st.caption("Export a completed run to a platform-ready folder with captions, thumbnail, and checklist.")

    run_ids_e = list_run_ids()
    col_e1, col_e2 = st.columns([2, 2])
    with col_e1:
        export_jid = st.selectbox("Job ID", options=[""] + run_ids_e, key="export_jid")
        if not export_jid:
            export_jid = st.text_input("Or type job ID", key="export_jid_text")
    with col_e2:
        export_plat = st.selectbox("Platform", PLATFORMS, key="export_plat")

    col_eb1, col_eb2, col_eb3 = st.columns(3)
    btn_do_export = col_eb1.button("📦 Export Package", type="primary", key="btn_do_export")
    btn_sel_thumb_exp = col_eb2.button("🖼️ Select Thumbnail", key="btn_sel_thumb_exp")
    btn_open_exp = col_eb3.button("📂 Open Export Folder", key="btn_open_exp")

    jid_e = str(export_jid or "").strip()

    if btn_do_export:
        if not jid_e:
            st.warning("Select a Job ID.")
        else:
            with st.spinner("Building export package…"):
                result = export_package(jid_e, platform=export_plat)
            _status_box(result, label="Export")

            if result.output_paths.get("export_dir"):
                ed = result.output_paths["export_dir"]
                st.success(f"Export folder: `{ed}`")

                # Show export contents
                ed_path = Path(ed)
                if ed_path.is_dir():
                    st.subheader("Export Package Contents")
                    col_ec1, col_ec2 = st.columns([2, 1])
                    with col_ec1:
                        for f in sorted(ed_path.iterdir()):
                            if f.suffix in (".txt", ".md") and f.stat().st_size < 8000:
                                with st.expander(f"📄 {f.name}"):
                                    try:
                                        st.text(f.read_text(encoding="utf-8"))
                                    except Exception:
                                        st.caption("Could not read file")
                    with col_ec2:
                        thumb = ed_path / "selected_thumbnail.jpg"
                        if thumb.is_file():
                            st.image(str(thumb), caption="Thumbnail", use_container_width=True)
                        video = ed_path / "draft_video.mp4"
                        if video.is_file():
                            try:
                                st.video(str(video))
                            except Exception:
                                st.caption(f"Video: {video}")

    if btn_sel_thumb_exp:
        if not jid_e:
            st.warning("Select a Job ID.")
        else:
            with st.spinner("Selecting thumbnail…"):
                result = select_thumbnail(jid_e)
            _status_box(result)

    if btn_open_exp:
        if not jid_e:
            st.warning("Select a Job ID.")
        else:
            exp_dir = _REPO / "exports" / jid_e / export_plat
            if exp_dir.is_dir():
                opened = open_in_browser(str(exp_dir / "README.md"))
                if not opened:
                    st.info(f"Open: `{exp_dir}`")
            else:
                st.warning(f"Export folder not found. Run export first.")

    if not jid_e and (btn_do_export or btn_sel_thumb_exp or btn_open_exp):
        st.warning("Select or enter a Job ID first.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════
with tab_settings:
    st.header("⚙️ Settings — Local LLM & AI Config")
    st.caption("Configure your local AI models. All settings are saved to `genesis/config/local_llm.json`.")

    import json as _json_mod

    _LLM_CFG_PATH = _REPO / "genesis" / "config" / "local_llm.json"

    def _load_llm_cfg() -> dict:
        if _LLM_CFG_PATH.is_file():
            try:
                return _json_mod.loads(_LLM_CFG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"enabled": False, "backend": "ollama", "endpoint_url": "http://localhost:11434/api/generate",
                "model": "llama3.1:latest", "timeout_seconds": 180, "max_tokens": 2000, "temperature": 0.75}

    current_cfg = _load_llm_cfg()

    st.subheader("Local LLM (Script Generation)")
    st.markdown("""
Your Llama 3.1 30B model generates the actual video scripts. Without it, Genesis falls back to
a deterministic template engine which produces generic placeholder content.

**To enable:** Start your LLM server (Ollama, LM Studio, llama.cpp, etc.), configure below, save, and enable it.
    """)

    col_s1, col_s2 = st.columns([2, 3])
    with col_s1:
        llm_enabled = st.toggle(
            "Enable local LLM for script generation",
            value=bool(current_cfg.get("enabled", False)),
            key="llm_enabled_toggle",
        )
        backend_opts = ["ollama", "lmstudio", "llama_cpp_server", "text_generation_webui", "custom_http"]
        backend = st.selectbox(
            "Backend / server type",
            backend_opts,
            index=backend_opts.index(current_cfg.get("backend", "ollama"))
                  if current_cfg.get("backend", "ollama") in backend_opts else 0,
            key="llm_backend",
        )
        endpoint_defaults = {
            "ollama": "http://localhost:11434/api/generate",
            "lmstudio": "http://localhost:1234/v1/chat/completions",
            "llama_cpp_server": "http://localhost:8080/completion",
            "text_generation_webui": "http://localhost:5000/api/v1/generate",
            "custom_http": "http://localhost:11434/api/generate",
        }
        endpoint = st.text_input(
            "Endpoint URL",
            value=current_cfg.get("endpoint_url", endpoint_defaults.get(backend, "")),
            key="llm_endpoint",
        )
        model_name = st.text_input(
            "Model name",
            value=current_cfg.get("model", "llama3.1:latest"),
            key="llm_model_name",
            help="For Ollama: use the exact model tag shown in 'ollama list'. For LM Studio: the model name shown in the UI.",
        )

    with col_s2:
        timeout = st.slider("Timeout (seconds)", 30, 300, int(current_cfg.get("timeout_seconds", 180)), step=10, key="llm_timeout")
        max_tok = st.slider("Max output tokens", 500, 4000, int(current_cfg.get("max_tokens", 2000)), step=100, key="llm_max_tokens")
        temperature = st.slider("Temperature", 0.0, 1.5, float(current_cfg.get("temperature", 0.75)), step=0.05, key="llm_temp")

        st.markdown("**Quick backend tips:**")
        st.markdown("""
- **Ollama**: `ollama serve` then `ollama run llama3.1:30b`
- **LM Studio**: Load model → Enable local server in UI
- **llama.cpp**: `./server -m model.gguf -c 4096`
- **text-generation-webui**: Start with `--api` flag
        """)

    col_sv1, col_sv2, col_sv3 = st.columns(3)
    if col_sv1.button("💾 Save LLM Config", key="btn_save_llm"):
        new_cfg = dict(current_cfg)
        new_cfg["enabled"] = llm_enabled
        new_cfg["backend"] = backend
        new_cfg["endpoint_url"] = endpoint
        new_cfg["model"] = model_name
        new_cfg["timeout_seconds"] = timeout
        new_cfg["max_tokens"] = max_tok
        new_cfg["temperature"] = temperature
        try:
            _LLM_CFG_PATH.write_text(
                _json_mod.dumps(new_cfg, indent=2),
                encoding="utf-8",
            )
            if llm_enabled:
                st.success(f"✓ LLM config saved — **{backend}** model `{model_name}` enabled.")
                st.info("The 'Use local LLM' toggle in Create Video tab will now use this config.")
            else:
                st.success("Config saved. LLM is currently disabled (template fallback will be used).")
        except Exception as exc:
            st.error(f"Could not save: {exc}")

    if col_sv2.button("🔌 Test Connection", key="btn_test_llm"):
        test_cfg = {
            "enabled": True,
            "backend": backend,
            "endpoint_url": endpoint,
            "model": model_name,
            "timeout_seconds": min(timeout, 15),
            "max_tokens": 50,
            "temperature": 0.1,
        }
        with st.spinner(f"Testing {backend} at {endpoint} …"):
            try:
                from genesis.integrations.local_llm_provider import generate_local_text
                r = generate_local_text("Say hello in one word.", config=test_cfg)
                if r.get("success"):
                    st.success(f"✓ Connected! Model responded: `{r.get('text','')[:80]}`")
                else:
                    st.error(f"Connection failed: {r.get('error', 'unknown')}")
                    st.info("Make sure your LLM server is running and the endpoint is correct.")
            except Exception as exc:
                st.error(f"Test error: {exc}")

    if col_sv3.button("🔄 Reload Config", key="btn_reload_llm"):
        st.rerun()

    st.divider()
    st.subheader("LLM Status")
    try:
        from genesis.integrations.local_llm_provider import load_local_llm_config, local_llm_ready
        cfg = load_local_llm_config()
        ready, reason = local_llm_ready(cfg)
        if ready:
            st.markdown(
                f'<div class="success-box">✓ Local LLM ready — backend: <b>{cfg.get("backend")}</b>, '
                f'model: <b>{cfg.get("model")}</b>, endpoint: {cfg.get("endpoint_url")}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="warn-box">⚠ Local LLM not ready: {reason}</div>',
                unsafe_allow_html=True,
            )
    except Exception as exc:
        st.error(f"Config load error: {exc}")

    st.divider()
    st.subheader("AI Image Generation (ComfyUI)")
    st.markdown("""
When **AI visual fill** is enabled in Create Video, Genesis can call a local **ComfyUI** instance
to generate cinematic scene images automatically.

**To enable:**
1. Install ComfyUI and launch it on port 8188
2. Create a `genesis/config/comfyui_workflow.json` with your image generation workflow
3. Toggle `allow_local_comfyui` on below and save
    """)

    _AIVIZ_CFG_PATH = _REPO / "genesis" / "config" / "ai_visuals.json"
    def _load_aiv_cfg() -> dict:
        if _AIVIZ_CFG_PATH.is_file():
            try:
                return _json_mod.loads(_AIVIZ_CFG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"enabled": True, "provider_mode": "auto", "allow_local_comfyui": False,
                "comfyui": {"endpoint_url": "http://127.0.0.1:8188"}}

    aiv_cfg = _load_aiv_cfg()
    st.markdown("""
**Auto-priority order** (highest quality available wins):
1. 🖥️ **ComfyUI** — if running locally (best quality, fully local)  
2. 🎨 **Automatic1111** — if running locally (Stable Diffusion WebUI, port 7860)  
3. 🌐 **Pollinations.ai** — free internet API, no key, uses FLUX model  
4. 🎞️ **Cinematic placeholder cards** — always works, no AI images
    """)

    # Live status check
    aiv_st_col1, aiv_st_col2, aiv_st_col3 = st.columns(3)
    with aiv_st_col1:
        try:
            from genesis.ai_visuals.provider_router import check_pollinations_available
            poll_ready, poll_msg = check_pollinations_available()
            if poll_ready:
                st.success("🌐 Pollinations.ai ✓")
            else:
                st.warning("🌐 Pollinations offline")
        except Exception:
            st.warning("🌐 Pollinations unknown")

    with aiv_st_col2:
        try:
            from genesis.ai_visuals.provider_router import check_auto1111_available
            a1_ready, a1_msg = check_auto1111_available(aiv_cfg)
            if a1_ready:
                st.success("🎨 Auto1111 ✓ (port 7860)")
            else:
                st.info("🎨 Auto1111 not running")
        except Exception:
            st.info("🎨 Auto1111 not running")

    with aiv_st_col3:
        try:
            from genesis.ai_visuals.provider_router import check_comfyui_available
            cfy_ready, cfy_msg = check_comfyui_available(aiv_cfg)
            if cfy_ready:
                st.success("🖥️ ComfyUI ✓ (port 8188)")
            else:
                st.info("🖥️ ComfyUI not running")
        except Exception:
            st.info("🖥️ ComfyUI not running")

    st.divider()
    aiv_col1, aiv_col2 = st.columns(2)
    with aiv_col1:
        allow_pollinations = st.toggle(
            "Allow Pollinations.ai (free FLUX images, needs internet)",
            value=bool(aiv_cfg.get("allow_pollinations", True)),
            key="allow_pollinations",
        )
        allow_auto1111 = st.toggle(
            "Allow Automatic1111 (local Stable Diffusion, port 7860)",
            value=bool(aiv_cfg.get("allow_auto1111", True)),
            key="allow_auto1111",
        )
        comfy_enabled = st.toggle(
            "Allow ComfyUI (local, requires workflow config)",
            value=bool(aiv_cfg.get("allow_local_comfyui")),
            key="comfy_enabled",
        )
    with aiv_col2:
        comfy_url = st.text_input("ComfyUI endpoint", value=aiv_cfg.get("comfyui", {}).get("endpoint_url", "http://127.0.0.1:8188"), key="comfy_url")
        comfy_workflow = st.text_input(
            "ComfyUI workflow JSON path",
            value=aiv_cfg.get("comfyui", {}).get("workflow_path", "genesis/config/comfyui_workflow.json"),
            key="comfy_workflow",
        )
        a1111_url = st.text_input(
            "Auto1111 endpoint",
            value=aiv_cfg.get("auto1111", {}).get("endpoint_url", "http://127.0.0.1:7860") if isinstance(aiv_cfg.get("auto1111"), dict) else "http://127.0.0.1:7860",
            key="a1111_url",
        )

    aiv_c1, aiv_c2 = st.columns(2)
    if aiv_c1.button("💾 Save Visual Config", key="btn_save_aiv"):
        aiv_cfg["allow_pollinations"] = allow_pollinations
        aiv_cfg["allow_auto1111"] = allow_auto1111
        aiv_cfg["allow_local_comfyui"] = comfy_enabled
        aiv_cfg.setdefault("comfyui", {})["endpoint_url"] = comfy_url
        aiv_cfg.setdefault("comfyui", {})["workflow_path"] = comfy_workflow
        aiv_cfg["auto1111"] = {"endpoint_url": a1111_url}
        try:
            _AIVIZ_CFG_PATH.write_text(_json_mod.dumps(aiv_cfg, indent=2), encoding="utf-8")
            st.success("✓ Visual generation config saved.")
        except Exception as exc:
            st.error(f"Save failed: {exc}")

    if aiv_c2.button("🔌 Test All Providers", key="btn_test_comfy"):
        import urllib.request as _ur
        for name, url, path in [
            ("ComfyUI", comfy_url, "/system_stats"),
            ("Auto1111", a1111_url, "/sdapi/v1/sd-models"),
        ]:
            try:
                with _ur.urlopen(url.rstrip("/") + path, timeout=3):
                    st.success(f"✓ {name} running at {url}")
            except Exception:
                st.info(f"  {name} not running at {url}")
        try:
            from genesis.ai_visuals.provider_router import check_pollinations_available
            ok, msg = check_pollinations_available()
            if ok:
                st.success("✓ Pollinations.ai reachable — FLUX images will be generated automatically")
            else:
                st.warning(f"Pollinations offline: {msg}")
        except Exception as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("Script Engine Status")
    st.caption("What happens when you click Create Video:")
    st.markdown("""
| Scenario | Script Source |
|----------|--------------|
| LLM enabled + server running | **Your Llama 3.1 model** writes a custom script for your exact idea |
| LLM enabled + server not running | Logs the error, falls back to templates |
| LLM disabled | Deterministic template engine (good quality for known formats like personal_story) |
| Neither | Placeholder text — this is what created your first bad video |
    """)

with tab_dashboard:
    st.header("Dashboard")
    st.caption("Build or open the local Genesis Studio dashboard.")

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    btn_build_dash = col_d1.button("🔨 Build Dashboard", key="btn_build_dash")
    btn_open_dash = col_d2.button("🌐 Open Dashboard", key="btn_open_dash")
    btn_refresh_thumbs = col_d3.button("🖼️ Refresh Thumbnails", key="btn_refresh_thumbs")
    btn_open_folder = col_d4.button("📂 Open Dashboard Folder", key="btn_open_folder")

    if btn_build_dash:
        with st.spinner("Building dashboard…"):
            result = rebuild_dashboard()
        _status_box(result, label="Dashboard")
        if result.output_paths.get("dashboard_html"):
            st.success(f"Dashboard HTML: `{result.output_paths['dashboard_html']}`")

    if btn_open_dash:
        dash_path = get_dashboard_path()
        if not Path(dash_path).is_file():
            with st.spinner("Building dashboard first…"):
                rebuild_dashboard()
        opened = open_in_browser(dash_path)
        if opened:
            st.success("Dashboard opened in browser.")
        else:
            st.info(f"Could not open browser automatically. Open manually:\n\n`{dash_path}`")

    if btn_refresh_thumbs:
        with st.spinner("Refreshing thumbnails…"):
            from genesis.dashboard.dashboard_cli import cmd_thumbnails
            import argparse
            try:
                ns = argparse.Namespace(runs_base="")
                cmd_thumbnails(ns)
                st.success("Thumbnails refreshed.")
            except Exception as exc:
                st.warning(f"Thumbnail refresh issue: {exc}")

    if btn_open_folder:
        dash_dir = _REPO / "assets" / "dashboard"
        st.info(f"Dashboard folder: `{dash_dir}`")
        open_in_browser(str(dash_dir / "index.html"))

    st.divider()
    st.subheader("Recent Runs")
    run_ids_d = list_run_ids(limit=20)
    if not run_ids_d:
        st.info("No runs found yet. Create a video first.")
    else:
        for rid in run_ids_d:
            run_dir = _RUNS_BASE / rid
            badge_p = run_dir / "ready_to_post_badge.txt"
            thumb_p = run_dir / "selected_thumbnail.jpg"
            badge_txt = ""
            if badge_p.is_file():
                try:
                    badge_txt = badge_p.read_text(encoding="utf-8").strip()
                except Exception:
                    pass
            video_ok = (run_dir / "draft_video.mp4").is_file()

            with st.container():
                dc1, dc2, dc3 = st.columns([1, 4, 2])
                with dc1:
                    if thumb_p.is_file():
                        try:
                            st.image(str(thumb_p), width=80)
                        except Exception:
                            st.caption("🖼️")
                    else:
                        st.caption("🎬")
                with dc2:
                    st.markdown(f"**{rid}**")
                    if video_ok:
                        st.caption("✓ draft_video.mp4")
                    if badge_txt:
                        color = "green" if "READY" in badge_txt else (
                            "orange" if "REVIEW" in badge_txt else "red"
                        )
                        st.markdown(f":{color}[{badge_txt}]")
                with dc3:
                    if st.button("Review", key=f"dash_review_{rid}"):
                        st.session_state["last_job_id"] = rid
                        st.info(f"Go to Review tab and load job `{rid}`")
