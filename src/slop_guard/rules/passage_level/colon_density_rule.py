"""Detect elaboration-colon overuse in prose passages.

Objective: Measure colon-heavy elaboration style while ignoring obvious code,
URLs, and metadata patterns that should not count as prose violations.

Example Rule Violations:
    - "Key point: we should retry: then back off: then log."
      Multiple prose colons create a formulaic explanatory cadence.
    - Repeated mid-sentence "X: y..." patterns throughout one passage.
      Elaboration punctuation becomes excessive.

Example Non-Violations:
    - "https://example.com:443" and JSON snippets in code fences.
      Technical colons are excluded from scoring logic.
    - Occasional colon in a heading-like sentence.
      Limited use remains within normal prose style.

Severity: Low to medium; punctuation style signal that compounds with others.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
)

_ELABORATION_COLON_RE = re.compile(r": [a-z]")
_MD_HEADER_LINE_RE = re.compile(r"^\s*#", re.MULTILINE)
_JSON_COLON_RE = re.compile(r': ["{\[\d]|: true|: false|: null')


@dataclass
class ColonDensityRuleConfig(RuleConfig):
    """Config for elaboration-colon density checks."""

    words_basis: float
    density_threshold: float
    penalty: int


class ColonDensityRule(Rule[ColonDensityRuleConfig]):
    """Detect dense elaboration colons outside code and metadata contexts."""

    name = "colon_density"
    count_key = "colon_density"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger colon-density matches."""
        return [
            "Plan: retry quickly. Next: log errors. Finally: alert on failure.",
            "Key idea: reduce retries. Why: fewer cascades.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid colon-density matches."""
        return [
            "The design avoids excessive elaboration punctuation in prose.",
            "See https://example.com:443 for endpoint metadata.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute elaboration-colon density for prose lines."""
        stripped_text = document.text_without_code_blocks
        colon_count = 0

        for line in stripped_text.split("\n"):
            if _MD_HEADER_LINE_RE.match(line):
                continue

            for match in _ELABORATION_COLON_RE.finditer(line):
                colon_pos = match.start()
                before = line[: colon_pos + 1]
                if before.endswith("http:") or before.endswith("https:"):
                    continue
                snippet = line[colon_pos : colon_pos + 10]
                if _JSON_COLON_RE.match(snippet):
                    continue
                colon_count += 1

        stripped_word_count = document.word_count_without_code_blocks
        if stripped_word_count <= 0:
            return RuleResult()

        ratio_per_basis = (colon_count / stripped_word_count) * self.config.words_basis
        if ratio_per_basis <= self.config.density_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="colon_density",
                    context=(
                        f"{colon_count} elaboration colons in {stripped_word_count} words "
                        f"({ratio_per_basis:.1f} per 150 words)"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Too many elaboration colons ({colon_count} in {stripped_word_count} words) "
                "\u2014 use periods or restructure sentences."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ColonDensityRuleConfig:
        """Fit colon density threshold from corpus elaboration ratios."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_ratios: list[float] = []
        for sample in positive_samples:
            document = AnalysisDocument.from_text(sample)
            stripped_text = document.text_without_code_blocks
            stripped_word_count = document.word_count_without_code_blocks
            if stripped_word_count <= 0:
                continue

            colon_count = 0
            for line in stripped_text.split("\n"):
                if _MD_HEADER_LINE_RE.match(line):
                    continue
                for match in _ELABORATION_COLON_RE.finditer(line):
                    colon_pos = match.start()
                    before = line[: colon_pos + 1]
                    if before.endswith("http:") or before.endswith("https:"):
                        continue
                    snippet = line[colon_pos : colon_pos + 10]
                    if _JSON_COLON_RE.match(snippet):
                        continue
                    colon_count += 1

            positive_ratios.append(
                (colon_count / stripped_word_count) * self.config.words_basis
            )

        if not positive_ratios:
            return self.config

        negative_ratios: list[float] = []
        for sample in negative_samples:
            document = AnalysisDocument.from_text(sample)
            stripped_text = document.text_without_code_blocks
            stripped_word_count = document.word_count_without_code_blocks
            if stripped_word_count <= 0:
                continue

            colon_count = 0
            for line in stripped_text.split("\n"):
                if _MD_HEADER_LINE_RE.match(line):
                    continue
                for match in _ELABORATION_COLON_RE.finditer(line):
                    colon_pos = match.start()
                    before = line[: colon_pos + 1]
                    if before.endswith("http:") or before.endswith("https:"):
                        continue
                    snippet = line[colon_pos : colon_pos + 10]
                    if _JSON_COLON_RE.match(snippet):
                        continue
                    colon_count += 1

            negative_ratios.append(
                (colon_count / stripped_word_count) * self.config.words_basis
            )

        density_threshold = fit_threshold_high_contrastive(
            default_value=self.config.density_threshold,
            positive_values=positive_ratios,
            negative_values=negative_ratios,
            lower=0.0,
            upper=100.0,
            positive_quantile=0.90,
            negative_quantile=0.10,
            blend_pivot=18.0,
        )
        positive_matches = sum(1 for ratio in positive_ratios if ratio > density_threshold)
        negative_matches = sum(1 for ratio in negative_ratios if ratio > density_threshold)

        return ColonDensityRuleConfig(
            words_basis=self.config.words_basis,
            density_threshold=density_threshold,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_ratios),
                negative_matches=negative_matches,
                negative_total=len(negative_ratios),
            ),
        )
