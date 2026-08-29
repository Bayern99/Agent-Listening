# Agent Listening (Audio-to-Music-IR)

A system for analyzing finished audio recordings into structured, verified intermediate representations (Music IR) to drive multimodal agent reasoning and sound synthesis systems.

## Language

### Observations & Evidence

**Observation**:
An uninterpreted, tool-specific raw measurement or label generated directly from audio analysis.
_Avoid_: Fact, ground truth, feature

**Evidence**:
A structured observation augmented with source tool identity, version hash, timestamp, and confidence metrics.
_Avoid_: Raw output, inference

**Provenance**:
The complete audit trail of tools, profile hashes, and execution parameters used to produce an analysis.
_Avoid_: Metadata, history

### Structure & Timing

**Time Grid**:
The temporal coordinate system of beats and downbeats marking musical pulses in seconds.
_Avoid_: Clock, timeline, ticks

**Section**:
A continuous musical segment bounded by structural change, labeled with a functional or formal role.
_Avoid_: Part, chunk, slice

**Downbeat**:
The primary accented pulse marking the beginning of a measure or metric unit.
_Avoid_: First beat, bar start

### Harmony & Acoustics

**Key Candidate**:
A probabilistic pitch center and scale mode hypothesis extracted from pitch distribution.
_Avoid_: Song key, absolute tonality

**Acoustic Profile**:
A vector of psychoacoustic and physical signal measurements (loudness, spectral centroid, flux, onset rate).
_Avoid_: Timbre description, sound quality

### Representation & Execution

**Music IR**:
The compact, multi-layered intermediate JSON schema representing a track's global, structural, harmonic, and acoustic reality.
_Avoid_: Music spec, audio transcript, metadata JSON

**JAMS Archive**:
The replaceable, schema-validated time-series annotation file carrying normalized evidence, candidates, and provenance pointers. Raw extractor outputs remain separate artifacts.
_Avoid_: Output JSON, cache

**Realization Hint**:
A non-binding parameter guideline derived from acoustic evidence to assist sound synthesis mapping.
_Avoid_: Synth parameter, preset, patch
