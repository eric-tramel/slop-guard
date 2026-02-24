"""Detect monotonous sentence-length rhythm.

Objective: Measure sentence-length variance across a passage and flag texts
whose cadence is too uniform, a common artifact of generated prose.

Example Rule Violations:
    - A long paragraph where nearly every sentence has similar token length.
      Low variation creates flat, synthetic rhythm.
    - Five to ten sentences all around the same size and pacing.
      Statistical variance falls below the configured threshold.

Example Non-Violations:
    - Mixed sentence lengths with short emphatic lines and longer explanation.
      Natural rhythm diversity is present.
    - A concise note with too few sentences for robust rhythm inference.
      Rule does not apply when sample size is small.

Severity: Medium; a useful style signal that is stronger with other findings.
"""


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

    def example_violations(self) -> list[str]:
        """Return samples that should trigger rhythm matches."""
        return [
            (
                "Alpha beta gamma delta. "
                "Alpha beta gamma delta. "
                "Alpha beta gamma delta. "
                "Alpha beta gamma delta. "
                "Alpha beta gamma delta."
            ),
            (
                "One two three four. "
                "Five six seven eight. "
                "Nine ten eleven twelve. "
                "Thirteen fourteen fifteen sixteen. "
                "Seventeen eighteen nineteen twenty."
            ),
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid rhythm matches."""
        return [
            "Short note. Still short. Not enough sentences. Stop.",
            (
                "Tiny line. "
                "This sentence has many extra words for strong variation now. "
                "Brief again. "
                "Another long sentence appears with additional explanatory detail. "
                "Done."
            ),
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute sentence-length CV and emit a rhythm violation if low."""
        sentence_count = len(document.sentence_word_counts)
        if sentence_count < self.config.min_sentences:
            return RuleResult()

        lengths = document.sentence_word_counts
        mean = sum(lengths) / sentence_count
        if mean <= 0:
            return RuleResult()

        variance = sum((value - mean) ** 2 for value in lengths) / sentence_count
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
                        f"CV={cv:.2f} across {sentence_count} sentences "
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
