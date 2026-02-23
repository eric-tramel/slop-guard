"""Detect runs of bullets that start with bold terms.

Objective: Identify repeated list entries in the pattern "- **Term** ...",
which often appears in assistant-generated listicle formatting.

Example Rule Violations:
    - "- **Reliability** ...\\n- **Scalability** ...\\n- **Security** ..."
      Consecutive bold-term bullets create rigid templated structure.
    - Numbered items where each starts with a bold label.
      Repetitive lead-term pattern dominates the section.

Example Non-Violations:
    - A short list with plain bullet text and no bold lead labels.
      List exists without the specific template shape.
    - Paragraph text with occasional inline bold for emphasis.
      Bold usage is not tied to repetitive bullet starts.

Severity: Medium to high when long runs appear in the same section.
"""

from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel


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
        for is_bold_term_bullet in document.line_is_bold_term_bullet:
            if is_bold_term_bullet:
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
