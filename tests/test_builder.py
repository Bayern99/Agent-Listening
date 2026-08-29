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

    def test_unimplemented_symbolic_transcription_is_not_claimed(self):
        _, ir = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
        )

        self.assertNotIn("symbols", ir)
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

        frame_ann = next(a for a in jams["annotations"] if a["namespace"] == "vector")
        self.assertEqual(frame_ann["sandbox"]["columns"], ["loudness_lufs", "spectral_centroid_hz", "spectral_flux"])

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
