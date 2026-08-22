# Issue 04: CLI Runner & End-to-End Integration

Status: resolved
Blocked by: 03
Type: task

## Context
Implement the public CLI interface (`src/cli.py`) and top-level runner that orchestrates extraction, archiving to `raw/`, generating `jams/`, and generating `music-ir/`.

## Acceptance Criteria
- [x] Command `python3 -m src.cli build-ir --allin1 <path> --essentia <path> --output-dir <dir>` produces both `.jams` and `.music-ir.json`.
- [x] Command `python3 -m src.cli analyze <audio_path>` orchestrates extractors when tools are present.
- [x] Integration tests in `tests/test_cli.py` pass.

## Answer
Implemented `src/cli.py` supporting `analyze` and `build-ir` subcommands. Verified with end-to-end integration tests.
