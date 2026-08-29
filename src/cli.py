"""CLI entry point for Agent Listening CLI (Audio-to-Music-IR).

Thin argument parsing wrapper delegating directly to `src.core`.
"""

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

from src.core import analyze, build_ir_from_files


RECEIPT_VERSION = "agent-listening/0.2"


def _receipt(command: str, output_dir: str, music_ir: dict, raw_dir: bool = False) -> dict:
    base = Path(output_dir).resolve()
    track_id = music_ir["track"]["id"]
    artifacts = {
        "music_ir": str(base / "music-ir" / f"{track_id}.music-ir.json"),
        "jams": str(base / "jams" / f"{track_id}.analysis.jams"),
        "raw_dir": str(base / "raw" / track_id) if raw_dir else None,
    }
    raw_root = base / "raw" / track_id
    if raw_dir and raw_root.is_dir():
        artifacts["raw"] = sorted(str(path) for path in raw_root.rglob("*") if path.is_file())
    symbols = music_ir.get("symbols", {})
    if symbols.get("artifacts"):
        artifacts["symbols"] = [str(base / path) if not Path(path).is_absolute() else path for path in symbols["artifacts"]]
    if music_ir.get("sources"):
        artifacts["stems"] = [
            str(base / source["audio_file"]) if not Path(source["audio_file"]).is_absolute() else source["audio_file"]
            for source in music_ir["sources"] if source.get("audio_file")
        ]
    return {
        "receipt_version": RECEIPT_VERSION,
        "status": "success",
        "command": command,
        "track_id": track_id,
        "artifacts": artifacts,
        "capabilities": music_ir.get("capabilities", {}),
        "validation": {
            "music_ir": "passed",
            "jams_base_schema": "passed",
            "jams_namespace_strict": "not_claimed",
            "human_listening": "passed" if music_ir.get("review", {}).get("human_checked") else "pending",
        },
        "next": ["music_ir", "jams", "symbols", "raw_dir"],
    }


def _print_receipt(receipt: dict, stream=None) -> None:
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True), file=stream or sys.stdout)


def main():
    parser = argparse.ArgumentParser(
        prog="agent-listening",
        description="Agent Listening CLI (Audio-to-Music-IR) Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze audio file into Music IR, JAMS, and evidence artifacts")
    p_analyze.add_argument("audio_path", help="Path to input audio file (.wav, .flac)")
    p_analyze.add_argument("-o", "--output-dir", default=".", help="Base output directory")
    p_analyze.add_argument("-p", "--profile", default="essentia_v0_1", help="Essentia profile name")
    p_analyze.add_argument("--analysis-mode", choices=["full_mix", "stem", "solo"], default="full_mix", help="Track analysis mode")
    p_analyze.add_argument("--overwrite", action="store_true", help="Replace existing artifacts for this track")
    p_analyze.add_argument("--json", action="store_true", help="Print a machine-readable result receipt")

    # Subcommand: build-ir
    p_build = subparsers.add_parser("build-ir", help="Fuse pre-existing extractor JSONs into IR and JAMS")
    p_build.add_argument("--allin1", required=False, help="Optional path to raw allin1 output JSON (full_mix only)")
    p_build.add_argument("--essentia", required=True, help="Path to raw Essentia output JSON")
    p_build.add_argument("--track-id", default=None, help="Track identifier")
    p_build.add_argument("--source-file", default=None, help="Path to original source file")
    p_build.add_argument("-o", "--output-dir", default=".", help="Base output directory")
    p_build.add_argument("-p", "--profile", default="essentia_v0_1", help="Profile name used")
    p_build.add_argument("--analysis-mode", choices=["full_mix", "stem", "solo"], default="full_mix", help="Track analysis mode")
    p_build.add_argument("--overwrite", action="store_true", help="Replace existing artifacts for this track")
    p_build.add_argument("--json", action="store_true", help="Print a machine-readable result receipt")

    args = parser.parse_args()

    try:
        if args.command == "analyze":
            analyze_kwargs = {
                "audio_path": args.audio_path,
                "output_dir": args.output_dir,
                "profile": args.profile,
                "analysis_mode": args.analysis_mode,
                "overwrite": args.overwrite,
            }
            # Native/model libraries sometimes print progress to stdout. Keep
            # --json a single machine-readable receipt by routing that chatter
            # to stderr.
            if args.json:
                with redirect_stdout(sys.stderr):
                    ir = analyze(**analyze_kwargs)
            else:
                ir = analyze(**analyze_kwargs)
            if args.json:
                _print_receipt(_receipt("analyze", args.output_dir, ir, raw_dir=True))
            else:
                print(f"[✓] Successfully analyzed '{args.audio_path}' -> Key: {ir['global']['key_summary']}, Tempo: {ir['global']['tempo_bpm']['value']} BPM")
        elif args.command == "build-ir":
            jams_data, music_ir = build_ir_from_files(
                allin1_path=args.allin1,
                essentia_path=args.essentia,
                track_id=args.track_id,
                source_file=args.source_file,
                output_dir=args.output_dir,
                profile_name=args.profile,
                analysis_mode=args.analysis_mode,
                overwrite=args.overwrite,
            )
            if args.json:
                _print_receipt(_receipt("build-ir", args.output_dir, music_ir, raw_dir=False))
            else:
                print(f"[✓] Successfully compiled IR and JAMS for track '{music_ir['track']['id']}'")
    except Exception as err:
        if getattr(args, "json", False):
            _print_receipt({
                "receipt_version": RECEIPT_VERSION,
                "status": "error",
                "command": args.command,
                "error": {"type": type(err).__name__, "message": str(err)},
            }, stream=sys.stderr)
        else:
            print(f"[Error] {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
