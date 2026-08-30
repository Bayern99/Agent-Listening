"""Pure Evidence Fusion and Artifact Builder.

Pure deterministic transformation functions that merge multi-extractor evidence into:
1. `JAMS` standard time-series annotation dict.
2. `MusicIR` JSON dict (conforming to schemas/music-ir-v0.2.schema.json).
"""

import json
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import jams as jams_library

from src.adapters.allin1_adapter import AllInOneEvidence
from src.adapters.essentia_adapter import EssentiaEvidence
from src.fusion.validator import validate_music_ir


def _aggregate_section_acoustics(
    start_s: float,
    end_s: float,
    frame_features: Dict[str, Any],
    pitch: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Slice frame features within [start_s, end_s] and compute local mean statistics."""
    timestamps = frame_features.get("timestamps_s", [])
    # Loudness has its own EBU momentary grid.  A missing grid is unknown,
    # not permission to relabel low-level frame timestamps as loudness.
    loudness_timestamps = frame_features.get("loudness_timestamps_s", [])
    loudness_frames = frame_features.get("loudness_lufs", [])
    centroid_frames = frame_features.get("spectral_centroid_hz", [])

    def _slice(values: List[float], value_timestamps: List[float]) -> List[float]:
        if not values or not value_timestamps or len(values) != len(value_timestamps):
            return []
        indices = [
            index for index, timestamp in enumerate(value_timestamps)
            if start_s <= timestamp < end_s
        ]
        if not indices:
            return []
        return [values[index] for index in indices]

    sliced_loudness = _slice(loudness_frames, loudness_timestamps)
    sliced_centroids = _slice(centroid_frames, timestamps)
    sec_loudness = sum(sliced_loudness) / len(sliced_loudness) if sliced_loudness else None
    sec_centroid = sum(sliced_centroids) / len(sliced_centroids) if sliced_centroids else None

    # Dynamic complexity approximation from local loudness variation
    if len(sliced_loudness) > 1:
        loudness_mean = sum(sliced_loudness) / len(sliced_loudness)
        variance = sum((x - loudness_mean) ** 2 for x in sliced_loudness) / len(sliced_loudness)
        sec_complexity = round(variance ** 0.5, 2)
    else:
        sec_complexity = None

    result = {
        "loudness_lufs": round(sec_loudness, 2) if sec_loudness is not None else None,
        "spectral_centroid_hz": round(sec_centroid, 2) if sec_centroid is not None else None,
        "dynamic_complexity": sec_complexity,
    }
    for name in (
        "spectral_rolloff_hz", "spectral_spread_hz", "spectral_flatness",
        "spectral_entropy", "spectral_energy", "spectral_energyband_low",
        "spectral_energyband_middle_low", "spectral_energyband_middle_high",
        "spectral_energyband_high", "dissonance", "pitch_salience",
    ):
        values = _slice(frame_features.get(name, []), timestamps)
        result[name] = round(sum(values) / len(values), 4) if values else None

    contour = (pitch or {}).get("contour", [])
    local_contour = [
        point for point in contour
        if start_s <= float(point.get("time_s", -1.0)) < end_s
    ]
    local_pitch = [
        point for point in local_contour
        if isinstance(point.get("frequency_hz"), (int, float))
        and point["frequency_hz"] > 0
    ]
    result["pitch_median_hz"] = (
        round(median(point["frequency_hz"] for point in local_pitch), 4)
        if local_pitch else None
    )
    result["voiced_ratio"] = (
        round(sum(
            1 for point in local_contour
            if isinstance(point.get("frequency_hz"), (int, float))
            and point["frequency_hz"] > 0
            and point.get("voiced_probability", 0) > 0
        ) / len(local_contour), 4)
        if local_contour else None
    )

    tonal_timestamps = frame_features.get("tonal_timestamps_s", [])
    hpcp_rows = frame_features.get("hpcp", [])
    local_hpcp = _slice(hpcp_rows, tonal_timestamps)
    result["hpcp_mean"] = (
        [round(sum(column) / len(column), 4) for column in zip(*local_hpcp)]
        if local_hpcp and all(len(row) == len(local_hpcp[0]) for row in local_hpcp)
        else None
    )
    return result


def _usable_allin1(evidence: AllInOneEvidence) -> bool:
    """Return whether all-in-one produced a usable metric grid."""
    beats = evidence.beats_s
    return (
        evidence.tempo_bpm is not None
        and evidence.tempo_bpm > 0
        and len(beats) >= 4
        and all(current > previous for previous, current in zip(beats, beats[1:]))
    )


def _usable_sections(evidence: AllInOneEvidence, duration_s: Optional[float] = None) -> bool:
    valid_sections = [
        section for section in evidence.sections
        if isinstance(section.get("start_s"), (int, float))
        and isinstance(section.get("end_s"), (int, float))
        and section["start_s"] >= 0
        and section["end_s"] > section["start_s"]
    ]
    labels = {str(section.get("label", "")).lower() for section in valid_sections}
    continuous = all(
        abs(current["start_s"] - previous["end_s"]) <= 1e-3
        for previous, current in zip(valid_sections, valid_sections[1:])
    )
    within_duration = duration_s is None or all(
        section["end_s"] <= duration_s + 1e-3 for section in valid_sections
    )
    return (
        len(valid_sections) == len(evidence.sections)
        and len(valid_sections) >= 2
        and continuous
        and within_duration
        and not labels.issubset({"start", "intro", "end"})
    )


def _material_event_series(frame_features: Dict[str, Any]) -> Dict[str, List[float]]:
    """Return feature series on the low-level grid for novelty scoring."""
    timestamps = frame_features.get("timestamps_s", [])
    series = {
        name: frame_features.get(name, [])
        for name in (
            "spectral_flux",
            "spectral_centroid_hz",
            "spectral_energyband_low",
            "spectral_energyband_middle_low",
            "spectral_energyband_middle_high",
            "spectral_energyband_high",
        )
        if len(frame_features.get(name, [])) == len(timestamps)
    }
    loudness_timestamps = frame_features.get("loudness_timestamps_s", [])
    loudness_values = frame_features.get("loudness_lufs", [])
    if timestamps and len(loudness_timestamps) == len(loudness_values) and loudness_values:
        # ponytail: nearest-neighbour resampling is sufficient for event
        # candidates; retain the native loudness grid in JAMS/raw artifacts.
        series["loudness_change"] = [
            loudness_values[
                min(range(len(loudness_timestamps)), key=lambda index: abs(loudness_timestamps[index] - timestamp))
            ]
            for timestamp in timestamps
        ]
    return series


def _material_events(frame_features: Dict[str, Any], duration_s: float) -> List[Dict[str, Any]]:
    """Find deterministic, machine-reviewable material changes from frame deltas."""
    timestamps = frame_features.get("timestamps_s", [])
    if len(timestamps) < 3:
        return []
    series = _material_event_series(frame_features)
    # Constant channels carry no change signal and should not dilute another
    # channel's novelty score.
    candidate_names = [
        name for name, values in series.items()
        if values and max(values) - min(values) > 1e-12
    ]
    if not candidate_names:
        return []

    normalized_deltas: Dict[str, List[float]] = {}
    for name in candidate_names:
        values = series[name]
        deltas = [0.0]
        deltas.extend(abs(values[index] - values[index - 1]) for index in range(1, len(values)))
        center = median(deltas)
        scale = median([abs(value - center) for value in deltas])
        if scale <= 1e-12:
            non_zero = [value for value in deltas if value > 0]
            # A single step change has zero MAD; half its typical magnitude
            # keeps the fixed 1.2 threshold useful without changing the raw
            # evidence or inventing a confidence score.
            scale = (median(non_zero) / 2.0) if non_zero else 1.0
        normalized_deltas[name] = [max(0.0, value - center) / scale for value in deltas]

    scores = [
        sum(normalized_deltas[name][index] for name in candidate_names) / len(candidate_names)
        for index in range(len(timestamps))
    ]
    events: List[Dict[str, Any]] = []
    last_time = -1e9
    for index in range(1, len(timestamps)):
        score = scores[index]
        if score < 1.2 or score < scores[index - 1] or (
            index + 1 < len(scores) and score < scores[index + 1]
        ):
            continue
        time_s = float(timestamps[index])
        if time_s - last_time < 0.5:
            continue
        changed = [
            name for name in candidate_names if normalized_deltas[name][index] >= 1.2
        ]
        events.append({
            "time_s": round(time_s, 3),
            "prominence": round(score / (score + 1.0), 3),
            "changed_features": changed,
            "before_window_s": [round(max(0.0, time_s - 0.5), 3), round(time_s, 3)],
            "after_window_s": [round(time_s, 3), round(min(duration_s, time_s + 0.5), 3)],
            "label": "material_change_candidate",
            "review_status": "machine_candidate",
        })
        last_time = time_s
    return events


def build_music_ir(
    track_id: str,
    source_file: str,
    duration_s: float,
    allin1_evidence: Optional[AllInOneEvidence] = None,
    essentia_evidence: Optional[EssentiaEvidence] = None,
    analysis_mode: str = "full_mix",
    profile_name: str = "essentia_v0_1",
    raw_paths: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
    created_at: str = "1970-01-01T00:00:00Z",
    schema: Optional[Dict[str, Any]] = None,
    source_sha256: Optional[str] = None,
    pitch: Optional[Dict[str, Any]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    symbols: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pure, deterministic fusion of evidence into a validated Music IR dictionary."""
    allin1_present = allin1_evidence is not None
    if allin1_evidence is None:
        allin1_evidence = AllInOneEvidence()
    essentia_present = essentia_evidence is not None
    if essentia_evidence is None:
        essentia_evidence = EssentiaEvidence()
    if raw_paths is None:
        raw_paths = {}

    has_metric_grid = _usable_allin1(allin1_evidence)
    has_functional_sections = _usable_sections(allin1_evidence, duration_s)
    material_events = _material_events(essentia_evidence.frame_features, duration_s)
    material_event_inputs = bool(_material_event_series(essentia_evidence.frame_features))

    # 1. Global & Tempo evidence
    tempo_val = (
        allin1_evidence.tempo_bpm
        if allin1_evidence.tempo_bpm is not None and allin1_evidence.tempo_bpm > 0
        else (essentia_evidence.bpm or None)
    )
    tempo_evidence = []
    tempo_candidates = []
    if allin1_evidence.tempo_bpm is not None and allin1_evidence.tempo_bpm > 0:
        tempo_evidence.append({"tool": "allin1", "field": "bpm", "value": allin1_evidence.tempo_bpm})
        tempo_candidates.append({"bpm": allin1_evidence.tempo_bpm, "weight": None, "tool": "allin1"})
    if essentia_evidence.bpm:
        tempo_evidence.append({"tool": "essentia", "field": "rhythm.bpm", "value": essentia_evidence.bpm})
    tempo_candidates.extend(essentia_evidence.bpm_candidates)

    # 2. Key arbitration in Fusion (ADR-0009: Max strength candidate wins)
    key_candidates = essentia_evidence.key_candidates
    key_summary: Optional[str] = None
    if key_candidates:
        winner = max(key_candidates, key=lambda c: c.get("strength", 0.0))
        if winner.get("key") and winner.get("scale") and winner.get("strength", 0.0) >= 0.5:
            key_summary = f"{winner['key']} {winner['scale']}"

    # 3. Structure & Sections with REAL inline acoustic aggregation (ADR-0008, ADR-0005)
    dur_rounded = round(duration_s, 2)
    sections = []
    source_sections = allin1_evidence.sections if has_functional_sections else []
    for sec in source_sections:
        local_acoustics = _aggregate_section_acoustics(
            start_s=sec["start_s"],
            end_s=sec["end_s"],
            frame_features=essentia_evidence.frame_features,
            pitch=pitch,
        )
        sections.append({
            "start_s": sec["start_s"],
            "end_s": sec["end_s"],
            "label": sec["label"],
            "tool": sec["tool"],
            "confidence": sec.get("confidence"),
            **local_acoustics,
        })
    if sections:
        sections[0]["start_s"] = 0.0
        sections[-1]["end_s"] = dur_rounded

    # 4. Audio features summary (ADR-0005)
    audio_features = {
        "loudness_ebu128_integrated_lufs": round(essentia_evidence.loudness_ebu128_integrated_lufs, 2),
        "loudness_range_lu": round(essentia_evidence.loudness_range_lu, 2),
        "dynamic_complexity": round(essentia_evidence.dynamic_complexity, 2),
        "spectral_centroid_hz_mean": round(essentia_evidence.spectral_centroid_hz_mean, 2),
        "spectral_flux_mean": round(essentia_evidence.spectral_flux_mean, 4),
        "onset_rate_per_s": round(essentia_evidence.onset_rate_per_s, 2),
        "notes": f"Extracted via Essentia profile '{profile_name}'. Cross-track comparisons require identical profile.",
    }
    audio_features.update({
        f"{key}": round(value, 4)
        for key, value in essentia_evidence.feature_summaries.items()
        if isinstance(value, (int, float))
    })

    # 5. Provenance
    provenance: Dict[str, Any] = {"created_at": created_at, "extractor_runs": []}
    if allin1_present:
        provenance["allin1"] = {
            "version": allin1_evidence.tool_version,
            "raw_json": raw_paths.get("allin1", f"raw/{track_id}/allin1.json"),
            "raw_sha256": allin1_evidence.raw_sha256,
        }
        provenance["extractor_runs"].append({
            "id": "allin1",
            "tool": "allin1",
            "version": allin1_evidence.tool_version,
            "model": None,
            "parameters": {},
            "source_sha256": source_sha256,
            "raw_json": provenance["allin1"]["raw_json"],
            "raw_sha256": allin1_evidence.raw_sha256,
            "status": "available" if allin1_evidence.sections or allin1_evidence.beats_s else "not_detected",
            "timestamp_semantics": "beats and downbeats are absolute seconds; sections are [start_s, end_s]",
        })
    if essentia_present:
        provenance["essentia"] = {
            "version": essentia_evidence.tool_version,
            "profile": f"profiles/{profile_name}.yaml",
            "raw_json": raw_paths.get("essentia", f"raw/{track_id}/essentia.json"),
            "raw_sha256": essentia_evidence.raw_sha256,
            "profile_sha256": essentia_evidence.profile_sha256,
        }
        provenance["extractor_runs"].append({
            "id": "essentia",
            "tool": "essentia",
            "version": essentia_evidence.tool_version,
            "model": None,
            "parameters": {"profile": f"profiles/{profile_name}.yaml"},
            "source_sha256": source_sha256,
            "profile": f"profiles/{profile_name}.yaml",
            "raw_json": provenance["essentia"]["raw_json"],
            "raw_sha256": essentia_evidence.raw_sha256,
            "profile_sha256": essentia_evidence.profile_sha256,
            "status": "available",
            "timestamp_semantics": essentia_evidence.frame_features.get("time_basis", {}),
        })
    if allin1_evidence.raw_sha256 and allin1_present:
        provenance["allin1"]["raw_sha256"] = allin1_evidence.raw_sha256
    if source_sha256:
        provenance["source"] = {"sha256": source_sha256}

    def _source_status(field: str) -> str:
        statuses = [
            source.get(field, {}).get("status")
            for source in sources or []
            if isinstance(source.get(field), dict)
        ]
        if "available" in statuses:
            return "available"
        if "failed" in statuses:
            return "failed"
        if statuses and all(status == "not_applicable" for status in statuses):
            return "not_applicable"
        return "not_detected"

    if analysis_mode == "full_mix" and sources:
        pitch_status = _source_status("pitch")
        symbols_status = _source_status("notes")
    else:
        pitch_status = pitch.get("status") if pitch else ("not_applicable" if analysis_mode == "full_mix" else "not_detected")
        symbols_status = symbols.get("status") if symbols else ("not_applicable" if analysis_mode == "full_mix" else "not_detected")
    source_status = "available" if sources else ("failed" if raw_paths.get("demucs") else "not_applicable")
    separation_status = raw_paths.get("demucs_status") or (
        "available" if sources else ("failed" if raw_paths.get("demucs") else "not_applicable")
    )
    capabilities = {
        "essentia": "available" if essentia_present else "not_applicable",
        "rhythm": "available" if has_metric_grid else "not_detected",
        "functional_sections": "available" if has_functional_sections else "not_detected",
        "material_events": "available" if material_event_inputs else "not_detected",
        "frame_evidence": "available" if essentia_evidence.frame_features.get("timestamps_s") else "not_detected",
        "pitch": pitch_status,
        "sources": source_status,
        "source_separation": separation_status,
        "notes": symbols_status,
    }

    pitch_fields = {
        "status", "tool", "version", "pitch_range_midi", "median_midi",
        "voiced_ratio", "note_count", "note_density_per_s",
        "pitch_class_distribution", "artifact", "source_sha256", "raw_sha256",
        "error",
    }
    pitch_ir = {
        key: value for key, value in (pitch or {
            "status": capabilities["pitch"],
            "pitch_range_midi": None,
            "median_midi": None,
            "voiced_ratio": None,
            "note_count": None,
            "note_density_per_s": None,
            "pitch_class_distribution": None,
        }).items() if key in pitch_fields
    }
    pitch_ir.setdefault("status", capabilities["pitch"])
    pitch_ir.setdefault("pitch_range_midi", None)
    pitch_ir.setdefault("median_midi", None)
    pitch_ir.setdefault("voiced_ratio", None)
    if symbols:
        pitch_ir.setdefault("note_count", symbols.get("note_count"))
        pitch_ir.setdefault("note_density_per_s", symbols.get("note_density_per_s"))
        pitch_ir.setdefault("pitch_class_distribution", symbols.get("pitch_class_distribution"))
    else:
        pitch_ir.setdefault("note_count", None)
        pitch_ir.setdefault("note_density_per_s", None)
        pitch_ir.setdefault("pitch_class_distribution", None)
    source_ir = []
    source_pitch_fields = pitch_fields
    source_note_fields = {
        "status", "tool", "version", "model", "note_count", "note_density_per_s",
        "pitch_range_midi", "pitch_class_distribution", "amplitude_is_not_loudness",
        "artifacts", "ground_truth",
        "source_id", "source_sha256", "raw_sha256",
        "error",
    }
    for source in sources or []:
        source_copy = dict(source)
        if isinstance(source_copy.get("pitch"), dict):
            source_copy["pitch"] = {
                key: value for key, value in source_copy["pitch"].items() if key in source_pitch_fields
            }
        if isinstance(source_copy.get("notes"), dict):
            source_copy["notes"] = {
                key: value for key, value in source_copy["notes"].items() if key in source_note_fields
            }
        source_ir.append(source_copy)
    symbols_ir = {
        key: value for key, value in (symbols or {
            "status": symbols_status,
            "artifacts": [],
            "ground_truth": False,
        }).items() if key in source_note_fields
    }

    def _pitch_run(run_id: str, evidence: Dict[str, Any], fallback_hash: Optional[str]) -> Dict[str, Any]:
        return {
            "id": run_id,
            "tool": evidence.get("tool", "essentia.pitch_yin_probabilistic"),
            "version": evidence.get("version", "unknown"),
            "model": None,
            "parameters": {"frame_size": 2048, "hop_size": 1024, "sample_rate_hz": 44100},
            "source_sha256": evidence.get("source_sha256", fallback_hash),
            "status": evidence.get("status", "failed"),
            "raw_json": evidence.get("artifact"),
            "raw_sha256": evidence.get("raw_sha256"),
            "timestamp_semantics": "frame index × hop_size / sample_rate_hz",
            "error": evidence.get("error"),
        }

    def _note_run(run_id: str, evidence: Dict[str, Any], fallback_hash: Optional[str]) -> Dict[str, Any]:
        raw_json = evidence.get("raw_json") or evidence.get("notes_path")
        if not raw_json and evidence.get("artifacts"):
            raw_json = evidence["artifacts"][0]
        return {
            "id": run_id,
            "tool": evidence.get("tool", "basic-pitch"),
            "version": evidence.get("version", "unknown"),
            "model": evidence.get("model", "basic-pitch-default"),
            "parameters": {},
            "source_sha256": evidence.get("source_sha256", fallback_hash),
            "status": evidence.get("status", "failed"),
            "artifacts": evidence.get("artifacts", []),
            "raw_json": raw_json,
            "raw_sha256": evidence.get("raw_sha256"),
            "timestamp_semantics": "note start/end are seconds in the source audio",
            "error": evidence.get("error"),
        }

    if pitch:
        provenance["extractor_runs"].append(_pitch_run("essentia.pitch", pitch, source_sha256))
    if symbols and not sources and analysis_mode != "full_mix":
        provenance["extractor_runs"].append(_note_run("basic-pitch", symbols, source_sha256))
    for source in sources or []:
        source_id = str(source.get("id", "source"))
        source_hash = source.get("source_sha256", source_sha256)
        source_extractor = source.get("extractor")
        if isinstance(source_extractor, dict):
            provenance["extractor_runs"].append({
                "id": f"essentia.{source_id}",
                "tool": source_extractor.get("tool", "essentia"),
                "version": source_extractor.get("version", "unknown"),
                "model": None,
                "parameters": {"profile": source_extractor.get("profile", profile_name)},
                "profile": source_extractor.get("profile", profile_name),
                "source_sha256": source_extractor.get("source_sha256", source_hash),
                "status": source_extractor.get("status", "unknown"),
                "raw_json": source_extractor.get("raw_json"),
                "raw_sha256": source_extractor.get("raw_sha256"),
                "timestamp_semantics": source_extractor.get("timestamp_semantics", {}),
                "error": source_extractor.get("error"),
            })
        source_pitch = source.get("pitch")
        if isinstance(source_pitch, dict):
            provenance["extractor_runs"].append(
                _pitch_run(f"essentia.pitch.{source_id}", source_pitch, source_hash)
            )
        source_notes = source.get("notes")
        if isinstance(source_notes, dict) and source_notes.get("status") != "not_applicable":
            provenance["extractor_runs"].append(
                _note_run(f"basic-pitch.{source_id}", source_notes, source_hash)
            )
    if raw_paths.get("demucs"):
        provenance["extractor_runs"].append({
            "id": "demucs",
            "tool": "demucs-infer",
            "version": raw_paths.get("demucs_version", "unknown"),
            "model": raw_paths.get("demucs_model", "htdemucs_6s"),
            "parameters": {"device": "cpu", "float32": True},
            "source_sha256": source_sha256,
            "status": raw_paths.get("demucs_status", "available" if sources else "failed"),
            "raw_json": raw_paths["demucs"],
            "raw_sha256": raw_paths.get("demucs_sha256"),
            "timestamp_semantics": "stem samples retain source timeline",
            "error": raw_paths.get("demucs_error"),
        })

    music_ir = {
        "schema_version": "music-ir/0.2",
        "track": {
            "id": track_id,
            "title": title or track_id,
            "source_file": source_file,
            "duration_s": round(duration_s, 2),
            "analysis_mode": analysis_mode,
        },
        "global": {
            "tempo_bpm": {
                "value": tempo_val,
                "evidence": tempo_evidence,
                "candidates": tempo_candidates,
            },
            "meter": {
                "value": None,
                "status": "not_inferred",
            },
            "key_summary": key_summary,
            "key_candidates": key_candidates,
        },
        "structure": {
            "beats_s": allin1_evidence.beats_s if has_metric_grid else [],
            "downbeats_s": allin1_evidence.downbeats_s if has_metric_grid else [],
            "sections": sections,
            "material_events": material_events,
        },
        "harmony": {
            "key_summary": key_summary,
            "chord_statistics": essentia_evidence.chord_statistics or {
                "histogram": {},
                "changes_rate": None,
                "source": "essentia",
            },
            "time_aligned_chords": {
                "enabled": False,
                "status": "optional_chordino_or_other_aligner_required",
            },
        },
        "audio_features": audio_features,
        "capabilities": capabilities,
        "interpretation": {
            "manual_notes": [],
            "derived_summary": {
                "enabled": False,
                "rule": "Can only be generated from evidence and manual notes (ADR-0004).",
            },
            "synthesis_hints": {
                "enabled": False,
                "notes": "Synthesis mapping delegated to downstream agent (ADR-0004).",
            },
        },
        "provenance": provenance,
        "pitch": pitch_ir,
        "sources": source_ir,
        "symbols": symbols_ir,
        "review": {
            "human_checked": False,
            "domains": {
                "rhythm": "pending",
                "structure": "pending",
                "key": "pending",
                "pitch": "pending",
                "notes": "pending",
                "sources": "pending",
                "material_events": "pending",
            },
            "known_uncertainties": [
                "Segment boundaries and key candidates require auditory verification.",
            ],
        },
    }

    # Validate against strict schema
    validate_music_ir(music_ir, schema=schema)
    return music_ir


def build_jams(
    track_id: str,
    duration_s: float,
    allin1_evidence: Optional[AllInOneEvidence] = None,
    essentia_evidence: Optional[EssentiaEvidence] = None,
    source_file: Optional[str] = None,
    raw_paths: Optional[Dict[str, str]] = None,
    created_at: Optional[str] = None,
    source_sha256: Optional[str] = None,
    pitch: Optional[Dict[str, Any]] = None,
    symbols: Optional[Dict[str, Any]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a JAMS document and validate the official base schema."""
    if allin1_evidence is None:
        allin1_evidence = AllInOneEvidence()
    if essentia_evidence is None:
        essentia_evidence = EssentiaEvidence()
    raw_paths = raw_paths or {}

    jam = jams_library.JAMS()
    jam.file_metadata.title = track_id
    jam.file_metadata.duration = round(duration_s, 2)
    jam.file_metadata.identifiers = {"track_id": track_id}

    if _usable_sections(allin1_evidence, duration_s):
        annotation = jams_library.Annotation(
            namespace="segment_open",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": "allin1", "version": allin1_evidence.tool_version},
            ),
        )
        for sec in allin1_evidence.sections:
            annotation.append(
                time=sec["start_s"],
                duration=round(sec["end_s"] - sec["start_s"], 3),
                value=sec["label"],
                confidence=sec.get("confidence"),
            )
        jam.annotations.append(annotation)

    if _usable_allin1(allin1_evidence):
        positions: List[Optional[int]] = list(allin1_evidence.beat_positions)
        if not positions:
            positions = [
                1 if any(abs(beat - downbeat) < 1e-6 for downbeat in allin1_evidence.downbeats_s) else None
                for beat in allin1_evidence.beats_s
            ]
        annotation = jams_library.Annotation(
            namespace="beat",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": "allin1", "version": allin1_evidence.tool_version},
            ),
        )
        for beat, position in zip(allin1_evidence.beats_s, positions):
            annotation.append(time=beat, duration=0.0, value=position, confidence=None)
        jam.annotations.append(annotation)

    tempo_val = (
        allin1_evidence.tempo_bpm
        if allin1_evidence.tempo_bpm is not None and allin1_evidence.tempo_bpm > 0
        else essentia_evidence.bpm
    )
    if tempo_val and tempo_val > 0:
        tempo_tool = (
            "allin1"
            if allin1_evidence.tempo_bpm is not None and allin1_evidence.tempo_bpm > 0
            else "essentia"
        )
        tempo_version = allin1_evidence.tool_version if tempo_tool == "allin1" else essentia_evidence.tool_version
        annotation = jams_library.Annotation(
            namespace="tempo",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": tempo_tool, "version": tempo_version},
            ),
        )
        annotation.append(time=0.0, duration=duration_s, value=tempo_val, confidence=None)
        jam.annotations.append(annotation)

    if essentia_evidence.key_candidates:
        annotation = jams_library.Annotation(
            namespace="key_mode",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": "essentia", "version": essentia_evidence.tool_version},
            ),
        )
        for candidate in essentia_evidence.key_candidates:
            if candidate.get("key") and candidate.get("scale"):
                annotation.append(
                    time=0.0,
                    duration=duration_s,
                    value=f"{candidate['key']}:{candidate['scale']}",
                    confidence=candidate["strength"],
                )
        jam.annotations.append(annotation)

    frame_features = essentia_evidence.frame_features

    def _append_vector_annotation(
        timestamps: List[float],
        columns: List[str],
        values: List[List[float]],
        grid_name: str,
    ) -> None:
        if not timestamps or not columns or not all(values):
            return
        lengths = {len(timestamps), *(len(series) for series in values)}
        if len(lengths) != 1:
            raise ValueError(f"Essentia {grid_name} frame arrays must have equal lengths")
        annotation = jams_library.Annotation(
            namespace="vector",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": "essentia", "version": essentia_evidence.tool_version},
            ),
            sandbox={"columns": columns, "grid": grid_name},
        )
        for index, timestamp in enumerate(timestamps):
            annotation.append(
                time=timestamp,
                duration=0.0,
                value=[series[index] for series in values],
                confidence=None,
            )
        jam.annotations.append(annotation)

    lowlevel_columns = [
        name for name in (
            "spectral_centroid_hz",
            "spectral_flux",
            "spectral_rolloff_hz",
            "spectral_spread_hz",
            "spectral_entropy",
            "spectral_flatness",
            "spectral_energy",
            "spectral_energyband_low",
            "spectral_energyband_middle_low",
            "spectral_energyband_middle_high",
            "spectral_energyband_high",
            "dissonance",
            "pitch_salience",
        )
        if len(frame_features.get(name, [])) == len(frame_features.get("timestamps_s", []))
    ]
    lowlevel_timestamps = frame_features.get("timestamps_s", [])
    loudness_timestamps = frame_features.get("loudness_timestamps_s", [])
    loudness_is_lowlevel_aligned = (
        bool(loudness_timestamps)
        and loudness_timestamps == lowlevel_timestamps
        and len(frame_features.get("loudness_lufs", [])) == len(lowlevel_timestamps)
    )
    if loudness_is_lowlevel_aligned:
        lowlevel_columns.insert(0, "loudness_lufs")
    _append_vector_annotation(
        lowlevel_timestamps,
        lowlevel_columns,
        [frame_features.get(name, []) for name in lowlevel_columns],
        "lowlevel",
    )
    if not loudness_is_lowlevel_aligned:
        _append_vector_annotation(
            loudness_timestamps,
            ["loudness_lufs"],
            [frame_features.get("loudness_lufs", [])],
            "loudness",
        )
    if frame_features.get("hpcp") and frame_features.get("tonal_timestamps_s"):
        hpcp_annotation = jams_library.Annotation(
            namespace="vector",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": "essentia", "version": essentia_evidence.tool_version},
            ),
            sandbox={"columns": ["hpcp"], "grid": "tonal"},
        )
        for timestamp, row in zip(frame_features["tonal_timestamps_s"], frame_features["hpcp"]):
            hpcp_annotation.append(time=timestamp, duration=0.0, value=row, confidence=None)
        jam.annotations.append(hpcp_annotation)

    material_events = _material_events(frame_features, duration_s)
    if material_events:
        annotation = jams_library.Annotation(
            namespace="onset",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": "agent-listening.material-events", "version": "0.2"},
            ),
        )
        for event in material_events:
            annotation.append(
                time=event["time_s"],
                duration=0.0,
                value=event,
                confidence=event["prominence"],
            )
        jam.annotations.append(annotation)

    pitch_records: List[Tuple[Optional[str], Dict[str, Any]]] = []
    if pitch and pitch.get("contour"):
        pitch_records.append((None, pitch))
    for source in sources or []:
        source_pitch = source.get("pitch")
        if isinstance(source_pitch, dict) and source_pitch.get("contour"):
            pitch_records.append((str(source.get("id", "source")), source_pitch))

    for source_id, pitch_data in pitch_records:
        annotation = jams_library.Annotation(
            namespace="pitch_contour",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": pitch_data.get("tool", "essentia"), "version": pitch_data.get("version", "unknown")},
            ),
            sandbox={"source_id": source_id} if source_id else None,
        )
        contour = pitch_data["contour"]
        for point in contour:
            annotation.append(
                time=float(point["time_s"]),
                duration=float(point.get("duration_s", 0.0)),
                value={"frequency_hz": point.get("frequency_hz"), "voiced_probability": point.get("voiced_probability")},
                confidence=point.get("voiced_probability"),
            )
        jam.annotations.append(annotation)

    note_records: List[Tuple[Optional[str], Dict[str, Any]]] = []
    if symbols and symbols.get("notes") and not sources:
        note_records.append((None, symbols))
    for source in sources or []:
        source_notes = source.get("notes")
        if isinstance(source_notes, dict) and source_notes.get("notes"):
            note_records.append((str(source.get("id", "source")), source_notes))

    for source_id, symbols_data in note_records:
        annotation = jams_library.Annotation(
            namespace="note_midi",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": symbols_data.get("tool", "basic-pitch"), "version": symbols_data.get("version", "unknown")},
            ),
            sandbox={"source_id": source_id} if source_id else None,
        )
        for note in symbols_data["notes"]:
            annotation.append(
                time=float(note["start_s"]),
                duration=float(note["duration_s"]),
                value=float(note["midi_pitch"]),
                confidence=note.get("confidence"),
            )
        jam.annotations.append(annotation)

    jam.sandbox = {
        "allin1_version": allin1_evidence.tool_version,
        "essentia_version": essentia_evidence.tool_version,
        "allin1_raw_json": raw_paths.get("allin1"),
        "essentia_raw_json": raw_paths.get("essentia"),
        "allin1_raw_sha256": allin1_evidence.raw_sha256,
        "essentia_raw_sha256": essentia_evidence.raw_sha256,
        "essentia_profile_sha256": essentia_evidence.profile_sha256,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "created_at": created_at,
        "time_basis": frame_features.get("time_basis", {}),
    }
    jam.sandbox["validation"] = "jams_schema; namespace confidence unavailable"
    document = json.loads(jam.dumps())
    jams_library.schema.VALIDATOR.validate(document)
    return document


def merge_evidence(
    allin1_evidence: Optional[AllInOneEvidence],
    essentia_evidence: Optional[EssentiaEvidence],
    track_id: str,
    source_file: str,
    duration_s: Optional[float] = None,
    analysis_mode: str = "full_mix",
    profile_name: str = "essentia_v0_1",
    raw_paths: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
    created_at: str = "1970-01-01T00:00:00Z",
    schema: Optional[Dict[str, Any]] = None,
    source_sha256: Optional[str] = None,
    pitch: Optional[Dict[str, Any]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    symbols: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Pure functional fusion: (allin1, essentia) -> (JAMS, MusicIR)."""
    if duration_s is None:
        dur_essentia = essentia_evidence.duration_s if essentia_evidence else 0.0
        dur_allin1 = allin1_evidence.duration_s if allin1_evidence else 0.0
        duration_s = dur_essentia or dur_allin1 or 0.0

    music_ir = build_music_ir(
        track_id=track_id,
        source_file=source_file,
        duration_s=duration_s,
        allin1_evidence=allin1_evidence,
        essentia_evidence=essentia_evidence,
        analysis_mode=analysis_mode,
        profile_name=profile_name,
        raw_paths=raw_paths,
        title=title,
        created_at=created_at,
        schema=schema,
        source_sha256=source_sha256,
        pitch=pitch,
        sources=sources,
        symbols=symbols,
    )
    jams = build_jams(
        track_id=track_id,
        duration_s=duration_s,
        allin1_evidence=allin1_evidence,
        essentia_evidence=essentia_evidence,
        source_file=source_file,
        raw_paths=raw_paths,
        created_at=created_at,
        source_sha256=source_sha256,
        pitch=pitch,
        symbols=symbols,
        sources=sources,
    )
    return jams, music_ir
