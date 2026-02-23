"""Detect overuse of horizontal rule separators.

Objective: Flag frequent markdown dividers ("---", "***", "___") that can make
documents look mechanically segmented instead of naturally structured.

Example Rule Violations:
    - Repeated "---" lines between many short sections.
      Divider count exceeds reasonable editorial use.
    - Alternating headers and horizontal rules throughout a brief note.
      Layout feels scaffolded rather than authored.

Example Non-Violations:
    - One divider between two major sections.
      Limited structural use is acceptable.
    - Sectioning done with headings and paragraph transitions only.
      No excessive visual separators.

Severity: Low to medium; mostly a formatting signal unless heavily repeated.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:---+|\*\*\*+|___+)\s*$", re.MULTILINE)


@dataclass
class HorizontalRuleOveruseRuleConfig(RuleConfig):
    """Config for horizontal rule overuse thresholds."""

    min_count: int
    penalty: int


class HorizontalRuleOveruseRule(Rule[HorizontalRuleOveruseRuleConfig]):
    """Detect heavy usage of markdown horizontal rule separators."""

    name = "structural"
    count_key = "horizontal_rules"
    level = RuleLevel.PARAGRAPH

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply horizontal-rule count thresholding."""
        count = len(_HORIZONTAL_RULE_RE.findall(document.text))
        if count < self.config.min_count:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="horizontal_rules",
                    context=f"{count} horizontal rules \u2014 excessive section dividers",
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"{count} horizontal rules \u2014 section headers alone are sufficient, "
                "dividers are a crutch."
            ],
            count_deltas={self.count_key: 1},
        )
