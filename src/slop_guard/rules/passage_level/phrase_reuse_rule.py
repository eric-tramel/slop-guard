"""Detect repeated long n-gram phrase reuse.

Objective: Find multi-word phrases that recur above threshold and keep longest
repeated spans, since repeated long phrasing often indicates template reuse.

Example Rule Violations:
    - Repeating "at the end of the day" many times in one document.
      Same phrase recurs instead of varied expression.
    - Reusing a 4-8 word clause across multiple paragraphs.
      Long repeated n-grams suggest copy-pattern generation.

Example Non-Violations:
    - Repeating short stopword-heavy fragments like "in the end".
      Common function phrases are filtered or suppressed.
    - Using related ideas with different wording across sections.
      Semantic repetition without lexical cloning is acceptable.

Severity: Medium to high; repeated long phrases are strong formulaicity signals.
"""

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
