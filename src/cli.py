"""CLI entry point for Agent Listening CLI (Audio-to-Music-IR).

Thin argument parsing wrapper delegating directly to `src.core`.
"""

import argparse
from contextlib import redirect_stdout
import json
from importlib.util import find_spec
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
import shutil
import sys
import tempfile

from src.resources import resource_path


def analyze(*args, **kwargs):
    from src.core import analyze as implementation

    return implementation(*args, **kwargs)


def build_ir_from_files(*args, **kwargs):
    from src.core import build_ir_from_files as implementation

    return implementation(*args, **kwargs)


RECEIPT_VERSION = "agent-listening/0.2"
VERSION = "0.2.0"
DOCTOR_SCHEMA_VERSION = "agent-listening-doctor/0.1"


def _installed_version() -> str:
    try:
        return version("agent-listening-cli")
    except PackageNotFoundError:
        return VERSION


def _probe_import(module_names):
    """Check module discoverability without importing a model or native runtime."""
    errors = []
    for module_name in module_names:
        try:
            if find_spec(module_name) is None:
                raise ModuleNotFoundError(module_name)
            return {"status": "passed", "module": module_name}
        except Exception as exc:  # pragma: no cover - exact native error varies
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
    return {"status": "failed", "code": "import_failed", "detail": "; ".join(errors)}


def _dependency_check(check_id, distribution, modules):
    try:
        installed = version(distribution)
    except PackageNotFoundError:
        return {"id": check_id, "status": "failed", "code": "missing_dependency", "distribution": distribution}
    result = {"id": check_id, "version": installed}
    if modules:
        result.update(_probe_import(modules))
    else:
        result["status"] = "passed"
    return result


def _executable_path(name):
    return shutil.which(name) or shutil.which(name, path=str(Path(sys.executable).parent))


def _output_check(output_dir):
    target = Path(output_dir).expanduser() if output_dir else None
    if target is not None and target.exists() and not target.is_dir():
        return {
            "id": "output.write",
            "status": "failed",
            "code": "output_not_writable",
            "path": str(target),
        }
    parent = target if target and target.is_dir() else (target.parent if target else None)
    if parent is not None and not parent.exists():
        return {
            "id": "output.write",
            "status": "failed",
            "code": "output_not_writable",
            "path": str(target),
        }
    try:
        with tempfile.TemporaryDirectory(
            dir=str(parent) if parent else None,
            prefix=".agent-listening-doctor-",
        ) as temp_dir:
            probe = Path(temp_dir) / "probe"
            staged = Path(temp_dir) / "probe.staged"
            staged.write_text("ok", encoding="utf-8")
            staged.replace(probe)
            if probe.read_text(encoding="utf-8") != "ok":
                raise OSError("write probe content mismatch")
    except Exception as exc:
        return {
            "id": "output.write",
            "status": "failed",
            "code": "output_not_writable",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    return {"id": "output.write", "status": "passed"}


def _doctor_report(analysis_mode="solo", output_dir=None):
    checks = []
    python_status = "passed" if sys.version_info[:2] == (3, 11) else "failed"
    checks.append({
        "id": "python.runtime",
        "status": python_status,
        "version": platform.python_version(),
        **({} if python_status == "passed" else {"code": "unsupported_python"}),
    })

    for relative_path, check_id in (
        (Path("profiles") / "essentia_v0_1.yaml", "resource.profile"),
        (Path("schemas") / "music-ir-v0.1.schema.json", "resource.schema.0.1"),
        (Path("schemas") / "music-ir-v0.2.schema.json", "resource.schema.0.2"),
    ):
        try:
            resource = resource_path(str(relative_path.parent), relative_path.name)
        except FileNotFoundError as exc:
            checks.append({
                "id": check_id,
                "status": "failed",
                "code": "missing_resource",
                "detail": str(exc),
            })
        else:
            checks.append({"id": check_id, "status": "passed", "path": str(resource)})

    checks.append(_dependency_check("dependency.essentia", "essentia", ["essentia"]))
    checks.append(_dependency_check("dependency.basic-pitch", "basic-pitch", ["basic_pitch"]))
    if analysis_mode == "full_mix":
        checks.append(_dependency_check("dependency.all-in-one-infer", "all-in-one-infer", ["allin1_infer", "allin1"]))
        demucs = _dependency_check("dependency.demucs-infer", "demucs-infer", None)
        if demucs["status"] == "passed" and _executable_path("demucs-infer") is None:
            demucs.update({"status": "failed", "code": "missing_executable", "executable": "demucs-infer"})
        elif demucs["status"] == "passed":
            demucs["executable"] = _executable_path("demucs-infer")
        checks.append(demucs)
    checks.append(_output_check(output_dir))
    return {
        "schema_version": DOCTOR_SCHEMA_VERSION,
        "status": "ready" if all(check["status"] == "passed" for check in checks) else "not_ready",
        "agent_listening_version": _installed_version(),
        "analysis_mode": analysis_mode,
        "platform": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "checks": checks,
        "limitations": [
            "model_weights_not_loaded",
            "audio_inference_not_run",
            "human_listening_not_performed",
        ],
    }


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
    next_artifacts = ["music_ir", "jams"]
    if artifacts.get("symbols"):
        next_artifacts.append("symbols")
    if artifacts.get("stems"):
        next_artifacts.append("stems")
    if artifacts.get("raw_dir"):
        next_artifacts.append("raw_dir")
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
        "next": next_artifacts,
    }


def _print_receipt(receipt: dict, stream=None) -> None:
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True), file=stream or sys.stdout)


def main():
    parser = argparse.ArgumentParser(
        prog="agent-listening",
        description="Agent Listening CLI (Audio-to-Music-IR) Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_installed_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: doctor
    p_doctor = subparsers.add_parser("doctor", help="Check installed dependencies and resources without analyzing audio")
    p_doctor.add_argument(
        "--analysis-mode",
        choices=["full_mix", "stem", "solo"],
        default="solo",
        help="Dependency surface to check",
    )
    p_doctor.add_argument("-o", "--output-dir", default=None, help="Optional output directory to probe")
    p_doctor.add_argument("--json", action="store_true", help="Print a machine-readable diagnostic report")

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
        if args.command == "doctor":
            report = _doctor_report(args.analysis_mode, args.output_dir)
            if args.json:
                _print_receipt(report)
            else:
                print(f"[{report['status']}] agent-listening {report['agent_listening_version']} ({args.analysis_mode})")
                for check in report["checks"]:
                    suffix = f" ({check.get('code')})" if check.get("code") else ""
                    print(f"- {check['id']}: {check['status']}{suffix}")
            if report["status"] != "ready":
                sys.exit(1)
        elif args.command == "analyze":
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
            })
        else:
            print(f"[Error] {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
