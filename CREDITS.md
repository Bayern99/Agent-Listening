# Credits and third-party notices

Agent Listening CLI is project-specific adapter, fusion, schema, CLI, receipt, and
Skill code. It invokes the components below at runtime; it does not copy their
source trees into this repository. Versions are declared in
[`pyproject.toml`](pyproject.toml) and resolved in [`uv.lock`](uv.lock).

The project code is released under the MIT License; see [`LICENSE`](LICENSE).
That project license does not relicense the direct or transitive dependencies,
model weights, or input audio listed below. Each remains subject to its own
notice and usage terms.

## Direct runtime dependencies

| Component | Version | Role here | Upstream and license notice |
| --- | --- | --- | --- |
| `all-in-one-infer` | `3.1.0` | Beat/downbeat and structural candidates in `full_mix` | [source](https://github.com/openmirlab/all-in-one-infer) · [MIT code license](https://github.com/openmirlab/all-in-one-infer/blob/main/LICENSE); see the [original All-In-One project](https://github.com/mir-aidj/all-in-one) and its released model files |
| Essentia | `2.1b6.dev1389` | Global/frame acoustic, spectral, rhythm, tonal, and continuous-pitch evidence | [source](https://github.com/MTG/essentia) · [AGPL-3.0/licensing notice](https://github.com/MTG/essentia/blob/master/Essentia%20Licensing.txt); model-free DSP runtime |
| `demucs-infer` | `4.2.2` | `htdemucs_6s` source separation in `full_mix` | [source](https://github.com/openmirlab/demucs-infer) · [MIT code license](https://github.com/openmirlab/demucs-infer/blob/main/LICENSE); model lineage and weight terms are in the [original Demucs project](https://github.com/facebookresearch/demucs) |
| `basic-pitch` | `0.4.0` | Machine note events and MIDI for solo/stems except drums | [source](https://github.com/spotify/basic-pitch) · [Apache-2.0 code license](https://github.com/spotify/basic-pitch/blob/main/LICENSE); use the upstream model/checkpoint notices for weights |
| `jams` | `0.3.5` | JAMS serialization and base-schema validation | [source](https://github.com/marl/jams) · [ISC code license](https://github.com/marl/jams/blob/main/LICENSE); format paper at [ISMIR 2014](https://archives.ismir.net/ismir2014/paper/000174.pdf) |
| `jsonschema` | `>=4.23,<5` | Draft 2020-12 validation of Music IR | [source](https://github.com/python-jsonschema/jsonschema) · [MIT code license](https://github.com/python-jsonschema/jsonschema/blob/main/COPYING) |
| `setuptools` | `<81` | Compatibility for Basic Pitch's `resampy` import path | [source](https://github.com/pypa/setuptools) · [MIT code license](https://github.com/pypa/setuptools/blob/main/LICENSE); this is a compatibility pin, not an analysis engine |

The table lists direct dependencies only. The lock file contains transitive
packages under their own licenses. Model weights, model caches, and input audio
may carry terms different from the code packages that download or read them;
review the current upstream and weight notices before redistribution or hosted
use.

`all-in-one-infer` currently brings `matplotlib` transitively. Agent Listening
does not directly import it or expose its visualization helpers; removing that
transitive package would require replacing the upstream runtime dependency.

## Design references (not runtime dependencies)

These repositories informed the boundary or the shape of a small feature. No
upstream source is copied, and none is installed by this project:

| Reference | What was used or intentionally excluded |
| --- | --- |
| [LiZhuoming-lab/soundscape-analyse](https://github.com/LiZhuoming-lab/soundscape-analyse) | Material novelty, before/after evidence, and reviewable change-event ideas; no GUI or whole-repository code. |
| [ennisaaaaaaaa-stack/ocean-listen](https://github.com/ennisaaaaaaaa-stack/ocean-listen) | Separation-first and per-stem energy/note pipeline ideas; no GUI, orchestrator, or bundled dependency tree. |
| [FelixNgFender/mu2mi](https://github.com/FelixNgFender/mu2mi) | Product-level comparison around a compact music representation; Web storage, sharing, and cloud-service features are not part of this tool. |
| [jackwener/OpenCLI](https://github.com/jackwener/OpenCLI) | Small `doctor`, structured-envelope, command-discovery, and compact-first ideas; no source or runtime dependency. The upstream project is Apache-2.0. |
| [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) | Interface archaeology, installed-command smoke, real-backend and semantic-artifact verification checklist; no generated harness, source, or runtime dependency. The upstream project is Apache-2.0. |

## Evaluated and not adopted

| Project | Decision |
| --- | --- |
| [libAudioFlux/audioFlux](https://github.com/libAudioFlux/audioFlux) | Not added: the current spectral and time-series evidence is already covered by Essentia. |
| [cuthbertLab/music21](https://github.com/cuthbertLab/music21) | Not added: it consumes symbolic music; it does not create new waveform evidence for this pipeline. |
| [wx9Songs/MOSS-Music-Data-Pipeline](https://github.com/wx9Songs/MOSS-Music-Data-Pipeline) | Evaluated as a larger data/model pipeline, but not a runtime dependency or source template. |

OpenCLI and CLI-Anything are design references only. Agent Listening does not
depend on either project, does not invoke either generator, and does not claim
that their interfaces or implementation are part of this codebase.

## Local standards and implementation boundary

- JAMS supplies the multi-annotation, time-aligned evidence container; the
  compact domain contract is the local `music-ir/0.2` schema.
- The split between raw observation, normalized evidence, compact inference,
  and downstream execution is a local design decision recorded in
  [`docs/adr/`](docs/adr/).
- The Skill is a thin instruction layer. It does not claim authorship of the
  upstream tools and does not silently load their raw data into an agent's
  context.
- Machine note events are not score ground truth; Basic Pitch amplitude is not
  loudness. Automatic validation is distinct from human listening approval.

## License and release status

The project-specific code in this repository is MIT-licensed; the complete
text is in [`LICENSE`](LICENSE). Third-party notices do not grant a license to
redistribute or relicense any dependency or model. Review each upstream code,
model-weight, and input-audio term before redistribution or hosted use.

The [`v0.2.0` release](https://github.com/Bayern99/Agent-Listening-CLI/releases/tag/v0.2.0)
is published through GitHub Release assets and a pinned Git URL; PyPI is
intentionally not a release channel for this version. The release does not
relicense model weights, input recordings, or transitive packages.

For model-specific terms, consult the upstream weight/release notices before
redistribution: [All-In-One releases](https://github.com/openmirlab/all-in-one-infer/releases),
[Demucs model releases](https://github.com/facebookresearch/demucs/releases),
and [Basic Pitch model/code notices](https://github.com/spotify/basic-pitch/blob/main/LICENSE).

This file is a provenance record, not legal advice. Recheck upstream code,
model-weight, and transitive dependency terms at release time.
