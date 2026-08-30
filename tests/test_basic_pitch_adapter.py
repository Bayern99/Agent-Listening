import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.adapters.basic_pitch_adapter import BasicPitchAdapter


class TestBasicPitchAdapter(unittest.TestCase):
    def test_note_events_preserve_timing_and_do_not_call_amplitude_loudness(self):
        fixture = Path(__file__).parent / "fixtures" / "basic_pitch_notes.json"
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        evidence = BasicPitchAdapter.parse_note_events(
            raw["note_events"], tool_version=raw["version"]
        )

        self.assertEqual(evidence["status"], "available")
        self.assertEqual(evidence["note_count"], 2)
        self.assertEqual(evidence["notes"][0]["midi_pitch"], 69)
        self.assertAlmostEqual(evidence["notes"][0]["duration_s"], 0.5)
        self.assertEqual(evidence["notes"][0]["amplitude"], 0.8)
        self.assertIsNone(evidence["notes"][0]["confidence"])
        self.assertAlmostEqual(evidence["notes"][1]["confidence"], 0.77)
        self.assertAlmostEqual(evidence["pitch_class_distribution"][9], 0.5, places=4)
        self.assertTrue(evidence["amplitude_is_not_loudness"])

    def test_empty_note_events_are_not_claimed_as_available(self):
        evidence = BasicPitchAdapter.parse_note_events([], tool_version="0.4.0")
        self.assertEqual(evidence["status"], "not_detected")
        self.assertIsNone(evidence["pitch_range_midi"])

    def test_note_density_uses_the_complete_audio_duration(self):
        evidence = BasicPitchAdapter.parse_note_events(
            [(0.0, 1.0, 69, 0.8)],
            tool_version="0.4.0",
            duration_s=60.0,
        )

        self.assertAlmostEqual(evidence["note_density_per_s"], 0.0167, places=4)

    def test_empty_prediction_writes_no_optional_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("basic_pitch.inference.predict", return_value=(None, None, [])):
                result = BasicPitchAdapter().run("input.wav", tmpdir, "input")
            self.assertEqual(result["status"], "not_detected")
            self.assertIsNone(result["notes_path"])
            self.assertIsNone(result["midi_path"])
            self.assertEqual(list(Path(tmpdir).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
