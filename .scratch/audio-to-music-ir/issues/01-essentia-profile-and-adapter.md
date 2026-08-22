# Issue 01: Essentia YAML Profile & Adapter

Status: resolved
Blocked by: None
Type: task

## Context
We need a standardized analysis profile (`profiles/essentia_v0_1.yaml`) for `essentia_streaming_extractor_music` and a Python adapter (`src/adapters/essentia_adapter.py`) to invoke the CLI and parse raw acoustic, loudness, and tonal features.

## Acceptance Criteria
- [x] `profiles/essentia_v0_1.yaml` defines frame parameters, EBU R128 loudness, spectral descriptors, and key candidates.
- [x] `EssentiaAdapter.parse_output(raw_dict)` extracts `loudness_ebu128_integrated_lufs`, `loudness_range_lu`, `dynamic_complexity`, `spectral_centroid_hz_mean`, `spectral_flux_mean`, `onset_rate_per_s`, and `key_candidates`.
- [x] Unit tests in `tests/test_essentia_adapter.py` pass against mock fixtures.

## Answer
Implemented `profiles/essentia_v0_1.yaml` and `src/adapters/essentia_adapter.py` with multi-key arbitration (ADR-0009). Verified with unit tests.
