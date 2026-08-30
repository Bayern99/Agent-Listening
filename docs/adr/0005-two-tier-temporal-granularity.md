# 0005. Two-Tier Temporal Granularity: Section Summaries in IR, Frame Curves in JAMS

We decided to aggregate acoustic features at the global and section level inside `music-ir.json` (keeping the token footprint small for agent reasoning). When aligned frame values are available, continuous loudness, spectral-centroid, spectral-flux, energy-band, tonal, and pitch values are stored in separate JAMS grids with explicit time bases. If a section has no valid local feature timeline, its local acoustic fields are `null`; global values are never copied into a section as a substitute.
