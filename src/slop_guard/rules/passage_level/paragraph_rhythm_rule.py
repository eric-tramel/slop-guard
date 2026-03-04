"""Detect suspiciously uniform paragraph lengths.

Objective: Measure paragraph-length variance across a passage and flag texts
whose paragraph rhythm is too uniform, a common artifact of generated prose.
Two complementary rules are provided:

  ParagraphBalanceRule  -  fires when the shortest body paragraph is more than
      a configured fraction of the longest (min/max ratio too high).

  ParagraphCVRule  -  fires when the coefficient of variation of all paragraph
      word-counts falls below a threshold (low spread = formulaic rhythm).

Example Rule Violations:
    - A multi-paragraph essay where every paragraph is 40-50 words.
      Both rules would flag the near-identical lengths.

Example Non-Violations:
    - A passage with one two-sentence paragraph and one eight-sentence sprawl.
      The high length variance passes both rules cleanly.

Severity: Low to medium; stronger when combined with other rhythm signals.
"""


import math
import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import fit_penalty_contrastive


_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


def _paragraph_word_counts(text: str) -> list[int]:
    """Split text on blank lines and return word counts per paragraph."""
    return [
        len(p.split())
        for p in _PARAGRAPH_SPLIT_RE.split(text)
        if p.strip()
    ]


# ---------------------------------------------------------------------------
# ParagraphBalanceRule
# ---------------------------------------------------------------------------


@dataclass
class ParagraphBalanceRuleConfig(RuleConfig):
    """Config for paragraph balance ratio detection."""

    min_body_paragraphs: int
    balance_threshold: float
    penalty: int


class ParagraphBalanceRule(Rule[ParagraphBalanceRuleConfig]):
    """Flag passages whose body paragraphs are suspiciously similar in length.

    Computes min/max ratio of body-paragraph word counts.  A ratio above
    the threshold means paragraphs are too evenly sized.
    """

    name = "paragraph_balance"
    count_key = "paragraph_balance"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger paragraph balance matches."""
        para = " ".join(["word"] * 40)
        return ["\n\n".join([para] * 5)]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid paragraph balance matches."""
        short = "word " * 10
        long_ = "word " * 80
        return [f"{short}\n\n{long_}\n\n{short}"]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute min/max balance ratio across body paragraphs."""
        lengths = _paragraph_word_counts(document.text)
        # Body paragraphs = everything after the first
        if len(lengths) < self.config.min_body_paragraphs + 1:
            return RuleResult()

        body = lengths[1:]
        max_len = max(body)
        if max_len == 0:
            return RuleResult()

        ratio = min(body) / max_len
        if ratio <= self.config.balance_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="paragraph_balance",
                    context=(
                        f"Body paragraph word counts {body} - "
                        f"balance ratio {ratio:.2f} "
                        f"(> {self.config.balance_threshold})"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Body paragraphs are suspiciously uniform in length "
                f"(ratio {ratio:.2f}). Vary paragraph sizes - "
                "some should be two sentences, some should sprawl."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ParagraphBalanceRuleConfig:
        """Fit penalty from paragraph balance prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_balance(sample: str) -> bool:
            lengths = _paragraph_word_counts(sample)
            if len(lengths) < self.config.min_body_paragraphs + 1:
                return False
            body = lengths[1:]
            max_len = max(body)
            return max_len > 0 and min(body) / max_len > self.config.balance_threshold

        positive_matches = sum(1 for s in positive_samples if has_balance(s))
        negative_matches = sum(1 for s in negative_samples if has_balance(s))
        return ParagraphBalanceRuleConfig(
            min_body_paragraphs=self.config.min_body_paragraphs,
            balance_threshold=self.config.balance_threshold,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
        )


# ---------------------------------------------------------------------------
# ParagraphCVRule
# ---------------------------------------------------------------------------


@dataclass
class ParagraphCVRuleConfig(RuleConfig):
    """Config for paragraph length coefficient-of-variation detection."""

    min_paragraphs: int
    cv_threshold: float
    penalty: int


class ParagraphCVRule(Rule[ParagraphCVRuleConfig]):
    """Flag passages whose paragraph lengths have low coefficient of variation.

    CV = std / mean across all paragraph word-counts.  A low CV means all
    paragraphs are nearly the same length - a formulaic AI rhythm tell.
    """

    name = "paragraph_cv"
    count_key = "paragraph_cv"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger paragraph CV matches."""
        para = " ".join(["word"] * 35)
        return ["\n\n".join([para] * 6)]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid paragraph CV matches."""
        paras = [
            "word " * 8,
            "word " * 60,
            "word " * 12,
            "word " * 55,
            "word " * 5,
        ]
        return ["\n\n".join(paras)]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute paragraph-length CV and emit a violation if low."""
        lengths = _paragraph_word_counts(document.text)
        if len(lengths) < self.config.min_paragraphs:
            return RuleResult()

        mean = sum(lengths) / len(lengths)
        if mean <= 0:
            return RuleResult()

        variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        cv = math.sqrt(variance) / mean
        if cv >= self.config.cv_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="paragraph_cv",
                    context=(
                        f"Paragraph length CV={cv:.2f} "
                        f"(< {self.config.cv_threshold:.2f}) "
                        f"across lengths {lengths}"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Paragraph lengths are too uniform (CV={cv:.2f}). "
                "Mix short punchy paragraphs with longer developed ones."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ParagraphCVRuleConfig:
        """Fit penalty from paragraph CV prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_low_cv(sample: str) -> bool:
            lengths = _paragraph_word_counts(sample)
            if len(lengths) < self.config.min_paragraphs:
                return False
            mean = sum(lengths) / len(lengths)
            if mean <= 0:
                return False
            variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
            return math.sqrt(variance) / mean < self.config.cv_threshold

        positive_matches = sum(1 for s in positive_samples if has_low_cv(s))
        negative_matches = sum(1 for s in negative_samples if has_low_cv(s))
        return ParagraphCVRuleConfig(
            min_paragraphs=self.config.min_paragraphs,
            cv_threshold=self.config.cv_threshold,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
        )
