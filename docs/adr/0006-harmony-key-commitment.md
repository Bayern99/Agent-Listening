# 0006. Global and Sectional Key Commitment without Time-Aligned Chords in V0.1

We decided that V0.1 will provide global and sectional tonality candidates from Essentia, while explicitly disabling `time_aligned_chords`. Time-aligned chord extraction introduces third-party C++ Vamp plugins with high noise in full mixes, and is isolated behind a clean future seam.
