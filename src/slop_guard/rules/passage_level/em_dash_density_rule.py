"""Detect overuse of em dashes across a passage.

Objective: Compute em-dash density relative to passage length and flag when
punctuation style becomes a repetitive rhetorical crutch.

Example Rule Violations:
    - "The plan works -- quickly -- and scales -- in production."
      Multiple dash interruptions in a short span.
    - Frequent " -- " or unicode em dash usage above configured density.
      Dash rate exceeds expected prose baseline.

Example Non-Violations:
    - Occasional em dash used once for emphasis in a long section.
      Stylistic punctuation remains moderate.
    - Punctuation primarily uses commas and periods with clear sentence flow.
      No overreliance on dash cadence.

Severity: Low to medium; stylistic alone, but meaningful when persistent.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import clamp_float, fit_penalty, percentile

_EM_DASH_RE = re.compile(r"\u2014| -- ")


@dataclass
class EmDashDensityRuleConfig(RuleConfig):
    """Config for em dash density thresholding."""

    words_basis: float
    density_threshold: float
    penalty: int


class EmDashDensityRule(Rule[EmDashDensityRuleConfig]):
    """Detect high em dash density relative to passage length."""

    name = "em_dash"
    count_key = "em_dash"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger em-dash density matches."""
        return [
            "Alpha -- beta gamma delta epsilon zeta eta theta iota kappa.",
            "This plan — while simple — now works.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid em-dash density matches."""
        return [
            "Punctuation primarily uses commas and periods with clear flow.",
            "Occasional emphasis appears once in longer sections without dash overuse.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute em-dash-per-basis ratio and emit one density violation."""
        if document.word_count <= 0:
            return RuleResult()

        em_dash_count = len(_EM_DASH_RE.findall(document.text))
        ratio_per_basis = (em_dash_count / document.word_count) * self.config.words_basis
        if ratio_per_basis <= self.config.density_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="em_dash_density",
                    context=(
                        f"{em_dash_count} em dashes in {document.word_count} words "
                        f"({ratio_per_basis:.1f} per 150 words)"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Too many em dashes ({em_dash_count} in {document.word_count} words) "
                "\u2014 use other punctuation."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> EmDashDensityRuleConfig:
        """Fit em-dash density threshold from empirical ratios."""
        fit_samples = self._select_fit_samples(samples, labels)
        if not fit_samples:
            return self.config

        ratio_values: list[float] = []
        for sample in fit_samples:
            document = AnalysisDocument.from_text(sample)
            if document.word_count <= 0:
                continue
            em_dash_count = len(_EM_DASH_RE.findall(sample))
            ratio_values.append(
                (em_dash_count / document.word_count) * self.config.words_basis
            )

        if not ratio_values:
            return self.config

        density_threshold = clamp_float(percentile(ratio_values, 0.90), 0.0, 100.0)
        matched_documents = sum(1 for ratio in ratio_values if ratio > density_threshold)

        return EmDashDensityRuleConfig(
            words_basis=self.config.words_basis,
            density_threshold=density_threshold,
            penalty=fit_penalty(
                self.config.penalty, matched_documents, len(ratio_values)
            ),
        )
