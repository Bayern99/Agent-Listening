# 0005. Two-Tier Temporal Granularity: Section Summaries in IR, Frame Curves in JAMS

We decided to aggregate acoustic features at the global and section level inside `music-ir.json` (keeping the token footprint under 10KB for LLM efficiency). When aligned frame values are available, continuous loudness, spectral-centroid, and spectral-flux values are stored in the standard JAMS `vector` namespace with named columns.
