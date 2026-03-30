"""Public package interface for slop-guard."""

from .config import DEFAULT_HYPERPARAMETERS, Hyperparameters
from .engine import analyze_document, analyze_text
from .models import AnalysisPayload
from .version import PACKAGE_VERSION as __version__

__all__ = [
    "AnalysisPayload",
    "DEFAULT_HYPERPARAMETERS",
    "Hyperparameters",
    "__version__",
    "analyze_document",
    "analyze_text",
]
