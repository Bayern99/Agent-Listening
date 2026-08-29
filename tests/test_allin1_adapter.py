import json
import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from src.adapters.allin1_adapter import AllInOneAdapter, AllInOneEvidence


class TestAllInOneAdapter(unittest.TestCase):
    def setUp(self):
        fixture_path = Path(__file__).parent / "fixtures" / "allin1_sample.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            self.sample_data = json.load(f)
        self.adapter = AllInOneAdapter()

    def test_parse_output_structure(self):
        evidence: AllInOneEvidence = self.adapter.parse_output(self.sample_data)

        self.assertAlmostEqual(evidence.duration_s, 183.42)
        self.assertAlmostEqual(evidence.tempo_bpm, 84.0)
        self.assertEqual(len(evidence.beats_s), 9)
        self.assertEqual(evidence.beat_positions, [1, 2, 3, 4, 1, 2, 3, 4, 1])
        self.assertEqual(len(evidence.downbeats_s), 3)
        self.assertEqual(len(evidence.sections), 5)

        first_section = evidence.sections[0]
        self.assertAlmostEqual(first_section["start_s"], 0.0)
        self.assertAlmostEqual(first_section["end_s"], 17.2)
        self.assertEqual(first_section["label"], "intro")
        self.assertEqual(first_section["tool"], "allin1")

    def test_missing_fields_fallback_gracefully(self):
        empty_data = {}
        evidence: AllInOneEvidence = self.adapter.parse_output(empty_data)
        self.assertEqual(evidence.duration_s, 0.0)
        self.assertIsNone(evidence.tempo_bpm)
        self.assertEqual(evidence.beats_s, [])
        self.assertEqual(evidence.downbeats_s, [])
        self.assertEqual(evidence.sections, [])

    def test_python_run_records_installed_version_and_beat_positions(self):
        result = SimpleNamespace(
            path="/does/not/matter.wav",
            bpm=120,
            beats=[0.5, 1.0],
            beat_positions=[1, 2],
            downbeats=[0.5],
            segments=[SimpleNamespace(start=0.0, end=1.5, label="intro")],
            activation_fps=50,
        )
        with tempfile.TemporaryDirectory() as tmpdir, patch("allin1_infer.analyze", return_value=result):
            output = Path(tmpdir) / "allin1.json"
            raw = self.adapter.run("/does/not/matter.wav", str(output))

        self.assertEqual(raw["version"], "3.1.0")
        self.assertEqual(raw["beat_positions"], [1, 2])
        self.assertEqual(raw["path"], "/does/not/matter.wav")
        self.assertEqual(raw["activation_fps"], 50)


if __name__ == "__main__":
    unittest.main()
