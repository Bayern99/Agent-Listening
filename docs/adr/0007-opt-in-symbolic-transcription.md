# 0007. Use Basic Pitch for Isolated Sources, Never as Score Ground Truth

Solo and caller-provided stem analyses run the real Basic Pitch adapter and
publish note JSON plus MIDI when the model succeeds. Full mixes run it only on
non-drum Demucs stems; the drums stem is represented by activity/onset
evidence. Every note artifact records the actual package/model version and is
marked machine transcription, not a symbolic-score ground truth. Basic Pitch
amplitude remains amplitude and is never renamed as loudness.
