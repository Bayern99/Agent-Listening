import json
import unittest
from pathlib import Path

from src.adapters.essentia_adapter import EssentiaAdapter, EssentiaEvidence


class TestEssentiaAdapter(unittest.TestCase):
    def setUp(self):
        fixture_path = Path(__file__).parent / "fixtures" / "essentia_sample.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            self.sample_data = json.load(f)
        self.adapter = EssentiaAdapter()

    def test_parse_output_structure(self):
        evidence: EssentiaEvidence = self.adapter.parse_output(self.sample_data, profile_name="essentia_v0_1")

        self.assertAlmostEqual(evidence.duration_s, 183.42)
        self.assertAlmostEqual(evidence.loudness_ebu128_integrated_lufs, -13.4)
        self.assertAlmostEqual(evidence.loudness_range_lu, 7.8)
        self.assertAlmostEqual(evidence.dynamic_complexity, 2.6)
        self.assertAlmostEqual(evidence.spectral_centroid_hz_mean, 1546.6)
        self.assertAlmostEqual(evidence.spectral_flux_mean, 0.1068)
        self.assertAlmostEqual(evidence.onset_rate_per_s, 1.2)
        self.assertEqual(evidence.tool_version, "2.1-beta6-git")

        # Frame curves parsed
        self.assertIn("timestamps_s", evidence.frame_features)
        self.assertIn("loudness_lufs", evidence.frame_features)
        self.assertEqual(len(evidence.frame_features["timestamps_s"]), 8)

    def test_key_candidates_pure_evidence(self):
        evidence: EssentiaEvidence = self.adapter.parse_output(self.sample_data)

        # 3 candidates preserved in evidence, adapter does NOT perform key_summary arbitration
        self.assertEqual(len(evidence.key_candidates), 3)
        edma = next(k for k in evidence.key_candidates if k["algorithm"] == "edma")
        self.assertEqual(edma["key"], "D")
        self.assertEqual(edma["scale"], "minor")
        self.assertAlmostEqual(edma["strength"], 0.88)

    def test_missing_fields_fallback_gracefully(self):
        empty_data = {}
        evidence: EssentiaEvidence = self.adapter.parse_output(empty_data)
        self.assertEqual(evidence.duration_s, 0.0)
        self.assertEqual(evidence.key_candidates, [])
        self.assertEqual(evidence.tool_version, "unknown")


if __name__ == "__main__":
    unittest.main()
