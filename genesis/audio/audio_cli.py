"""Genesis Studio — Audio CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="genesis.audio.audio_cli")
    p.add_argument("--runs-base", default="")
    p.add_argument("--repo-root", default="")
    sub = p.add_subparsers(dest="command")

    ins = sub.add_parser("inspect")
    ins.add_argument("file")

    plan = sub.add_parser("plan")
    plan.add_argument("job_id")

    mix = sub.add_parser("mix")
    mix.add_argument("job_id")
    mix.add_argument("--music", default="")
    mix.add_argument("--music-volume", type=float, default=0.18)
    mix.add_argument("--narration-volume", type=float, default=1.0)
    mix.add_argument("--no-duck", action="store_true")

    ml = sub.add_parser("music-list")
    ml.add_argument("job_id")
    ml.add_argument("--global", action="store_true", dest="allow_global")

    args = p.parse_args(argv)
    repo = Path(args.repo_root) if args.repo_root else _REPO
    runs = Path(args.runs_base) if args.runs_base else repo / "assets" / "runs"

    if args.command == "inspect":
        from genesis.audio.audio_inspector import inspect_audio_file
        a = inspect_audio_file(Path(args.file))
        print(json.dumps(a.to_dict(), indent=2))
        return 0

    if args.command == "music-list":
        from genesis.audio.music_bed import find_music_assets_for_run
        run_dir = runs / args.job_id
        assets = find_music_assets_for_run(run_dir, repo_root=repo, allow_global=args.allow_global)
        for a in assets:
            print(f"  {a.filename} ({a.volume_role}) {a.duration_seconds}s")
        return 0

    if args.command in ("plan", "mix"):
        from genesis.video.media_resolver import resolve_narration_path
        from genesis.audio.audio_mixer import run_audio_mix_for_job, build_audio_mix_plan
        from genesis.audio.audio_models import AudioMixSettings
        from genesis.audio.music_bed import find_music_assets_for_run, select_music_bed

        run_dir = runs / args.job_id
        narr = resolve_narration_path(args.job_id, run_dir, repo_root=repo)
        settings = AudioMixSettings(
            music_volume=getattr(args, "music_volume", 0.18),
            narration_volume=getattr(args, "narration_volume", 1.0),
            duck_music_under_voice=not getattr(args, "no_duck", False),
        )
        if args.command == "plan":
            narr_p = repo / narr if narr else Path()
            music_assets = find_music_assets_for_run(run_dir, repo_root=repo, allow_global=True)
            m = select_music_bed(music_assets, explicit_path=getattr(args, "music", "") or "", repo_root=repo)
            music_p = (repo / m.stored_path) if m else None
            plans, _, w = build_audio_mix_plan(
                args.job_id, narration_path=narr_p, music_path=music_p, settings=settings,
            )
            doc = {"track_plans": [x.to_dict() for x in plans], "warnings": w}
            (run_dir / "audio_mix_plan.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
            print(f"Wrote {run_dir / 'audio_mix_plan.json'}")
            return 0

        result = run_audio_mix_for_job(
            args.job_id,
            narration_rel=narr,
            run_dir=run_dir,
            repo_root=repo,
            music_path=getattr(args, "music", "") or None,
            settings=settings,
            allow_global_music=True,
        )
        from genesis.audio.audio_manifest import build_audio_manifest, write_audio_manifest
        write_audio_manifest(run_dir, build_audio_manifest(args.job_id, mix_result=result))
        print(f"Status: {result.status}  Output: {result.output_path}")
        return 0 if result.status in ("complete", "partial") else 1

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
