"""Pure Evidence Fusion and Artifact Builder.

Pure deterministic transformation functions that merge multi-extractor evidence into:
1. `JAMS` standard time-series annotation dict.
2. `MusicIR` JSON dict (conforming to schemas/music-ir-v0.1.schema.json).
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import jams as jams_library

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

    if not timestamps or len(timestamps) != len(loudness_frames) or len(timestamps) != len(centroid_frames):
        return round(global_loudness, 2), round(global_centroid, 2), round(global_complexity, 2)

    indices = [index for index, timestamp in enumerate(timestamps) if start_s <= timestamp <= end_s]
    if not indices:
        indices = [min(range(len(timestamps)), key=lambda index: abs(timestamps[index] - (start_s + end_s) / 2.0))]
    sliced_loudness = [loudness_frames[index] for index in indices]
    sliced_centroids = [centroid_frames[index] for index in indices]
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
    raw_paths: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
    created_at: str = "1970-01-01T00:00:00Z",
    schema: Optional[Dict[str, Any]] = None,
    source_sha256: Optional[str] = None,
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
    dur_rounded = round(duration_s, 2)
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

    # 5. Provenance
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
        "created_at": created_at,
    }
    if allin1_evidence.raw_sha256:
        provenance["allin1"]["raw_sha256"] = allin1_evidence.raw_sha256
    if essentia_evidence.raw_sha256:
        provenance["essentia"]["raw_sha256"] = essentia_evidence.raw_sha256
    if essentia_evidence.profile_sha256:
        provenance["essentia"]["profile_sha256"] = essentia_evidence.profile_sha256
    if source_sha256:
        provenance["source"] = {"sha256": source_sha256}

    music_ir = {
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

    if allin1_evidence.sections:
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

    if allin1_evidence.beats_s:
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

    tempo_val = allin1_evidence.tempo_bpm or essentia_evidence.bpm
    if tempo_val:
        tempo_tool = "allin1" if allin1_evidence.tempo_bpm is not None else "essentia"
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
    columns = ["loudness_lufs", "spectral_centroid_hz", "spectral_flux"]
    vectors = [frame_features.get(name, []) for name in columns]
    timestamps = frame_features.get("timestamps_s", [])
    if timestamps and all(vectors):
        lengths = {len(timestamps), *(len(values) for values in vectors)}
        if len(lengths) != 1:
            raise ValueError("Essentia frame feature arrays must have equal lengths")
        annotation = jams_library.Annotation(
            namespace="vector",
            time=0,
            duration=duration_s,
            annotation_metadata=jams_library.AnnotationMetadata(
                data_source="program",
                annotator={"tool": "essentia", "version": essentia_evidence.tool_version},
            ),
            sandbox={"columns": columns},
        )
        for index, timestamp in enumerate(timestamps):
            annotation.append(
                time=timestamp,
                duration=0.0,
                value=[values[index] for values in vectors],
                confidence=None,
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
    )
    return jams, music_ir
