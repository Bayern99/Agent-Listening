"""Essentia Extractor Adapter.

Handles running `essentia_streaming_extractor_music` CLI or `essentia` Python library,
and parsing raw output JSON into normalized EssentiaEvidence.
"""

from dataclasses import dataclass, field
import json
from importlib.metadata import PackageNotFoundError, version
from math import log2
from pathlib import Path
import shutil
from statistics import median
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional


LOWLEVEL_HOP_SIZE = 1024
TONAL_HOP_SIZE = 2048
ANALYSIS_SAMPLE_RATE = 44100.0
EBU_MOMENTARY_WINDOW_S = 0.4
EBU_LOUDNESS_HOP_S = 0.1


def _essentia_version() -> str:
    try:
        return version("essentia")
    except PackageNotFoundError:
        return "unknown"


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
    bpm_candidates: List[Dict[str, Any]] = field(default_factory=list)
    key_candidates: List[Dict[str, Any]] = field(default_factory=list)
    chord_statistics: Dict[str, Any] = field(default_factory=dict)
    frame_features: Dict[str, Any] = field(default_factory=dict)
    feature_summaries: Dict[str, Any] = field(default_factory=dict)
    material_events: List[Dict[str, Any]] = field(default_factory=list)
    tool_version: str = "unknown"
    profile: Optional[str] = None
    raw_sha256: Optional[str] = None
    profile_sha256: Optional[str] = None


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
        except ImportError as exc:
            raise FileNotFoundError(
                f"Essentia extractor binary '{self.binary_path}' and Python package 'essentia' are both not found.\n"
                "Install Essentia via `uv sync`."
            ) from exc

        # Configuration and extraction errors are intentionally preserved.
        extractor = es.MusicExtractor(profile=profile_path)
        aggregate_pool, frame_pool = extractor(audio_path)
        with TemporaryDirectory() as temp_dir:
            aggregate_path = str(Path(temp_dir) / "aggregate.json")
            frames_path = str(Path(temp_dir) / "frames.json")
            es.YamlOutput(filename=aggregate_path, format="json")(aggregate_pool)
            es.YamlOutput(filename=frames_path, format="json")(frame_pool)
            with open(aggregate_path, "r", encoding="utf-8") as f:
                aggregate = json.load(f)
            with open(frames_path, "r", encoding="utf-8") as f:
                frames = json.load(f)

        output_dict = {"aggregate": aggregate, "frames": frames}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=2)
        return output_dict

    def run_pitch(self, audio_path: str, output_path: str) -> Dict[str, Any]:
        """Extract a mono pitch contour using the installed Essentia binding."""
        try:
            import essentia.standard as es
        except ImportError as exc:
            raise FileNotFoundError("Essentia is required for pitch extraction") from exc

        sample_rate = ANALYSIS_SAMPLE_RATE
        audio = es.MonoLoader(filename=audio_path, sampleRate=sample_rate)()
        pitches, voiced = es.PitchYinProbabilistic(
            frameSize=2048,
            hopSize=LOWLEVEL_HOP_SIZE,
            sampleRate=sample_rate,
            outputUnvoiced="zero",
        )(audio)
        data = {
            "tool": "essentia.pitch_yin_probabilistic",
            "version": _essentia_version(),
            "sample_rate_hz": sample_rate,
            "hop_size": LOWLEVEL_HOP_SIZE,
            "timestamps_s": [round(index * LOWLEVEL_HOP_SIZE / sample_rate, 5) for index in range(len(pitches))],
            "pitch_hz": [float(value) for value in pitches],
            "voiced_probability": [float(value) for value in voiced],
        }
        Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    @staticmethod
    def parse_pitch_output(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a pitch JSON output without inventing values for unvoiced frames."""
        timestamps = [float(value) for value in raw_data.get("timestamps_s", [])]
        pitches = [float(value) for value in raw_data.get("pitch_hz", [])]
        voiced = [float(value) for value in raw_data.get("voiced_probability", [])]
        length = min(len(timestamps), len(pitches), len(voiced))
        contour = []
        midi_values = []
        for index in range(length):
            frequency = pitches[index]
            probability = voiced[index]
            midi = 69.0 + 12.0 * log2(frequency / 440.0) if frequency > 0 else None
            contour.append({
                "time_s": timestamps[index],
                "duration_s": 0.0,
                "frequency_hz": frequency if frequency > 0 else None,
                "voiced_probability": probability,
            })
            if midi is not None and probability > 0:
                midi_values.append(midi)
        return {
            "status": "available" if contour else "not_detected",
            "tool": "essentia.pitch_yin_probabilistic",
            "version": raw_data.get("version", "unknown"),
            "contour": contour,
            "pitch_range_midi": [round(min(midi_values), 2), round(max(midi_values), 2)] if midi_values else None,
            "median_midi": round(median(midi_values), 2) if midi_values else None,
            "voiced_ratio": round(sum(1 for value in voiced[:length] if value > 0) / length, 4) if length else 0.0,
        }

    def parse_output(self, raw_data: Dict[str, Any], profile_name: Optional[str] = None) -> EssentiaEvidence:
        """Parse raw Essentia JSON dict into normalized EssentiaEvidence without decision making."""
        aggregate = raw_data.get("aggregate", raw_data)
        metadata = aggregate.get("metadata", {})
        audio_props = metadata.get("audio_properties", {})
        duration_s = float(audio_props.get("length", 0.0))
        version_info = metadata.get("version", {})
        tool_version = version_info.get("essentia", "unknown")

        analysis_props = audio_props.get("analysis", {})
        sample_rate = float(
            analysis_props.get("sample_rate")
            or audio_props.get("sample_rate")
            or ANALYSIS_SAMPLE_RATE
        )
        start_time_s = float(analysis_props.get("start_time", 0.0))

        lowlevel = aggregate.get("lowlevel", {})
        loudness_info = lowlevel.get("loudness_ebu128", {})
        loudness_integrated = float(loudness_info.get("integrated", 0.0))
        loudness_range = float(loudness_info.get("loudness_range", 0.0))
        dynamic_complexity = float(lowlevel.get("dynamic_complexity", 0.0))

        spectral_centroid = lowlevel.get("spectral_centroid", {})
        spectral_centroid_mean = float(spectral_centroid.get("mean", 0.0))

        spectral_flux = lowlevel.get("spectral_flux", {})
        spectral_flux_mean = float(spectral_flux.get("mean", 0.0))

        native_frames = raw_data.get("frames", {})
        raw_frames = native_frames.get("lowlevel", {}) or lowlevel.get("frames", {})

        def _values(name: str) -> List[float]:
            value = raw_frames.get(name, [])
            if isinstance(value, dict):
                value = value.get("values", value.get("mean", []))
            if not isinstance(value, list):
                return []
            return [float(item) for item in value if isinstance(item, (int, float))]

        explicit_timestamps = _values("timestamps_s")
        frame_values = {
            "spectral_centroid_hz": _values("spectral_centroid") or _values("spectral_centroid_hz"),
            "spectral_flux": _values("spectral_flux"),
            "spectral_rolloff_hz": _values("spectral_rolloff") or _values("spectral_rolloff_hz"),
            "spectral_spread_hz": _values("spectral_spread") or _values("spectral_spread_hz"),
            "spectral_entropy": _values("spectral_entropy"),
            "spectral_flatness": _values("spectral_flatness"),
            "spectral_energy": _values("spectral_energy"),
            "spectral_energyband_low": _values("spectral_energyband_low"),
            "spectral_energyband_middle_low": _values("spectral_energyband_middle_low"),
            "spectral_energyband_middle_high": _values("spectral_energyband_middle_high"),
            "spectral_energyband_high": _values("spectral_energyband_high"),
            "dissonance": _values("dissonance"),
            "pitch_salience": _values("pitch_salience"),
        }
        lowlevel_length = max((len(values) for values in frame_values.values()), default=0)
        lowlevel_timestamps = explicit_timestamps or [
            round(start_time_s + index * LOWLEVEL_HOP_SIZE / sample_rate, 5)
            for index in range(lowlevel_length)
        ]

        loudness_block = raw_frames.get("loudness_ebu128", {})
        if not isinstance(loudness_block, dict):
            loudness_block = {}
        loudness_values = [
            float(value)
            for value in loudness_block.get("momentary", raw_frames.get("loudness_lufs", []))
            if isinstance(value, (int, float))
        ]
        explicit_loudness_timestamps = _values("loudness_timestamps_s")
        if explicit_loudness_timestamps:
            loudness_timestamps = explicit_loudness_timestamps
        else:
            loudness_timestamps = [
                round(start_time_s + EBU_MOMENTARY_WINDOW_S + index * EBU_LOUDNESS_HOP_S, 5)
                for index in range(len(loudness_values))
            ]

        frame_features: Dict[str, Any] = {
            "timestamps_s": lowlevel_timestamps,
            "loudness_timestamps_s": loudness_timestamps,
            "loudness_lufs": loudness_values,
            **frame_values,
            "time_basis": {
                "lowlevel": {
                    "start_s": start_time_s,
                    "hop_s": LOWLEVEL_HOP_SIZE / sample_rate,
                    "sample_rate_hz": sample_rate,
                    "semantics": "frame_center_zero_based",
                },
                "loudness": {
                    "start_s": start_time_s + EBU_MOMENTARY_WINDOW_S,
                    "hop_s": EBU_LOUDNESS_HOP_S,
                    "window_s": EBU_MOMENTARY_WINDOW_S,
                    "semantics": "momentary_window_end_aligned",
                },
            },
        }

        tonal_frames = native_frames.get("tonal", {}) or aggregate.get("tonal", {}).get("frames", {})
        if isinstance(tonal_frames, dict):
            hpcp = tonal_frames.get("hpcp", [])
            if isinstance(hpcp, list) and hpcp and isinstance(hpcp[0], list):
                frame_features["tonal_timestamps_s"] = [
                    round(start_time_s + index * TONAL_HOP_SIZE / sample_rate, 5)
                    for index in range(len(hpcp))
                ]
                frame_features["hpcp"] = [
                    [float(value) for value in row if isinstance(value, (int, float))]
                    for row in hpcp
                ]
                frame_features["time_basis"]["tonal"] = {
                    "start_s": start_time_s,
                    "hop_s": TONAL_HOP_SIZE / sample_rate,
                    "sample_rate_hz": sample_rate,
                    "semantics": "frame_center_zero_based",
                }

        rhythm = aggregate.get("rhythm", {})
        bpm = float(rhythm.get("bpm", 0.0))
        onset_rate = float(rhythm.get("onset_rate", 0.0))

        tonal = aggregate.get("tonal", {})
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
            "histogram": chords_hist if isinstance(chords_hist, (dict, list)) else {},
            "changes_rate": float(chords_changes) if chords_changes is not None else None,
            "source": "essentia",
        }

        def _summary(section: Dict[str, Any], key: str) -> Optional[float]:
            value = section.get(key)
            if isinstance(value, dict):
                value = value.get("mean")
            return float(value) if isinstance(value, (int, float)) else None

        feature_summaries: Dict[str, Any] = {}
        for key in (
            "silence_rate_20dB",
            "silence_rate_30dB",
            "silence_rate_60dB",
            "spectral_rolloff",
            "spectral_spread",
            "spectral_entropy",
            "spectral_flatness",
            "spectral_rms",
            "spectral_energy",
            "spectral_energyband_low",
            "spectral_energyband_middle_low",
            "spectral_energyband_middle_high",
            "spectral_energyband_high",
            "dissonance",
            "pitch_salience",
        ):
            value = _summary(lowlevel, key)
            if value is not None:
                feature_summaries[key] = value

        bpm_candidates = []
        for bpm_key, weight_key in (
            ("bpm_histogram_first_peak_bpm", "bpm_histogram_first_peak_weight"),
            ("bpm_histogram_second_peak_bpm", "bpm_histogram_second_peak_weight"),
        ):
            bpm_value = _summary(rhythm, bpm_key)
            weight = _summary(rhythm, weight_key)
            if bpm_value is not None:
                bpm_candidates.append({"bpm": bpm_value, "weight": weight, "tool": "essentia"})
        for key in (
            "bpm_histogram_first_peak_bpm",
            "bpm_histogram_first_peak_weight",
            "bpm_histogram_second_peak_bpm",
            "bpm_histogram_second_peak_weight",
            "beats_loudness",
            "danceability",
        ):
            value = _summary(rhythm, key)
            if value is not None:
                feature_summaries[key] = value
        for key in (
            "tuning_frequency",
            "tuning_equal_tempered_deviation",
            "tuning_diatonic_strength",
            "tuning_nontempered_energy_ratio",
            "hpcp_entropy",
            "chords_strength",
        ):
            value = _summary(tonal, key)
            if value is not None:
                feature_summaries[key] = value

        return EssentiaEvidence(
            duration_s=duration_s,
            loudness_ebu128_integrated_lufs=loudness_integrated,
            loudness_range_lu=loudness_range,
            dynamic_complexity=dynamic_complexity,
            spectral_centroid_hz_mean=spectral_centroid_mean,
            spectral_flux_mean=spectral_flux_mean,
            onset_rate_per_s=onset_rate,
            bpm=bpm,
            bpm_candidates=bpm_candidates,
            key_candidates=key_candidates,
            chord_statistics=chord_statistics,
            frame_features=frame_features,
            feature_summaries=feature_summaries,
            tool_version=tool_version,
            profile=profile_name,
        )
