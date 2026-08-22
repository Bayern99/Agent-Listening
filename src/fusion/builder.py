"""Pure Evidence Fusion and Artifact Builder.

Pure deterministic transformation functions that merge multi-extractor evidence into:
1. `JAMS` standard time-series annotation dict.
2. `MusicIR` JSON dict (conforming to schemas/music-ir-v0.1.schema.json).
"""

from typing import Any, Dict, List, Optional, Tuple

from src.adapters.allin1_adapter import AllInOneEvidence
from src.adapters.essentia_adapter import EssentiaEvidence
from src.fusion.validator import validate_music_ir


def _aggregate_section_acoustics(
    start_s: float,
    end_s: float,
    frame_features: Dict[str, List[float]],
    global_loudness: float,
    global_centroid: float,
    global_complexity: float,
) -> Tuple[float, float, float]:
    """Slice frame features within [start_s, end_s] and compute local mean statistics."""
    timestamps = frame_features.get("timestamps_s", [])
    loudness_frames = frame_features.get("loudness_lufs", [])
    centroid_frames = frame_features.get("spectral_centroid_hz", [])

    if not timestamps or not loudness_frames or not centroid_frames:
        # Fallback to global characteristics if frame curves not provided
        return round(global_loudness, 2), round(global_centroid, 2), round(global_complexity, 2)

    sliced_loudness = []
    sliced_centroids = []

    for t, l, c in zip(timestamps, loudness_frames, centroid_frames):
        if start_s <= t <= end_s:
            sliced_loudness.append(l)
            sliced_centroids.append(c)

    if not sliced_loudness:
        # Interpolate closest point
        closest_idx = min(range(len(timestamps)), key=lambda i: abs(timestamps[i] - (start_s + end_s) / 2.0))
        sliced_loudness = [loudness_frames[closest_idx]]
        sliced_centroids = [centroid_frames[closest_idx]]

    sec_loudness = sum(sliced_loudness) / len(sliced_loudness)
    sec_centroid = sum(sliced_centroids) / len(sliced_centroids)

    # Dynamic complexity approximation from local loudness variation
    if len(sliced_loudness) > 1:
        variance = sum((x - sec_loudness) ** 2 for x in sliced_loudness) / len(sliced_loudness)
        sec_complexity = round(variance ** 0.5, 2)
    else:
        sec_complexity = round(global_complexity, 2)

    return round(sec_loudness, 2), round(sec_centroid, 2), sec_complexity


def build_music_ir(
    track_id: str,
    source_file: str,
    duration_s: float,
    allin1_evidence: Optional[AllInOneEvidence] = None,
    essentia_evidence: Optional[EssentiaEvidence] = None,
    analysis_mode: str = "full_mix",
    profile_name: str = "essentia_v0_1",
    enable_symbols: bool = False,
    raw_paths: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
    created_at: str = "1970-01-01T00:00:00Z",
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pure, deterministic fusion of evidence into a validated Music IR dictionary."""
    if allin1_evidence is None:
        allin1_evidence = AllInOneEvidence()
    if essentia_evidence is None:
        essentia_evidence = EssentiaEvidence()
    if raw_paths is None:
        raw_paths = {}

    # 1. Global & Tempo evidence
    tempo_val = allin1_evidence.tempo_bpm if allin1_evidence.tempo_bpm is not None else (essentia_evidence.bpm or None)
    tempo_evidence = []
    if allin1_evidence.tempo_bpm is not None:
        tempo_evidence.append({"tool": "allin1", "field": "bpm", "value": allin1_evidence.tempo_bpm})
    if essentia_evidence.bpm:
        tempo_evidence.append({"tool": "essentia", "field": "rhythm.bpm", "value": essentia_evidence.bpm})

    # 2. Key arbitration in Fusion (ADR-0009: Max strength candidate wins)
    key_candidates = essentia_evidence.key_candidates
    key_summary: Optional[str] = None
    if key_candidates:
        winner = max(key_candidates, key=lambda c: c.get("strength", 0.0))
        if winner.get("key") and winner.get("scale"):
            key_summary = f"{winner['key']} {winner['scale']}"

    # 3. Structure & Sections with REAL inline acoustic aggregation (ADR-0008, ADR-0005)
    sections = []
    for sec in allin1_evidence.sections:
        sec_loudness, sec_centroid, sec_complexity = _aggregate_section_acoustics(
            start_s=sec["start_s"],
            end_s=sec["end_s"],
            frame_features=essentia_evidence.frame_features,
            global_loudness=essentia_evidence.loudness_ebu128_integrated_lufs,
            global_centroid=essentia_evidence.spectral_centroid_hz_mean,
            global_complexity=essentia_evidence.dynamic_complexity,
        )
        sections.append({
            "start_s": sec["start_s"],
            "end_s": sec["end_s"],
            "label": sec["label"],
            "tool": sec["tool"],
            "confidence": sec.get("confidence"),
            "loudness_lufs": sec_loudness,
            "spectral_centroid_hz": sec_centroid,
            "dynamic_complexity": sec_complexity,
        })

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

    # 5. Symbols opt-in logic (ADR-0007)
    symbols_active = enable_symbols or analysis_mode == "solo"
    symbols_dict = {
        "enabled": symbols_active,
        "note_events_csv": f"raw/{track_id}.notes.csv" if symbols_active else None,
        "midi_file": f"raw/{track_id}.mid" if symbols_active else None,
        "caveat": "Enabled for solo tracks / explicit opt-in." if symbols_active else "Disabled by default for full mix audio (ADR-0007).",
    }

    # 6. Provenance
    provenance = {
        "allin1": {
            "version": allin1_evidence.tool_version,
            "raw_json": raw_paths.get("allin1", f"raw/{track_id}/allin1.json"),
        },
        "essentia": {
            "version": essentia_evidence.tool_version,
            "profile": f"profiles/{profile_name}.yaml",
            "raw_json": raw_paths.get("essentia", f"raw/{track_id}/essentia.json"),
        },
        "basic_pitch": {
            "enabled": symbols_active,
            "version": "0.2.0" if symbols_active else None,
            "note_events_csv": symbols_dict["note_events_csv"],
        },
        "created_at": created_at,
    }

    music_ir = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "music-ir/0.1",
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
            },
            "meter": {
                "value": None,
                "status": "not_inferred_in_v0_1",
            },
            "key_summary": key_summary,
            "key_candidates": key_candidates,
        },
        "structure": {
            "beats_s": allin1_evidence.beats_s,
            "downbeats_s": allin1_evidence.downbeats_s,
            "sections": sections,
        },
        "harmony": {
            "key_summary": key_summary,
            "chord_statistics": essentia_evidence.chord_statistics,
            "time_aligned_chords": {
                "enabled": False,
                "status": "optional_chordino_or_other_aligner_required",
            },
        },
        "symbols": symbols_dict,
        "audio_features": audio_features,
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
        "review": {
            "human_checked": False,
            "known_uncertainties": [
                "Segment boundaries and key candidates require auditory verification.",
                "Symbolic transcription disabled by default for full mix.",
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
) -> Dict[str, Any]:
    """Pure, deterministic construction of standard JAMS time-series annotation dictionary."""
    if allin1_evidence is None:
        allin1_evidence = AllInOneEvidence()
    if essentia_evidence is None:
        essentia_evidence = EssentiaEvidence()

    annotations = []

    # 1. Section annotation (segment_open namespace) - NO confidence fabrication!
    if allin1_evidence.sections:
        sec_data = []
        for sec in allin1_evidence.sections:
            entry = {
                "time": sec["start_s"],
                "duration": round(sec["end_s"] - sec["start_s"], 3),
                "value": sec["label"],
            }
            # Only include confidence if actually present, do not fabricate 1.0
            if sec.get("confidence") is not None:
                entry["confidence"] = float(sec["confidence"])
            sec_data.append(entry)

        annotations.append({
            "namespace": "segment_open",
            "annotation_metadata": {
                "curator": {"name": "allin1", "email": ""},
                "data_source": "allin1 structure analysis",
            },
            "data": sec_data,
        })

    # 2. Beat annotation (beat namespace)
    if allin1_evidence.beats_s:
        beat_data = [
            {"time": b, "duration": 0.0, "value": idx + 1}
            for idx, b in enumerate(allin1_evidence.beats_s)
        ]
        annotations.append({
            "namespace": "beat",
            "annotation_metadata": {
                "curator": {"name": "allin1", "email": ""},
                "data_source": "allin1 beat tracking",
            },
            "data": beat_data,
        })

    # 3. Tempo annotation
    tempo_val = allin1_evidence.tempo_bpm or essentia_evidence.bpm
    if tempo_val:
        annotations.append({
            "namespace": "tempo",
            "annotation_metadata": {
                "curator": {"name": "allin1/essentia", "email": ""},
                "data_source": "tempo estimation",
            },
            "data": [{"time": 0.0, "duration": duration_s, "value": tempo_val}],
        })

    # 4. Key candidate annotations (key_mode namespace)
    if essentia_evidence.key_candidates:
        key_data = [
            {
                "time": 0.0,
                "duration": duration_s,
                "value": f"{c['key']} {c['scale']}",
                "confidence": c["strength"],
            }
            for c in essentia_evidence.key_candidates
            if c.get("key") and c.get("scale")
        ]
        annotations.append({
            "namespace": "key_mode",
            "annotation_metadata": {
                "curator": {"name": "essentia", "email": ""},
                "data_source": "essentia key estimation",
            },
            "data": key_data,
        })

    # 5. Continuous frame curves in JAMS (ADR-0005)
    frame_features = essentia_evidence.frame_features
    if frame_features.get("timestamps_s"):
        loudness_data = [
            {"time": t, "duration": 0.0, "value": l}
            for t, l in zip(frame_features["timestamps_s"], frame_features.get("loudness_lufs", []))
        ]
        if loudness_data:
            annotations.append({
                "namespace": "loudness",
                "annotation_metadata": {
                    "curator": {"name": "essentia", "email": ""},
                    "data_source": "essentia frame-level loudness",
                },
                "data": loudness_data,
            })

    return {
        "file_metadata": {
            "title": track_id,
            "artist": "",
            "release": "",
            "duration": round(duration_s, 2),
            "identifiers": {"track_id": track_id},
            "jams_version": "0.3.4",
        },
        "annotations": annotations,
        "sandbox": {
            "allin1_version": allin1_evidence.tool_version,
            "essentia_version": essentia_evidence.tool_version,
        },
    }


def merge_evidence(
    allin1_evidence: Optional[AllInOneEvidence],
    essentia_evidence: Optional[EssentiaEvidence],
    track_id: str,
    source_file: str,
    duration_s: Optional[float] = None,
    analysis_mode: str = "full_mix",
    profile_name: str = "essentia_v0_1",
    enable_symbols: bool = False,
    raw_paths: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
    created_at: str = "1970-01-01T00:00:00Z",
    schema: Optional[Dict[str, Any]] = None,
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
        enable_symbols=enable_symbols,
        raw_paths=raw_paths,
        title=title,
        created_at=created_at,
        schema=schema,
    )
    jams = build_jams(
        track_id=track_id,
        duration_s=duration_s,
        allin1_evidence=allin1_evidence,
        essentia_evidence=essentia_evidence,
    )
    return jams, music_ir
