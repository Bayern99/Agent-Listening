---
name: agent-listening
description: Use when an agent needs to analyze finished audio into compact Music IR, JAMS timing evidence, or optional stem/note artifacts with the local CLI.
---

# Agent Listening

The distribution is `agent-listening-cli`; the stable executable and Skill name
are both `agent-listening`. For v0.2.0, install the CLI from the pinned GitHub
Release tag; the Skill is installed separately at project or user scope.

The v0.2.0 environment requires CPython 3.11. Basic Pitch 0.4.0 does not have
a compatible TensorFlow macOS wheel for CPython 3.13, so always select the
3.11 interpreter explicitly.

Use the installed CLI as the only integration surface:

```bash
uv tool install --python 3.11 "git+https://github.com/Bayern99/Agent-Listening-CLI.git@v0.2.0"
agent-listening --version
agent-listening doctor --analysis-mode solo --json
```

Then run an analysis:

```bash
agent-listening analyze "/absolute/path/to/audio.wav" \
  --analysis-mode solo \
  --output-dir "/absolute/path/to/job-output" \
  --json
```

Choose the mode from the actual input:

- `solo`: one isolated vocal/instrument file; runs Essentia pitch and Basic
  Pitch notes/MIDI in addition to acoustic evidence.
- `stem`: a caller-provided stem; same analyzers as `solo`, with the caller's
  source identity.
- `full_mix`: a finished mix; runs all-in-one and Demucs `htdemucs_6s`, then
  per-stem activity/pitch/notes. Do not run Basic Pitch on `drums`.

The Skill is deliberately thin. Do not read the repository source, raw JSON,
or all frame arrays into the agent context before running the command. Do not
start a server, call an MCP endpoint, render a GUI, or invent a second adapter.

Read the machine-readable receipt first. It contains absolute artifact paths,
capability statuses, validation state, and the progressive-disclosure order:

1. receipt;
2. `music-ir/<track>.music-ir.json` for ordinary reasoning;
3. `jams/<track>.analysis.jams` for timing, candidates, frame vectors, and
   material-event timestamps;
4. `symbols/` or `stems/` only when the receipt says those capabilities are
   available;
5. `raw/` only for provenance or diagnosis.

Open a timestamp in an external player or DAW when a person needs to audition
the corresponding passage. Numeric waveform/spectrum evidence is retained in
JAMS/raw, but this tool does not produce plots or interactive pages.

Execution success means machine extraction, artifact persistence, and schema
validation completed. It does not mean a human has confirmed sections, key,
source separation, or automatic transcription. Machine note events are not
score ground truth, and Basic Pitch amplitude is never loudness.

`doctor` is a preflight check only: it verifies Python, package metadata,
module discovery, packaged resources, and output writability. It does not load
model weights, run audio inference, or perform human listening.

## Installation scope

Install this Skill as a symlink so the checkout remains the one authority.
For one audio project:

```bash
mkdir -p "/absolute/path/to/audio-project/.agents/skills"
ln -s "/absolute/path/to/Agent Listening/.agents/skills/agent-listening" \
  "/absolute/path/to/audio-project/.agents/skills/agent-listening"
```

When the host supports `gh skill`, a pinned project install is preferable:

```bash
gh skill install Bayern99/Agent-Listening-CLI \
  .agents/skills/agent-listening/SKILL.md \
  --allow-hidden-dirs --agent codex --scope project --pin v0.2.0
```

For several local projects, use the global discovery location instead:

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "/absolute/path/to/Agent Listening/.agents/skills/agent-listening" \
  "$HOME/.agents/skills/agent-listening"
```

For a shared user-level Skill, use `--scope user` or the equivalent symlink
under `$HOME/.agents/skills`. Do not copy the Agent Listening source tree into
an audio project. The checkout wrapper `bin/agent-listening` is contributor
convenience only; downstream agents should call the installed console script.
Inspect existing destinations before replacing them. Project-local scope is the
default recommendation; user scope is only for deliberate multi-project
discovery.
