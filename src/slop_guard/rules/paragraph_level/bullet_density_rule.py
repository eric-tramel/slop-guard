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

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_BULLET_DENSITY_RE = re.compile(r"^\s*[-*]\s|^\s*\d+[.)]\s")


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

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute non-empty line bullet ratio and flag if too high."""
        non_empty_lines = [line for line in document.lines if line.strip()]
        total_non_empty = len(non_empty_lines)
        if total_non_empty <= 0:
            return RuleResult()

        bullet_count = sum(
            1 for line in non_empty_lines if _BULLET_DENSITY_RE.match(line)
        )
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
