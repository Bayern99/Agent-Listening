# 0010. CLI Analysis Modes and Offline Evidence Compilation

The public analysis command keeps three explicit source semantics:
`solo` (one isolated source), `stem` (a caller-identified stem), and
`full_mix` (all-in-one plus Demucs separation and per-stem evidence). The
developer-only `build-ir` command remains a pure offline compiler for captured
extractor JSON and fixtures. Both paths emit the same compact Music IR/JAMS
contract and never start a server or load raw evidence into an agent context.
