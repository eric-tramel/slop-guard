"""Typed payloads and result models for slop-guard."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from typing_extensions import TypedDict

Counts: TypeAlias = dict[str, int]
BandLabel: TypeAlias = Literal["clean", "light", "moderate", "heavy", "saturated"]


class ViolationPayload(TypedDict):
    """Structured violation payload returned to CLI and MCP consumers."""

    type: Literal["Violation"]
    rule: str
    match: str
    context: str
    penalty: int
    start: int
    end: int


class ReviewCriterionPayload(TypedDict):
    """One semantic criterion that a writing agent must judge."""

    key: str
    instruction: str


class ReviewRequirementPayload(TypedDict):
    """Semantic review work that deterministic rules cannot resolve."""

    type: Literal["ReviewRequirement"]
    rule: str
    reason: str
    criteria: list[ReviewCriterionPayload]


class AnalysisPayload(TypedDict):
    """Structured analyzer result produced by the core analyzer."""

    score: int
    band: BandLabel
    word_count: int
    violations: list[ViolationPayload]
    review_requirements: list[ReviewRequirementPayload]
    counts: Counts
    total_penalty: int
    weighted_sum: float
    density: float
    advice: list[str]


class SourceAnalysisPayload(AnalysisPayload):
    """Structured analyzer result augmented with a source label."""

    source: str


@dataclass(frozen=True)
class Violation:
    """Canonical violation record emitted by a rule."""

    rule: str
    match: str
    context: str
    penalty: int
    start: int | None = None
    end: int | None = None

    def explicit_span(self) -> tuple[int, int] | None:
        """Return the exact rule-provided span when one exists."""
        if self.start is None or self.end is None:
            return None
        return (self.start, self.end)

    def to_payload(self, start: int, end: int) -> ViolationPayload:
        """Serialize a typed violation for tool output."""
        return {
            "type": "Violation",
            "rule": self.rule,
            "match": self.match,
            "context": self.context,
            "penalty": self.penalty,
            "start": start,
            "end": end,
        }


@dataclass(frozen=True)
class ReviewCriterion:
    """One semantic question supplied to a writing agent."""

    key: str
    instruction: str

    def to_payload(self) -> ReviewCriterionPayload:
        """Serialize this criterion for CLI and MCP consumers."""
        return {"key": self.key, "instruction": self.instruction}


@dataclass(frozen=True)
class ReviewRequirement:
    """A semantic review that must follow the deterministic lint pass."""

    rule: str
    reason: str
    criteria: tuple[ReviewCriterion, ...]

    def to_payload(self) -> ReviewRequirementPayload:
        """Serialize this review requirement for CLI and MCP consumers."""
        return {
            "type": "ReviewRequirement",
            "rule": self.rule,
            "reason": self.reason,
            "criteria": [criterion.to_payload() for criterion in self.criteria],
        }


@dataclass
class RuleResult:
    """Output payload emitted by a single rule invocation."""

    violations: list[Violation] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    count_deltas: Counts = field(default_factory=dict)
    review_requirements: list[ReviewRequirement] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisState:
    """Immutable accumulator carrying merged rule output."""

    violations: tuple[Violation, ...]
    advice: tuple[str, ...]
    counts: Counts
    review_requirements: tuple[ReviewRequirement, ...]

    @classmethod
    def initial(cls, count_keys: Iterable[str] | None = None) -> "AnalysisState":
        """Construct an empty state with canonical counts initialized to zero."""
        from .scoring import initial_counts

        return cls(
            violations=(),
            advice=(),
            counts=initial_counts(count_keys),
            review_requirements=(),
        )

    def merge(self, result: RuleResult) -> "AnalysisState":
        """Merge one rule result into a new state instance."""
        merged_counts = dict(self.counts)
        for key, delta in result.count_deltas.items():
            if delta:
                merged_counts[key] = merged_counts.get(key, 0) + delta

        return AnalysisState(
            violations=self.violations + tuple(result.violations),
            advice=self.advice + tuple(result.advice),
            counts=merged_counts,
            review_requirements=(
                self.review_requirements + tuple(result.review_requirements)
            ),
        )
