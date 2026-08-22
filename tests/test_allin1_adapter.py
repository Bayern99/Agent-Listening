import json
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
