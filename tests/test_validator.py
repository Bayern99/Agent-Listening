import copy
import json
from pathlib import Path
import unittest

from src.fusion.validator import ValidationError, validate_music_ir


class TestMusicIRValidator(unittest.TestCase):
    def setUp(self):
        example_path = Path(__file__).parent / "fixtures" / "valid_music_ir_fixture.json"
        # We also have music-ir/demo-track-001.music-ir.json
        demo_path = Path(__file__).parent.parent / "music-ir" / "demo-track-001.music-ir.json"
        with open(demo_path, "r", encoding="utf-8") as f:
            self.valid_data = json.load(f)

    def test_valid_music_ir_passes(self):
        # Should validate without raising ValidationError
        validate_music_ir(self.valid_data)

    def test_missing_required_top_level_fails(self):
        for required_field in ["schema_version", "track", "global", "structure", "harmony", "audio_features", "provenance", "review"]:
            with self.subTest(field=required_field):
                invalid = copy.deepcopy(self.valid_data)
                del invalid[required_field]
                with self.assertRaises(ValidationError):
                    validate_music_ir(invalid)

    def test_invalid_schema_version_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["schema_version"] = "music-ir/999.0"
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_invalid_analysis_mode_enum_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["track"]["analysis_mode"] = "invalid_mode"
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_negative_duration_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["track"]["duration_s"] = -10.5
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_invalid_section_schema_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        # Missing label in a section
        del invalid["structure"]["sections"][0]["label"]
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_invalid_key_candidates_schema_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        # Missing strength in key candidate
        del invalid["global"]["key_candidates"][0]["strength"]
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_missing_audio_features_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        del invalid["audio_features"]["loudness_ebu128_integrated_lufs"]
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)


if __name__ == "__main__":
    unittest.main()
