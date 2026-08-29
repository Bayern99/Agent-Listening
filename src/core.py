"""Core Analysis Pipeline & Deep Module Implementation.

Provides the minimal public interface for the audio-to-music-ir system.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional, Tuple

from src.adapters.allin1_adapter import AllInOneAdapter
from src.adapters.basic_pitch_adapter import BasicPitchAdapter
from src.adapters.demucs_adapter import DemucsAdapter
from src.adapters.essentia_adapter import EssentiaAdapter
from src.fusion.builder import merge_evidence


def _sha256_file(path: Path) -> str:
    with open(path, "rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _artifact_paths(output_dir: str, track_id: str) -> Tuple[Path, Path]:
    if not track_id or Path(track_id).name != track_id or track_id in {".", ".."}:
        raise ValueError("track_id must be a single safe path component")
    out_base = Path(output_dir)
    return (
        out_base / "jams" / f"{track_id}.analysis.jams",
        out_base / "music-ir" / f"{track_id}.music-ir.json",
    )


def _assert_writable(paths: Tuple[Path, ...], overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {existing[0]}")


def _write_artifacts(
    jams_data: Dict[str, Any],
    music_ir: Dict[str, Any],
    output_dir: str,
    track_id: str,
    overwrite: bool,
    raw_files: Optional[Dict[str, Path]] = None,
    artifact_files: Optional[Dict[str, Path]] = None,
) -> None:
    jams_file, ir_file = _artifact_paths(output_dir, track_id)
    raw_files = raw_files or {}
    raw_destinations = {
        name: Path(output_dir) / "raw" / track_id / f"{name}.json"
        for name in raw_files
    }
    artifact_files = artifact_files or {}
    artifact_destinations = {Path(relative): source for relative, source in artifact_files.items()}
    extra_destinations = [Path(output_dir) / relative for relative in artifact_destinations]
    _assert_writable((jams_file, ir_file, *raw_destinations.values(), *extra_destinations), overwrite)

    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out_base, prefix=f".{track_id}-commit-") as temp_dir:
        stage = Path(temp_dir)
        staged_jams = stage / jams_file.name
        staged_ir = stage / ir_file.name
        staged_jams.write_text(json.dumps(jams_data, indent=2, ensure_ascii=False), encoding="utf-8")
        staged_ir.write_text(json.dumps(music_ir, indent=2, ensure_ascii=False), encoding="utf-8")
        staged_raw = {}
        for name, source in raw_files.items():
            staged_raw[name] = stage / f"{name}.json"
            staged_raw[name].parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staged_raw[name])

        destinations = [(staged_jams, jams_file), (staged_ir, ir_file)]
        destinations.extend((staged_raw[name], destination) for name, destination in raw_destinations.items())
        staged_extra = {}
        for relative, source in artifact_destinations.items():
            staged_extra[relative] = stage / relative
            destinations.append((staged_extra[relative], Path(output_dir) / relative))
            staged_extra[relative].parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staged_extra[relative])
        for _, destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
        for source, destination in destinations:
            source.replace(destination)


def build_ir_from_files(
    allin1_path: Optional[str],
    essentia_path: str,
    track_id: Optional[str] = None,
    source_file: Optional[str] = None,
    output_dir: str = ".",
    profile_name: str = "essentia_v0_1",
    analysis_mode: str = "full_mix",
    created_at: Optional[str] = None,
    overwrite: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Compile MusicIR and JAMS from existing JSON files (pure offline mode)."""
    if analysis_mode not in {"full_mix", "stem", "solo"}:
        raise ValueError(f"Unsupported analysis_mode: {analysis_mode}")
    if allin1_path and analysis_mode != "full_mix":
        raise ValueError("allin1 evidence is only valid for full_mix mode")
    allin1_raw = None
    if allin1_path:
        with open(allin1_path, "r", encoding="utf-8") as f:
            allin1_raw = json.load(f)
    with open(essentia_path, "r", encoding="utf-8") as f:
        essentia_raw = json.load(f)

    if track_id is None:
        track_id = Path(allin1_path or essentia_path).stem.replace(".allin1", "").replace(".raw", "")
    if source_file is None:
        source_file = f"source/{track_id}.wav"

    allin1_ev = AllInOneAdapter().parse_output(allin1_raw) if allin1_raw is not None else None
    essentia_ev = EssentiaAdapter().parse_output(essentia_raw, profile_name=profile_name)
    if allin1_ev is not None and allin1_path:
        allin1_ev.raw_sha256 = _sha256_file(Path(allin1_path))
    essentia_ev.raw_sha256 = _sha256_file(Path(essentia_path))
    profile_path = Path(__file__).parent.parent / "profiles" / f"{profile_name}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Essentia profile not found: {profile_path}")
    essentia_ev.profile_sha256 = _sha256_file(profile_path)

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    source_path = Path(source_file)
    source_sha256 = _sha256_file(source_path) if source_path.is_file() else None

    jams_data, music_ir = merge_evidence(
        allin1_evidence=allin1_ev,
        essentia_evidence=essentia_ev,
        track_id=track_id,
        source_file=source_file,
        analysis_mode=analysis_mode,
        profile_name=profile_name,
        raw_paths={"allin1": allin1_path, "essentia": essentia_path} if allin1_path else {"essentia": essentia_path},
        created_at=created_at,
        source_sha256=source_sha256,
    )

    _write_artifacts(jams_data, music_ir, output_dir, track_id, overwrite)

    return jams_data, music_ir


def analyze(
    audio_path: str,
    output_dir: str = ".",
    profile: str = "essentia_v0_1",
    profile_path: Optional[str] = None,
    analysis_mode: str = "full_mix",
    created_at: Optional[str] = None,
    allin1_adapter: Optional[AllInOneAdapter] = None,
    essentia_adapter: Optional[EssentiaAdapter] = None,
    demucs_adapter: Optional[DemucsAdapter] = None,
    basic_pitch_adapter: Optional[BasicPitchAdapter] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Small public interface: analyze(audio_path, profile) -> MusicIR.

    Hides the complexity of subprocess invocation, JSON normalization,
    pure evidence fusion, and dual-artifact persistence.
    """
    if analysis_mode not in {"full_mix", "stem", "solo"}:
        raise ValueError(f"Unsupported analysis_mode: {analysis_mode}")
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    track_id = audio_file.stem
    out_base = Path(output_dir)
    raw_dir = out_base / "raw" / track_id
    essentia_raw_path = raw_dir / "essentia.json"
    jams_file, ir_file = _artifact_paths(output_dir, track_id)
    _assert_writable((essentia_raw_path, jams_file, ir_file), overwrite)

    if profile_path is None:
        profile_path = str(Path(__file__).parent.parent / "profiles" / f"{profile}.yaml")
    profile_file = Path(profile_path)
    if not profile_file.exists():
        raise FileNotFoundError(f"Essentia profile not found: {profile_path}")

    out_base.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out_base, prefix=f".{track_id}-extract-") as temp_dir:
        staged_allin1 = Path(temp_dir) / "allin1.json"
        staged_essentia = Path(temp_dir) / "essentia.json"
        raw_files: Dict[str, Path] = {"essentia": staged_essentia}
        artifact_files: Dict[str, Path] = {}

        # Essentia is the common evidence engine for every input mode.
        adapter_essentia = essentia_adapter or EssentiaAdapter()
        essentia_raw = adapter_essentia.run(str(audio_file), profile_path, str(staged_essentia))
        essentia_ev = adapter_essentia.parse_output(essentia_raw, profile_name=profile)
        essentia_ev.raw_sha256 = _sha256_file(staged_essentia)
        essentia_ev.profile_sha256 = _sha256_file(profile_file)

        allin1_ev = None
        raw_paths: Dict[str, str] = {"essentia": str(essentia_raw_path)}
        if analysis_mode == "full_mix":
            adapter_allin1 = allin1_adapter or AllInOneAdapter()
            allin1_raw = adapter_allin1.run(str(audio_file), str(staged_allin1))
            allin1_ev = adapter_allin1.parse_output(allin1_raw)
            allin1_ev.raw_sha256 = _sha256_file(staged_allin1)
            raw_files["allin1"] = staged_allin1
            raw_paths["allin1"] = str(raw_dir / "allin1.json")

        pitch_evidence: Optional[Dict[str, Any]] = None
        symbols: Optional[Dict[str, Any]] = None
        sources: List[Dict[str, Any]] = []

        def _write_returned_json(path: Path, value: Any) -> None:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value, indent=2), encoding="utf-8")

        def _run_pitch(source_path: Path, source_id: str) -> Optional[Dict[str, Any]]:
            raw_pitch_path = Path(temp_dir) / f"{source_id}.pitch.json"
            try:
                raw_pitch = adapter_essentia.run_pitch(str(source_path), str(raw_pitch_path))
                _write_returned_json(raw_pitch_path, raw_pitch)
                result = EssentiaAdapter.parse_pitch_output(raw_pitch)
                result["artifact"] = str(raw_dir / "pitch.json") if source_id == track_id else str(raw_dir / "stems" / f"{source_id}.pitch.json")
                result["source_sha256"] = _sha256_file(source_path)
                result["raw_sha256"] = _sha256_file(raw_pitch_path)
                if source_id == track_id:
                    raw_files["pitch"] = raw_pitch_path
                else:
                    raw_files[f"stems/{source_id}.pitch"] = raw_pitch_path
                return result
            # ponytail: pitch is optional; keep acoustic evidence when the
            # codec or native algorithm cannot read one source.
            except Exception:
                return {"status": "failed", "tool": "essentia.pitch_yin_probabilistic", "contour": [], "artifact": None}

        def _run_notes(source_path: Path, source_id: str) -> Dict[str, Any]:
            adapter_notes = basic_pitch_adapter or BasicPitchAdapter()
            try:
                result = adapter_notes.run(str(source_path), str(Path(temp_dir) / "symbols"), source_id)
                if not isinstance(result, dict):
                    raise TypeError("Basic Pitch adapter must return a mapping")
            # ponytail: note extraction is optional; preserve the primary IR when
            # a model, codec, or input format is unavailable.
            except Exception:
                return {
                    "status": "failed",
                    "tool": "basic-pitch",
                    "version": "unknown",
                    "notes": [],
                    "artifacts": [],
                    "ground_truth": False,
                }
            note_artifacts = BasicPitchAdapter.artifact_paths(result)
            notes_path = note_artifacts["notes"]
            midi_path = note_artifacts["midi"]
            final_notes = Path("symbols") / track_id / f"{source_id}.notes.json"
            final_midi = Path("symbols") / track_id / f"{source_id}.mid"
            artifacts = []
            if notes_path and notes_path.is_file():
                artifact_files[str(final_notes)] = notes_path
                raw_files[f"basic-pitch/{source_id}.notes"] = notes_path
                artifacts.append(str(final_notes))
            if midi_path and midi_path.is_file():
                artifact_files[str(final_midi)] = midi_path
                artifacts.append(str(final_midi))
            result["artifacts"] = artifacts
            result["ground_truth"] = False
            result["source_id"] = source_id
            result["source_sha256"] = _sha256_file(source_path)
            result["audio_path"] = (
                str(source_path)
                if source_id == track_id
                else str(Path("stems") / track_id / f"{source_id}.wav")
            )
            if notes_path and notes_path.is_file():
                result["notes_path"] = str(final_notes)
                result["midi_path"] = str(final_midi) if midi_path and midi_path.is_file() else None
                result["raw_json"] = str(raw_dir / "basic-pitch" / f"{source_id}.notes.json")
                notes_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                result["raw_sha256"] = _sha256_file(notes_path)
            return result

        if analysis_mode in {"solo", "stem"}:
            pitch_evidence = _run_pitch(audio_file, track_id)
            symbols = _run_notes(audio_file, track_id)
        elif analysis_mode == "full_mix":
            separator = demucs_adapter or DemucsAdapter()
            try:
                manifest = separator.run(str(audio_file), str(Path(temp_dir) / "demucs"))
                manifest_path = Path(temp_dir) / "demucs" / "demucs-manifest.json"
                _write_returned_json(manifest_path, manifest)
                raw_files["demucs-manifest"] = manifest_path
                raw_paths["demucs"] = str(raw_dir / "demucs-manifest.json")
                demucs_metadata = DemucsAdapter.metadata(manifest)
                raw_paths["demucs_version"] = demucs_metadata["version"]
                raw_paths["demucs_model"] = demucs_metadata["model"]
                for stem in DemucsAdapter.parse_manifest(manifest):
                    stem_id = stem["id"]
                    stem_path = Path(stem["path"])
                    final_stem = Path("stems") / track_id / f"{stem_id}.wav"
                    artifact_files[str(final_stem)] = stem_path
                    stem_record: Dict[str, Any] = {
                        "id": stem_id,
                        "role": stem.get("role", stem_id),
                        "audio_file": str(final_stem),
                        "source_sha256": _sha256_file(stem_path),
                        "duration_s": stem.get("duration_s"),
                        "activity": {
                            "status": "not_detected",
                            "loudness_lufs": None,
                            "energy": None,
                            "onset_rate_per_s": None,
                        },
                        "extractor": {
                            "tool": "essentia",
                            "version": "unknown",
                            "profile": profile,
                            "source_sha256": _sha256_file(stem_path),
                            "raw_json": str(raw_dir / "stems" / f"{stem_id}.essentia.json"),
                            "raw_sha256": None,
                            "status": "not_detected",
                        },
                        "separation": {
                            "tool": demucs_metadata["tool"],
                            "version": demucs_metadata["version"],
                            "model": demucs_metadata["model"],
                        },
                        "status": "available",
                    }
                    try:
                        stem_raw_path = Path(temp_dir) / f"{stem_id}.essentia.json"
                        stem_raw = adapter_essentia.run(str(stem_path), profile_path, str(stem_raw_path))
                        stem_ev = adapter_essentia.parse_output(stem_raw, profile_name=profile)
                        stem_record["duration_s"] = round(stem_ev.duration_s, 2)
                        stem_record["audio_features"] = {
                            "loudness_lufs": round(stem_ev.loudness_ebu128_integrated_lufs, 2),
                            "spectral_centroid_hz": round(stem_ev.spectral_centroid_hz_mean, 2),
                            "onset_rate_per_s": round(stem_ev.onset_rate_per_s, 2),
                        }
                        stem_record["activity"] = {
                            "status": "available",
                            "loudness_lufs": round(stem_ev.loudness_ebu128_integrated_lufs, 2),
                            "energy": stem_ev.feature_summaries.get("spectral_energy"),
                            "onset_rate_per_s": round(stem_ev.onset_rate_per_s, 2),
                        }
                        stem_record["extractor"] = {
                            "tool": "essentia",
                            "version": stem_ev.tool_version,
                            "profile": profile,
                            "source_sha256": stem_record["source_sha256"],
                            "raw_json": str(raw_dir / "stems" / f"{stem_id}.essentia.json"),
                            "raw_sha256": _sha256_file(stem_raw_path),
                            "status": "available",
                            "timestamp_semantics": stem_ev.frame_features.get("time_basis", {}),
                        }
                        raw_files[f"stems/{stem_id}.essentia"] = stem_raw_path
                    except Exception:
                        # Optional per-stem evidence must not erase successful
                        # separation or other stems; the status stays explicit.
                        stem_record["status"] = "failed"
                        stem_record["extractor"]["status"] = "failed"
                    if stem_id != "drums":
                        stem_record["pitch"] = _run_pitch(stem_path, stem_id)
                        stem_record["notes"] = _run_notes(stem_path, stem_id)
                    else:
                        stem_record["notes"] = {"status": "not_applicable", "notes": [], "ground_truth": False}
                    sources.append(stem_record)
                # Keep the raw manifest useful after the temporary extraction
                # directory is removed: point `path` at committed artifacts
                # and preserve the extractor path for audit.
                manifest_for_artifact = DemucsAdapter.artifact_manifest(manifest, track_id)
                manifest_path.write_text(json.dumps(manifest_for_artifact, indent=2), encoding="utf-8")
                raw_paths["demucs_sha256"] = _sha256_file(manifest_path)
                raw_paths["demucs_status"] = manifest_for_artifact["status"]
                all_notes = [note for source in sources for note in source.get("notes", {}).get("notes", [])]
                all_artifacts = [artifact for source in sources for artifact in source.get("notes", {}).get("artifacts", [])]
                note_summary = BasicPitchAdapter.parse_note_events(
                    [
                        (
                            note["start_s"],
                            note["end_s"],
                            note["midi_pitch"],
                            note.get("amplitude", 0.0),
                            note.get("pitch_bends"),
                            note.get("confidence"),
                        )
                        for note in all_notes
                    ],
                    tool_version=next(
                        (
                            source.get("notes", {}).get("version")
                            for source in sources
                            if source.get("notes", {}).get("version")
                        ),
                        "0.4.0",
                    ),
                )
                symbols = {
                    **note_summary,
                    "notes": all_notes,
                    "artifacts": all_artifacts,
                    "ground_truth": False,
                }
            except Exception as exc:
                failure_manifest = {
                    "tool": "demucs-infer",
                    "model": getattr(separator, "model", "htdemucs_6s"),
                    "version": "4.2.2",
                    "status": "failed",
                    "error": str(exc),
                }
                manifest_path = Path(temp_dir) / "demucs" / "demucs-manifest.json"
                _write_returned_json(manifest_path, failure_manifest)
                raw_files["demucs-manifest"] = manifest_path
                raw_paths["demucs"] = str(raw_dir / "demucs-manifest.json")
                raw_paths["demucs_version"] = failure_manifest["version"]
                raw_paths["demucs_model"] = failure_manifest["model"]
                raw_paths["demucs_sha256"] = _sha256_file(manifest_path)
                raw_paths["demucs_status"] = "failed"
                symbols = {"status": "not_applicable", "notes": [], "artifacts": [], "ground_truth": False}

        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()

        jams_data, music_ir = merge_evidence(
            allin1_evidence=allin1_ev,
            essentia_evidence=essentia_ev,
            track_id=track_id,
            source_file=str(audio_file),
            analysis_mode=analysis_mode,
            profile_name=profile,
            raw_paths=raw_paths,
            created_at=created_at,
            source_sha256=_sha256_file(audio_file),
            pitch=pitch_evidence,
            sources=sources,
            symbols=symbols,
        )

        _write_artifacts(
            jams_data,
            music_ir,
            output_dir,
            track_id,
            overwrite,
            raw_files=raw_files,
            artifact_files=artifact_files,
        )

    return music_ir
