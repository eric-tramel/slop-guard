"""Detect short evaluative pivot fragments.

Objective: Flag very short sentences that pivot with conjunctions ("but", "yet",
"and") in a punchy evaluative style that can resemble assistant phrasing.

Example Rule Violations:
    - "Simple, but powerful."
      Short evaluative fragment with pivot conjunction.
    - "Fast, yet reliable."
      Compact slogan-like pivot pattern.

Example Non-Violations:
    - "The service is simple to run but expensive at peak load."
      Full sentence with concrete tradeoff detail.
    - "It is fast and reliable in this benchmark."
      Plain claim without fragment-style punch line.

Severity: Low to medium; mostly stylistic alone, stronger when clustered.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    clamp_int,
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_low_contrastive,
)

_PITHY_PIVOT_RE = re.compile(r",\s+(?:but|yet|and|not|or)\b", re.IGNORECASE)


@dataclass
class PithyFragmentRuleConfig(RuleConfig):
    """Config for pithy fragment thresholds."""

    penalty: int
    max_sentence_words: int
    record_cap: int


class PithyFragmentRule(Rule[PithyFragmentRuleConfig]):
    """Detect short sentence fragments that pivot evaluatively."""

    name = "pithy_fragment"
    count_key = "pithy_fragment"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger pithy-fragment matches."""
        return [
            "Simple, but powerful.",
            "Fast, yet reliable.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid pithy-fragment matches."""
        return [
            "The service is simple to run but expensive at peak load.",
            "It is fast and reliable in this benchmark.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Scan sentence list for pithy pivot signatures."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for sentence_text, sentence_words in zip(
            document.sentences, document.sentence_word_counts
        ):
            if sentence_words > self.config.max_sentence_words:
                continue
            if _PITHY_PIVOT_RE.search(sentence_text) is None:
                continue

            if count < self.config.record_cap:
                violations.append(
                    Violation(
                        rule=self.name,
                        match=sentence_text,
                        context=sentence_text,
                        penalty=self.config.penalty,
                    )
                )
                advice.append(
                    f"'{sentence_text}' \u2014 pithy evaluative fragments are a Claude tell. "
                    "Expand or cut."
                )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> PithyFragmentRuleConfig:
        """Fit pithy fragment thresholds from corpus sentence patterns."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_lengths: list[int] = []
        positive_counts: list[int] = []
        for sample in positive_samples:
            document = AnalysisDocument.from_text(sample)
            sample_count = 0
            for sentence_text, sentence_words in zip(
                document.sentences, document.sentence_word_counts
            ):
                if _PITHY_PIVOT_RE.search(sentence_text) is None:
                    continue
                positive_lengths.append(sentence_words)
                sample_count += 1
            positive_counts.append(sample_count)

        if not positive_lengths:
            return self.config

        negative_lengths: list[int] = []
        negative_counts: list[int] = []
        for sample in negative_samples:
            document = AnalysisDocument.from_text(sample)
            sample_count = 0
            for sentence_text, sentence_words in zip(
                document.sentences, document.sentence_word_counts
            ):
                if _PITHY_PIVOT_RE.search(sentence_text) is None:
                    continue
                negative_lengths.append(sentence_words)
                sample_count += 1
            negative_counts.append(sample_count)

        max_sentence_words = clamp_int(
            int(
                round(
                    fit_threshold_low_contrastive(
                        default_value=float(self.config.max_sentence_words),
                        positive_values=positive_lengths,
                        negative_values=negative_lengths,
                        lower=2.0,
                        upper=64.0,
                        positive_quantile=0.90,
                        negative_quantile=0.10,
                        blend_pivot=16.0,
                    )
                )
            ),
            2,
            64,
        )
        positive_matches = sum(1 for count in positive_counts if count > 0)
        negative_matches = sum(1 for count in negative_counts if count > 0)

        record_cap = fit_count_cap_contrastive(
            default_value=self.config.record_cap,
            positive_values=[count for count in positive_counts if count > 0],
            negative_values=[count for count in negative_counts if count > 0],
            lower=1,
            upper=64,
            positive_quantile=0.90,
            negative_quantile=0.90,
            blend_pivot=20.0,
        )

        return PithyFragmentRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            max_sentence_words=max_sentence_words,
            record_cap=record_cap,
        )
