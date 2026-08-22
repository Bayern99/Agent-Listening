# 0009. Multi-Algorithm Key Conflict Resolution via Maximum Strength

We decided that `global.key_summary` will automatically select the candidate with the highest `strength` score across Essentia's 3 key estimation algorithms (EDMA, Temperley, Krumhansl), while preserving all 3 raw hypotheses in `global.key_candidates` for full provenance.
