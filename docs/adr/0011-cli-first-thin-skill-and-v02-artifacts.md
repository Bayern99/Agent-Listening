# 0011. CLI-First Thin Skill and Music IR 0.2 Artifacts

Agent Listening exposes one supported integration boundary:
`agent-listening analyze AUDIO --analysis-mode MODE --output-dir OUTPUT --json`.
The installed `agent-listening` console script is the downstream authority;
`bin/agent-listening` remains a checkout convenience. A project-local or user
scope Skill makes the command discoverable to an Agent host. The Skill only
selects a mode, optionally runs the lightweight `doctor`, executes the command,
reads the receipt, and progressively opens artifacts. It does not copy the
repository, start an MCP/Web service, or inject raw frame arrays into an agent
context.

The distribution will be installed from a pinned GitHub Release tag for
v0.2.0 once that release is created.
PyPI, standalone binaries, OpenCLI, CLI-Anything, CLI-Hub, and a project-owned
plugin registry are outside this release.

Music IR 0.2 adds explicit capability states, material-change candidates,
continuous pitch, source/stem summaries, symbolic artifact references, and
extractor-run provenance. Full frame vectors and machine transcription remain
in JAMS/raw/symbol artifacts. Optional artifacts are omitted on failure and
existing output is no-clobber unless `--overwrite` is supplied.
