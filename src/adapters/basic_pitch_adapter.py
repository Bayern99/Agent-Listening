"""Basic Pitch adapter for machine-transcribed note evidence."""

from importlib.metadata import PackageNotFoundError, version
import json
from math import pow
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class BasicPitchAdapter:
    """Run and normalize Basic Pitch without treating MIDI as ground truth."""

    DISTRIBUTION = "basic-pitch"

    @staticmethod
    def _version() -> str:
        try:
            return version(BasicPitchAdapter.DISTRIBUTION)
        except PackageNotFoundError:
            return "unknown"

    @staticmethod
    def parse_note_events(
        note_events: Iterable[Tuple[Any, ...]],
        tool_version: str = "unknown",
    ) -> Dict[str, Any]:
        notes: List[Dict[str, Any]] = []
        for event in note_events:
            if len(event) < 4:
                continue
            start_s, end_s, midi_pitch, amplitude = event[:4]
            start_s = float(start_s)
            end_s = float(end_s)
            midi_pitch = int(midi_pitch)
            amplitude = float(amplitude)
            note = {
                "start_s": start_s,
                "end_s": end_s,
                "duration_s": max(0.0, end_s - start_s),
                "midi_pitch": midi_pitch,
                "frequency_hz": round(440.0 * pow(2.0, (midi_pitch - 69) / 12.0), 4),
                "amplitude": amplitude,
                "confidence": None,
            }
            if len(event) >= 5 and event[4] is not None:
                if isinstance(event[4], (list, tuple)):
                    note["pitch_bends"] = [int(value) for value in event[4]]
                elif isinstance(event[4], (int, float)):
                    note["confidence"] = float(event[4])
            if len(event) >= 6 and event[5] is not None:
                note["confidence"] = float(event[5])
            notes.append(note)

        pitches = [note["midi_pitch"] for note in notes]
        duration_s = max((note["end_s"] for note in notes), default=0.0)
        pitch_classes = [0] * 12
        for pitch in pitches:
            pitch_classes[pitch % 12] += 1
        pitch_class_distribution = [
            round(count / len(pitches), 4) for count in pitch_classes
        ] if pitches else None
        return {
            "status": "available" if notes else "not_detected",
            "tool": "basic-pitch",
            "version": tool_version,
            "notes": notes,
            "note_count": len(notes),
            "note_density_per_s": round(len(notes) / duration_s, 4) if duration_s else 0.0,
            "pitch_range_midi": [min(pitches), max(pitches)] if pitches else None,
            "pitch_class_distribution": pitch_class_distribution,
            "midi_path": None,
            "amplitude_is_not_loudness": True,
        }

    @staticmethod
    def artifact_paths(result: Dict[str, Any]) -> Dict[str, Optional[Path]]:
        """Expose only normalized artifact paths to the orchestration layer."""
        return {
            kind: Path(value) if value else None
            for kind, value in (
                ("notes", result.get("notes_path")),
                ("midi", result.get("midi_path")),
            )
        }

    def run(self, audio_path: str, output_dir: str, source_id: str) -> Dict[str, Any]:
        """Run Basic Pitch and write MIDI plus compact note evidence JSON."""
        try:
            from basic_pitch.inference import predict
        except ImportError as exc:
            raise FileNotFoundError(
                "Basic Pitch is not installed; run `uv sync` to enable note extraction"
            ) from exc

        model_output, midi_data, note_events = predict(audio_path)
        del model_output
        output_path = Path(output_dir)
        data = self.parse_note_events(note_events, tool_version=self._version())
        data["model"] = "basic-pitch-default"
        data["audio_path"] = str(audio_path)
        if data["notes"]:
            output_path.mkdir(parents=True, exist_ok=True)
            midi_path = output_path / f"{source_id}.mid"
            midi_data.write(str(midi_path))
            data["midi_path"] = str(midi_path)
            notes_path = output_path / f"{source_id}.notes.json"
            data["notes_path"] = str(notes_path)
            notes_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        else:
            data["midi_path"] = None
            data["notes_path"] = None
        return data
