# 0005. Two-Tier Temporal Granularity: Section Summaries in IR, Frame Curves in JAMS

We decided to aggregate acoustic features at the global and section level inside `music-ir.json` (keeping the token footprint under 10KB for LLM efficiency). Continuous frame-level curves (e.g. 100Hz spectral flux, energy trajectories) are preserved exclusively in the `analysis.jams` evidence archive for specialized parameter automation when needed.
