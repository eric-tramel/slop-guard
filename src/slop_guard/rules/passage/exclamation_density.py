"""Detect excessive exclamation marks across a passage.

Objective: Compute exclamation density relative to passage length and flag
when the punctuation rate exceeds the configured threshold (mirrors
``EmDashDensityRule`` and ``ColonDensityRule``).

Example Rule Violations:
    - "We shipped it! It works! Amazing!"
      Three exclamations across 7 words.

Example Non-Violations:
    - "We shipped it. It works. The release closed 12 bugs."
      Period-only punctuation.

Severity: Medium when over threshold; one violation per passage.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import (
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
)

_EXCLAMATION_RE = re.compile(r"!")


@dataclass
class ExclamationDensityRuleConfig(RuleConfig):
    """Config for exclamation-density thresholding."""

    words_basis: float = field(
        metadata={
            "description": (
                "Word count used as the denominator basis for computing "
                "exclamation density (typically 150)."
            )
        }
    )
    density_threshold: float = field(
        metadata={
            "description": (
                "Maximum allowed exclamations per words_basis words; a "
                "density strictly greater than this triggers the violation."
            )
        }
    )
    penalty: int = field(
        metadata={
            "description": (
                "Penalty applied once when exclamation density exceeds "
                "density_threshold."
            )
        }
    )


class ExclamationDensityRule(Rule[ExclamationDensityRuleConfig]):
    """Detect high exclamation density relative to passage length."""

    name = "exclamation_density"
    count_key = "exclamation_density"
    level = RuleLevel.PASSAGE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger exclamation-density matches."""
        return [
            "We shipped it! It works! Amazing!",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid exclamation-density matches."""
        return [
            "We shipped it. It works. The release closed 12 bugs.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute exclamation-per-basis ratio and emit one density violation."""
        word_count = document.word_count_without_code_blocks
        if word_count <= 0:
            return RuleResult()

        exclamation_count = len(
            _EXCLAMATION_RE.findall(document.text_without_code_blocks)
        )
        ratio_per_basis = (exclamation_count / word_count) * self.config.words_basis
        if ratio_per_basis <= self.config.density_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="exclamation_density",
                    context=(
                        f"{exclamation_count} exclamations in {word_count} words "
                        f"({ratio_per_basis:.1f} per {int(self.config.words_basis)} words)"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Too many exclamation marks ({exclamation_count} in {word_count} words) — "
                "let the content carry the emphasis."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ExclamationDensityRuleConfig:
        """Fit exclamation density threshold from empirical ratios."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def ratio(sample: str) -> float | None:
            doc = AnalysisDocument.from_text(sample)
            wc = doc.word_count_without_code_blocks
            if wc <= 0:
                return None
            count = len(_EXCLAMATION_RE.findall(doc.text_without_code_blocks))
            return (count / wc) * self.config.words_basis

        positive_ratios = [
            r for sample in positive_samples if (r := ratio(sample)) is not None
        ]
        if not positive_ratios:
            return self.config
        negative_ratios = [
            r for sample in negative_samples if (r := ratio(sample)) is not None
        ]

        density_threshold = fit_threshold_high_contrastive(
            default_value=self.config.density_threshold,
            positive_values=positive_ratios,
            negative_values=negative_ratios,
            lower=0.0,
            upper=100.0,
            positive_quantile=0.90,
            negative_quantile=0.10,
            blend_pivot=5.0,
        )
        positive_matches = sum(1 for r in positive_ratios if r > density_threshold)
        negative_matches = sum(1 for r in negative_ratios if r > density_threshold)

        return ExclamationDensityRuleConfig(
            words_basis=self.config.words_basis,
            density_threshold=density_threshold,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_ratios),
                negative_matches=negative_matches,
                negative_total=len(negative_ratios),
            ),
        )
