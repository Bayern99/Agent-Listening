# Agent Listening

Agent Listening converts finished audio into two complementary artifacts:

- `jams/<track>.analysis.jams`: JAMS-structured evidence and timing annotations.
- `music-ir/<track>.music-ir.json`: compact Music IR for downstream reasoning.

The fixture-driven offline compiler is verified. Native audio analysis additionally requires the pinned all-in-one and Essentia runtimes and their model assets; do not claim a track has been analyzed until those extractors complete successfully.

## Setup

Python 3.11 and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync
```

## Local agent integration

From the repository root, expose the versioned command and Skill through the
local agent paths (create each link only when its target is absent):

```bash
ln -s "$(pwd)/bin/agent-listening" "$HOME/.local/bin/agent-listening"
ln -s "$(pwd)/.agents/skills/agent-listening" "$HOME/.agents/skills/agent-listening"
```

## Commands

Build artifacts from captured extractor JSON:

```bash
uv run python -m src.cli build-ir \
  --allin1 tests/fixtures/allin1_sample.json \
  --essentia tests/fixtures/essentia_sample.json \
  --track-id example \
  --output-dir /tmp/agent-listening-output
```

Analyze audio with the native extractors:

```bash
agent-listening analyze source/example.wav --output-dir /tmp/agent-listening-output --json
```

The command is safe to call from another working directory. It returns a compact JSON receipt with absolute paths to the generated Music IR, JAMS, and raw evidence directory. Read Music IR by default; open JAMS or raw extractor JSON only when the task needs detailed timing or provenance evidence.

For repository development, the equivalent direct entrypoint is `uv run python -m src.cli`.

Existing raw, JAMS, or Music IR artifacts are not overwritten by default. Pass `--overwrite` only when replacing that evidence is intentional.

Symbolic transcription is not implemented in V0.1. The CLI does not claim MIDI or note-event artifacts.

## Verify

```bash
uv run python -m unittest discover -v
```

Generated Music IR is checked with Draft 2020-12 JSON Schema plus temporal invariants. JAMS is constructed by the official library and checked against its base schema. Namespace-strict JAMS validation is not claimed because the extractors do not provide numeric confidence for every observation; unknown confidence remains `null` rather than being fabricated.
