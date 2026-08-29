from pathlib import Path
import tempfile
import json
import unittest

from src.adapters.demucs_adapter import DemucsAdapter


class TestDemucsAdapter(unittest.TestCase):
    def test_parse_manifest_keeps_known_existing_stems_only(self):
        fixture = Path(__file__).parent / "fixtures" / "demucs_manifest.json"
        manifest = json.loads(fixture.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmpdir:
            vocals = Path(tmpdir) / "vocals.wav"
            vocals.write_bytes(b"wav")
            for stem in manifest["stems"]:
                stem["path"] = str(Path(tmpdir) / stem["path"])
            stems = DemucsAdapter.parse_manifest(manifest)
            stable = DemucsAdapter.artifact_manifest(manifest, "track")

        self.assertEqual(stems, [{"id": "vocals", "role": "vocals", "path": str(vocals)}])
        self.assertEqual(stable["model"], "htdemucs_6s")
        self.assertEqual(stable["status"], "failed")
        self.assertIn("bass", stable["missing_stems"])
        self.assertEqual(stable["stems"][0]["path"], "stems/track/vocals.wav")


if __name__ == "__main__":
    unittest.main()
