"""CLI Entrypoint for Agent Listening (Audio-to-Music-IR).

Thin argument parsing wrapper delegating directly to `src.core`.
"""

import argparse
from pathlib import Path
import sys

from src.core import analyze, build_ir_from_files


def main():
    parser = argparse.ArgumentParser(
        description="Agent Listening (Audio-to-Music-IR) CLI Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze audio file using allin1 and Essentia")
    p_analyze.add_argument("audio_path", help="Path to input audio file (.wav, .flac)")
    p_analyze.add_argument("-o", "--output-dir", default=".", help="Base output directory")
    p_analyze.add_argument("-p", "--profile", default="essentia_v0_1", help="Essentia profile name")
    p_analyze.add_argument("--enable-symbols", action="store_true", help="Enable symbolic / MIDI transcription (ADR-0007)")
    p_analyze.add_argument("--analysis-mode", choices=["full_mix", "stem", "solo"], default="full_mix", help="Track analysis mode")

    # Subcommand: build-ir
    p_build = subparsers.add_parser("build-ir", help="Fuse pre-existing extractor JSONs into IR and JAMS")
    p_build.add_argument("--allin1", required=True, help="Path to raw allin1 output JSON")
    p_build.add_argument("--essentia", required=True, help="Path to raw Essentia output JSON")
    p_build.add_argument("--track-id", default=None, help="Track identifier")
    p_build.add_argument("--source-file", default=None, help="Path to original source file")
    p_build.add_argument("-o", "--output-dir", default=".", help="Base output directory")
    p_build.add_argument("-p", "--profile", default="essentia_v0_1", help="Profile name used")
    p_build.add_argument("--enable-symbols", action="store_true", help="Enable symbolic / MIDI transcription (ADR-0007)")
    p_build.add_argument("--analysis-mode", choices=["full_mix", "stem", "solo"], default="full_mix", help="Track analysis mode")

    args = parser.parse_args()

    try:
        if args.command == "analyze":
            ir = analyze(
                audio_path=args.audio_path,
                output_dir=args.output_dir,
                profile=args.profile,
                enable_symbols=args.enable_symbols,
                analysis_mode=args.analysis_mode,
            )
            print(f"[✓] Successfully analyzed '{args.audio_path}' -> Key: {ir['global']['key_summary']}, Tempo: {ir['global']['tempo_bpm']['value']} BPM")
        elif args.command == "build-ir":
            jams_data, music_ir = build_ir_from_files(
                allin1_path=args.allin1,
                essentia_path=args.essentia,
                track_id=args.track_id,
                source_file=args.source_file,
                output_dir=args.output_dir,
                profile_name=args.profile,
                enable_symbols=args.enable_symbols,
                analysis_mode=args.analysis_mode,
            )
            print(f"[✓] Successfully compiled IR and JAMS for track '{music_ir['track']['id']}'")
    except Exception as err:
        print(f"[Error] {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
