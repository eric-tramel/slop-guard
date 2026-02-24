"""Shared base types for rule definitions."""


from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Generic, Mapping, TypeAlias, TypeVar, cast, get_args, get_origin

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

    def to_dict(self) -> dict[str, object]:
        """Serialize the config dataclass to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(
        cls: type["ConfigFromDictT"], raw: Mapping[str, object]
    ) -> "ConfigFromDictT":
        """Instantiate a config dataclass from a plain dictionary."""
        return cls(**dict(raw))


ConfigT = TypeVar("ConfigT", bound=RuleConfig)
ConfigFromDictT = TypeVar("ConfigFromDictT", bound=RuleConfig)
RuleFromDictT = TypeVar("RuleFromDictT", bound="Rule[RuleConfig]")


class Rule(ABC, Generic[ConfigT]):
    """Base rule class exposing a forward pass and optional fit step."""

    name: str = "rule"
    count_key: str = "rule"
    level: RuleLevel = RuleLevel.PASSAGE

    def __init__(self, config: ConfigT) -> None:
        """Initialize a rule with explicit configuration."""
        self.config = config

    def to_dict(self) -> dict[str, object]:
        """Serialize this rule's config as a plain dictionary."""
        return self.config.to_dict()

    @classmethod
    def from_dict(
        cls: type["RuleFromDictT"], raw: Mapping[str, object]
    ) -> "RuleFromDictT":
        """Instantiate a rule from a plain config dictionary."""
        config_type = cls._resolve_config_type()
        config = config_type.from_dict(raw)
        return cls(config)

    @classmethod
    def _resolve_config_type(cls) -> type[RuleConfig]:
        """Infer the concrete config type from ``Rule[Config]`` inheritance."""
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is Rule:
                args = get_args(base)
                if len(args) != 1:
                    break
                config_type = args[0]
                if isinstance(config_type, type) and issubclass(
                    config_type, RuleConfig
                ):
                    return cast(type[RuleConfig], config_type)
                break
        raise TypeError(
            f"Could not infer config type for rule class {cls.__name__}. "
            "Ensure it subclasses Rule[ConcreteConfig]."
        )

    @abstractmethod
    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply the rule and return violations, advice, and counter deltas."""

    @abstractmethod
    def example_violations(self) -> list[str]:
        """Return text samples that should trigger this rule."""

    @abstractmethod
    def example_non_violations(self) -> list[str]:
        """Return text samples that should not trigger this rule."""

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
