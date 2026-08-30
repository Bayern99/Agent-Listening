---
name: agent-listening
description: Analyze rendered or finished audio with the installed agent-listening CLI into compact Music IR, JAMS timing evidence, and optional stem or note artifacts. Use for machine-readable evidence from an audio file; not for audio generation, editing, or live monitoring.
---

# Agent Listening

Use the installed `agent-listening` command as the only integration surface.
Do not import repository internals, invoke the contributor checkout wrapper, or
load source code and frame arrays into the agent context.

## Runtime contract

This Skill targets `agent-listening-cli` v0.2.0 on CPython 3.11. First check the
command and version:

```bash
command -v agent-listening
agent-listening --version
```

If the command is missing, the version is not `agent-listening 0.2.0`, or
`doctor` is unavailable, install the pinned release. Do not reinstall on every
invocation.

```bash
uv tool install --python 3.11 --force \
  "git+https://github.com/Bayern99/Agent-Listening-CLI.git@v0.2.0" &&
hash -r &&
agent-listening --version &&
agent-listening doctor --analysis-mode solo --json
```

If installation, version verification, or `doctor` fails, stop and report the
error. Do not fall through to another same-named executable already on `PATH`.
The binary help is the versioned command contract; run
`agent-listening --help` or `agent-listening <command> --help` instead of
guessing flags.

## Choose the analysis mode

- `solo`: one isolated voice or instrument; runs acoustic evidence, continuous
  pitch, and Basic Pitch notes/MIDI.
- `stem`: an already-isolated source supplied by the caller; runs the same
  pitch/note path as `solo`. The CLI records `analysis_mode=stem` but does not
  accept or infer a richer caller-supplied source role.
- `full_mix`: a finished mix; runs full-mix evidence, all-in-one, Demucs
  `htdemucs_6s`, and per-stem analysis. It is slower, may download model
  weights, and does not run Basic Pitch on `drums`.

Choose from the actual input; do not use `full_mix` merely because it is the CLI
default. Before an expensive first analysis, run `doctor --json` with the same
`solo`, `stem`, or `full_mix` mode you selected.

## Analyze

Use absolute paths, a fresh job output directory, and structured output:

```bash
agent-listening analyze "/absolute/path/to/audio.wav" \
  --analysis-mode solo \
  --output-dir "/absolute/path/to/job-output" \
  --json
```

Existing artifacts are no-clobber by default. On `FileExistsError`, inspect the
existing output or choose a new directory. Use `--overwrite` only when the user
has explicitly authorized replacing that track's existing JAMS, Music IR, raw,
stem, and symbol artifacts.

## Read the result

Require both exit code `0` and `receipt.status == "success"`. On a nonzero exit,
parse the JSON error receipt from stdout and stop. Extractor chatter belongs on
stderr and is not the receipt.

Follow `receipt.next` and open only artifact paths listed by the receipt. Usually
this means compact Music IR first, JAMS for timing or candidates, symbols/stems
when available, and raw evidence only for provenance or diagnosis. Never load
large frame arrays by default.

Interpret capability values literally:

- `available`: evidence exists and may be read;
- `not_applicable`: the mode does not use that capability;
- `not_detected`: the extractor ran but did not publish usable evidence;
- `failed`: that extractor failed; preserve and use other successful evidence.

Execution and schema validation are not human listening approval. Sections,
key, separation, and automatic transcription remain machine evidence until a
person reviews them. Note events are not score ground truth, and Basic Pitch
amplitude is not loudness. Use timestamps in an external player or DAW when
human audition is needed; do not start a GUI, Web server, or MCP service.
