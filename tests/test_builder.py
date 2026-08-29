import json
import unittest
from pathlib import Path
import tempfile

from src.adapters.allin1_adapter import AllInOneAdapter, AllInOneEvidence
from src.adapters.essentia_adapter import EssentiaAdapter, EssentiaEvidence
from src.fusion.builder import build_jams, build_music_ir, merge_evidence
from src.fusion.validator import validate_music_ir


class TestFusionBuilder(unittest.TestCase):
    def setUp(self):
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "allin1_sample.json", "r", encoding="utf-8") as f:
            self.allin1_raw = json.load(f)
        with open(fixtures_dir / "essentia_sample.json", "r", encoding="utf-8") as f:
            self.essentia_raw = json.load(f)

        self.allin1_evidence = AllInOneAdapter().parse_output(self.allin1_raw)
        self.essentia_evidence = EssentiaAdapter().parse_output(self.essentia_raw, profile_name="essentia_v0_1")
        self.allin1_evidence.raw_sha256 = "a" * 64
        self.essentia_evidence.raw_sha256 = "b" * 64
        self.essentia_evidence.profile_sha256 = "c" * 64

    def test_pure_deterministic_fusion(self):
        # Same input with explicit created_at must yield identical outputs
        jams1, ir1 = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
            created_at="2026-08-23T00:00:00Z",
        )
        jams2, ir2 = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
            created_at="2026-08-23T00:00:00Z",
        )
        self.assertEqual(ir1, ir2)
        self.assertEqual(jams1, jams2)

    def test_section_acoustic_aggregation(self):
        # Legacy fixture provides generic frame values; give its loudness
        # values the native EBU momentary grid before testing locality.
        self.essentia_evidence.frame_features["loudness_timestamps_s"] = [
            0.4, 10.4, 20.4, 50.4, 80.4, 120.4, 150.4, 180.4
        ]
        jams, ir = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
        )

        validate_music_ir(ir)

        # Ensure section acoustics are REAL aggregated numbers, not None/null (ADR-0005, ADR-0008)
        intro = ir["structure"]["sections"][0]
        self.assertIsNotNone(intro["loudness_lufs"])
        self.assertIsNotNone(intro["spectral_centroid_hz"])
        self.assertIsNotNone(intro["dynamic_complexity"])

        # Intro (0-17.2s) should have lower loudness than chorus (48.7-78.1s)
        chorus = ir["structure"]["sections"][2]
        self.assertLess(intro["loudness_lufs"], chorus["loudness_lufs"])

    def test_section_summary_does_not_fallback_to_global_without_timestamps(self):
        evidence = EssentiaEvidence(
            duration_s=183.42,
            loudness_ebu128_integrated_lufs=-13.4,
            spectral_centroid_hz_mean=1546.6,
            dynamic_complexity=2.6,
            raw_sha256="b" * 64,
            profile_sha256="c" * 64,
        )
        allin1 = AllInOneEvidence(
            duration_s=0.5,
            sections=[
                {"start_s": 0.0, "end_s": 0.25, "label": "verse", "tool": "allin1", "confidence": None},
                {"start_s": 0.25, "end_s": 0.5, "label": "chorus", "tool": "allin1", "confidence": None},
            ],
            raw_sha256="a" * 64,
        )
        _, ir = merge_evidence(
            allin1_evidence=allin1,
            essentia_evidence=evidence,
            track_id="no-frame-track",
            source_file="source/no-frame-track.wav",
        )

        self.assertIsNone(ir["structure"]["sections"][0]["loudness_lufs"])
        self.assertIsNone(ir["structure"]["sections"][0]["spectral_centroid_hz"])
        self.assertIsNone(ir["structure"]["sections"][0]["dynamic_complexity"])

    def test_section_loudness_does_not_reuse_lowlevel_grid(self):
        evidence = EssentiaEvidence(
            duration_s=1.0,
            raw_sha256="b" * 64,
            profile_sha256="c" * 64,
            frame_features={
                "timestamps_s": [0.0, 0.5, 1.0],
                "loudness_lufs": [-20.0, -10.0, -5.0],
                "spectral_centroid_hz": [100.0, 200.0, 300.0],
            },
        )
        allin1 = AllInOneEvidence(
            duration_s=1.0,
            sections=[
                {"start_s": 0.0, "end_s": 0.5, "label": "verse", "tool": "allin1"},
                {"start_s": 0.5, "end_s": 1.0, "label": "chorus", "tool": "allin1"},
            ],
            raw_sha256="a" * 64,
        )
        _, ir = merge_evidence(
            allin1_evidence=allin1,
            essentia_evidence=evidence,
            track_id="missing-loudness-grid",
            source_file="source/missing-loudness-grid.wav",
            duration_s=1.0,
        )
        self.assertIsNone(ir["structure"]["sections"][0]["loudness_lufs"])
        self.assertIsNotNone(ir["structure"]["sections"][0]["spectral_centroid_hz"])

    def test_key_arbitration_in_fusion(self):
        _, ir = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
        )

        # EDMA had strength 0.88, Temperley 0.79, Krumhansl 0.65 -> Winner is "D minor"
        self.assertEqual(ir["global"]["key_summary"], "D minor")
        self.assertEqual(len(ir["global"]["key_candidates"]), 3)

    def test_nonpositive_allin1_bpm_does_not_hide_essentia_tempo(self):
        allin1 = AllInOneEvidence(tempo_bpm=0.0, beats_s=[0.1, 0.2], raw_sha256="a" * 64)
        essentia = EssentiaEvidence(bpm=123.0, raw_sha256="b" * 64, profile_sha256="c" * 64)
        _, ir = merge_evidence(
            allin1_evidence=allin1,
            essentia_evidence=essentia,
            track_id="tempo-fallback",
            source_file="source/tempo-fallback.wav",
        )
        self.assertEqual(ir["global"]["tempo_bpm"]["value"], 123.0)

    def test_material_events_expose_frame_change_candidates(self):
        evidence = EssentiaEvidence(
            duration_s=0.5,
            loudness_ebu128_integrated_lufs=-12.0,
            spectral_centroid_hz_mean=1000.0,
            dynamic_complexity=1.0,
            raw_sha256="b" * 64,
            profile_sha256="c" * 64,
            frame_features={
                "timestamps_s": [0.0, 0.1, 0.2, 0.3, 0.4],
                "loudness_timestamps_s": [0.0, 0.1, 0.2, 0.3, 0.4],
                "loudness_lufs": [-20.0, -20.0, -10.0, -11.0, -11.0],
                "spectral_centroid_hz": [100.0, 100.0, 1000.0, 900.0, 900.0],
                "spectral_flux": [0.0, 0.0, 10.0, 1.0, 1.0],
            },
        )
        allin1 = AllInOneEvidence(duration_s=0.5, raw_sha256="a" * 64)

        jams, ir = merge_evidence(
            allin1_evidence=allin1,
            essentia_evidence=evidence,
            track_id="material-event-track",
            source_file="source/material-event-track.wav",
            duration_s=0.5,
        )

        self.assertEqual(len(ir["structure"]["material_events"]), 1)
        self.assertAlmostEqual(ir["structure"]["material_events"][0]["time_s"], 0.2)
        onset = next(annotation for annotation in jams["annotations"] if annotation["namespace"] == "onset")
        self.assertAlmostEqual(onset["data"][0]["time"], 0.2)

    def test_material_events_include_loudness_changes_from_native_grid(self):
        evidence = EssentiaEvidence(
            duration_s=1.0,
            loudness_ebu128_integrated_lufs=-12.0,
            spectral_centroid_hz_mean=1000.0,
            dynamic_complexity=1.0,
            raw_sha256="b" * 64,
            profile_sha256="c" * 64,
            frame_features={
                "timestamps_s": [0.0, 0.1, 0.2, 0.3, 0.4],
                "loudness_timestamps_s": [0.0, 0.2, 0.4],
                "loudness_lufs": [-20.0, -20.0, -5.0],
                "spectral_flux": [0.0, 0.0, 0.0, 0.0, 0.0],
            },
        )
        _, ir = merge_evidence(
            allin1_evidence=AllInOneEvidence(duration_s=1.0, raw_sha256="a" * 64),
            essentia_evidence=evidence,
            track_id="loudness-event-track",
            source_file="source/loudness-event-track.wav",
            duration_s=1.0,
        )

        self.assertEqual(ir["capabilities"]["material_events"], "available")
        self.assertTrue(any("loudness_change" in event["changed_features"] for event in ir["structure"]["material_events"]))

    def test_jams_keeps_lowlevel_loudness_and_tonal_grids_separate(self):
        evidence = EssentiaEvidence(
            duration_s=1.0,
            raw_sha256="b" * 64,
            profile_sha256="c" * 64,
            frame_features={
                "timestamps_s": [0.0, 0.1, 0.2],
                "loudness_timestamps_s": [0.4, 0.5],
                "loudness_lufs": [-20.0, -10.0],
                "spectral_centroid_hz": [100.0, 200.0, 300.0],
                "tonal_timestamps_s": [0.0],
                "hpcp": [[0.1] * 12],
            },
        )
        jams, _ = merge_evidence(
            allin1_evidence=AllInOneEvidence(raw_sha256="a" * 64),
            essentia_evidence=evidence,
            track_id="grid-track",
            source_file="source/grid-track.wav",
            duration_s=1.0,
        )

        grids = {
            annotation["sandbox"].get("grid")
            for annotation in jams["annotations"]
            if annotation["namespace"] == "vector"
        }
        self.assertEqual(grids, {"lowlevel", "loudness", "tonal"})

    def test_jams_keeps_lowlevel_dissonance_and_pitch_salience(self):
        evidence = EssentiaEvidence(
            duration_s=0.2,
            raw_sha256="b" * 64,
            profile_sha256="c" * 64,
            frame_features={
                "timestamps_s": [0.0, 0.1],
                "dissonance": [0.1, 0.2],
                "pitch_salience": [0.3, 0.4],
            },
        )
        jams, _ = merge_evidence(
            allin1_evidence=AllInOneEvidence(raw_sha256="a" * 64),
            essentia_evidence=evidence,
            track_id="frame-columns",
            source_file="source/frame-columns.wav",
            duration_s=0.2,
        )
        frame = next(
            annotation for annotation in jams["annotations"]
            if annotation["namespace"] == "vector" and annotation["sandbox"]["grid"] == "lowlevel"
        )
        self.assertEqual(frame["sandbox"]["columns"], ["dissonance", "pitch_salience"])

    def test_jams_keeps_source_pitch_and_note_identity(self):
        source = {
            "id": "vocals",
            "pitch": {
                "tool": "essentia.pitch_yin_probabilistic",
                "version": "2.1",
                "contour": [{"time_s": 0.0, "frequency_hz": 440.0, "voiced_probability": 0.9}],
            },
            "notes": {
                "tool": "basic-pitch",
                "version": "0.4.0",
                "notes": [{"start_s": 0.0, "duration_s": 0.5, "midi_pitch": 69, "confidence": None}],
            },
        }
        jams, _ = merge_evidence(
            allin1_evidence=AllInOneEvidence(raw_sha256="a" * 64),
            essentia_evidence=EssentiaEvidence(duration_s=1.0, raw_sha256="b" * 64, profile_sha256="c" * 64),
            track_id="source-evidence",
            source_file="source/source-evidence.wav",
            duration_s=1.0,
            analysis_mode="full_mix",
            source_sha256="d" * 64,
            sources=[source],
        )
        source_annotations = [
            annotation for annotation in jams["annotations"]
            if annotation["namespace"] in {"pitch_contour", "note_midi"}
        ]
        self.assertEqual(
            {(annotation["namespace"], annotation["sandbox"]["source_id"]) for annotation in source_annotations},
            {("pitch_contour", "vocals"), ("note_midi", "vocals")},
        )

    def test_unimplemented_symbolic_transcription_is_not_claimed(self):
        _, ir = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
        )

        self.assertEqual(ir["symbols"]["status"], "not_applicable")
        self.assertFalse(ir["symbols"]["ground_truth"])
        self.assertNotIn("basic_pitch", ir["provenance"])

    def test_jams_no_confidence_spoofing_and_frame_curves(self):
        jams, _ = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
            raw_paths={"allin1": "raw/a.json", "essentia": "raw/e.json"},
            source_sha256="d" * 64,
        )

        # Unknown confidence remains explicit null, never fabricated as 1.0.
        seg_ann = next(a for a in jams["annotations"] if a["namespace"] == "segment_open")
        self.assertIsNone(seg_ann["data"][0]["confidence"])

        beat_ann = next(a for a in jams["annotations"] if a["namespace"] == "beat")
        self.assertEqual(
            [observation["value"] for observation in beat_ann["data"]],
            [1, 2, 3, 4, 1, 2, 3, 4, 1],
        )

        frame_ann = next(
            a for a in jams["annotations"]
            if a["namespace"] == "vector" and a["sandbox"]["grid"] == "lowlevel"
        )
        self.assertEqual(frame_ann["sandbox"]["columns"], ["spectral_centroid_hz", "spectral_flux"])
        loudness_ann = next(
            a for a in jams["annotations"]
            if a["namespace"] == "vector" and a["sandbox"]["grid"] == "loudness"
        )
        self.assertEqual(loudness_ann["sandbox"]["columns"], ["loudness_lufs"])

        import jams as jams_library

        with tempfile.NamedTemporaryFile("w", suffix=".jams", encoding="utf-8") as output:
            json.dump(jams, output)
            output.flush()
            jams_library.load(output.name, validate=False)
        jams_library.schema.VALIDATOR.validate(jams)

        self.assertEqual(jams["sandbox"]["allin1_raw_sha256"], "a" * 64)
        self.assertEqual(jams["sandbox"]["essentia_raw_sha256"], "b" * 64)
        self.assertEqual(jams["sandbox"]["essentia_profile_sha256"], "c" * 64)
        self.assertEqual(jams["sandbox"]["source_sha256"], "d" * 64)
        self.assertEqual(jams["sandbox"]["allin1_raw_json"], "raw/a.json")
        tempo_ann = next(a for a in jams["annotations"] if a["namespace"] == "tempo")
        self.assertEqual(tempo_ann["annotation_metadata"]["annotator"]["tool"], "allin1")


if __name__ == "__main__":
    unittest.main()
