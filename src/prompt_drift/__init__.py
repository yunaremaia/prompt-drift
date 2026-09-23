"""prompt-drift — detect drift between LLM prompts and their evaluation tests."""

__version__ = "0.1.0"

from prompt_drift.scanner import scan_directory, collect_prompts, collect_evals
from prompt_drift.detectors import detect_drift

__all__ = ["scan_directory", "collect_prompts", "collect_evals", "detect_drift", "__version__"]
