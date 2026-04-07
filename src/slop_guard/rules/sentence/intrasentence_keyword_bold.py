"""Detect short, mid-sentence keyword bold spans (LLM emphasis tic).

Objective: Identify ``**short**`` Markdown bold spans appearing inside flowing
prose, used as keyword emphasis. This pattern is a common LLM stylistic tic
where models bold a word or short phrase mid-sentence to mimic glossary or
keyword formatting where none is warranted.

Example Rule Violations:
    - "We need to **carefully consider** all the options before deciding."
      Mid-sentence bold span used as arbitrary keyword emphasis.
    - "The system must remain **highly available** during peak hours."
      Two-word emphasis inserted into otherwise normal prose.

Example Non-Violations:
    - "**Note:** make sure to back up your data first."
      Bold acts as a labeled lead-in at the start of the line.
    - "## A section heading without inline emphasis"
      Markdown heading line with no inline bold.
    - "The release shipped on schedule and the team celebrated."
      Plain prose without any bold formatting.

Severity: Low per instance, medium when repeated frequently in one passage.
"""

import math
import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import TypeAlias

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import (
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
)

_BOLD_SPAN_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
_HEADING_LINE_RE = re.compile(r"^\s*#")
_BLOCKQUOTE_LINE_RE = re.compile(r"^\s*>")
_BULLET_LIKE_LINE_RE = re.compile(r"^\s*[-*]\s|^\s*\d+[.)]\s")
_NUMERIC_BOLD_RE = re.compile(r"^[\s$%€£¥+\-.,]*\d[\s\d.,$%€£¥+\-]*[%a-zA-Z]{0,4}$")
_WORD_TOKEN_RE = re.compile(r"\w+")

KeywordBoldMatch: TypeAlias = tuple[int, int, str]


def _line_start_offsets(text: str) -> tuple[int, ...]:
    """Return cumulative line-start character offsets for ``text``."""
    offsets = [0]
    for index, char in enumerate(text):
        if char == "\n":
            offsets.append(index + 1)
    return tuple(offsets)


def _line_index_for_offset(line_starts: tuple[int, ...], offset: int) -> int:
    """Return the line index whose span contains ``offset``."""
    return max(0, bisect_right(line_starts, offset) - 1)


def _is_excluded_line(line: str) -> bool:
    """Return whether ``line`` is a non-prose context where bold is allowed."""
    return (
        _HEADING_LINE_RE.match(line) is not None
        or _BLOCKQUOTE_LINE_RE.match(line) is not None
        or _BULLET_LIKE_LINE_RE.match(line) is not None
    )


def _is_label_form(inner_text: str) -> bool:
    """Return whether the bold inner text ends in label punctuation.

    The ``**Term:**`` and ``**Term.**`` shapes are already covered by
    :class:`StructuralPatternRule`'s bold-header detection, so this rule must
    not double-count them.
    """
    return inner_text.endswith(":") or inner_text.endswith(".")


def _is_numeric_only(inner_text: str) -> bool:
    """Return whether the bold inner text is purely numeric or unit-tagged."""
    return _NUMERIC_BOLD_RE.match(inner_text) is not None


def _word_count(text: str) -> int:
    """Return the alphanumeric word-token count for ``text``."""
    return len(_WORD_TOKEN_RE.findall(text))


def _collect_keyword_bold_matches(
    document: AnalysisDocument, max_words: int
) -> tuple[KeywordBoldMatch, ...]:
    """Return surviving mid-sentence keyword bold matches.

    Args:
        document: Source document providing text and Markdown projections.
        max_words: Maximum word count of the bold span's inner text.

    Returns:
        Ordered ``(start, end, snippet)`` tuples for spans that pass every
        keyword-bold filter.
    """
    text = document.text
    masked = document.text_with_markdown_code_masked
    line_starts = _line_start_offsets(text)
    survivors: list[KeywordBoldMatch] = []

    for match in _BOLD_SPAN_RE.finditer(masked):
        inner = match.group(1)
        if _is_label_form(inner):
            continue
        if _is_numeric_only(inner):
            continue
        if _word_count(inner) > max_words:
            continue

        start = match.start()
        end = match.end()
        line_index = _line_index_for_offset(line_starts, start)
        line_start_offset = line_starts[line_index]
        line_end_offset = (
            line_starts[line_index + 1] - 1
            if line_index + 1 < len(line_starts)
            else len(text)
        )
        line_text = text[line_start_offset:line_end_offset]
        if _is_excluded_line(line_text):
            continue

        prefix_on_line = text[line_start_offset:start]
        if not prefix_on_line.strip():
            continue

        survivors.append((start, end, text[start:end]))

    return tuple(survivors)


@dataclass
class IntrasentenceKeywordBoldRuleConfig(RuleConfig):
    """Config for the intra-sentence keyword bold detector."""

    penalty: int
    record_cap: int
    advice_min: int
    max_words: int
    context_window_chars: int


class IntrasentenceKeywordBoldRule(Rule[IntrasentenceKeywordBoldRuleConfig]):
    """Detect short Markdown bold spans appearing mid-sentence in prose."""

    name = "intrasentence_keyword_bold"
    count_key = "intrasentence_keyword_bold"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger keyword-bold matches."""
        return [
            "We need to **carefully consider** all the options before deciding.",
            "The system must remain **highly available** during peak hours.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid keyword-bold matches."""
        return [
            "**Note:** make sure to back up your data first.",
            "## A section heading without inline emphasis",
            "The release shipped on schedule and the team celebrated.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply keyword-bold detection and aggregate advice."""
        matches = _collect_keyword_bold_matches(document, self.config.max_words)
        violations: list[Violation] = []
        advice: list[str] = []

        for start, end, snippet in matches[: self.config.record_cap]:
            violations.append(
                Violation(
                    rule=self.name,
                    match=snippet,
                    context=context_around(
                        document.text,
                        start,
                        end,
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.penalty,
                    start=start,
                    end=end,
                )
            )
            advice.append(
                f"Drop the mid-sentence bold around '{snippet}' \u2014 use plain "
                "prose instead of keyword emphasis."
            )

        if len(matches) >= self.config.advice_min:
            advice.append(
                f"{len(matches)} mid-sentence keyword bolds \u2014 stop using "
                "**emphasis** to highlight keywords inside running prose."
            )

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)} if violations else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> IntrasentenceKeywordBoldRuleConfig:
        """Fit cap and penalty from positive vs negative bold prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_counts = [
            len(
                _collect_keyword_bold_matches(
                    AnalysisDocument.from_text(sample), self.config.max_words
                )
            )
            for sample in positive_samples
        ]
        negative_counts = [
            len(
                _collect_keyword_bold_matches(
                    AnalysisDocument.from_text(sample), self.config.max_words
                )
            )
            for sample in negative_samples
        ]
        positive_matches = sum(1 for count in positive_counts if count > 0)
        negative_matches = sum(1 for count in negative_counts if count > 0)
        positive_nonzero = [count for count in positive_counts if count > 0]
        negative_nonzero = [count for count in negative_counts if count > 0]

        record_cap = fit_count_cap_contrastive(
            default_value=self.config.record_cap,
            positive_values=positive_nonzero or [self.config.record_cap],
            negative_values=negative_nonzero,
            lower=1,
            upper=64,
            positive_quantile=0.90,
            negative_quantile=0.75,
            blend_pivot=18.0,
        )
        advice_min = math.ceil(
            fit_threshold_high_contrastive(
                default_value=float(self.config.advice_min),
                positive_values=positive_counts,
                negative_values=negative_counts,
                lower=1.0,
                upper=64.0,
                positive_quantile=0.75,
                negative_quantile=0.25,
                blend_pivot=18.0,
                match_mode="ge",
            )
        )

        return IntrasentenceKeywordBoldRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            record_cap=record_cap,
            advice_min=advice_min,
            max_words=self.config.max_words,
            context_window_chars=self.config.context_window_chars,
        )
