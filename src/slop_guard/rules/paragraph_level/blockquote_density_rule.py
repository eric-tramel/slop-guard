"""Detect excessive thesis-style blockquote usage.

Objective: Flag frequent blockquote lines used as stand-alone thesis statements
outside code fences, a pattern common in templated assistant markdown.

Example Rule Violations:
    - Multiple consecutive lines starting with ">" for key arguments.
      Heavy quote styling replaces integrated prose argumentation.
    - Repeated pull-quote sections throughout a short document.
      Presentation style becomes formulaic.

Example Non-Violations:
    - One short quotation used to cite a source.
      Quote usage is limited and justified.
    - Code blocks and normal paragraphs without blockquote overuse.
      Structural emphasis remains balanced.

Severity: Medium; usually indicates a style issue rather than factual error.
"""


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

    def example_violations(self) -> list[str]:
        """Return samples that should trigger blockquote-density matches."""
        return [
            "> Claim one\n> Claim two\n> Claim three\nRegular line.",
            "Lead.\n> Thesis one\n> Thesis two\n> Thesis three",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid blockquote-density matches."""
        return [
            "> One quote line\n> Second quote line\nThen regular prose.",
            "Normal prose paragraph with no blockquote overuse.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute blockquote density and apply capped penalty scaling."""
        in_code_block = False
        blockquote_count = 0

        for line, is_blockquote in zip(document.lines, document.line_is_blockquote):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if not in_code_block and is_blockquote:
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
