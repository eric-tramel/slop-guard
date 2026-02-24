"""Detect repeated "X, not Y" contrast constructions.

Objective: Identify overuse of a specific rhetorical pattern where contrast is
presented as "A, not B"; repeated use can make prose feel formulaic.

Example Rule Violations:
    - "This is focus, not frenzy."
      Uses the targeted contrast shape.
    - "It is clarity, not complexity."
      Repeats the same sentence skeleton as a style tic.

Example Non-Violations:
    - "This approach prioritizes focus over speed."
      Contrast exists, but not in the repetitive pattern form.
    - "The design reduces complexity while improving clarity."
      Balanced comparison without slogan-like structure.

Severity: Low per instance, medium when repeated frequently in one passage.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    clamp_int,
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
    percentile_ceil,
)

_CONTRAST_PAIR_RE = re.compile(r"\b(\w+), not (\w+)\b")


@dataclass
class ContrastPairRuleConfig(RuleConfig):
    """Config for contrast pair detection and recording limits."""

    penalty: int
    record_cap: int
    advice_min: int
    context_window_chars: int


class ContrastPairRule(Rule[ContrastPairRuleConfig]):
    """Detect the Claude-style "X, not Y" rhetorical construction."""

    name = "contrast_pair"
    count_key = "contrast_pairs"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger contrast-pair matches."""
        return [
            "This is focus, not frenzy.",
            "It is clarity, not complexity.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid contrast-pair matches."""
        return [
            "This approach prioritizes focus over speed.",
            "The design reduces complexity while improving clarity.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply contrast detection and aggregate advice."""
        matches = list(_CONTRAST_PAIR_RE.finditer(document.text))
        violations: list[Violation] = []
        advice: list[str] = []

        for match in matches[: self.config.record_cap]:
            snippet = match.group(0)
            violations.append(
                Violation(
                    rule=self.name,
                    match=snippet,
                    context=context_around(
                        document.text,
                        match.start(),
                        match.end(),
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.penalty,
                )
            )
            advice.append(
                f"'{snippet}' \u2014 'X, not Y' contrast \u2014 consider rephrasing to avoid the Claude pattern."
            )

        if len(matches) >= self.config.advice_min:
            advice.append(
                f"{len(matches)} 'X, not Y' contrasts \u2014 this is a Claude rhetorical tic. "
                "Vary your phrasing."
            )

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)} if violations else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ContrastPairRuleConfig:
        """Fit match-driven caps and penalties from corpus counts."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_counts = [
            len(_CONTRAST_PAIR_RE.findall(sample)) for sample in positive_samples
        ]
        negative_counts = [
            len(_CONTRAST_PAIR_RE.findall(sample)) for sample in negative_samples
        ]
        positive_matches = sum(1 for count in positive_counts if count > 0)
        negative_matches = sum(1 for count in negative_counts if count > 0)
        positive_nonzero_counts = [count for count in positive_counts if count > 0]
        negative_nonzero_counts = [count for count in negative_counts if count > 0]

        record_cap = fit_count_cap_contrastive(
            default_value=clamp_int(
                percentile_ceil(positive_nonzero_counts, 0.90), 1, 64
            )
            if positive_nonzero_counts
            else self.config.record_cap,
            positive_values=positive_nonzero_counts,
            negative_values=negative_nonzero_counts,
            lower=1,
            upper=64,
            positive_quantile=0.90,
            negative_quantile=0.90,
            blend_pivot=20.0,
        )
        advice_min = clamp_int(
            int(
                round(
                    fit_threshold_high_contrastive(
                        default_value=float(
                            clamp_int(percentile_ceil(positive_counts, 0.75), 1, 64)
                        ),
                        positive_values=positive_counts,
                        negative_values=negative_counts,
                        lower=1.0,
                        upper=64.0,
                        positive_quantile=0.75,
                        negative_quantile=0.25,
                        blend_pivot=16.0,
                    )
                )
            ),
            1,
            64,
        )

        return ContrastPairRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            record_cap=record_cap,
            advice_min=advice_min,
            context_window_chars=self.config.context_window_chars,
        )
