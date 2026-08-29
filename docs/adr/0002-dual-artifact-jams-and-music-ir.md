# 0002. Maintain Dual Artifacts: JAMS for Evidence and Music-IR for Consumption

We decided to produce both `analysis.jams` and `music-ir.json` per track. JAMS carries schema-validated timing annotations, frame vectors, multi-candidate hypotheses, and tool provenance, while `music-ir.json` serves as the concise domain representation optimized for multimodal agent reasoning and sound synthesis parameterization. Artifact writes fail on existing paths by default; `--overwrite` is an explicit destructive replacement, not an immutable-history mechanism.
