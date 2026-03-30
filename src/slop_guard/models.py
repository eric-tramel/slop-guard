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


class AnalysisPayload(TypedDict):
    """Structured analyzer result produced by the core analyzer."""

    score: int
    band: BandLabel
    word_count: int
    violations: list[ViolationPayload]
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


@dataclass
class RuleResult:
    """Output payload emitted by a single rule invocation."""

    violations: list[Violation] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    count_deltas: Counts = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisState:
    """Immutable accumulator carrying merged rule output."""

    violations: tuple[Violation, ...]
    advice: tuple[str, ...]
    counts: Counts

    @classmethod
    def initial(cls, count_keys: Iterable[str] | None = None) -> "AnalysisState":
        """Construct an empty state with canonical counts initialized to zero."""
        from .scoring import initial_counts

        return cls(violations=(), advice=(), counts=initial_counts(count_keys))

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
        )
