"""Detect setup-resolution rhetorical flips.

Objective: Catch "this is not X, it is Y" sentence choreography that can read
as a repeated assistant rhetorical template when used heavily.

Example Rule Violations:
    - "This is not about tooling. It is about discipline."
      Classic setup then immediate reframing resolution.
    - "It is not random; it is deliberate."
      Same flip pattern with compressed punctuation.

Example Non-Violations:
    - "The problem is tooling and team discipline."
      States both ideas directly without staged reversal.
    - "This approach emphasizes discipline over tooling."
      Comparative statement without setup-resolution cadence.

Severity: Medium; repeated occurrences strongly suggest formulaic generation.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_SETUP_RESOLUTION_A_RE = re.compile(
    r"\b(this|that|these|those|it|they|we)\s+"
    r"(isn't|aren't|wasn't|weren't|doesn't|don't|didn't|hasn't|haven't|won't|can't|couldn't|shouldn't"
    r"|is\s+not|are\s+not|was\s+not|were\s+not|does\s+not|do\s+not|did\s+not"
    r"|has\s+not|have\s+not|will\s+not|cannot|could\s+not|should\s+not)\b"
    r".{0,80}[.;:,]\s*"
    r"(it's|they're|that's|he's|she's|we're|it\s+is|they\s+are|that\s+is|this\s+is"
    r"|these\s+are|those\s+are|he\s+is|she\s+is|we\s+are|what's|what\s+is"
    r"|the\s+real|the\s+actual|instead|rather)",
    re.IGNORECASE,
)

_SETUP_RESOLUTION_B_RE = re.compile(
    r"\b(it's|that's|this\s+is|they're|he's|she's|we're)\s+not\b"
    r".{0,80}[.;:,]\s*"
    r"(it's|they're|that's|he's|she's|we're|it\s+is|they\s+are|that\s+is|this\s+is"
    r"|these\s+are|those\s+are|what's|what\s+is|the\s+real|the\s+actual|instead|rather)",
    re.IGNORECASE,
)


@dataclass
class SetupResolutionRuleConfig(RuleConfig):
    """Config for setup-resolution pattern detection."""

    penalty: int
    record_cap: int
    context_window_chars: int


class SetupResolutionRule(Rule[SetupResolutionRuleConfig]):
    """Detect "This isn't X. It's Y." setup-resolution patterning."""

    name = "setup_resolution"
    count_key = "setup_resolution"
    level = RuleLevel.SENTENCE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply both setup-resolution regex forms."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for pattern in (_SETUP_RESOLUTION_A_RE, _SETUP_RESOLUTION_B_RE):
            for match in pattern.finditer(document.text):
                if len(violations) < self.config.record_cap:
                    matched_text = match.group(0)
                    violations.append(
                        Violation(
                            rule=self.name,
                            match=matched_text,
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
                        f"'{matched_text}' \u2014 setup-and-resolution is a Claude rhetorical tic. "
                        "Just state the point directly."
                    )
                count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
