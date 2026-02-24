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
from slop_guard.rules.helpers import clamp_int, fit_penalty, percentile_ceil

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
        fit_samples = self._select_fit_samples(samples, labels)
        if not fit_samples:
            return self.config

        pivot_sentence_lengths: list[int] = []
        per_document_counts: list[int] = []
        for sample in fit_samples:
            document = AnalysisDocument.from_text(sample)
            sample_count = 0
            for sentence_text, sentence_words in zip(
                document.sentences, document.sentence_word_counts
            ):
                if _PITHY_PIVOT_RE.search(sentence_text) is None:
                    continue
                pivot_sentence_lengths.append(sentence_words)
                sample_count += 1
            per_document_counts.append(sample_count)

        matched_documents = sum(1 for count in per_document_counts if count > 0)

        max_sentence_words = self.config.max_sentence_words
        if pivot_sentence_lengths:
            max_sentence_words = clamp_int(
                percentile_ceil(pivot_sentence_lengths, 0.90), 2, 64
            )

        record_cap = self.config.record_cap
        if matched_documents:
            positive_counts = [count for count in per_document_counts if count > 0]
            record_cap = clamp_int(percentile_ceil(positive_counts, 0.90), 1, 64)

        return PithyFragmentRuleConfig(
            penalty=fit_penalty(
                self.config.penalty, matched_documents, len(fit_samples)
            ),
            max_sentence_words=max_sentence_words,
            record_cap=record_cap,
        )
