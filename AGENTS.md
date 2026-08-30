# AGENTS.md

Welcome to **Agent Listening CLI** (Audio-to-Music-IR). The project/distribution
name is `agent-listening-cli`; the stable executable and Skill name remain
`agent-listening`. It converts finished mixed audio into structured,
machine-readable, and verified intermediate representations (Music IR) for
consumption by downstream multimodal music agents and sound synthesis systems.

---

## Agent Skills

### Issue tracker

Issues and tracer-bullet specs are tracked via GitHub Issues (`gh`). See `docs/agents/issue-tracker.md`.

### Triage Labels

Default canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain Docs

Single-context layout at repo root (`CONTEXT.md` and `docs/adr/`). See `docs/agents/domain.md`.

---

## Core Engineering Principles

1. **First Principles over Analogies**:
   - Audio is a continuous 1D physical waveform; sound synthesis is deterministic symbolic execution.
   - Separate **Observation (Raw)** from **Evidence (Normalized)** from **Inference (IR)** from **Execution (Code)**.
   - Do not let LLMs perform raw acoustic perception. Use specialized, deterministic MIR extractors (`allin1`, `Essentia`) for physical/structural facts, and use LLMs strictly for reasoning, semantic tagging, and code synthesis.

2. **Deep Modules & Clean Seams** (Matt Pocock / John Ousterhout):
   - **Small Interface, Deep Implementation**: The analysis surface should be minimal (`analyze(audio_path, profile) -> MusicIR`), while hiding the complexity of sub-process invocation, JSON normalization, confidence scoring, and format bridging.
   - **Clean Adapters**: Treat MIR extractors as swappable adapters behind private seams. Never leak raw tool-specific output formats directly into consumer code.
   - **Pure Transformations**: Make data fusion functions pure and deterministic (`merge_evidence(raw_allin1, raw_essentia) -> (JAMS, MusicIR)`).

3. **Dual-Artifact Preservation**:
   - **`analysis.jams`**: JAMS-structured timing evidence, multi-candidates, and tool provenance. Writes are no-clobber by default; explicit overwrite is a destructive replacement.
   - **`music-ir.json`**: Compact, domain-aligned representation tailored for downstream agent reasoning and sound synthesis parameterization.

4. **Test-Driven Development (TDD)**:
   - Every extractor parser and schema validator must have unit tests against fixture files (e.g. `tests/fixtures/`).
   - Red-Green-Refactor slices: test schema constraints and edge cases before writing mapping logic.

5. **Installed CLI as the Integration Seam**:
   - Downstream agents call the `agent-listening` console script installed from a pinned GitHub Release tag.
   - `bin/agent-listening` is a contributor checkout wrapper, not the downstream installation contract.
   - `--version`, mode-specific `doctor --json`, and installed-command smoke must remain lightweight and must not load models before analysis.

---

## Workspace Structure

```text
.
├── AGENTS.md                         # This file (Agent entry point & instructions)
├── README.md                         # Setup, commands, and current capability boundary
├── LICENSE / CREDITS.md               # Project license and third-party notices
├── pyproject.toml / uv.lock          # Python 3.11 dependency contract
├── MANIFEST.in                       # sdist resource inclusion
├── CONTEXT.md                        # Ubiquitous domain glossary (no implementation noise)
├── docs/
│   ├── adr/                          # Architectural Decision Records
│   │   ├── 0001-allin1-essentia-dual-engine.md
│   │   ├── 0002-dual-artifact-jams-and-music-ir.md
│   │   └── 0003-static-cli-glue-pipeline.md
│   └── agents/                       # Skill configurations
│       ├── domain.md
│       ├── issue-tracker.md
│       └── triage-labels.md
├── Research/                         # Research artifacts, benchmark findings, candidate JSONs
├── profiles/                         # Fixed analysis profiles (e.g. essentia_v0_1.yaml)
├── schemas/                          # JSON Schemas (e.g. music-ir-v0.1.schema.json)
├── source/                           # Local input audio files (.wav, .flac) - gitignored
├── raw/                              # Raw extractor outputs (evidence archive)
├── jams/                             # JAMS serialized evidence
├── music-ir/                         # Final generated Music-IR JSON files
└── .scratch/                         # Active feature specs, maps, and issues
```

---

## Agent Flow & Skills Protocol

When developing in this repo, follow the **Matt Pocock Engineering Flow**:
1. **Explore & Align**: Read `CONTEXT.md` and `docs/adr/` before touching code.
2. **Interactive Clarification**: Use `/grill-with-docs` to sharpen ideas and record decisions.
3. **Specification & Task Breakdown**: Use `/to-spec` and `/to-tickets` into `.scratch/<feature>/issues/`.
4. **Execution**: Use `/implement` driving `/tdd` for each ticket, running `/code-review` before finishing.
