"""Passage-level rule detecting monotonous sentence-length rhythm."""

from __future__ import annotations

import math
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel


@dataclass
class RhythmRuleConfig(RuleConfig):
    """Config for rhythm variance thresholding."""

    min_sentences: int
    cv_threshold: float
    penalty: int


class RhythmRule(Rule[RhythmRuleConfig]):
    """Flag low-variance sentence cadence across the full passage."""

    name = "rhythm"
    count_key = "rhythm"
    level = RuleLevel.PASSAGE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute sentence-length CV and emit a rhythm violation if low."""
        if len(document.sentences) < self.config.min_sentences:
            return RuleResult()

        lengths = [len(sentence.split()) for sentence in document.sentences]
        mean = sum(lengths) / len(lengths)
        if mean <= 0:
            return RuleResult()

        variance = sum((value - mean) ** 2 for value in lengths) / len(lengths)
        std = math.sqrt(variance)
        cv = std / mean
        if cv >= self.config.cv_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="monotonous_rhythm",
                    context=(
                        f"CV={cv:.2f} across {len(document.sentences)} sentences "
                        f"(mean {mean:.1f} words)"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Sentence lengths are too uniform (CV={cv:.2f}) \u2014 vary short and long."
            ],
            count_deltas={self.count_key: 1},
        )
