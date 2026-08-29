---
name: agent-listening
description: Use when an agent needs to analyze finished audio into compact Music IR, JAMS timing evidence, or optional stem/note artifacts with the local CLI.
---

# Agent Listening

The project/lock metadata is `agent-listening-cli`; the stable executable and
Skill name are both `agent-listening`. This checkout is not a published PyPI
package; call the wrapper or a PATH symlink.

Use the local CLI as the only integration surface:

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

## Installation scope

Install this Skill as a symlink so the checkout remains the one authority.
For one audio project:

```bash
mkdir -p "/absolute/path/to/audio-project/.agents/skills"
ln -s "/absolute/path/to/Agent Listening/.agents/skills/agent-listening" \
  "/absolute/path/to/audio-project/.agents/skills/agent-listening"
```

For several local projects, use the global discovery location instead:

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "/absolute/path/to/Agent Listening/.agents/skills/agent-listening" \
  "$HOME/.agents/skills/agent-listening"
```

Do not copy the Agent Listening source tree into an audio project. The CLI
wrapper can be called directly from the checkout, or exposed separately as a
`PATH` symlink to `bin/agent-listening`. Inspect existing destinations before
replacing them. Project-local scope is the default recommendation; global
scope is only for deliberate multi-project discovery.
