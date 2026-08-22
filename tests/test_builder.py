import json
import unittest
from pathlib import Path

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

    def test_symbols_opt_in(self):
        # Default full_mix -> symbols disabled (ADR-0007)
        _, ir_default = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
            enable_symbols=False,
            analysis_mode="full_mix",
        )
        self.assertFalse(ir_default["symbols"]["enabled"])

        # Explicit opt-in -> symbols enabled
        _, ir_symbols = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
            enable_symbols=True,
            analysis_mode="full_mix",
        )
        self.assertTrue(ir_symbols["symbols"]["enabled"])

    def test_jams_no_confidence_spoofing_and_frame_curves(self):
        jams, _ = merge_evidence(
            allin1_evidence=self.allin1_evidence,
            essentia_evidence=self.essentia_evidence,
            track_id="my-track-001",
            source_file="source/my-track-001.wav",
        )

        # Sections where confidence was None should not have confidence = 1.0
        seg_ann = next(a for a in jams["annotations"] if a["namespace"] == "segment_open")
        self.assertNotIn("confidence", seg_ann["data"][0])

        # Loudness frame curve present (ADR-0005)
        loudness_ann = next(a for a in jams["annotations"] if a["namespace"] == "loudness")
        self.assertGreater(len(loudness_ann["data"]), 0)


if __name__ == "__main__":
    unittest.main()
