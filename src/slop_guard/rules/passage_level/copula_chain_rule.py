"""Detect high copula-sentence density - an encyclopedic AI chain pattern.

Objective: Flag passages where too many sentences begin with a copula verb
(is/are/was/were), producing the "X is Y. Z is W." alternating chain that AI
models use for comparison or definition text.  Human writers rarely sustain
this pattern at high density across a full passage.

Example Rule Violations:
    - "Python is a language. Lists are mutable. Dicts are mappings. Sets are
      unordered. Tuples are immutable. Generators are lazy."
      Over half the sentences open with a copula verb.

Example Non-Violations:
    - "Python handles this with generators. You can use a list comprehension.
      This avoids materialising the whole sequence."
      Copula density stays well below the threshold.

Severity: Medium; a single passage-level flag with concentrated penalty.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import fit_penalty_contrastive


_COPULA_FIRST_WORDS_RE = re.compile(r"\b(is|are|was|were)\b", re.IGNORECASE)


@dataclass
class CopulaChainRuleConfig(RuleConfig):
    """Config for copula-chain density detection."""

    min_sentences: int
    threshold: float
    penalty: int


class CopulaChainRule(Rule[CopulaChainRuleConfig]):
    """Flag passages where copula-sentence density exceeds the threshold."""

    name = "copula_chain"
    count_key = "copula_chain"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger copula-chain matches."""
        return [
            (
                "Python is a high-level language. Lists are ordered sequences. "
                "Dicts are key-value mappings. Sets are unordered collections. "
                "Tuples are immutable sequences. Generators are lazy iterators."
            ),
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid copula-chain matches."""
        return [
            (
                "Python handles this with generators. You can use a list comprehension. "
                "This avoids materialising the whole sequence. Most of the time that is fine."
            ),
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute copula density and emit a violation if threshold is exceeded."""
        if len(document.sentences) < self.config.min_sentences:
            return RuleResult()

        copula_count = sum(
            1
            for s in document.sentences
            if _COPULA_FIRST_WORDS_RE.search(" ".join(s.split()[:6]))
        )
        density = copula_count / len(document.sentences)
        if density < self.config.threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="copula_density",
                    context=(
                        f"{copula_count}/{len(document.sentences)} sentences "
                        f"({density:.0%}) use a copula within the first 6 words"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Copula density is {density:.0%} - too many 'X is Y' sentences. "
                "Use active verbs or restructure to vary sentence patterns."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> CopulaChainRuleConfig:
        """Fit penalty from copula-chain prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_chain(sample: str) -> bool:
            doc = AnalysisDocument.from_text(sample)
            if len(doc.sentences) < self.config.min_sentences:
                return False
            count = sum(
                1
                for s in doc.sentences
                if _COPULA_FIRST_WORDS_RE.search(" ".join(s.split()[:6]))
            )
            return count / len(doc.sentences) >= self.config.threshold

        positive_matches = sum(1 for s in positive_samples if has_chain(s))
        negative_matches = sum(1 for s in negative_samples if has_chain(s))
        return CopulaChainRuleConfig(
            min_sentences=self.config.min_sentences,
            threshold=self.config.threshold,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
        )
