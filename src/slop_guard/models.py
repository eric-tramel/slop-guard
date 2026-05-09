"""Typed payloads and result models for slop-guard."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

Counts: TypeAlias = dict[str, int]
BandLabel: TypeAlias = Literal["clean", "light", "moderate", "heavy", "saturated"]


class ViolationPayload(TypedDict):
    """Structured violation payload returned to CLI and MCP consumers.

    The optional ``category`` field appears only when the active pipeline
    includes rules tagged with a non-default category (i.e. when the
    writing-quality preset is loaded alongside or instead of the default).
    """

    type: Literal["Violation"]
    rule: str
    match: str
    context: str
    penalty: int
    start: int
    end: int
    category: NotRequired[str]


class AnalysisPayload(TypedDict):
    """Structured analyzer result produced by the core analyzer.

    The optional ``category_counts`` field appears only when the active
    pipeline includes rules tagged with a non-default category.
    """

    score: int
    band: BandLabel
    word_count: int
    violations: list[ViolationPayload]
    counts: Counts
    total_penalty: int
    weighted_sum: float
    density: float
    advice: list[str]
    category_counts: NotRequired[Counts]


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
    category: str = "ai_slop"

    def explicit_span(self) -> tuple[int, int] | None:
        """Return the exact rule-provided span when one exists."""
        if self.start is None or self.end is None:
            return None
        return (self.start, self.end)

    def to_payload(
        self, start: int, end: int, *, include_category: bool = False
    ) -> ViolationPayload:
        """Serialize a typed violation for tool output.

        Args:
            start: Resolved start offset in the original text.
            end: Resolved end offset in the original text.
            include_category: When True, also emit the rule's category in the
                payload. Callers should set this only when the active pipeline
                contains rules from more than the default category.
        """
        payload: ViolationPayload = {
            "type": "Violation",
            "rule": self.rule,
            "match": self.match,
            "context": self.context,
            "penalty": self.penalty,
            "start": start,
            "end": end,
        }
        if include_category:
            payload["category"] = self.category
        return payload


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
