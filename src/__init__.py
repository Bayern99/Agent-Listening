"""Agent Listening CLI (Audio-to-Music-IR).

The public functions load the analysis implementation only when called so the
installed command can answer ``--version`` and ``doctor`` without importing
the native/model dependency stack.
"""


def analyze(*args, **kwargs):
    from src.core import analyze as implementation

    return implementation(*args, **kwargs)


def build_ir_from_files(*args, **kwargs):
    from src.core import build_ir_from_files as implementation

    return implementation(*args, **kwargs)


def merge_evidence(*args, **kwargs):
    from src.fusion.builder import merge_evidence as implementation

    return implementation(*args, **kwargs)

__all__ = ["analyze", "build_ir_from_files", "merge_evidence"]
