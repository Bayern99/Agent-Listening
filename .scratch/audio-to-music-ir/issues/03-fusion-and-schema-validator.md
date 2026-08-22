# Issue 03: Evidence Fusion, JAMS Generation & Schema Validation

Status: resolved
Blocked by: 01, 02
Type: task

## Context
Implement the pure transformation module `src/fusion/builder.py` that takes normalized evidence from `allin1` and `Essentia`, metadata, and produces:
1. Validated `MusicIR` JSON dict conforming to `schemas/music-ir-v0.1.schema.json`.
2. Standard `JAMS` dict with multi-candidate timing annotations.

## Acceptance Criteria
- [x] `build_music_ir(...)` is pure and deterministic.
- [x] Validates output against `schemas/music-ir-v0.1.schema.json`.
- [x] `build_jams(...)` generates valid JAMS structure with namespace annotations (`segment_open`, `beat`, `tempo`, `key_mode`).
- [x] Unit tests in `tests/test_builder.py` verify full schema compliance.

## Answer
Implemented `src/fusion/builder.py` and `src/fusion/validator.py`. Validated against JSON schema.
