# Specification: Audio-to-Music-IR V0.1 Pipeline

## 1. Goal

Provide a lightweight, robust, deterministic CLI pipeline to convert mixed music audio files into:
1. `raw/*.json` (unprocessed extractor outputs)
2. `jams/*.analysis.jams` (standardized time-annotated evidence archive)
3. `music-ir/*.music-ir.json` (compact domain model for downstream multimodal agents and sound synthesis)

## 2. Architecture & Seams

- **Adapter Seam**: `EssentiaAdapter` and `AllInOneAdapter` abstract external CLI calls and raw JSON parsing.
- **Fusion Seam**: `build_music_ir()` is a pure, side-effect-free function fusing multi-tool evidence.
- **Contract**: Every output MUST pass validation against `schemas/music-ir-v0.1.schema.json`.

## 3. Tracer-Bullet Tickets

- `01-essentia-profile-and-adapter.md` (Blocked by: None)
- `02-allin1-adapter.md` (Blocked by: None)
- `03-fusion-and-schema-validator.md` (Blocked by: 01, 02)
- `04-cli-runner-and-end-to-end.md` (Blocked by: 03)
