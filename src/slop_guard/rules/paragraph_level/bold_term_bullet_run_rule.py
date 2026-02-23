"""Paragraph-level rule detecting runs of bold-term bullets."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_BOLD_TERM_BULLET_RE = re.compile(r"^\s*[-*]\s+\*\*|^\s*\d+[.)]\s+\*\*")


@dataclass
class BoldTermBulletRunRuleConfig(RuleConfig):
    """Config for bold-term bullet run thresholds."""

    min_run_length: int
    penalty: int


class BoldTermBulletRunRule(Rule[BoldTermBulletRunRuleConfig]):
    """Detect long runs of bullets that all start with bold terms."""

    name = "structural"
    count_key = "bold_bullet_list"
    level = RuleLevel.PARAGRAPH

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Track contiguous bold-term bullet runs and emit violations."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        run = 0
        for line in document.lines:
            if _BOLD_TERM_BULLET_RE.match(line):
                run += 1
                continue

            if run >= self.config.min_run_length:
                violations.append(
                    Violation(
                        rule=self.name,
                        match="bold_bullet_list",
                        context=f"Run of {run} bold-term bullets",
                        penalty=self.config.penalty,
                    )
                )
                advice.append(
                    f"Run of {run} bold-term bullets \u2014 this is an LLM listicle pattern. "
                    "Use varied paragraph structure."
                )
                count += 1
            run = 0

        if run >= self.config.min_run_length:
            violations.append(
                Violation(
                    rule=self.name,
                    match="bold_bullet_list",
                    context=f"Run of {run} bold-term bullets",
                    penalty=self.config.penalty,
                )
            )
            advice.append(
                f"Run of {run} bold-term bullets \u2014 this is an LLM listicle pattern. "
                "Use varied paragraph structure."
            )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
