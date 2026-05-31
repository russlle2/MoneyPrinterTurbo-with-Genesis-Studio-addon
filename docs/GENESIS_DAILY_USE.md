# Genesis Studio — Daily Use Guide

This guide covers the complete daily workflow for creating, checking, and exporting
short-form videos with Genesis Studio.

**Baseline:** After Phase 28, all core features are production-ready. Stop feature-building
and use Genesis for real production testing.

---

## Open the Genesis Interface

Build and open the local dashboard in your browser:

```bash
python -m genesis.dashboard.dashboard_cli build
python -m genesis.dashboard.dashboard_cli open
```

Alternative (build + open in one command):

```bash
python -m genesis.project.batch_cli dashboard --open
```

If the browser does not open automatically, manually open:

```
assets/dashboard/index.html
```

(Open the file in any browser — it is a local static HTML file, no server required.)

---

## Single-Video Workflow

Full pipeline: create → thumbnail → quality check → export.

```bash
python -m genesis.creator.creator_cli create "your idea here" \
  --template affiliate_product \
  --platform tiktok \
  --brand bold_viral \
  --media ./clips \
  --music assets/music/light_energy.mp3 \
  --ai-visual-fill \
  --import-visuals \
  --select-thumbnail \
  --quality-check \
  --export
```

After it finishes:

```bash
python -m genesis.review.review_cli show <job_id>
```

---

## Batch Workflow

Create multiple videos from a JSON file:

```bash
python -m genesis.project.batch_cli batch-create batch_jobs.json
```

Export all complete runs for a platform:

```bash
python -m genesis.project.batch_cli batch-export job-001 job-002 job-003 --platform tiktok
```

List all indexed runs:

```bash
python -m genesis.project.batch_cli list --status complete
python -m genesis.project.batch_cli list --platform tiktok
```

---

## Manual Visual Import (Diffus.me / External Images)

After generating images externally (e.g. Diffus.me, Midjourney, DALL-E):

1. Place images in:

   ```
   assets/runs/<job_id>/manual_visual_imports/
   ```

2. Import and re-render:

   ```bash
   python -m genesis.ai_visuals.visual_cli import-and-render <job_id> \
     --platform tiktok --brand bold_viral
   ```

3. Validate imported assets:

   ```bash
   python -m genesis.ai_visuals.visual_cli validate <job_id>
   ```

---

## Quality Check Workflow

Run a standard quality check:

```bash
python -m genesis.quality.quality_cli check <job_id> --platform tiktok
```

Run a strict quality check (fails if NOT_READY):

```bash
python -m genesis.quality.quality_cli strict-check <job_id> --platform tiktok
```

Check multiple runs:

```bash
python -m genesis.quality.quality_cli batch-check job-001 job-002 --platform tiktok
```

Check the latest run:

```bash
python -m genesis.quality.quality_cli latest
```

Quality outputs written to:

- `assets/runs/<job_id>/ready_to_post_report.json`
- `assets/runs/<job_id>/ready_to_post_report.md`
- `assets/runs/<job_id>/ready_to_post_badge.txt`

---

## Thumbnail Selection Workflow

Auto-select the best thumbnail from manual files, generated visuals, and video frames:

```bash
python -m genesis.thumbnail.thumbnail_cli select <job_id>
```

Use a specific image as thumbnail:

```bash
python -m genesis.thumbnail.thumbnail_cli select <job_id> \
  --thumbnail-path ./my_thumbnail.jpg
```

List thumbnail candidates (without extracting frames):

```bash
python -m genesis.thumbnail.thumbnail_cli candidates <job_id>
```

Export the selected thumbnail for a specific platform:

```bash
python -m genesis.thumbnail.thumbnail_cli export <job_id> --platform tiktok
```

Select thumbnail for the latest run:

```bash
python -m genesis.thumbnail.thumbnail_cli latest
```

Thumbnail source priority:

1. Manual file (`thumbnail.jpg` / `thumbnail.png` in run folder)
2. Generated visual marked as thumbnail candidate
3. Video frame from `draft_video.mp4`
4. Placeholder fallback

---

## Dashboard Workflow

Build the local dashboard:

```bash
python -m genesis.dashboard.dashboard_cli build
```

Open in browser:

```bash
python -m genesis.dashboard.dashboard_cli open
```

Print dashboard path (for manual opening):

```bash
python -m genesis.dashboard.dashboard_cli open-path
```

Rebuild thumbnails only:

```bash
python -m genesis.dashboard.dashboard_cli thumbnails
```

Print summary counts:

```bash
python -m genesis.dashboard.dashboard_cli summary
```

---

## Export Workflow

Export a single run to a platform folder:

```bash
python -m genesis.review.review_cli export <job_id> --platform tiktok
```

Or via batch CLI:

```bash
python -m genesis.project.batch_cli batch-export <job_id> --platform tiktok
```

Export folder structure:

```
exports/<job_id>/tiktok/
├── README.md              ← posting instructions
├── draft_video.mp4        ← final video
├── selected_thumbnail.jpg ← selected thumbnail
├── caption.txt            ← post caption
├── hashtags.txt           ← hashtags
├── pinned_comment.txt     ← pin as first comment
├── posting_checklist.md   ← manual checklist
├── ready_to_post_report.md ← quality report
└── export_summary.json    ← export manifest
```

---

## Final Quality Check Before Posting

Run the full strict check, then open the dashboard for review:

```bash
python -m genesis.quality.quality_cli strict-check <job_id> --platform tiktok
python -m genesis.dashboard.dashboard_cli build
python -m genesis.dashboard.dashboard_cli open
```

---

## One-Command Final Video (Recommended)

```bash
python -m genesis.creator.creator_cli create "your idea here" \
  --template affiliate_product \
  --platform tiktok \
  --brand bold_viral \
  --media ./clips \
  --select-thumbnail \
  --quality-check \
  --export
```

---

## Batch Production Run (Recommended)

1. Create `batch_jobs.json` with your video ideas.
2. Run:

   ```bash
   python -m genesis.project.batch_cli batch-create batch_jobs.json
   python -m genesis.project.batch_cli batch-export job-001 job-002 --platform tiktok
   python -m genesis.dashboard.dashboard_cli build
   python -m genesis.dashboard.dashboard_cli open
   ```

3. Review each export folder before posting.

---

## Recommended Stop Point After Phase 28

Phase 28 is the final feature-building phase. After this point:

- Use Genesis for **real-world production testing**.
- Post videos manually using the generated export packages.
- Collect feedback on quality, engagement, and workflow friction.
- Do not add new features until you have completed at least 10 real production posts.

---

## What Not to Automate Yet

The following are **intentionally not automated** in Phase 28:

| Feature | Why not automated |
|---|---|
| Auto-posting | Platform APIs require careful review and compliance |
| Live trend lookup | Would add paid API dependencies |
| Scheduler | Out of scope until workflow is validated manually |
| Analytics dashboard | Post-production validation first |
| Cloud upload | Requires credentials management not yet designed |
| Multi-user support | Single-operator use case first |

These may be added in future phases after real-world testing.

---

## Troubleshooting

**Dashboard does not open automatically:**

```bash
python -m genesis.dashboard.dashboard_cli open-path
```

Open the printed path manually in your browser.

**Quality check fails with NEEDS_REVIEW:**

Read `assets/runs/<job_id>/ready_to_post_report.md` for specific issues and recommended fixes.

**No thumbnail found:**

```bash
python -m genesis.thumbnail.thumbnail_cli select <job_id>
```

Or manually place `thumbnail.jpg` in `assets/runs/<job_id>/` before running select.

**ComfyUI not available:**

Genesis will skip AI visual generation and fall back to prompt cards. Check
`assets/runs/<job_id>/provider_debug.md` for details.

**Missing media assets:**

Place clip files in `./clips/` or your `--media` folder and rerun:

```bash
python -m genesis.media.media_cli ingest-folder <job_id> ./clips
```
