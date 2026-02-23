"""Paragraph-level rule detecting excessive thesis-style blockquotes."""

from __future__ import annotations

from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel


@dataclass
class BlockquoteDensityRuleConfig(RuleConfig):
    """Config for blockquote overuse detection."""

    min_lines: int
    free_lines: int
    cap: int
    penalty_step: int


class BlockquoteDensityRule(Rule[BlockquoteDensityRuleConfig]):
    """Detect frequent blockquote lines outside fenced code blocks."""

    name = "structural"
    count_key = "blockquote_density"
    level = RuleLevel.PARAGRAPH

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute blockquote density and apply capped penalty scaling."""
        in_code_block = False
        blockquote_count = 0

        for line in document.lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if not in_code_block and line.startswith(">"):
                blockquote_count += 1

        if blockquote_count < self.config.min_lines:
            return RuleResult()

        excess = blockquote_count - self.config.free_lines
        capped = min(excess, self.config.cap)
        penalty = self.config.penalty_step * capped

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="blockquote_density",
                    context=(
                        f"{blockquote_count} blockquote lines \u2014 Claude uses these "
                        "as thesis statements"
                    ),
                    penalty=penalty,
                )
            ],
            advice=[
                f"{blockquote_count} blockquotes \u2014 integrate key claims into prose "
                "instead of pulling them out as blockquotes."
            ],
            count_deltas={self.count_key: 1},
        )
