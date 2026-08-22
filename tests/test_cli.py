import json
from pathlib import Path
import tempfile
from typing import Any, Dict
import unittest
from unittest.mock import MagicMock

from src import analyze, build_ir_from_files
from src.adapters.allin1_adapter import AllInOneAdapter
from src.adapters.essentia_adapter import EssentiaAdapter


class TestCLIAndCore(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = Path(__file__).parent / "fixtures"
        self.allin1_path = str(self.fixtures_dir / "allin1_sample.json")
        self.essentia_path = str(self.fixtures_dir / "essentia_sample.json")

    def test_build_ir_from_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            jams, music_ir = build_ir_from_files(
                allin1_path=self.allin1_path,
                essentia_path=self.essentia_path,
                track_id="test_track_001",
                output_dir=str(out_dir),
                created_at="2026-08-23T00:00:00Z",
            )

            # Check return objects
            self.assertEqual(music_ir["track"]["id"], "test_track_001")
            self.assertEqual(music_ir["global"]["key_summary"], "D minor")
            self.assertEqual(music_ir["provenance"]["created_at"], "2026-08-23T00:00:00Z")

            # Check files written
            expected_ir_path = out_dir / "music-ir" / "test_track_001.music-ir.json"
            expected_jams_path = out_dir / "jams" / "test_track_001.analysis.jams"

            self.assertTrue(expected_ir_path.exists())
            self.assertTrue(expected_jams_path.exists())

            with open(expected_ir_path, "r", encoding="utf-8") as f:
                saved_ir = json.load(f)
            self.assertEqual(saved_ir["track"]["id"], "test_track_001")

    def test_analyze_integration_with_mock_adapters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            dummy_audio = tmp_path / "test_song.wav"
            dummy_audio.write_bytes(b"RIFFdummywavdata")

            # Load fixture data
            with open(self.allin1_path, "r", encoding="utf-8") as f:
                allin1_fixture = json.load(f)
            with open(self.essentia_path, "r", encoding="utf-8") as f:
                essentia_fixture = json.load(f)

            # Mock adapters
            mock_allin1 = MagicMock(spec=AllInOneAdapter)
            mock_allin1.run.return_value = allin1_fixture
            mock_allin1.parse_output.return_value = AllInOneAdapter().parse_output(allin1_fixture)

            mock_essentia = MagicMock(spec=EssentiaAdapter)
            mock_essentia.run.return_value = essentia_fixture
            mock_essentia.parse_output.return_value = EssentiaAdapter().parse_output(essentia_fixture, profile_name="essentia_v0_1")

            # Call top-level analyze
            music_ir = analyze(
                audio_path=str(dummy_audio),
                output_dir=str(tmp_path),
                profile="essentia_v0_1",
                enable_symbols=True,
                analysis_mode="solo",
                created_at="2026-08-23T00:00:00Z",
                allin1_adapter=mock_allin1,
                essentia_adapter=mock_essentia,
            )

            # Check that analyze returns MusicIR and writes files
            self.assertEqual(music_ir["track"]["id"], "test_song")
            self.assertEqual(music_ir["track"]["analysis_mode"], "solo")
            self.assertTrue(music_ir["symbols"]["enabled"])

            # Verify mock calls
            mock_allin1.run.assert_called_once()
            mock_essentia.run.assert_called_once()

            # Verify files on disk
            self.assertTrue((tmp_path / "music-ir" / "test_song.music-ir.json").exists())
            self.assertTrue((tmp_path / "jams" / "test_song.analysis.jams").exists())


if __name__ == "__main__":
    unittest.main()
