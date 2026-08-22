# 0007. Explicit Opt-In Policy for Symbolic Transcription on Full Mixes

We decided that automatic music transcription (AMT / MIDI generation via Basic Pitch) will be disabled by default for full-mix recordings (`analysis_mode: full_mix`), because polyphonic multi-instrument mix transcription generates severe ghost-note artifacts. Symbol extraction can only be enabled via explicit flag `--enable-symbols` or for solo tracks (`analysis_mode: solo`).
