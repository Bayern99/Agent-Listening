"""Essentia Extractor Adapter.

Handles running `essentia_streaming_extractor_music` CLI or `essentia` Python library,
and parsing raw output JSON into normalized EssentiaEvidence.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional


@dataclass
class EssentiaEvidence:
    duration_s: float = 0.0
    loudness_ebu128_integrated_lufs: float = 0.0
    loudness_range_lu: float = 0.0
    dynamic_complexity: float = 0.0
    spectral_centroid_hz_mean: float = 0.0
    spectral_flux_mean: float = 0.0
    onset_rate_per_s: float = 0.0
    bpm: float = 0.0
    key_candidates: List[Dict[str, Any]] = field(default_factory=list)
    chord_statistics: Dict[str, Any] = field(default_factory=dict)
    frame_features: Dict[str, List[float]] = field(default_factory=dict)
    tool_version: str = "unknown"
    profile: Optional[str] = None


class EssentiaAdapter:
    """Adapter for Essentia streaming music extractor."""

    DEFAULT_BINARY = "essentia_streaming_extractor_music"

    def __init__(self, binary_path: Optional[str] = None):
        self.binary_path = binary_path or self.DEFAULT_BINARY

    def is_available(self) -> bool:
        """Check if essentia executable or python module is available."""
        if shutil.which(self.binary_path) is not None:
            return True
        try:
            import essentia  # noqa: F401
            return True
        except Exception:
            return False

    def run(self, audio_path: str, profile_path: str, output_path: str) -> Dict[str, Any]:
        """Run Essentia extractor on audio file and save output JSON."""
        # 1. Try binary CLI first if present
        if shutil.which(self.binary_path) is not None:
            cmd = [
                self.binary_path,
                audio_path,
                output_path,
                profile_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Essentia extractor failed (exit {result.returncode}): {result.stderr}")

            with open(output_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 2. Try Python bindings if binary is not present
        try:
            import essentia
            import essentia.standard as es
            essentia_ver = getattr(essentia, "__version__", getattr(essentia, "ESSENTIA_VERSION", "2.1"))
            
            # Run MusicExtractor in Python
            extractor = es.MusicExtractor(profile=profile_path)
            pool, _ = extractor(audio_path)
            
            # Serialize pool to dict/json format
            output_dict: Dict[str, Any] = {
                "metadata": {
                    "version": {"essentia": essentia_ver, "extractor": "python_music_extractor"},
                    "audio_properties": {
                        "length": float(pool.get("metadata.audio_properties.length", 0.0)),
                        "sample_rate": float(pool.get("metadata.audio_properties.sample_rate", 44100)),
                    },
                },
                "lowlevel": {
                    "loudness_ebu128": {
                        "integrated": float(pool.get("lowlevel.loudness_ebu128.integrated", 0.0)),
                        "loudness_range": float(pool.get("lowlevel.loudness_ebu128.loudness_range", 0.0)),
                    },
                    "dynamic_complexity": float(pool.get("lowlevel.dynamic_complexity", 0.0)),
                    "spectral_centroid": {"mean": float(pool.get("lowlevel.spectral_centroid.mean", 0.0))},
                    "spectral_flux": {"mean": float(pool.get("lowlevel.spectral_flux.mean", 0.0))},
                },
                "rhythm": {
                    "bpm": float(pool.get("rhythm.bpm", 0.0)),
                    "onset_rate": float(pool.get("rhythm.onset_rate", 0.0)),
                },
                "tonal": {
                    "key_edma": {
                        "key": str(pool.get("tonal.key_edma.key", "")),
                        "scale": str(pool.get("tonal.key_edma.scale", "")),
                        "strength": float(pool.get("tonal.key_edma.strength", 0.0)),
                    },
                    "key_temperley": {
                        "key": str(pool.get("tonal.key_temperley.key", "")),
                        "scale": str(pool.get("tonal.key_temperley.scale", "")),
                        "strength": float(pool.get("tonal.key_temperley.strength", 0.0)),
                    },
                    "key_krumhansl": {
                        "key": str(pool.get("tonal.key_krumhansl.key", "")),
                        "scale": str(pool.get("tonal.key_krumhansl.scale", "")),
                        "strength": float(pool.get("tonal.key_krumhansl.strength", 0.0)),
                    },
                    "chords_histogram": pool.get("tonal.chords_histogram", {}),
                    "chords_changes_rate": float(pool.get("tonal.chords_changes_rate", 0.0)),
                },
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_dict, f, indent=2)
            return output_dict
        except Exception:
            pass

        raise FileNotFoundError(
            f"Essentia extractor binary '{self.binary_path}' and Python package 'essentia' are both not found.\n"
            "Install Essentia via:\n"
            "  uv pip install essentia\n"
            "or via Homebrew:\n"
            "  brew tap MTG/essentia && brew install essentia"
        )

    def parse_output(self, raw_data: Dict[str, Any], profile_name: Optional[str] = None) -> EssentiaEvidence:
        """Parse raw Essentia JSON dict into normalized EssentiaEvidence without decision making."""
        metadata = raw_data.get("metadata", {})
        audio_props = metadata.get("audio_properties", {})
        duration_s = float(audio_props.get("length", 0.0))
        version_info = metadata.get("version", {})
        tool_version = version_info.get("essentia", "unknown")

        lowlevel = raw_data.get("lowlevel", {})
        loudness_info = lowlevel.get("loudness_ebu128", {})
        loudness_integrated = float(loudness_info.get("integrated", 0.0))
        loudness_range = float(loudness_info.get("loudness_range", 0.0))
        dynamic_complexity = float(lowlevel.get("dynamic_complexity", 0.0))

        spectral_centroid = lowlevel.get("spectral_centroid", {})
        spectral_centroid_mean = float(spectral_centroid.get("mean", 0.0))

        spectral_flux = lowlevel.get("spectral_flux", {})
        spectral_flux_mean = float(spectral_flux.get("mean", 0.0))

        # Parse frame features if present
        raw_frames = lowlevel.get("frames", {})
        frame_features = {
            "timestamps_s": [float(t) for t in raw_frames.get("timestamps_s", [])],
            "loudness_lufs": [float(l) for l in raw_frames.get("loudness_lufs", [])],
            "spectral_centroid_hz": [float(c) for c in raw_frames.get("spectral_centroid_hz", [])],
            "spectral_flux": [float(f) for f in raw_frames.get("spectral_flux", [])],
        }

        rhythm = raw_data.get("rhythm", {})
        bpm = float(rhythm.get("bpm", 0.0))
        onset_rate = float(rhythm.get("onset_rate", 0.0))

        tonal = raw_data.get("tonal", {})
        key_candidates: List[Dict[str, Any]] = []

        # Parse key profiles: edma, temperley, krumhansl
        for alg in ["edma", "temperley", "krumhansl"]:
            key_field = f"key_{alg}"
            if key_field in tonal:
                k_data = tonal[key_field]
                key_candidates.append({
                    "algorithm": alg,
                    "key": str(k_data.get("key", "")),
                    "scale": str(k_data.get("scale", "")),
                    "strength": float(k_data.get("strength", 0.0)),
                    "tool": "essentia",
                })

        chords_hist = tonal.get("chords_histogram", {})
        chords_changes = tonal.get("chords_changes_rate", None)
        chord_statistics = {
            "histogram": chords_hist if isinstance(chords_hist, dict) else {},
            "changes_rate": float(chords_changes) if chords_changes is not None else None,
            "source": "essentia",
        }

        return EssentiaEvidence(
            duration_s=duration_s,
            loudness_ebu128_integrated_lufs=loudness_integrated,
            loudness_range_lu=loudness_range,
            dynamic_complexity=dynamic_complexity,
            spectral_centroid_hz_mean=spectral_centroid_mean,
            spectral_flux_mean=spectral_flux_mean,
            onset_rate_per_s=onset_rate,
            bpm=bpm,
            key_candidates=key_candidates,
            chord_statistics=chord_statistics,
            frame_features=frame_features,
            tool_version=tool_version,
            profile=profile_name,
        )
