# Changelog

All notable changes to Agent Listening CLI are recorded here. Release notes
describe the shipped interface and its verification boundary; they do not turn
machine-generated evidence into human listening approval.

## [Unreleased]

No unreleased changes.

## [0.2.0] - 2026-08-30

`v0.2.0` is the first published installable release of the local,
artifact-first Agent Listening CLI.

### Added

- The `agent-listening-cli` Python distribution and stable `agent-listening`
  executable.
- `solo`, `stem`, and `full_mix` analysis modes with explicit cost and routing
  semantics.
- Compact Music IR 0.2, time-aligned JAMS evidence, preserved raw extractor
  output, and optional stem, note-event, and MIDI artifacts.
- Receipt-first output with absolute artifact paths, capability statuses,
  machine validation, and progressive-disclosure guidance.
- Essentia and all-in-one acoustic/structural evidence, Demucs `htdemucs_6s`
  separation for full mixes, and Basic Pitch note evidence for solo and
  non-drum sources.
- `agent-listening --version` and mode-specific `doctor --json` checks that do
  not load model weights.
- English and Simplified Chinese integration documentation, a thin Agent
  Skill, an MIT project license, and third-party provenance in `CREDITS.md`.

### Changed

- The supported integration seam is the installed CLI. A downstream project
  exposes only the Skill (project scope or intentionally shared user scope) and
  keeps generated artifacts in its own output directory; no MCP server or
  source-tree copy is required.
- The release is pinned to CPython 3.11 because Basic Pitch 0.4.0 has no
  compatible TensorFlow macOS wheel for CPython 3.13.
- The reviewed Skill runtime contract is pinned separately to commit
  `4dfa5177b7ecd21dd8cbe5860f1ae37fb8f987c2`; the immutable release tag
  predates that Skill-only documentation revision.

### Verification boundary

- The repository release checks cover locked dependency synchronization, the
  unittest suite, bytecode compilation, CLI help, package building, schema
  validation, and an installed-wheel smoke outside the checkout.
- CLI success means execution and schema validation completed. Automatic notes,
  key, sections, material events, and source separation remain machine
  candidates until a person listens and reviews the timestamps.
- The release does not publish to PyPI and does not render GUI, waveform,
  spectrogram, HTML, or PDF reports. Numeric waveform and spectral evidence is
  retained in artifacts for later inspection.

### Provenance

Direct runtime dependencies and design references are listed with their own
licenses and notices in [`CREDITS.md`](CREDITS.md). Agent Listening CLI does not
copy upstream source trees or relicense dependency code, model weights, or
input recordings.

[Unreleased]: https://github.com/Bayern99/Agent-Listening-CLI/compare/v0.2.0...main
[0.2.0]: https://github.com/Bayern99/Agent-Listening-CLI/releases/tag/v0.2.0
