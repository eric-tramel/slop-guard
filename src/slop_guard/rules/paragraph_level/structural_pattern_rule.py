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


import math
import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
)

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

    def example_violations(self) -> list[str]:
        """Return samples that should trigger structural-pattern matches."""
        return [
            "Fast, reliable, and maintainable.",
            "**Problem:** latency\n**Cause:** retries\n**Fix:** batching",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid structural-pattern matches."""
        return [
            "The section opens with one heading followed by normal paragraphs.",
            "The system is reliable and maintainable at this workload.",
        ]

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

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> StructuralPatternRuleConfig:
        """Fit structural thresholds from corpus formatting patterns."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_bold_header_counts: list[int] = []
        positive_triadic_counts: list[int] = []
        positive_bullet_run_lengths: list[int] = []
        positive_bold_documents = 0
        positive_triadic_documents = 0
        positive_bullet_run_documents = 0

        for sample in positive_samples:
            document = AnalysisDocument.from_text(sample)

            bold_count = len(_BOLD_HEADER_RE.findall(sample))
            positive_bold_header_counts.append(bold_count)
            if bold_count > 0:
                positive_bold_documents += 1

            triadic_count = len(_TRIADIC_RE.findall(sample))
            positive_triadic_counts.append(triadic_count)
            if triadic_count > 0:
                positive_triadic_documents += 1

            run = 0
            has_run = False
            for is_bullet in (*document.line_is_bullet, False):
                if is_bullet:
                    run += 1
                    continue
                if run > 0:
                    positive_bullet_run_lengths.append(run)
                    has_run = True
                    run = 0
            if has_run:
                positive_bullet_run_documents += 1

        negative_bold_header_counts: list[int] = []
        negative_triadic_counts: list[int] = []
        negative_bullet_run_lengths: list[int] = []
        negative_bold_documents = 0
        negative_triadic_documents = 0
        negative_bullet_run_documents = 0
        for sample in negative_samples:
            document = AnalysisDocument.from_text(sample)

            bold_count = len(_BOLD_HEADER_RE.findall(sample))
            negative_bold_header_counts.append(bold_count)
            if bold_count > 0:
                negative_bold_documents += 1

            triadic_count = len(_TRIADIC_RE.findall(sample))
            negative_triadic_counts.append(triadic_count)
            if triadic_count > 0:
                negative_triadic_documents += 1

            run = 0
            has_run = False
            for is_bullet in (*document.line_is_bullet, False):
                if is_bullet:
                    run += 1
                    continue
                if run > 0:
                    negative_bullet_run_lengths.append(run)
                    has_run = True
                    run = 0
            if has_run:
                negative_bullet_run_documents += 1

        bold_header_min = math.ceil(
            fit_threshold_high_contrastive(
                default_value=float(self.config.bold_header_min),
                positive_values=positive_bold_header_counts,
                negative_values=negative_bold_header_counts,
                lower=1.0,
                upper=128.0,
                positive_quantile=0.90,
                negative_quantile=0.10,
                blend_pivot=18.0,
                match_mode="ge",
            )
        )
        bullet_run_min = math.ceil(
            fit_threshold_high_contrastive(
                default_value=float(self.config.bullet_run_min),
                positive_values=positive_bullet_run_lengths or [self.config.bullet_run_min],
                negative_values=negative_bullet_run_lengths,
                lower=2.0,
                upper=128.0,
                positive_quantile=0.90,
                negative_quantile=0.10,
                blend_pivot=18.0,
                match_mode="ge",
            )
        )

        positive_triadic_nonzero = [count for count in positive_triadic_counts if count > 0]
        negative_triadic_nonzero = [count for count in negative_triadic_counts if count > 0]
        triadic_record_cap = fit_count_cap_contrastive(
            default_value=self.config.triadic_record_cap,
            positive_values=positive_triadic_nonzero or [self.config.triadic_record_cap],
            negative_values=negative_triadic_nonzero,
            lower=1,
            upper=128,
            positive_quantile=0.90,
            negative_quantile=0.75,
            blend_pivot=18.0,
            max_multiplier=2.0,
        )
        triadic_advice_min = math.ceil(
            fit_threshold_high_contrastive(
                default_value=float(self.config.triadic_advice_min),
                positive_values=positive_triadic_counts,
                negative_values=negative_triadic_counts,
                lower=1.0,
                upper=128.0,
                positive_quantile=0.75,
                negative_quantile=0.50,
                blend_pivot=18.0,
                match_mode="ge",
            )
        )

        return StructuralPatternRuleConfig(
            bold_header_min=bold_header_min,
            bold_header_penalty=fit_penalty_contrastive(
                base_penalty=self.config.bold_header_penalty,
                positive_matches=positive_bold_documents,
                positive_total=len(positive_samples),
                negative_matches=negative_bold_documents,
                negative_total=len(negative_samples),
            ),
            bullet_run_min=bullet_run_min,
            bullet_run_penalty=fit_penalty_contrastive(
                base_penalty=self.config.bullet_run_penalty,
                positive_matches=positive_bullet_run_documents,
                positive_total=len(positive_samples),
                negative_matches=negative_bullet_run_documents,
                negative_total=len(negative_samples),
            ),
            triadic_record_cap=triadic_record_cap,
            triadic_penalty=fit_penalty_contrastive(
                base_penalty=self.config.triadic_penalty,
                positive_matches=positive_triadic_documents,
                positive_total=len(positive_samples),
                negative_matches=negative_triadic_documents,
                negative_total=len(negative_samples),
            ),
            triadic_advice_min=triadic_advice_min,
            context_window_chars=self.config.context_window_chars,
        )
