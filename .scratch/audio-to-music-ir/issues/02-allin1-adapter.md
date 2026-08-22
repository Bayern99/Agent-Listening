# Issue 02: allin1 Adapter & Structure Extractor

Status: resolved
Blocked by: None
Type: task

## Context
We need a Python adapter (`src/adapters/allin1_adapter.py`) to run `allin1.analyze()` / CLI and parse BPM, beat grid, downbeats, and functional sections (`start_s`, `end_s`, `label`).

## Acceptance Criteria
- [x] `AllInOneAdapter.parse_output(raw_dict)` extracts `tempo_bpm`, `beats_s`, `downbeats_s`, and `sections`.
- [x] Handles edge cases (empty beats, missing label gracefully).
- [x] Unit tests in `tests/test_allin1_adapter.py` pass against mock fixtures.

## Answer
Implemented `src/adapters/allin1_adapter.py` supporting both native python library calls and CLI fallback with structured evidence normalization.
