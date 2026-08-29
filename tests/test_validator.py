import copy
import json
from pathlib import Path
import unittest

from src.adapters.allin1_adapter import AllInOneAdapter
from src.adapters.essentia_adapter import EssentiaAdapter
from src.fusion.builder import build_music_ir
from src.fusion.validator import ValidationError, validate_music_ir


class TestMusicIRValidator(unittest.TestCase):
    def setUp(self):
        fixtures = Path(__file__).parent / "fixtures"
        with open(fixtures / "allin1_sample.json", "r", encoding="utf-8") as f:
            allin1 = AllInOneAdapter().parse_output(json.load(f))
        with open(fixtures / "essentia_sample.json", "r", encoding="utf-8") as f:
            essentia = EssentiaAdapter().parse_output(json.load(f))
        allin1.raw_sha256 = "a" * 64
        essentia.raw_sha256 = "b" * 64
        essentia.profile_sha256 = "c" * 64
        self.valid_data = build_music_ir(
            track_id="validator-fixture",
            source_file="source/validator-fixture.wav",
            duration_s=essentia.duration_s,
            allin1_evidence=allin1,
            essentia_evidence=essentia,
        )

    def test_valid_music_ir_passes(self):
        # Should validate without raising ValidationError
        validate_music_ir(self.valid_data)

    def test_historical_v01_artifact_still_uses_legacy_schema(self):
        legacy_path = Path(__file__).parent.parent / "music-ir" / "demo-track-001.music-ir.json"
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        self.assertEqual(legacy["schema_version"], "music-ir/0.1")
        validate_music_ir(legacy)

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

    def test_unknown_top_level_field_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["typo_field"] = True
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_unknown_nested_field_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["track"]["duraton_s"] = invalid["track"]["duration_s"]
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

        invalid = copy.deepcopy(self.valid_data)
        invalid["global"]["typo"] = True
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

        invalid = copy.deepcopy(self.valid_data)
        invalid["structure"]["sections"][0]["typo"] = True
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_key_strength_outside_probability_range_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["global"]["key_candidates"][0]["strength"] = 1.1
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_invalid_creation_timestamp_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["provenance"]["created_at"] = "not-a-date"
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_invalid_source_hash_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["provenance"]["source"] = {"sha256": "not-a-sha256"}
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_negative_section_time_fails(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["structure"]["sections"][0]["start_s"] = -0.1
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_overlapping_or_reversed_sections_fail(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["structure"]["sections"][1]["start_s"] = 10.0
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_sections_must_cover_the_track_continuously(self):
        invalid = copy.deepcopy(self.valid_data)
        invalid["structure"]["sections"][0]["start_s"] = 0.1
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

        invalid = copy.deepcopy(self.valid_data)
        invalid["structure"]["sections"][1]["start_s"] += 0.1
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

        invalid = copy.deepcopy(self.valid_data)
        invalid["structure"]["sections"][-1]["end_s"] -= 0.1
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)

    def test_provenance_hashes_are_required(self):
        for path in (("allin1", "raw_sha256"), ("essentia", "raw_sha256"), ("essentia", "profile_sha256")):
            with self.subTest(path=path):
                invalid = copy.deepcopy(self.valid_data)
                del invalid["provenance"][path[0]][path[1]]
                with self.assertRaises(ValidationError):
                    validate_music_ir(invalid)

        invalid = copy.deepcopy(self.valid_data)
        invalid["structure"]["sections"][0]["end_s"] = 0.0
        with self.assertRaises(ValidationError):
            validate_music_ir(invalid)


if __name__ == "__main__":
    unittest.main()
