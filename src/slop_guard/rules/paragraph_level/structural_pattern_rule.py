"""Paragraph-level rule detecting listicle-like structural patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_BOLD_HEADER_RE = re.compile(r"\*\*[^*]+[.:]\*\*\s+\S")
_BULLET_LINE_RE = re.compile(r"^(\s*[-*]\s|\s*\d+\.\s)")
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
        for line in document.lines:
            if _BULLET_LINE_RE.match(line):
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
