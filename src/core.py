"""Core Analysis Pipeline & Deep Module Implementation.

Provides the minimal public interface for the audio-to-music-ir system.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional, Tuple

from src.adapters.allin1_adapter import AllInOneAdapter
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
) -> None:
    jams_file, ir_file = _artifact_paths(output_dir, track_id)
    raw_files = raw_files or {}
    raw_destinations = {
        name: Path(output_dir) / "raw" / track_id / f"{name}.json"
        for name in raw_files
    }
    _assert_writable((jams_file, ir_file, *raw_destinations.values()), overwrite)

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
            shutil.copy2(source, staged_raw[name])

        destinations = [(staged_jams, jams_file), (staged_ir, ir_file)]
        destinations.extend((staged_raw[name], destination) for name, destination in raw_destinations.items())
        for _, destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
        for source, destination in destinations:
            source.replace(destination)


def build_ir_from_files(
    allin1_path: str,
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
    with open(allin1_path, "r", encoding="utf-8") as f:
        allin1_raw = json.load(f)
    with open(essentia_path, "r", encoding="utf-8") as f:
        essentia_raw = json.load(f)

    if track_id is None:
        track_id = Path(allin1_path).stem.replace(".allin1", "").replace(".raw", "")
    if source_file is None:
        source_file = f"source/{track_id}.wav"

    allin1_ev = AllInOneAdapter().parse_output(allin1_raw)
    essentia_ev = EssentiaAdapter().parse_output(essentia_raw, profile_name=profile_name)
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
        raw_paths={"allin1": allin1_path, "essentia": essentia_path},
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
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Small public interface: analyze(audio_path, profile) -> MusicIR.

    Hides the complexity of subprocess invocation, JSON normalization,
    pure evidence fusion, and dual-artifact persistence.
    """
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    track_id = audio_file.stem
    out_base = Path(output_dir)
    raw_dir = out_base / "raw" / track_id
    allin1_raw_path = raw_dir / "allin1.json"
    essentia_raw_path = raw_dir / "essentia.json"
    jams_file, ir_file = _artifact_paths(output_dir, track_id)
    _assert_writable((allin1_raw_path, essentia_raw_path, jams_file, ir_file), overwrite)

    if profile_path is None:
        profile_path = str(Path(__file__).parent.parent / "profiles" / f"{profile}.yaml")
    profile_file = Path(profile_path)
    if not profile_file.exists():
        raise FileNotFoundError(f"Essentia profile not found: {profile_path}")

    out_base.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out_base, prefix=f".{track_id}-extract-") as temp_dir:
        staged_allin1 = Path(temp_dir) / "allin1.json"
        staged_essentia = Path(temp_dir) / "essentia.json"

        # 1. Run allin1
        adapter_allin1 = allin1_adapter or AllInOneAdapter()
        allin1_raw = adapter_allin1.run(str(audio_file), str(staged_allin1))
        allin1_ev = adapter_allin1.parse_output(allin1_raw)
        allin1_ev.raw_sha256 = _sha256_file(staged_allin1)

        # 2. Run Essentia
        adapter_essentia = essentia_adapter or EssentiaAdapter()
        essentia_raw = adapter_essentia.run(str(audio_file), profile_path, str(staged_essentia))
        essentia_ev = adapter_essentia.parse_output(essentia_raw, profile_name=profile)
        essentia_ev.raw_sha256 = _sha256_file(staged_essentia)
        essentia_ev.profile_sha256 = _sha256_file(profile_file)

        # 3. Fuse evidence into dual artifacts
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()

        jams_data, music_ir = merge_evidence(
            allin1_evidence=allin1_ev,
            essentia_evidence=essentia_ev,
            track_id=track_id,
            source_file=str(audio_file),
            analysis_mode=analysis_mode,
            profile_name=profile,
            raw_paths={"allin1": str(allin1_raw_path), "essentia": str(essentia_raw_path)},
            created_at=created_at,
            source_sha256=_sha256_file(audio_file),
        )

        # 4. Persist all artifacts only after both extractors and validation succeed.
        _write_artifacts(
            jams_data,
            music_ir,
            output_dir,
            track_id,
            overwrite,
            raw_files={"allin1": staged_allin1, "essentia": staged_essentia},
        )

    return music_ir
