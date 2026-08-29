import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

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

    def test_chord_histogram_array_is_preserved(self):
        data = {"tonal": {"chords_histogram": [0.25, 0.75]}}
        evidence = self.adapter.parse_output(data)
        self.assertEqual(evidence.chord_statistics["histogram"], [0.25, 0.75])

    def test_missing_fields_fallback_gracefully(self):
        empty_data = {}
        evidence: EssentiaEvidence = self.adapter.parse_output(empty_data)
        self.assertEqual(evidence.duration_s, 0.0)
        self.assertEqual(evidence.key_candidates, [])
        self.assertEqual(evidence.tool_version, "unknown")

    def test_project_profile_configures_installed_essentia(self):
        import essentia.standard as es

        profile_path = Path(__file__).parent.parent / "profiles" / "essentia_v0_1.yaml"
        es.MusicExtractor(profile=str(profile_path))

    def test_run_preserves_essentia_configuration_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "invalid.yaml"
            profile_path.write_text("lowlevel:\n  stats: invalid\n", encoding="utf-8")

            with self.assertRaises(RuntimeError) as raised:
                EssentiaAdapter(binary_path="definitely-not-installed").run(
                    "/does/not/exist.wav",
                    str(profile_path),
                    str(Path(tmpdir) / "output.json"),
                )

            self.assertNotIn("both not found", str(raised.exception))

    def test_python_extractor_serializes_real_essentia_pool(self):
        import essentia

        aggregate = essentia.Pool()
        aggregate.set("metadata.audio_properties.length", 12.5)
        frames = essentia.Pool()
        frames.add("lowlevel.spectral_centroid", 440.0)
        frames.add("lowlevel.spectral_centroid", 880.0)
        extractor = lambda _audio_path: (aggregate, frames)

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "essentia.standard.MusicExtractor", return_value=extractor
        ):
            output_path = Path(tmpdir) / "essentia.json"
            result = EssentiaAdapter(binary_path="definitely-not-installed").run(
                "/does/not/matter.wav",
                str(Path(tmpdir) / "profile.yaml"),
                str(output_path),
            )

        self.assertEqual(result["aggregate"]["metadata"]["audio_properties"]["length"], 12.5)
        self.assertEqual(result["frames"]["lowlevel"]["spectral_centroid"], [440.0, 880.0])
        evidence = self.adapter.parse_output(result)
        self.assertEqual(evidence.frame_features["spectral_centroid_hz"], [])
        self.assertEqual(evidence.frame_features["timestamps_s"], [])


if __name__ == "__main__":
    unittest.main()
