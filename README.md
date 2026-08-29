# Agent Listening CLI

[简体中文](README.zh-CN.md)

Agent Listening CLI is a local, deterministic, artifact-first audio analysis
tool. It turns a finished recording into a compact Music IR for downstream
agents, a time-aligned JAMS evidence archive, and preserved raw extractor
outputs. It is designed for an agent to call without filling its context with
source code or large frame arrays.

The names are intentionally split:

| Thing | Stable name | Meaning |
| --- | --- | --- |
| Project/lock metadata | `agent-listening-cli` | The name in `pyproject.toml` and `uv.lock`; no PyPI publication is implied. |
| Executable | `agent-listening` | The supported command-line interface. |
| Agent Skill | `agent-listening` | The thin instruction folder under `.agents/skills/`. |

The checkout can therefore be renamed or symlinked without breaking existing
commands. The supported integration surface is the CLI; the Skill is a small
discovery and progressive-disclosure layer around that CLI. There is no MCP
server to configure.

## Product boundary

The pipeline is deliberately small and explicit:

- local execution; no cloud service, account, or local web server;
- deterministic MIR extractors for acoustic and structural observations;
- raw observations, normalized evidence, and compact inference kept separate;
- atomic, no-clobber artifact writes by default;
- a machine-readable receipt before any deeper artifact is opened;
- timestamps that let a person audition a claim in an external player or DAW;
- no claim that automatic notes, key, sections, or source separation are human
  listening truth.

The output is useful to another agent because ordinary reasoning needs only a
small JSON document. Complete frame vectors, pitch contours, note events, and
extractor payloads remain available when a question actually needs them.

## Architecture

```text
audio file
    │
    ▼
bin/agent-listening  ── locked uv environment ──►  src.cli
                                                     │
                                                     ▼
                                             src.core orchestrator
                                                     │
                 ┌───────────────────────────────────┼────────────────────┐
                 ▼                                   ▼                    ▼
          Essentia adapter                    all-in-one adapter      Demucs adapter
          acoustic/frame/pitch                rhythm/sections         full_mix stems
                 │                                   │                    │
                 └─────────────── raw extractor evidence ────────────────┘
                                                     │
                                                     ▼
                                      pure evidence fusion / validation
                                                     │
                       ┌────────────────────────────┼─────────────────────┐
                       ▼                            ▼                     ▼
                 Music IR 0.2                    JAMS                raw/symbol/stem files
                       └────────────────────────────┬─────────────────────┘
                                                    ▼
                                                JSON receipt
                                                    │
                                                    ▼
                                     thin Skill → downstream music agent
```

The implementation follows four layers:

| Layer | What it contains | Where to look |
| --- | --- | --- |
| Observation | Tool-native frame arrays and model output | `src/adapters/`, `raw/` |
| Evidence | Time grids, provenance, confidence, normalized events | `src/fusion/`, JAMS |
| Inference | Compact summaries and capability statuses | `schemas/`, Music IR |
| Execution | CLI invocation and agent handoff | `bin/`, `src/cli.py`, Skill |

The important seam is `src.core.analyze(audio_path, profile, ...)`. Adapters
can be replaced behind that seam; downstream callers do not consume an
Essentia-specific or Basic-Pitch-specific JSON shape.

## Analysis modes

Choose the mode from the input you actually have:

| Mode | Use it for | Runs | Does not run |
| --- | --- | --- | --- |
| `solo` | One humming, vocal, or instrument render | Essentia acoustic/frame/material evidence, Essentia continuous pitch, Basic Pitch notes and MIDI | all-in-one, Demucs |
| `stem` | A caller-provided stem whose identity is already known | The same acoustic, pitch, and note pipeline as `solo` | all-in-one, Demucs |
| `full_mix` | A finished mix with multiple sources | Full-mix Essentia and all-in-one evidence, material events, Demucs `htdemucs_6s`, then per-stem activity/pitch/notes | Basic Pitch on `drums` |

`solo` is the cheapest useful first run. `full_mix` is materially more
expensive: it can download model weights and analyzes up to six separated
stems (`vocals`, `drums`, `bass`, `guitar`, `piano`, `other`). The first run
may also download all-in-one or Basic Pitch weights. Model download terms are
separate from Python package licenses; see [CREDITS.md](CREDITS.md).

## New-project integration

An audio project does not need a copy of this source tree. Keep one checkout
as the authority and expose only the Skill and/or wrapper that the project
needs.

### 1. Prepare the authority checkout once

From this repository:

```bash
uv sync --locked
```

The wrapper is self-contained and resolves this checkout even when called from
another directory:

```bash
"/absolute/path/to/Agent Listening/bin/agent-listening" --help
```

### 2. Choose Skill scope

Project-local is the default: use it when one audio project should explicitly
own the integration.

```bash
REPO="/absolute/path/to/Agent Listening"
AUDIO_PROJECT="/absolute/path/to/my-audio-project"
mkdir -p "$AUDIO_PROJECT/.agents/skills"
test ! -e "$AUDIO_PROJECT/.agents/skills/agent-listening" || {
  echo "destination already exists; inspect it before replacing" >&2
  exit 1
}
ln -s "$REPO/.agents/skills/agent-listening" \
  "$AUDIO_PROJECT/.agents/skills/agent-listening"
```

Global discovery is appropriate when several local projects should all use the
same checkout and the same Skill version:

```bash
REPO="/absolute/path/to/Agent Listening"
mkdir -p "$HOME/.agents/skills"
test ! -e "$HOME/.agents/skills/agent-listening" || {
  echo "destination already exists; inspect it before replacing" >&2
  exit 1
}
ln -s "$REPO/.agents/skills/agent-listening" \
  "$HOME/.agents/skills/agent-listening"
```

Use project-local scope when reproducibility and explicit ownership matter;
use global scope only when the same local authority is intentionally shared.
Do not copy Agent Listening into every project. A real copy is a conscious
portability trade-off and will otherwise drift from the authority checkout.

### 3. Expose the CLI when convenient

The Skill does not replace the executable. Agents and scripts can call the
wrapper directly, or you can put one separate symlink on `PATH`:

```bash
REPO="/absolute/path/to/Agent Listening"
mkdir -p "$HOME/.local/bin"
test ! -e "$HOME/.local/bin/agent-listening" || {
  echo "destination already exists; inspect it before replacing" >&2
  exit 1
}
ln -s "$REPO/bin/agent-listening" "$HOME/.local/bin/agent-listening"
```

This checkout is the supported installation form today. It is not a claim
that a PyPI package or a system-wide binary has been published.

### 4. Run an analysis into the project output area

Keep generated artifacts in a project-owned analysis directory, not inside the
Agent Listening source checkout:

```bash
agent-listening analyze \
  "/absolute/path/to/my-audio-project/renders/humming.wav" \
  --analysis-mode solo \
  --output-dir "/absolute/path/to/my-audio-project/analysis/humming" \
  --json
```

For a caller-provided stem, change only the mode and source path:

```bash
agent-listening analyze \
  "/absolute/path/to/my-audio-project/stems/woodwind.wav" \
  --analysis-mode stem \
  --output-dir "/absolute/path/to/my-audio-project/analysis/woodwind" \
  --json
```

Use `full_mix` only for a finished mix when source separation is worth the
extra model load and runtime:

```bash
agent-listening analyze \
  "/absolute/path/to/my-audio-project/renders/final-mix.wav" \
  --analysis-mode full_mix \
  --output-dir "/absolute/path/to/my-audio-project/analysis/final-mix" \
  --json
```

The only thing a project needs to add for Skill discovery is therefore a
symlink like this:

```text
my-audio-project/
└── .agents/
    └── skills/
        └── agent-listening -> /absolute/path/to/Agent Listening/.agents/skills/agent-listening
```

### 5. Let an agent read progressively

The Skill must not preload source code or raw frame arrays. The intended read
order is:

1. receipt printed by `--json`;
2. `music-ir/<track>.music-ir.json` for ordinary reasoning;
3. `jams/<track>.analysis.jams` for timestamps, candidates, curves, and
   material events;
4. `symbols/` or `stems/` only when the receipt says the capability is
   available;
5. `raw/` only for provenance or diagnosis.

When a person needs to check a claim, use the event timestamp in an external
player or DAW. The tool retains numeric waveform/spectrum evidence but does
not render a GUI, waveform page, or spectrogram image.

## CLI reference

The official interface is:

```text
agent-listening analyze AUDIO \
  --analysis-mode full_mix|stem|solo \
  --output-dir OUTPUT \
  --json
```

| Option | Purpose |
| --- | --- |
| `analyze AUDIO` | Run native/model-backed analysis on one audio file (`.wav` or `.flac`). |
| `--analysis-mode` | Select `solo`, `stem`, or `full_mix`; default is `full_mix`. |
| `--output-dir`, `-o` | Base directory for all artifacts; default is the current directory. |
| `--profile`, `-p` | Essentia profile name; default is `essentia_v0_1`. |
| `--json` | Print one machine-readable receipt to stdout; library progress goes to stderr. |
| `--overwrite` | Explicitly replace existing artifacts for this track. Omit it for no-clobber behavior. |

`build-ir` is a developer-only offline compiler for already captured extractor
JSON. It is useful for fixtures and debugging, not the normal agent boundary:

```bash
uv run --locked python -m src.cli build-ir \
  --allin1 tests/fixtures/allin1_sample.json \
  --essentia tests/fixtures/essentia_sample.json \
  --track-id example \
  --output-dir /tmp/agent-listening-output \
  --json
```

An error with `--json` exits non-zero and emits an error receipt on stderr.
Do not treat a partially existing output directory as a successful analysis.

## Artifact contract

Each successful run writes atomically beneath the requested output directory:

```text
output/
├── music-ir/<track>.music-ir.json       # compact Music IR 0.2
├── jams/<track>.analysis.jams            # time-aligned evidence
├── raw/<track>/
│   ├── essentia.json
│   ├── allin1.json                       # full_mix only
│   ├── demucs-manifest.json              # full_mix only
│   ├── pitch.json                        # solo/stem when pitch succeeds
│   ├── stems/<source>.essentia.json      # full_mix when available
│   └── basic-pitch/<source>.notes.json   # when note extraction succeeds
├── stems/<track>/*.wav                   # full_mix, only existing stems
└── symbols/<track>/
    ├── <source>.notes.json               # full note evidence
    └── <source>.mid                      # MIDI, when produced
```

Optional artifacts are omitted when an extractor fails or detects nothing; no
empty placeholder is created. The receipt contains absolute paths, capability
statuses, machine validation results, and the same progressive-disclosure
order. A compact IR contains summaries such as loudness, spectral descriptors,
energy bands, tempo candidates, tuning/key evidence, pitch range, note density,
source summaries, and material-change candidates. Complete frame arrays stay
in JAMS/raw instead of entering every downstream prompt.

Important evidence rules:

- section acoustic summaries use a legal local time grid; if none exists, the
  value is `null`, never a copied whole-track value;
- material events are machine candidates with before/after windows, not human
  labels;
- automatic note events are machine transcription, not score ground truth;
- Basic Pitch amplitude/velocity is not loudness;
- weak key, beat, or section candidates remain available as raw evidence but
  are not upgraded to a deterministic fact;
- `review.human_checked` stays pending until a person listens.

## Verification

### Verify the checkout after code or dependency changes

Run the smallest complete local gate:

```bash
uv sync --locked
uv run --locked python -m unittest discover -v
uv run --locked python -m compileall -q src tests
bin/agent-listening --help
bin/agent-listening analyze --help
git diff --check
```

The test suite covers adapter parsing, native timestamp grids, local section
aggregation, material-event timing, mode routing, Basic Pitch preservation,
Demucs manifests, schema compatibility, receipt/no-clobber behavior, and
atomic artifacts. Music IR uses Draft 2020-12 JSON Schema; JAMS uses the
official base schema. A strict confidence claim is not made where an
extractor did not provide numeric confidence for every observation.

To check both schema files and the tracked demo artifact without a separate
validation package:

```bash
uv run --locked python - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

for schema_path in Path("schemas").glob("music-ir-v*.schema.json"):
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)

demo = json.loads(Path("music-ir/demo-track-001.music-ir.json").read_text())
version = demo["schema_version"].rsplit("/", 1)[-1]
schema = json.loads(Path(f"schemas/music-ir-v{version}.schema.json").read_text())
Draft202012Validator(schema).validate(demo)
print(f"schema checks passed ({demo['schema_version']})")
PY
```

### Verify one real run

Capture the receipt and inspect it before opening anything else:

```bash
RECEIPT="$(agent-listening analyze \
  "/absolute/path/to/audio.wav" \
  --analysis-mode solo \
  --output-dir "/absolute/path/to/analysis/audio" \
  --json)"
printf '%s\n' "$RECEIPT"
```

Confirm `status == "success"`, parse the absolute paths under `artifacts`,
and check `validation.music_ir == "passed"` and
`validation.jams_base_schema == "passed"`. Then read the compact IR. Open
JAMS or raw files only for the specific question being answered. A successful
receipt proves execution, persistence, and machine validation; it does not
prove perceptual correctness.

For `full_mix`, additionally check the receipt capability status and the
Demucs manifest before relying on any stem claim. A failed optional extractor
must remain visibly `failed` or `not_detected`; it must not erase successful
full-mix acoustic evidence.

## Credits, licensing, and release status

Project-specific code is MIT-licensed; see [LICENSE](LICENSE). Runtime
dependencies and design references retain their own terms and are listed with
links in [CREDITS.md](CREDITS.md). In particular, Essentia is AGPL-licensed,
and model weights from all-in-one, Demucs, and Basic Pitch have release terms
that are separate from their Python package code. We do not copy upstream
source trees into this repository.

The references that shaped the boundary are credited separately from runtime
dependencies: soundscape-analyse informed material-change review ideas,
Ocean Listen informed separation-first/per-stem thinking, and Mu2Mi informed
the compact representation comparison. audioFlux and music21 were evaluated
but not added. Their names and links are not claims of code reuse.

The MIT file makes the project terms explicit; it does not mean that a model,
input recording, or transitive package can be redistributed under MIT. This
checkout is technically implemented and locally tested, but no commit, push,
package publication, or public release is implied by the presence of the
license file.

## Deliberate non-goals

This version does not include a GUI, desktop app, Web app, local Web server,
MCP server, interactive waveform/spectrogram page, or default PNG/SVG/HTML/PDF
report. It does not add Streamlit, React, Next.js, Plotly, Altair, Matplotlib,
PANNs, Parselmouth, Whisper, FunASR, audioFlux, music21, MOSS, or a separate
audio language model. `all-in-one-infer` currently loads Matplotlib
transitively, but this project does not directly invoke its plotting helpers.

Waveform and spectrum values remain available as numeric evidence. A future
human-audition workflow can add a separately justified render command when a
real need exists; this version intentionally does not reserve an empty GUI or
plotting interface.
