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


from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, Hyperparameters

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    clamp_int,
    fit_penalty,
    find_repeated_ngrams_from_tokens,
    has_repeated_ngram_prefix,
    percentile_ceil,
    percentile_floor,
)


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

    def example_violations(self) -> list[str]:
        """Return samples that should trigger phrase-reuse matches."""
        return [
            (
                "red blue green yellow red blue green yellow "
                "red blue green yellow"
            ),
            (
                "we deploy with canary rollout we deploy with canary rollout "
                "we deploy with canary rollout"
            ),
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid phrase-reuse matches."""
        return [
            "Each paragraph expresses a related idea with different wording.",
            "The rollout, validation, and recovery sections use distinct phrasing.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Run repeated n-gram detection and emit capped findings."""
        tokens = document.ngram_tokens_lower
        if len(tokens) < self.config.repeated_ngram_min_n:
            return RuleResult()

        if self.config.repeated_ngram_min_n > 1:
            token_ids, base = document.ngram_token_ids_and_base
            has_prefix_repeat = has_repeated_ngram_prefix(
                token_ids=token_ids,
                base=base,
                n=self.config.repeated_ngram_min_n - 1,
                min_count=self.config.repeated_ngram_min_count,
            )
            if not has_prefix_repeat:
                return RuleResult()

        ngram_hyperparameters = Hyperparameters(
            repeated_ngram_min_n=self.config.repeated_ngram_min_n,
            repeated_ngram_max_n=self.config.repeated_ngram_max_n,
            repeated_ngram_min_count=self.config.repeated_ngram_min_count,
        )
        repeated_ngrams = find_repeated_ngrams_from_tokens(tokens, ngram_hyperparameters)
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

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> PhraseReuseRuleConfig:
        """Fit n-gram reuse thresholds from observed repeated phrases."""
        fit_samples = self._select_fit_samples(samples, labels)
        if not fit_samples:
            return self.config

        scan_hp = Hyperparameters(
            repeated_ngram_min_n=2,
            repeated_ngram_max_n=8,
            repeated_ngram_min_count=2,
        )
        observed_n_values: list[int] = []
        observed_counts: list[int] = []
        per_document_hits: list[int] = []
        for sample in fit_samples:
            document = AnalysisDocument.from_text(sample)
            repeated = find_repeated_ngrams_from_tokens(
                document.ngram_tokens_lower, scan_hp
            )
            per_document_hits.append(len(repeated))
            for hit in repeated:
                observed_n_values.append(int(hit["n"]))
                observed_counts.append(int(hit["count"]))

        matched_documents = sum(1 for count in per_document_hits if count > 0)

        repeated_ngram_min_n = self.config.repeated_ngram_min_n
        repeated_ngram_max_n = self.config.repeated_ngram_max_n
        if observed_n_values:
            repeated_ngram_min_n = clamp_int(
                percentile_floor(observed_n_values, 0.20), 2, 12
            )
            repeated_ngram_max_n = clamp_int(
                percentile_ceil(observed_n_values, 0.90), repeated_ngram_min_n, 16
            )

        repeated_ngram_min_count = self.config.repeated_ngram_min_count
        if observed_counts:
            repeated_ngram_min_count = clamp_int(
                percentile_ceil(observed_counts, 0.75), 2, 32
            )

        record_cap = self.config.record_cap
        if matched_documents:
            positive_hit_counts = [count for count in per_document_hits if count > 0]
            record_cap = clamp_int(percentile_ceil(positive_hit_counts, 0.90), 1, 128)

        return PhraseReuseRuleConfig(
            penalty=fit_penalty(
                self.config.penalty, matched_documents, len(fit_samples)
            ),
            record_cap=record_cap,
            repeated_ngram_min_n=repeated_ngram_min_n,
            repeated_ngram_max_n=repeated_ngram_max_n,
            repeated_ngram_min_count=repeated_ngram_min_count,
        )
