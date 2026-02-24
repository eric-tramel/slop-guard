"""Detect unfinished placeholder markers.

Objective: Catch template remnants (for example bracketed TODO or insert text)
that indicate the draft is incomplete or programmatically scaffolded.

Example Rule Violations:
    - "[insert source citation]"
      Placeholder was left unresolved in final prose.
    - "Contact: [your email here]"
      Template token is present instead of real content.

Example Non-Violations:
    - "Contact: security@example.com"
      Real value is present and complete.
    - "The appendix lists all citations."
      No unresolved placeholder syntax.

Severity: High for publication quality; placeholders are explicit unfinished
content and should generally be fixed before release.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import fit_penalty

_PLACEHOLDER_RE = re.compile(
    r"\[insert [^\]]*\]|\[describe [^\]]*\]|\[url [^\]]*\]|\[your [^\]]*\]|\[todo[^\]]*\]",
    re.IGNORECASE,
)


@dataclass
class PlaceholderRuleConfig(RuleConfig):
    """Config for placeholder text detection."""

    penalty: int
    context_window_chars: int


class PlaceholderRule(Rule[PlaceholderRuleConfig]):
    """Detect bracketed placeholders that indicate unfinished drafts."""

    name = "placeholder"
    count_key = "placeholder"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger placeholder matches."""
        return [
            "[insert source citation] before publishing.",
            "Contact: [your email here]",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid placeholder matches."""
        return [
            "Contact: security@example.com",
            "The appendix lists all citations.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply placeholder regex checks to the text."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for match in _PLACEHOLDER_RE.finditer(document.text):
            value = match.group(0).lower()
            violations.append(
                Violation(
                    rule=self.name,
                    match=value,
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
                f"Remove placeholder '{value}' \u2014 this is unfinished template text."
            )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> PlaceholderRuleConfig:
        """Fit penalty from unresolved placeholder prevalence."""
        fit_samples = self._select_fit_samples(samples, labels)
        if not fit_samples:
            return self.config
        matched_documents = sum(
            1 for sample in fit_samples if _PLACEHOLDER_RE.search(sample) is not None
        )
        return PlaceholderRuleConfig(
            penalty=fit_penalty(
                self.config.penalty, matched_documents, len(fit_samples)
            ),
            context_window_chars=self.config.context_window_chars,
        )
