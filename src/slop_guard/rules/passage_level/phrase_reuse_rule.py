"""Passage-level rule detecting repeated long n-gram phrases."""

from __future__ import annotations

from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, Hyperparameters

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import find_repeated_ngrams


@dataclass
class PhraseReuseRuleConfig(RuleConfig):
    """Config for phrase-reuse detection and recording."""

    penalty: int
    record_cap: int
    repeated_ngram_min_n: int
    repeated_ngram_max_n: int
    repeated_ngram_min_count: int


class PhraseReuseRule(Rule[PhraseReuseRuleConfig]):
    """Detect repeated multi-word phrases that signal formulaic output."""

    name = "phrase_reuse"
    count_key = "phrase_reuse"
    level = RuleLevel.PASSAGE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Run repeated n-gram detection and emit capped findings."""
        ngram_hyperparameters = Hyperparameters(
            repeated_ngram_min_n=self.config.repeated_ngram_min_n,
            repeated_ngram_max_n=self.config.repeated_ngram_max_n,
            repeated_ngram_min_count=self.config.repeated_ngram_min_count,
        )

        repeated_ngrams = find_repeated_ngrams(document.text, ngram_hyperparameters)
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for ngram in repeated_ngrams:
            if count >= self.config.record_cap:
                break

            phrase = str(ngram["phrase"])
            n_value = int(ngram["n"])
            phrase_count = int(ngram["count"])
            violations.append(
                Violation(
                    rule=self.name,
                    match=phrase,
                    context=f"'{phrase}' ({n_value}-word phrase) appears {phrase_count} times",
                    penalty=self.config.penalty,
                )
            )
            advice.append(
                f"'{phrase}' appears {phrase_count} times \u2014 vary your phrasing to avoid repetition."
            )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
