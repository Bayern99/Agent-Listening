# 0011. CLI-First Thin Skill and Music IR 0.2 Artifacts

Agent Listening exposes one supported integration boundary:
`agent-listening analyze AUDIO --analysis-mode MODE --output-dir OUTPUT --json`.
The repository wrapper and a project-local or global symlink make that command
discoverable; the Skill only selects a mode, executes the command, reads the
receipt, and progressively opens artifacts. It does not copy the repository,
start an MCP/Web service, or inject raw frame arrays into an agent context.

Music IR 0.2 adds explicit capability states, material-change candidates,
continuous pitch, source/stem summaries, symbolic artifact references, and
extractor-run provenance. Full frame vectors and machine transcription remain
in JAMS/raw/symbol artifacts. Optional artifacts are omitted on failure and
existing output is no-clobber unless `--overwrite` is supplied.
