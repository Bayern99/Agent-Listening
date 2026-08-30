"""Locate data shipped with the checkout or an installed tool environment."""

from pathlib import Path
import sys


def resource_path(directory: str, filename: str) -> Path:
    """Return a packaged resource without making checkout paths mandatory."""
    roots = (Path(__file__).resolve().parent.parent, Path(sys.prefix))
    for root in roots:
        candidate = root / directory / filename
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(root / directory / filename) for root in roots)
    raise FileNotFoundError(f"Resource not found; searched: {searched}")
