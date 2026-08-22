"""Agent Listening (Audio-to-Music-IR).

Deep module providing a minimal public interface for audio music perception.
"""

from src.core import analyze, build_ir_from_files
from src.fusion.builder import merge_evidence

__all__ = ["analyze", "build_ir_from_files", "merge_evidence"]
