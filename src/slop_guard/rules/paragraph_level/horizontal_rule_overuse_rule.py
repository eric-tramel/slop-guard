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

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import clamp_int, fit_penalty, percentile_ceil

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

    def example_violations(self) -> list[str]:
        """Return samples that should trigger horizontal-rule matches."""
        return [
            "---\n---\n---\n---\nSection text.",
            "***\n***\n***\n***\nSummary.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid horizontal-rule matches."""
        return [
            "---\n---\n---\nSection text.",
            "Section one.\nSection two.\nNo divider overuse.",
        ]

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

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> HorizontalRuleOveruseRuleConfig:
        """Fit horizontal-rule threshold from corpus separator counts."""
        fit_samples = self._select_fit_samples(samples, labels)
        if not fit_samples:
            return self.config

        counts = [len(_HORIZONTAL_RULE_RE.findall(sample)) for sample in fit_samples]
        min_count = clamp_int(percentile_ceil(counts, 0.90), 1, 64)
        matched_documents = sum(1 for count in counts if count >= min_count)

        return HorizontalRuleOveruseRuleConfig(
            min_count=min_count,
            penalty=fit_penalty(self.config.penalty, matched_documents, len(counts)),
        )
