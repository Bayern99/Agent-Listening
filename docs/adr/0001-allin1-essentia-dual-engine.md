# 0001. Use allin1 and Essentia Dual-Engine for V0.1 Audio Extraction

We chose `allin1` for structure/beats and `Essentia` music extractor CLI for acoustic/tonal features instead of an end-to-end Audio Language Model (ALM) or heavy Ray pipeline. This provides deterministic, reproducible, CPU-friendly JSON outputs without large GPU clusters or hallucinated metric timing.
