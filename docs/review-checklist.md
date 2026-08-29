# Music IR Human Review Checklist

This checklist defines the Standard Operating Procedure (SOP) for an audio engineer or musician to audit, verify, and finalize a newly generated `music-ir.json` file.

---

## Pre-Check

- [ ] Audio source file exists in `source/<track-id>.wav` or `source/<track-id>.flac`.
- [ ] Analysis files generated:
  - `music-ir/<track-id>.music-ir.json`
  - `jams/<track-id>.analysis.jams`
- [ ] Open your DAW or preferred audio player with second-accurate playhead display.

---

## Step 1: Tempo & Time Grid Verification

1. **BPM Sanity Check**:
   - Compare `global.tempo_bpm.value` against your metronome or DAW project tempo.
   - [ ] Is the detected tempo within ±1 BPM of the actual tempo?
   - [ ] Is there an octave error (e.g. detected 60 BPM when the track is 120 BPM)?
2. **Downbeat Phase Alignment**:
   - Play audio at `structure.downbeats_s[0]`.
   - [ ] Does `downbeats_s[0]` land on the actual first downbeat of Bar 1?
   - If offset by a pickup measure / anacrusis, log note in `review.known_uncertainties`.

---

## Step 2: Structural Form & Section Boundaries

1. **Boundary Transition Check**:
   - Jump playhead to each `structure.sections[i].start_s` and `end_s`.
   - [ ] Do segment transitions align with actual musical phrase changes (e.g. drum drop, chord shift, vocal entrance)?
   - [ ] Are boundaries within ±0.5s of the perceptual transition?
2. **Functional Label Audit**:
   - Review labels (`intro`, `verse`, `chorus`, `bridge`, `outro`).
   - [ ] Are non-pop/electronic sections reasonably labeled, or should `label` be refined in `manual_notes`?

---

## Step 3: Tonality & Harmonic Key Audit

1. **Candidate Disagreement Resolution**:
   - Inspect `global.key_candidates`.
   - [ ] Did EDMA, Temperley, and Krumhansl agree on the tonic and scale?
   - [ ] If algorithms disagree (e.g., D minor vs F major), listen to the final cadence or bass root notes to confirm the true tonal center.
2. **Key Summary Validation**:
   - [ ] Does `global.key_summary` match the true musical key center? If not, correct `key_summary` and note the algorithm discrepancy.

---

## Step 4: Acoustic Feature Sanity Bounds

Verify that acoustic parameters fall within normal physical musical ranges:

- [ ] **Loudness (LUFS)**: Typically between `-24.0 LUFS` (dynamic acoustic) and `-6.0 LUFS` (commercial master).
- [ ] **Dynamic Range (LU)**: Typically between `3.0 LU` (brickwall limited) and `14.0 LU` (orchestral).
- [ ] **Spectral Centroid (Hz)**: Typically between `800 Hz` (dark/bass-heavy) and `4500 Hz` (bright/sizzling).
- [ ] **Onset Rate**: Typically between `0.5` (ambient/drone) and `8.0` (fast drum/percussion).

## Step 4A: Material, Pitch, and Source Candidates (Music IR 0.2)

- [ ] Jump to each `structure.material_events[].time_s` in the external player
  or DAW and decide whether the before/after windows describe a real material
  change. Keep the machine candidate label when it is useful; record a human
  decision in `review.known_uncertainties` or project notes rather than
  silently rewriting raw evidence.
- [ ] Treat `pitch` and `symbols` as machine observations. Compare the JAMS
  `pitch_contour` and `note_midi` timestamps with the audio; never treat MIDI
  notes as a score without a separate human transcription decision.
- [ ] For `full_mix`, audition each listed `sources[].audio_file` and confirm
  the Demucs role is useful for the intended downstream task. A source with
  `status: "failed"` or activity `status: "not_detected"` needs a human or
  alternate tool before it is used as a musical fact.

---

## Step 5: Finalizing the Audit

Once verified:

1. Update `review.human_checked` to `true`:
   ```json
   "review": {
     "human_checked": true,
     "known_uncertainties": [
       "Section 3 has modal shift from D minor to G minor from 48.7s to 78.1s."
     ]
   }
   ```
2. (Optional) Add human musical observations in `interpretation.manual_notes`:
   ```json
   "interpretation": {
     "manual_notes": [
       "Main lead uses analog filter sweep during chorus (bars 16-24)."
     ]
   }
   ```
3. Save the modified `music-ir/<track-id>.music-ir.json`.
