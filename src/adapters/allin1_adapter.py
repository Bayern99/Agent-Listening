"""allin1 Music Structure Extractor Adapter.

Handles running allin1 CLI / python library and parsing BPM, beat grid, and section boundaries.
"""

from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional


@dataclass
class AllInOneEvidence:
    duration_s: float = 0.0
    tempo_bpm: Optional[float] = None
    beats_s: List[float] = field(default_factory=list)
    beat_positions: List[int] = field(default_factory=list)
    downbeats_s: List[float] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    tool_version: str = "unknown"
    raw_sha256: Optional[str] = None


class AllInOneAdapter:
    """Adapter for allin1 music structure analyzer."""

    DEFAULT_BINARY = "allin1"

    def __init__(self, binary_path: Optional[str] = None):
        self.binary_path = binary_path or self.DEFAULT_BINARY

    def is_available(self) -> bool:
        """Check if allin1 CLI or python module is available."""
        if shutil.which(self.binary_path) is not None:
            return True
        try:
            import allin1_infer  # noqa: F401
            return True
        except Exception:
            pass
        try:
            import allin1  # noqa: F401
            return True
        except Exception:
            pass
        return False

    def run(self, audio_path: str, output_path: str) -> Dict[str, Any]:
        """Run allin1 analysis on audio file and save output JSON."""
        # 1. Try direct python API (allin1_infer or allin1)
        allin1_mod = None
        distribution = None
        try:
            import allin1_infer as allin1_mod  # noqa: F401
            distribution = "all-in-one-infer"
        except Exception:
            try:
                import allin1 as allin1_mod  # noqa: F401
                distribution = "allin1"
            except Exception:
                pass

        if allin1_mod is not None:
            result = allin1_mod.analyze(audio_path)
            segments = [
                {
                    "start": float(s.start),
                    "end": float(s.end),
                    "label": str(s.label),
                }
                for s in getattr(result, "segments", [])
            ]
            duration_s = segments[-1]["end"] if segments else 0.0
            data = {
                "path": str(getattr(result, "path", audio_path)),
                "bpm": getattr(result, "bpm", None),
                "beats": [float(b) for b in getattr(result, "beats", [])],
                "beat_positions": [int(p) for p in getattr(result, "beat_positions", [])],
                "downbeats": [float(db) for db in getattr(result, "downbeats", [])],
                "segments": segments,
                "duration": duration_s,
                "activation_fps": getattr(result, "activation_fps", None),
            }
            try:
                data["version"] = version(distribution) if distribution else "unknown"
            except PackageNotFoundError:
                data["version"] = "unknown"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return data

        # 2. Fallback to CLI
        if shutil.which(self.binary_path) is None:
            raise FileNotFoundError(
                f"allin1 binary or python package not found. "
                "Please install `all-in-one-infer` (uv pip install all-in-one-infer) or run in offline/fixture mode."
            )

        out_dir = Path(output_path).parent
        cmd = [self.binary_path, audio_path, "-o", str(out_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"allin1 CLI failed (exit {proc.returncode}): {proc.stderr}")

        # allin1 CLI writes `{stem}.json` by default in output directory
        audio_stem = Path(audio_path).stem
        default_cli_output = out_dir / f"{audio_stem}.json"
        if default_cli_output.exists() and default_cli_output != Path(output_path):
            shutil.copy2(default_cli_output, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def parse_output(self, raw_data: Dict[str, Any]) -> AllInOneEvidence:
        """Parse raw allin1 output JSON dict into normalized AllInOneEvidence."""
        bpm_val = raw_data.get("bpm", None)
        tempo_bpm = float(bpm_val) if bpm_val is not None else None

        raw_beats = raw_data.get("beats", [])
        beats_s = [float(b) for b in raw_beats]
        beat_positions = [int(p) for p in raw_data.get("beat_positions", [])]
        if beat_positions and len(beat_positions) != len(beats_s):
            raise ValueError("allin1 beat_positions must align with beats")

        raw_downbeats = raw_data.get("downbeats", [])
        downbeats_s = [float(db) for db in raw_downbeats]

        raw_segments = raw_data.get("segments", [])
        sections: List[Dict[str, Any]] = []
        for seg in raw_segments:
            start_s = float(seg.get("start", 0.0))
            end_s = float(seg.get("end", 0.0))
            label = str(seg.get("label", "section"))
            sections.append({
                "start_s": start_s,
                "end_s": end_s,
                "label": label,
                "tool": "allin1",
                "confidence": None,
                "loudness_lufs": None,
                "spectral_centroid_hz": None,
                "dynamic_complexity": None,
            })

        duration_s = float(raw_data.get("duration", 0.0))
        if not duration_s and sections:
            duration_s = sections[-1]["end_s"]

        tool_version = raw_data.get("version", "unknown")

        return AllInOneEvidence(
            duration_s=duration_s,
            tempo_bpm=tempo_bpm,
            beats_s=beats_s,
            beat_positions=beat_positions,
            downbeats_s=downbeats_s,
            sections=sections,
            tool_version=tool_version,
        )
