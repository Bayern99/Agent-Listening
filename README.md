# Agent Listening

Agent Listening converts finished audio into two complementary artifacts:

- `jams/<track>.analysis.jams`: JAMS-structured evidence and timing annotations.
- `music-ir/<track>.music-ir.json`: compact Music IR for downstream reasoning.

The fixture-driven offline compiler is verified. Native audio analysis additionally requires the pinned all-in-one and Essentia runtimes and their model assets; do not claim a track has been analyzed until those extractors complete successfully.

## Setup

Python 3.11 and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --locked
```

## Agent integration: CLI first, Skill only where needed

The supported integration surface is the local CLI. The Skill is a thin,
automatic instruction layer for agents; it does not replace the CLI and it
does not load this whole repository into an agent's context. There is no MCP
server in V0.1 because a local command already covers the single-machine,
batch-analysis use case without a server process or extra context boundary.

Choose the installation scope deliberately:

| Situation | Put the Skill here | Recommendation |
| --- | --- | --- |
| One audio project needs analysis | `<audio-project>/.agents/skills/agent-listening` | **Recommended.** Only agents working in that project discover it. |
| Several local projects need analysis | `$HOME/.agents/skills/agent-listening` | Optional global convenience. It is still a thin trigger, not a context bundle. |

You do not need to copy the Agent Listening source tree into the audio
project. A symlink keeps one versioned implementation as the authority; use a
real copy only when that project must be portable without this checkout.

### Project-local Skill (recommended for one audio project)

Run this once, replacing the two paths:

```bash
REPO="/path/to/Agent Listening"
AUDIO_PROJECT="/path/to/my-audio-project"
mkdir -p "$AUDIO_PROJECT/.agents/skills"
ln -s "$REPO/.agents/skills/agent-listening" \
  "$AUDIO_PROJECT/.agents/skills/agent-listening"
```

The CLI can be called through the repository wrapper, so no global command
installation is required:

```bash
"$REPO/bin/agent-listening" analyze \
  "/absolute/path/to/render.wav" \
  --output-dir "/absolute/path/to/job-output" --json
```

### Global CLI and Skill (when several projects need them)

```bash
REPO="/path/to/Agent Listening"
mkdir -p "$HOME/.local/bin" "$HOME/.agents/skills"
[ -e "$HOME/.local/bin/agent-listening" ] || \
  ln -s "$REPO/bin/agent-listening" "$HOME/.local/bin/agent-listening"
[ -e "$HOME/.agents/skills/agent-listening" ] || \
  ln -s "$REPO/.agents/skills/agent-listening" \
    "$HOME/.agents/skills/agent-listening"
```

The two links are independent: install only the CLI if agents will call it
explicitly, or install the Skill as well when automatic discovery is useful.
Inspect an existing destination before replacing it; the commands above leave
an existing path untouched.

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

The command is safe to call from another working directory. With `--json`,
success is one machine-readable receipt on stdout; failure is one error receipt
on stderr and exit code `1`. A success receipt contains absolute paths and
validation state, for example:

```json
{
  "receipt_version": "agent-listening/0.1",
  "status": "success",
  "command": "analyze",
  "track_id": "example",
  "artifacts": {
    "music_ir": "/tmp/job-output/music-ir/example.music-ir.json",
    "jams": "/tmp/job-output/jams/example.analysis.jams",
    "raw_dir": "/tmp/job-output/raw/example"
  },
  "validation": {
    "music_ir": "passed",
    "jams_base_schema": "passed",
    "jams_namespace_strict": "not_claimed",
    "human_listening": "pending"
  }
}
```

The output directory has this shape:

```text
job-output/
├── music-ir/<track>.music-ir.json
├── jams/<track>.analysis.jams
└── raw/<track>/                   # analyze only
    ├── allin1.json
    └── essentia.json
```

Read the receipt first, then `music-ir.json` for ordinary reasoning. Open JAMS
only for timing, candidates, or frame evidence; open raw extractor JSON only
for provenance or diagnosis. This receipt-first order keeps every downstream
agent's context small and makes the evidence boundary explicit.

`analyze` runs the pinned native all-in-one and Essentia extractors. The
offline `build-ir` command instead fuses already captured extractor JSON, so it
is the cheap path for tests, fixtures, and environments without native model
assets. The direct developer entrypoint is always available as
`uv run python -m src.cli`.

Common flags are `--output-dir`, `--profile`, `--analysis-mode`
(`full_mix`, `stem`, or `solo`), `--json`, and the explicit replacement flag
`--overwrite`. Run `agent-listening <command> --help` for the complete current
surface.

Existing raw, JAMS, or Music IR artifacts are not overwritten by default. Pass `--overwrite` only when replacing that evidence is intentional.

Symbolic transcription is not implemented in V0.1. The CLI does not claim MIDI or note-event artifacts.

## Credits, provenance, and license boundary

See [CREDITS.md](CREDITS.md) for the direct runtime dependencies, the JAMS and
JSON Schema standards used by this project, design references, and links to
the upstream license notices. The repository does not vendor upstream source
files; its adapters, fusion, schema, CLI, receipt, and Skill are project code.

The repository currently has no top-level `LICENSE` file. Third-party notices
do not grant a license to redistribute or relicense Agent Listening itself;
choose and add a project license before publishing a distributable release.

## Verify

```bash
uv run python -m unittest discover -v
```

Generated Music IR is checked with Draft 2020-12 JSON Schema plus temporal invariants. JAMS is constructed by the official library and checked against its base schema. Namespace-strict JAMS validation is not claimed because the extractors do not provide numeric confidence for every observation; unknown confidence remains `null` rather than being fabricated.
