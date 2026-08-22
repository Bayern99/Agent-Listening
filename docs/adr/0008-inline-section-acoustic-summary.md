# 0008. Inline Section Acoustic Summary for Locality

We decided to inline section-level acoustic descriptors (`loudness_lufs`, `spectral_centroid_hz`, `dynamic_complexity`) directly inside each `structure.sections[i]` item rather than in a separate decoupled table. This provides maximal locality for downstream agents and synthesis state transitions without cross-field joins.
