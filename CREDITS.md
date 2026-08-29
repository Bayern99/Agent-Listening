# Credits and third-party notices

Agent Listening is a small project-specific adapter and evidence-fusion layer.
It invokes the dependencies below at runtime; it does not vendor their source
files. Versions are pinned or constrained in [`pyproject.toml`](pyproject.toml)
and resolved in [`uv.lock`](uv.lock).

## Direct runtime dependencies

| Component | Version | Use in this repository | Upstream and notice |
| --- | --- | --- | --- |
| `all-in-one-infer` | `3.1.0` | Structure, beat, and downbeat observations | [openmirlab/all-in-one-infer](https://github.com/openmirlab/all-in-one-infer) · MIT. The maintained package also links the [original All-In-One project](https://github.com/mir-aidj/all-in-one). |
| Essentia | `2.1b6.dev1389` | Acoustic, rhythm, tonal, and descriptor observations | [MTG/essentia](https://github.com/MTG/essentia) · AGPL-3.0. Read the upstream [licensing notice](https://github.com/MTG/essentia/blob/master/Essentia%20Licensing.txt) before redistribution or hosted use. |
| `jams` | `0.3.5` | JAMS serialization and base-schema validation | [marl/jams](https://github.com/marl/jams) · ISC. The format is described in the [JAMS paper](https://archives.ismir.net/ismir2014/paper/000174.pdf). |
| `jsonschema` | `>=4.23,<5` (lock resolves `4.26.0`) | Draft 2020-12 Music-IR validation | [python-jsonschema/jsonschema](https://github.com/python-jsonschema/jsonschema) · MIT. |

The table covers direct dependencies only. The full transitive dependency set
is the lockfile's responsibility; every transitive package remains under its
own license. Model weights, caches, and audio inputs can carry separate terms
from the code packages that download or read them.

## Development and research references (not runtime dependencies)

These projects were inspected while choosing the V0.1 shape. They are credited
as references only: their source is not copied into this repository and they
are not installed by `pyproject.toml`.

| Reference | What was borrowed or deliberately left out |
| --- | --- |
| [wx9Songs/MOSS-Music-Data-Pipeline](https://github.com/wx9Songs/MOSS-Music-Data-Pipeline) | Multi-branch perception followed by an explicit merge step informed the evidence-fusion boundary; its large training-data pipeline is not a V0.1 dependency. |
| [spotify/basic-pitch](https://github.com/spotify/basic-pitch) and [magenta/mt3](https://github.com/magenta/mt3) | Considered for symbolic transcription; MIDI/note artifacts remain intentionally out of scope in V0.1. |
| [ASLP-lab/SongFormer](https://github.com/ASLP-lab/SongFormer) | Considered for long-form section detection; current structure evidence comes from the pinned all-in-one runtime. |
| [yizhilll/MERT](https://github.com/yizhilll/MERT), [Tencent-AILab/MuQ](https://github.com/tencent-ailab/muq), and [AMAAI-Lab/MERIT](https://github.com/AMAAI-Lab/MERIT) | Considered as continuous music representations; embeddings are not part of the current artifact contract. |
| [NVIDIA/audio-flamingo](https://github.com/NVIDIA/audio-flamingo) and [OpenMOSS/MOSS-Music](https://github.com/OpenMOSS/MOSS-Music) | Considered for semantic audio-language assistance; language-model output is not used as ground truth by this pipeline. |

The project's own research record includes an external research session labelled
“Manus AI” on 2026-08-22 in
[`Research/mcp_result_d8f1dec8-0732-4f31-911c-9ae123971aa9.json`](Research/mcp_result_d8f1dec8-0732-4f31-911c-9ae123971aa9.json).
It informed the candidate comparison above; it is not executable code and is
not presented as authorship of the Agent Listening implementation.

## Standards and design references

- **JAMS** supplies the multi-annotation, time-aligned evidence container. The
  project keeps JAMS as the evidence archive and derives a smaller
  `music-ir.json` for downstream reasoning; this boundary is recorded in
  [ADR-0002](docs/adr/0002-dual-artifact-jams-and-music-ir.md).
- **JSON Schema Draft 2020-12** supplies the schema vocabulary; the local
  domain schema is [`schemas/music-ir-v0.1.schema.json`](schemas/music-ir-v0.1.schema.json).
- The dual-engine choice and the static CLI shape are local decisions recorded
  in [ADR-0001](docs/adr/0001-allin1-essentia-dual-engine.md) and
  [ADR-0003](docs/adr/0003-static-cli-glue-pipeline.md), informed by the
  upstream tools' documented capabilities.
- Earlier architectural exploration is preserved in the project's
  [`Research/`](Research/) notes. Those notes are references and provenance,
  not copied upstream implementation code and not additional runtime
  dependencies.

## What this project claims

- Upstream tools are credited by name, version, role, and license link above.
- No upstream repository is represented as the author of Agent Listening's
  adapters, fusion rules, schema, CLI, receipt format, or Skill text.
- The receipt distinguishes automatic validation from human listening, and the
  project does not claim namespace-strict JAMS confidence validation when an
  extractor does not provide the required numeric confidence.

This is a provenance record, not legal advice. Before distributing a bundled
application, container, model cache, or hosted service, review the current
license and model terms of every included component.
