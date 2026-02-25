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

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    clamp_int,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
    fit_threshold_low_contrastive,
    percentile_floor,
)


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

    def _fit(self, samples: list[str], labels: list[Label] | None) -> RhythmRuleConfig:
        """Fit rhythm thresholds from sentence-length distributions."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_sentence_counts: list[int] = []
        positive_cv_values: list[float] = []
        for sample in positive_samples:
            document = AnalysisDocument.from_text(sample)
            sentence_count = len(document.sentence_word_counts)
            if sentence_count <= 0:
                continue
            positive_sentence_counts.append(sentence_count)
            if sentence_count < 2:
                continue
            mean = sum(document.sentence_word_counts) / sentence_count
            if mean <= 0:
                continue
            variance = (
                sum((value - mean) ** 2 for value in document.sentence_word_counts)
                / sentence_count
            )
            positive_cv_values.append(math.sqrt(variance) / mean)

        if not positive_sentence_counts:
            return self.config

        negative_sentence_counts: list[int] = []
        negative_cv_values: list[float] = []
        for sample in negative_samples:
            document = AnalysisDocument.from_text(sample)
            sentence_count = len(document.sentence_word_counts)
            if sentence_count <= 0:
                continue
            negative_sentence_counts.append(sentence_count)
            if sentence_count < 2:
                continue
            mean = sum(document.sentence_word_counts) / sentence_count
            if mean <= 0:
                continue
            variance = (
                sum((value - mean) ** 2 for value in document.sentence_word_counts)
                / sentence_count
            )
            negative_cv_values.append(math.sqrt(variance) / mean)

        min_sentences = clamp_int(
            math.ceil(
                fit_threshold_high_contrastive(
                    default_value=float(
                        clamp_int(percentile_floor(positive_sentence_counts, 0.25), 2, 200)
                    ),
                    positive_values=positive_sentence_counts,
                    negative_values=negative_sentence_counts,
                    lower=2.0,
                    upper=200.0,
                    positive_quantile=0.25,
                    negative_quantile=0.75,
                    blend_pivot=28.0,
                    match_mode="ge",
                )
            ),
            2,
            200,
        )
        cv_threshold = fit_threshold_low_contrastive(
            default_value=self.config.cv_threshold,
            positive_values=positive_cv_values or [self.config.cv_threshold],
            negative_values=negative_cv_values,
            lower=0.05,
            upper=2.0,
            positive_quantile=0.10,
            negative_quantile=0.90,
            blend_pivot=20.0,
            match_mode="lt",
        )
        positive_matches = sum(1 for value in positive_cv_values if value < cv_threshold)
        negative_matches = sum(1 for value in negative_cv_values if value < cv_threshold)
        penalty = fit_penalty_contrastive(
            base_penalty=self.config.penalty,
            positive_matches=positive_matches,
            positive_total=len(positive_samples),
            negative_matches=negative_matches,
            negative_total=len(negative_samples),
        )

        return RhythmRuleConfig(
            min_sentences=min_sentences,
            cv_threshold=cv_threshold,
            penalty=penalty,
        )
