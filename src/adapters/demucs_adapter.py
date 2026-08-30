"""Demucs source-separation adapter."""

import json
from importlib.metadata import PackageNotFoundError, version
import hashlib
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional


class DemucsAdapter:
    """Run the installed demucs-infer CLI and return a stem manifest."""

    DEFAULT_BINARY = "demucs-infer"
    DEFAULT_MODEL = "htdemucs_6s"
    STEMS = ("vocals", "drums", "bass", "guitar", "piano", "other")

    def __init__(self, binary_path: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.binary_path = binary_path or self.DEFAULT_BINARY
        self.model = model

    def is_available(self) -> bool:
        return shutil.which(self.binary_path) is not None

    def run(self, audio_path: str, output_dir: str) -> Dict[str, Any]:
        if not self.is_available():
            raise FileNotFoundError(
                f"Demucs executable '{self.binary_path}' not found; run `uv sync` to enable full_mix stems"
            )
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        command = [
            self.binary_path,
            "-n", self.model,
            "-d", "cpu",
            "--float32",
            "-o", str(destination),
            audio_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Demucs separation failed (exit {result.returncode}): {result.stderr.strip()}")
        track_dir = destination / self.model / Path(audio_path).stem
        stems = [
            {
                "id": stem,
                "role": stem,
                "path": str(track_dir / f"{stem}.wav"),
                "duration_s": self._duration(track_dir / f"{stem}.wav"),
            }
            for stem in self.STEMS
            if (track_dir / f"{stem}.wav").exists()
        ]
        if not stems:
            raise RuntimeError(f"Demucs completed without stem files in {track_dir}")
        missing = sorted(set(self.STEMS) - {stem["id"] for stem in stems})
        if missing:
            raise RuntimeError(
                f"Demucs completed with incomplete htdemucs_6s stems in {track_dir}; "
                f"missing: {', '.join(missing)}"
            )
        manifest = {
            "tool": "demucs-infer",
            "version": self.version(),
            "model": self.model,
            "audio_path": str(audio_path),
            "source_sha256": self._sha256(Path(audio_path)),
            "stems": stems,
        }
        (destination / "demucs-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    @staticmethod
    def version() -> str:
        try:
            return version("demucs-infer")
        except PackageNotFoundError:
            return "unknown"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _duration(path: Path) -> Optional[float]:
        try:
            import soundfile as sf
            return round(float(sf.info(str(path)).duration), 6)
        except Exception:
            return None

    @staticmethod
    def parse_manifest(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return only known, existing stem entries from a separation manifest."""
        result = []
        for stem in manifest.get("stems", []):
            path = Path(str(stem.get("path", "")))
            if stem.get("id") in DemucsAdapter.STEMS and path.is_file():
                record = {
                    "id": str(stem["id"]),
                    "role": str(stem.get("role", stem["id"])),
                    "path": str(path),
                }
                if "duration_s" in stem:
                    record["duration_s"] = stem["duration_s"]
                result.append(record)
        return result

    @staticmethod
    def metadata(manifest: Dict[str, Any]) -> Dict[str, str]:
        """Normalize tool metadata before it crosses the adapter seam."""
        return {
            "tool": str(manifest.get("tool", "demucs-infer")),
            "version": str(manifest.get("version", "unknown")),
            "model": str(manifest.get("model", DemucsAdapter.DEFAULT_MODEL)),
        }

    @staticmethod
    def separation_status(manifest: Dict[str, Any]) -> str:
        """Classify a manifest without hiding available partial evidence."""
        stem_ids = {stem["id"] for stem in DemucsAdapter.parse_manifest(manifest)}
        if stem_ids == set(DemucsAdapter.STEMS):
            return "available"
        if stem_ids:
            return "failed"
        return "failed"

    @staticmethod
    def artifact_manifest(manifest: Dict[str, Any], track_id: str) -> Dict[str, Any]:
        """Return a stable-path manifest suitable for the persisted raw artifact."""
        metadata = DemucsAdapter.metadata(manifest)
        stable_stems = []
        for stem in DemucsAdapter.parse_manifest(manifest):
            stable_stems.append({
                **stem,
                "extracted_path": stem["path"],
                "path": str(Path("stems") / track_id / f"{stem['id']}.wav"),
            })
        return {
            **manifest,
            **metadata,
            "status": DemucsAdapter.separation_status(manifest),
            "missing_stems": sorted(set(DemucsAdapter.STEMS) - {stem["id"] for stem in stable_stems}),
            "stems": stable_stems,
        }
