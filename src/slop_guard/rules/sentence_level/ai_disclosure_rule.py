"""Detect direct AI self-disclosure statements.

Objective: Flag explicit model identity disclosures that may be acceptable in
chat contexts but are usually inappropriate in authored prose deliverables.

Example Rule Violations:
    - "As an AI language model, I cannot browse the web."
      Explicitly discloses model identity and capability limits.
    - "I am just an AI, so I do not have personal experience."
      First-person model disclaimer breaks authorial voice.

Example Non-Violations:
    - "The report uses only the provided dataset."
      States scope directly without AI identity disclosure.
    - "I do not have evidence for that claim."
      Epistemic limitation without model-specific boilerplate.

Severity: High; disclosure phrases are strong and explicit AI-origin signals.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_AI_DISCLOSURE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bas an ai\b", re.IGNORECASE),
    re.compile(r"\bas a language model\b", re.IGNORECASE),
    re.compile(r"\bi don't have personal\b", re.IGNORECASE),
    re.compile(r"\bi cannot browse\b", re.IGNORECASE),
    re.compile(r"\bup to my last training\b", re.IGNORECASE),
    re.compile(r"\bas of my (last |knowledge )?cutoff\b", re.IGNORECASE),
    re.compile(r"\bi'm just an? ai\b", re.IGNORECASE),
)


@dataclass
class AIDisclosureRuleConfig(RuleConfig):
    """Config for AI self-disclosure pattern matching."""

    penalty: int
    context_window_chars: int


class AIDisclosureRule(Rule[AIDisclosureRuleConfig]):
    """Detect AI self-disclosure phrases in authored prose."""

    name = "ai_disclosure"
    count_key = "ai_disclosure"
    level = RuleLevel.SENTENCE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply disclosure regex checks to the text."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for pattern in _AI_DISCLOSURE_PATTERNS:
            for match in pattern.finditer(document.text):
                phrase = match.group(0).lower()
                violations.append(
                    Violation(
                        rule=self.name,
                        match=phrase,
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
                    "Remove "
                    f"'{phrase}' \u2014 AI self-disclosure in authored prose is a critical tell."
                )
                count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
