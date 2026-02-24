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

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    blend_toward_default_float,
    clamp_int,
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
    percentile_floor,
)


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

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> BlockquoteDensityRuleConfig:
        """Fit blockquote density thresholds from corpus line counts."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_counts: list[int] = []
        for sample in positive_samples:
            document = AnalysisDocument.from_text(sample)
            in_code_block = False
            blockquote_count = 0
            for line, is_blockquote in zip(document.lines, document.line_is_blockquote):
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if not in_code_block and is_blockquote:
                    blockquote_count += 1
            positive_counts.append(blockquote_count)

        negative_counts: list[int] = []
        for sample in negative_samples:
            document = AnalysisDocument.from_text(sample)
            in_code_block = False
            blockquote_count = 0
            for line, is_blockquote in zip(document.lines, document.line_is_blockquote):
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if not in_code_block and is_blockquote:
                    blockquote_count += 1
            negative_counts.append(blockquote_count)

        min_lines = int(
            fit_threshold_high_contrastive(
                default_value=float(self.config.min_lines),
                positive_values=positive_counts,
                negative_values=negative_counts,
                lower=1.0,
                upper=128.0,
                positive_quantile=0.90,
                negative_quantile=0.10,
                blend_pivot=18.0,
            )
        )
        free_lines = clamp_int(
            int(
                round(
                    blend_toward_default_float(
                        float(self.config.free_lines),
                        float(percentile_floor(positive_counts, 0.50)),
                        len(positive_counts) + len(negative_counts),
                        pivot=20.0,
                    )
                )
            ),
            0,
            max(0, min_lines - 1),
        )
        positive_excess = [max(0, count - free_lines) for count in positive_counts]
        negative_excess = [max(0, count - free_lines) for count in negative_counts]
        cap = fit_count_cap_contrastive(
            default_value=self.config.cap,
            positive_values=positive_excess,
            negative_values=negative_excess,
            lower=1,
            upper=128,
            positive_quantile=0.90,
            negative_quantile=0.75,
            blend_pivot=18.0,
            max_multiplier=2.0,
        )
        positive_matches = sum(1 for count in positive_counts if count >= min_lines)
        negative_matches = sum(1 for count in negative_counts if count >= min_lines)

        return BlockquoteDensityRuleConfig(
            min_lines=min_lines,
            free_lines=free_lines,
            cap=cap,
            penalty_step=fit_penalty_contrastive(
                base_penalty=self.config.penalty_step,
                positive_matches=positive_matches,
                positive_total=len(positive_counts),
                negative_matches=negative_matches,
                negative_total=len(negative_counts),
            ),
        )
