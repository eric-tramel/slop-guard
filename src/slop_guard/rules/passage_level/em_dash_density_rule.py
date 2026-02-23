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

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

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
