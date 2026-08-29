---
name: agent-listening
description: Analyze finished audio into Music-IR and JAMS artifacts with the local Agent Listening CLI. Use when an agent needs structured evidence from a rendered audio file.
---

# Agent Listening

Run the local tool from any working directory:

```bash
agent-listening analyze "/absolute/path/to/audio.wav" \
  --output-dir "/absolute/path/to/job-output" --json
```

Read the JSON receipt first. It gives the track ID, absolute artifact paths,
automatic validation status, and whether human listening is still pending.

Progressive disclosure:

1. Read the receipt.
2. Read the referenced `music-ir` file for ordinary musical reasoning.
3. Read `jams` only when timing, candidates, or frame evidence is needed.
4. Read raw extractor JSON only for provenance audit or diagnosis.

Use a new output directory for a new analysis. Existing artifacts are
protected; pass `--overwrite` only when intentional replacement is authorized.

Execution success means the automatic validation path completed. It does not
mean that a human approved section boundaries or key candidates. The receipt
may report JAMS base-schema success while namespace-strict validation is not
claimed when extractor confidence is unknown.
