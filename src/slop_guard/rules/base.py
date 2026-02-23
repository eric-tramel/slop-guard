"""Shared base types for rule definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeAlias, TypeVar

from slop_guard.analysis import AnalysisDocument, RuleResult

Label: TypeAlias = int


class RuleLevel(StrEnum):
    """Hierarchy grouping used to organize rule modules."""

    WORD = "word"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    PASSAGE = "passage"


@dataclass
class RuleConfig:
    """Base config container inherited by concrete rule configs."""


ConfigT = TypeVar("ConfigT", bound=RuleConfig)


class Rule(ABC, Generic[ConfigT]):
    """Base rule class exposing a forward pass and optional fit step."""

    name: str = "rule"
    count_key: str = "rule"
    level: RuleLevel = RuleLevel.PASSAGE

    def __init__(self, config: ConfigT) -> None:
        """Initialize a rule with explicit configuration."""
        self.config = config

    @abstractmethod
    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply the rule and return violations, advice, and counter deltas."""

    def fit(self, samples: list[str], labels: list[Label]) -> "Rule[ConfigT]":
        """Fit rule configuration from labeled samples, scikit-style.

        Args:
            samples: Raw text samples used for fitting.
            labels: Integer targets where positive and negative classes map to
                integer labels (for example, 1 and 0).

        Returns:
            The same rule instance after updating ``self.config``.
        """
        self._validate_fit_inputs(samples, labels)
        self.config = self._fit(samples, labels)
        return self

    def _fit(self, samples: list[str], labels: list[Label]) -> ConfigT:
        """Learn and return a fitted config.

        The default implementation is a no-op so existing hard-coded
        hyperparameters stay active until per-rule fitting is implemented.
        """
        _ = samples
        _ = labels
        return self.config

    def _validate_fit_inputs(self, samples: list[str], labels: list[Label]) -> None:
        """Validate shape and types for fit inputs."""
        if len(samples) != len(labels):
            raise ValueError("samples and labels must have the same length")
        if not all(isinstance(sample, str) for sample in samples):
            raise TypeError("samples must be a list of strings")
        if not all(isinstance(label, int) for label in labels):
            raise TypeError("labels must be a list of integers")
