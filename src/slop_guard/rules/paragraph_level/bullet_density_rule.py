"""Detect bullet-heavy document formatting.

Objective: Measure whether non-empty lines are dominated by bullets, which can
signal list-first AI drafting instead of cohesive prose development.

Example Rule Violations:
    - A section where most lines begin with "-", "*", or numbered bullets.
      High bullet ratio indicates list dominance.
    - A long checklist with minimal paragraph text.
      Formatting overwhelms narrative flow.

Example Non-Violations:
    - One short bullet list embedded in otherwise normal prose.
      Bullets are used sparingly for clarity.
    - Paragraph-only explanatory text.
      No list dominance.

Severity: Medium to high depending on how much of the passage is list-form.
"""

from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
)


@dataclass
class BulletDensityRuleConfig(RuleConfig):
    """Config for bullet density thresholds."""

    ratio_threshold: float
    penalty: int


class BulletDensityRule(Rule[BulletDensityRuleConfig]):
    """Detect documents dominated by bullet-formatted lines."""

    name = "structural"
    count_key = "bullet_density"
    level = RuleLevel.PARAGRAPH

    def example_violations(self) -> list[str]:
        """Return samples that should trigger bullet-density matches."""
        return [
            "- first item\n- second item\nContext line.",
            "1) alpha\n2) beta\n3) gamma\nSummary.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid bullet-density matches."""
        return [
            "Intro line.\n- one bullet\nDetails continue here.\nClosing line.",
            "Paragraph-only explanatory text with no list dominance.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute non-empty line bullet ratio and flag if too high."""
        total_non_empty = len(document.non_empty_lines)
        if total_non_empty <= 0:
            return RuleResult()

        bullet_count = document.non_empty_bullet_count
        bullet_ratio = bullet_count / total_non_empty
        if bullet_ratio <= self.config.ratio_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="bullet_density",
                    context=(
                        f"{bullet_count} of {total_non_empty} non-empty lines are bullets "
                        f"({bullet_ratio:.0%})"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Over {bullet_ratio:.0%} of lines are bullets \u2014 write prose instead of lists."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> BulletDensityRuleConfig:
        """Fit bullet-density threshold from corpus line ratios."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_ratios: list[float] = []
        for sample in positive_samples:
            document = AnalysisDocument.from_text(sample)
            total_non_empty = len(document.non_empty_lines)
            if total_non_empty <= 0:
                continue
            positive_ratios.append(document.non_empty_bullet_count / total_non_empty)

        if not positive_ratios:
            return self.config

        negative_ratios: list[float] = []
        for sample in negative_samples:
            document = AnalysisDocument.from_text(sample)
            total_non_empty = len(document.non_empty_lines)
            if total_non_empty <= 0:
                continue
            negative_ratios.append(document.non_empty_bullet_count / total_non_empty)

        ratio_threshold = fit_threshold_high_contrastive(
            default_value=self.config.ratio_threshold,
            positive_values=positive_ratios,
            negative_values=negative_ratios,
            lower=0.0,
            upper=1.0,
            positive_quantile=0.90,
            negative_quantile=0.10,
            blend_pivot=18.0,
        )
        positive_matches = sum(1 for ratio in positive_ratios if ratio > ratio_threshold)
        negative_matches = sum(1 for ratio in negative_ratios if ratio > ratio_threshold)

        return BulletDensityRuleConfig(
            ratio_threshold=ratio_threshold,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_ratios),
                negative_matches=negative_matches,
                negative_total=len(negative_ratios),
            ),
        )
