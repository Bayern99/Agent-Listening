import json
import io
from pathlib import Path
import contextlib
import sys
import tempfile
from typing import Any, Dict
import unittest
from unittest.mock import MagicMock, patch

from src import analyze, build_ir_from_files
from src import cli
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
            source = out_dir / "source.wav"
            source.write_bytes(b"source-audio")
            jams, music_ir = build_ir_from_files(
                allin1_path=self.allin1_path,
                essentia_path=self.essentia_path,
                track_id="test_track_001",
                source_file=str(source),
                output_dir=str(out_dir),
                created_at="2026-08-23T00:00:00Z",
            )

            # Check return objects
            self.assertEqual(music_ir["track"]["id"], "test_track_001")
            self.assertEqual(music_ir["global"]["key_summary"], "D minor")
            self.assertEqual(music_ir["provenance"]["created_at"], "2026-08-23T00:00:00Z")
            self.assertEqual(
                music_ir["provenance"]["allin1"]["raw_sha256"],
                "2ad0b3462f10eacbf004a6384dea027c08c90a9dab19c2a3fb9da2c471922d28",
            )
            self.assertEqual(
                music_ir["provenance"]["essentia"]["raw_sha256"],
                "2ce59450e0a2e4a6c8fab07491221306d704d7852898ec9d3b664e814f32a835",
            )
            self.assertEqual(
                music_ir["provenance"]["essentia"]["profile_sha256"],
                "951db93fd9ec885c7d52206396359a26f5d1e29cb246b14f46ca8b3c5af9883b",
            )
            self.assertEqual(
                music_ir["provenance"]["source"]["sha256"],
                "2578ea4ee8aa86428a0bb186f0a10b576a608fe22921b8d903f684443b7fe170",
            )

            # Check files written
            expected_ir_path = out_dir / "music-ir" / "test_track_001.music-ir.json"
            expected_jams_path = out_dir / "jams" / "test_track_001.analysis.jams"

            self.assertTrue(expected_ir_path.exists())
            self.assertTrue(expected_jams_path.exists())

            with open(expected_ir_path, "r", encoding="utf-8") as f:
                saved_ir = json.load(f)
            self.assertEqual(saved_ir["track"]["id"], "test_track_001")

            with self.assertRaises(FileExistsError):
                build_ir_from_files(
                    allin1_path=self.allin1_path,
                    essentia_path=self.essentia_path,
                    track_id="test_track_001",
                    source_file=str(source),
                    output_dir=str(out_dir),
                    created_at="2026-08-23T00:00:00Z",
                )

            build_ir_from_files(
                allin1_path=self.allin1_path,
                essentia_path=self.essentia_path,
                track_id="test_track_001",
                source_file=str(source),
                output_dir=str(out_dir),
                created_at="2026-08-23T00:00:00Z",
                overwrite=True,
            )

    def test_build_ir_rejects_unsafe_track_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                build_ir_from_files(
                    allin1_path=self.allin1_path,
                    essentia_path=self.essentia_path,
                    track_id="../escape",
                    output_dir=tmpdir,
                )

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
            def run_allin1(_audio_path, output_path):
                Path(output_path).write_text(json.dumps(allin1_fixture), encoding="utf-8")
                return allin1_fixture

            mock_allin1.run.side_effect = run_allin1
            mock_allin1.parse_output.return_value = AllInOneAdapter().parse_output(allin1_fixture)

            mock_essentia = MagicMock(spec=EssentiaAdapter)
            def run_essentia(_audio_path, _profile_path, output_path):
                Path(output_path).write_text(json.dumps(essentia_fixture), encoding="utf-8")
                return essentia_fixture

            mock_essentia.run.side_effect = run_essentia
            mock_essentia.parse_output.return_value = EssentiaAdapter().parse_output(essentia_fixture, profile_name="essentia_v0_1")

            # Call top-level analyze
            music_ir = analyze(
                audio_path=str(dummy_audio),
                output_dir=str(tmp_path),
                profile="essentia_v0_1",
                analysis_mode="solo",
                created_at="2026-08-23T00:00:00Z",
                allin1_adapter=mock_allin1,
                essentia_adapter=mock_essentia,
            )

            # Check that analyze returns MusicIR and writes files
            self.assertEqual(music_ir["track"]["id"], "test_song")
            self.assertEqual(music_ir["track"]["analysis_mode"], "solo")
            self.assertNotIn("symbols", music_ir)
            self.assertEqual(
                music_ir["provenance"]["source"]["sha256"],
                "73fd3366fce238b05b6657bbf1c676505efca23072a5337e74c34719b1665ffb",
            )

            # Verify mock calls
            mock_allin1.run.assert_called_once()
            mock_essentia.run.assert_called_once()

            # Verify files on disk
            self.assertTrue((tmp_path / "music-ir" / "test_song.music-ir.json").exists())
            self.assertTrue((tmp_path / "jams" / "test_song.analysis.jams").exists())

    def test_failed_extractor_leaves_no_partial_raw_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            audio = tmp_path / "failure.wav"
            audio.write_bytes(b"RIFFdummywavdata")

            allin1 = MagicMock(spec=AllInOneAdapter)
            allin1.run.side_effect = lambda _audio, output: Path(output).write_text("{}", encoding="utf-8") or {}
            allin1.parse_output.return_value = AllInOneAdapter().parse_output({})
            essentia = MagicMock(spec=EssentiaAdapter)
            essentia.run.side_effect = RuntimeError("extractor failed")

            with self.assertRaisesRegex(RuntimeError, "extractor failed"):
                analyze(
                    str(audio),
                    output_dir=str(tmp_path),
                    allin1_adapter=allin1,
                    essentia_adapter=essentia,
                )

            self.assertFalse((tmp_path / "raw" / "failure").exists())

    def test_cli_json_receipt_is_compact_and_absolute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            stdout = io.StringIO()
            argv = [
                "cli.py",
                "build-ir",
                "--allin1", self.allin1_path,
                "--essentia", self.essentia_path,
                "--track-id", "receipt-test",
                "--output-dir", str(output_dir),
                "--json",
            ]
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                cli.main()

            receipt = json.loads(stdout.getvalue())
            self.assertEqual(receipt["receipt_version"], "agent-listening/0.1")
            self.assertEqual(receipt["status"], "success")
            self.assertEqual(receipt["command"], "build-ir")
            self.assertEqual(receipt["track_id"], "receipt-test")
            self.assertTrue(Path(receipt["artifacts"]["music_ir"]).is_absolute())
            self.assertTrue(Path(receipt["artifacts"]["jams"]).is_absolute())
            self.assertIsNone(receipt["artifacts"]["raw_dir"])
            self.assertEqual(receipt["validation"]["human_listening"], "pending")

    def test_cli_json_error_is_machine_readable(self):
        stderr = io.StringIO()
        argv = [
            "cli.py",
            "build-ir",
            "--allin1", self.allin1_path,
            "--essentia", self.essentia_path,
            "--track-id", "../escape",
            "--json",
        ]
        with patch.object(sys, "argv", argv), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                cli.main()

        self.assertEqual(raised.exception.code, 1)
        receipt = json.loads(stderr.getvalue())
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["error"]["type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
