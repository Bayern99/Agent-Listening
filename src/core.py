"""Core Analysis Pipeline & Deep Module Implementation.

Provides the minimal public interface for the audio-to-music-ir system.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.adapters.allin1_adapter import AllInOneAdapter
from src.adapters.essentia_adapter import EssentiaAdapter
from src.fusion.builder import merge_evidence


def build_ir_from_files(
    allin1_path: str,
    essentia_path: str,
    track_id: Optional[str] = None,
    source_file: Optional[str] = None,
    output_dir: str = ".",
    profile_name: str = "essentia_v0_1",
    enable_symbols: bool = False,
    analysis_mode: str = "full_mix",
    created_at: Optional[str] = None,
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

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()

    jams_data, music_ir = merge_evidence(
        allin1_evidence=allin1_ev,
        essentia_evidence=essentia_ev,
        track_id=track_id,
        source_file=source_file,
        analysis_mode=analysis_mode,
        profile_name=profile_name,
        enable_symbols=enable_symbols,
        raw_paths={"allin1": allin1_path, "essentia": essentia_path},
        created_at=created_at,
    )

    out_base = Path(output_dir)
    ir_dir = out_base / "music-ir"
    jams_dir = out_base / "jams"
    ir_dir.mkdir(parents=True, exist_ok=True)
    jams_dir.mkdir(parents=True, exist_ok=True)

    ir_file = ir_dir / f"{track_id}.music-ir.json"
    jams_file = jams_dir / f"{track_id}.analysis.jams"

    with open(ir_file, "w", encoding="utf-8") as f:
        json.dump(music_ir, f, indent=2, ensure_ascii=False)
    with open(jams_file, "w", encoding="utf-8") as f:
        json.dump(jams_data, f, indent=2, ensure_ascii=False)

    return jams_data, music_ir


def analyze(
    audio_path: str,
    output_dir: str = ".",
    profile: str = "essentia_v0_1",
    profile_path: Optional[str] = None,
    enable_symbols: bool = False,
    analysis_mode: str = "full_mix",
    created_at: Optional[str] = None,
    allin1_adapter: Optional[AllInOneAdapter] = None,
    essentia_adapter: Optional[EssentiaAdapter] = None,
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
    raw_dir.mkdir(parents=True, exist_ok=True)

    allin1_raw_path = raw_dir / "allin1.json"
    essentia_raw_path = raw_dir / "essentia.json"

    if profile_path is None:
        profile_path = str(Path(__file__).parent.parent / "profiles" / f"{profile}.yaml")

    # 1. Run allin1
    adapter_allin1 = allin1_adapter or AllInOneAdapter()
    allin1_raw = adapter_allin1.run(str(audio_file), str(allin1_raw_path))
    allin1_ev = adapter_allin1.parse_output(allin1_raw)

    # 2. Run Essentia
    adapter_essentia = essentia_adapter or EssentiaAdapter()
    essentia_raw = adapter_essentia.run(str(audio_file), profile_path, str(essentia_raw_path))
    essentia_ev = adapter_essentia.parse_output(essentia_raw, profile_name=profile)

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
        enable_symbols=enable_symbols,
        raw_paths={"allin1": str(allin1_raw_path), "essentia": str(essentia_raw_path)},
        created_at=created_at,
    )

    # 4. Persist dual artifacts
    ir_dir = out_base / "music-ir"
    jams_dir = out_base / "jams"
    ir_dir.mkdir(parents=True, exist_ok=True)
    jams_dir.mkdir(parents=True, exist_ok=True)

    ir_file = ir_dir / f"{track_id}.music-ir.json"
    jams_file = jams_dir / f"{track_id}.analysis.jams"

    with open(ir_file, "w", encoding="utf-8") as f:
        json.dump(music_ir, f, indent=2, ensure_ascii=False)
    with open(jams_file, "w", encoding="utf-8") as f:
        json.dump(jams_data, f, indent=2, ensure_ascii=False)

    return music_ir
