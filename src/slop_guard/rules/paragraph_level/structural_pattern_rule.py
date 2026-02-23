"""Detect listicle-like structural patterns in paragraphs.

Objective: Capture structural tics such as repeated bold lead-ins, long bullet
runs, and triadic cadence that can make prose read like templated output.

Example Rule Violations:
    - "**Problem:** ... **Solution:** ... **Result:** ..."
      Repeated bold-header blocks produce rigid listicle framing.
    - "Reliable, scalable, and maintainable."
      Triadic pattern used repeatedly creates synthetic cadence.

Example Non-Violations:
    - "The section opens with one heading followed by normal paragraphs."
      Uses structure, but not repetitive patterning.
    - "The system is reliable and maintainable at this workload."
      Natural phrasing without triadic slogan cadence.

Severity: Medium to high when multiple structural signals co-occur.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_BOLD_HEADER_RE = re.compile(r"\*\*[^*]+[.:]\*\*\s+\S")
_TRIADIC_RE = re.compile(r"\w+, \w+, and \w+", re.IGNORECASE)


@dataclass
class StructuralPatternRuleConfig(RuleConfig):
    """Config for listicle-like structural pattern thresholds."""

    bold_header_min: int
    bold_header_penalty: int
    bullet_run_min: int
    bullet_run_penalty: int
    triadic_record_cap: int
    triadic_penalty: int
    triadic_advice_min: int
    context_window_chars: int


class StructuralPatternRule(Rule[StructuralPatternRuleConfig]):
    """Detect bold-header blocks, long bullet runs, and triadic cadence."""

    name = "structural"
    count_key = "structural"
    level = RuleLevel.PARAGRAPH

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply structural pattern checks across lines and full text."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        bold_matches = list(_BOLD_HEADER_RE.finditer(document.text))
        if len(bold_matches) >= self.config.bold_header_min:
            violations.append(
                Violation(
                    rule=self.name,
                    match="bold_header_explanation",
                    context=f"Found {len(bold_matches)} instances of **Bold.** pattern",
                    penalty=self.config.bold_header_penalty,
                )
            )
            advice.append(
                f"Vary paragraph structure \u2014 {len(bold_matches)} bold-header-explanation "
                "blocks in a row reads as LLM listicle."
            )
            count += 1

        run_length = 0
        for is_bullet in document.line_is_bullet:
            if is_bullet:
                run_length += 1
                continue

            if run_length >= self.config.bullet_run_min:
                violations.append(
                    Violation(
                        rule=self.name,
                        match="excessive_bullets",
                        context=f"Run of {run_length} consecutive bullet lines",
                        penalty=self.config.bullet_run_penalty,
                    )
                )
                advice.append(
                    f"Consider prose instead of this {run_length}-item bullet list."
                )
                count += 1
            run_length = 0

        if run_length >= self.config.bullet_run_min:
            violations.append(
                Violation(
                    rule=self.name,
                    match="excessive_bullets",
                    context=f"Run of {run_length} consecutive bullet lines",
                    penalty=self.config.bullet_run_penalty,
                )
            )
            advice.append(
                f"Consider prose instead of this {run_length}-item bullet list."
            )
            count += 1

        triadic_matches = list(_TRIADIC_RE.finditer(document.text))
        triadic_count = len(triadic_matches)
        for match in triadic_matches[: self.config.triadic_record_cap]:
            violations.append(
                Violation(
                    rule=self.name,
                    match="triadic",
                    context=context_around(
                        document.text,
                        match.start(),
                        match.end(),
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.triadic_penalty,
                )
            )
            count += 1

        if triadic_count >= self.config.triadic_advice_min:
            advice.append(
                f"{triadic_count} triadic structures ('X, Y, and Z') \u2014 vary your list cadence."
            )

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
