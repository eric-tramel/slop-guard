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
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
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
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        scan_hp = Hyperparameters(
            repeated_ngram_min_n=2,
            repeated_ngram_max_n=8,
            repeated_ngram_min_count=2,
        )
        positive_n_values: list[int] = []
        positive_counts: list[int] = []
        positive_per_document_hits: list[int] = []
        for sample in positive_samples:
            document = AnalysisDocument.from_text(sample)
            repeated = find_repeated_ngrams_from_tokens(
                document.ngram_tokens_lower, scan_hp
            )
            positive_per_document_hits.append(len(repeated))
            for hit in repeated:
                positive_n_values.append(int(hit["n"]))
                positive_counts.append(int(hit["count"]))

        if not positive_n_values or not positive_counts:
            return self.config

        negative_n_values: list[int] = []
        negative_counts: list[int] = []
        negative_per_document_hits: list[int] = []
        for sample in negative_samples:
            document = AnalysisDocument.from_text(sample)
            repeated = find_repeated_ngrams_from_tokens(
                document.ngram_tokens_lower, scan_hp
            )
            negative_per_document_hits.append(len(repeated))
            for hit in repeated:
                negative_n_values.append(int(hit["n"]))
                negative_counts.append(int(hit["count"]))

        positive_matches = sum(1 for count in positive_per_document_hits if count > 0)
        negative_matches = sum(1 for count in negative_per_document_hits if count > 0)

        positive_repeated_ngram_min_n = clamp_int(
            percentile_floor(positive_n_values, 0.20), 2, 12
        )
        repeated_ngram_min_n = clamp_int(
            int(
                round(
                    fit_threshold_high_contrastive(
                        default_value=float(positive_repeated_ngram_min_n),
                        positive_values=positive_n_values,
                        negative_values=negative_n_values,
                        lower=2.0,
                        upper=12.0,
                        positive_quantile=0.20,
                        negative_quantile=0.80,
                        blend_pivot=16.0,
                    )
                )
            ),
            2,
            12,
        )
        repeated_ngram_max_n = fit_count_cap_contrastive(
            default_value=clamp_int(
                percentile_ceil(positive_n_values, 0.90), repeated_ngram_min_n, 16
            ),
            positive_values=positive_n_values,
            negative_values=negative_n_values,
            lower=repeated_ngram_min_n,
            upper=16,
            positive_quantile=0.90,
            negative_quantile=0.90,
            blend_pivot=16.0,
        )

        repeated_ngram_min_count = clamp_int(
            int(
                round(
                    fit_threshold_high_contrastive(
                        default_value=float(
                            clamp_int(percentile_ceil(positive_counts, 0.75), 2, 32)
                        ),
                        positive_values=positive_counts,
                        negative_values=negative_counts,
                        lower=2.0,
                        upper=32.0,
                        positive_quantile=0.75,
                        negative_quantile=0.25,
                        blend_pivot=12.0,
                    )
                )
            ),
            2,
            32,
        )

        record_cap = fit_count_cap_contrastive(
            default_value=clamp_int(
                percentile_ceil(
                    [count for count in positive_per_document_hits if count > 0], 0.90
                ),
                1,
                128,
            )
            if positive_matches > 0
            else self.config.record_cap,
            positive_values=[count for count in positive_per_document_hits if count > 0],
            negative_values=[count for count in negative_per_document_hits if count > 0],
            lower=1,
            upper=128,
            positive_quantile=0.90,
            negative_quantile=0.90,
            blend_pivot=20.0,
        )

        return PhraseReuseRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            record_cap=record_cap,
            repeated_ngram_min_n=repeated_ngram_min_n,
            repeated_ngram_max_n=repeated_ngram_max_n,
            repeated_ngram_min_count=repeated_ngram_min_count,
        )
