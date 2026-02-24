"""Detect direct AI self-disclosure statements.

Objective: Flag explicit model identity disclosures that may be acceptable in
chat contexts but are usually inappropriate in authored prose deliverables.

Example Rule Violations:
    - "As an AI language model, I cannot browse the web."
      Explicitly discloses model identity and capability limits.
    - "I am just an AI, so I do not have personal experience."
      First-person model disclaimer breaks authorial voice.

Example Non-Violations:
    - "The report uses only the provided dataset."
      States scope directly without AI identity disclosure.
    - "I do not have evidence for that claim."
      Epistemic limitation without model-specific boilerplate.

Severity: High; disclosure phrases are strong and explicit AI-origin signals.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import fit_penalty_contrastive

_AI_DISCLOSURE_LITERALS: tuple[str, ...] = (
    "as an ai",
    "as a language model",
    "i don't have personal",
    "i cannot browse",
    "up to my last training",
)
_AI_DISCLOSURE_LITERAL_LENGTHS: tuple[int, ...] = tuple(
    len(phrase) for phrase in _AI_DISCLOSURE_LITERALS
)
_AI_DISCLOSURE_LITERAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(phrase), re.IGNORECASE)
    for phrase in _AI_DISCLOSURE_LITERALS
)
_AI_DISCLOSURE_CUTOFF_RE = re.compile(
    r"\bas of my (last |knowledge )?cutoff\b", re.IGNORECASE
)
_AI_DISCLOSURE_JUST_AI_RE = re.compile(r"\bi'm just an? ai\b", re.IGNORECASE)
_AI_DISCLOSURE_COMPLEX_PATTERNS: tuple[re.Pattern[str], ...] = (
    _AI_DISCLOSURE_CUTOFF_RE,
    _AI_DISCLOSURE_JUST_AI_RE,
)


@dataclass
class AIDisclosureRuleConfig(RuleConfig):
    """Config for AI self-disclosure pattern matching."""

    penalty: int
    context_window_chars: int


class AIDisclosureRule(Rule[AIDisclosureRuleConfig]):
    """Detect AI self-disclosure phrases in authored prose."""

    name = "ai_disclosure"
    count_key = "ai_disclosure"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger AI-disclosure matches."""
        return [
            "As an AI language model, I cannot browse the web.",
            "I'm just an AI, so I do not have personal experience.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid AI-disclosure matches."""
        return [
            "The report uses only the provided dataset.",
            "I do not have evidence for that claim.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply disclosure regex checks to the text."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        if document.text.isascii():
            lower_text = document.lower_text
            for index, phrase in enumerate(_AI_DISCLOSURE_LITERALS):
                phrase_len = _AI_DISCLOSURE_LITERAL_LENGTHS[index]
                start = 0
                while True:
                    hit_start = lower_text.find(phrase, start)
                    if hit_start < 0:
                        break
                    hit_end = hit_start + phrase_len
                    violations.append(
                        Violation(
                            rule=self.name,
                            match=phrase,
                            context=context_around(
                                document.text,
                                hit_start,
                                hit_end,
                                width=self.config.context_window_chars,
                            ),
                            penalty=self.config.penalty,
                        )
                    )
                    advice.append(
                        "Remove "
                        f"'{phrase}' \u2014 AI self-disclosure in authored prose is a critical tell."
                    )
                    count += 1
                    start = hit_end

            if "as of my" in lower_text and "cutoff" in lower_text:
                for match in _AI_DISCLOSURE_CUTOFF_RE.finditer(document.text):
                    phrase = match.group(0).lower()
                    violations.append(
                        Violation(
                            rule=self.name,
                            match=phrase,
                            context=context_around(
                                document.text,
                                match.start(),
                                match.end(),
                                width=self.config.context_window_chars,
                            ),
                            penalty=self.config.penalty,
                        )
                    )
                    advice.append(
                        "Remove "
                        f"'{phrase}' \u2014 AI self-disclosure in authored prose is a critical tell."
                    )
                    count += 1

            if "i'm just a" in lower_text:
                for match in _AI_DISCLOSURE_JUST_AI_RE.finditer(document.text):
                    phrase = match.group(0).lower()
                    violations.append(
                        Violation(
                            rule=self.name,
                            match=phrase,
                            context=context_around(
                                document.text,
                                match.start(),
                                match.end(),
                                width=self.config.context_window_chars,
                            ),
                            penalty=self.config.penalty,
                        )
                    )
                    advice.append(
                        "Remove "
                        f"'{phrase}' \u2014 AI self-disclosure in authored prose is a critical tell."
                    )
                    count += 1
        else:
            for pattern in _AI_DISCLOSURE_LITERAL_PATTERNS:
                for match in pattern.finditer(document.text):
                    phrase = match.group(0).lower()
                    violations.append(
                        Violation(
                            rule=self.name,
                            match=phrase,
                            context=context_around(
                                document.text,
                                match.start(),
                                match.end(),
                                width=self.config.context_window_chars,
                            ),
                            penalty=self.config.penalty,
                        )
                    )
                    advice.append(
                        "Remove "
                        f"'{phrase}' \u2014 AI self-disclosure in authored prose is a critical tell."
                    )
                    count += 1

            for pattern in _AI_DISCLOSURE_COMPLEX_PATTERNS:
                for match in pattern.finditer(document.text):
                    phrase = match.group(0).lower()
                    violations.append(
                        Violation(
                            rule=self.name,
                            match=phrase,
                            context=context_around(
                                document.text,
                                match.start(),
                                match.end(),
                                width=self.config.context_window_chars,
                            ),
                            penalty=self.config.penalty,
                        )
                    )
                    advice.append(
                        "Remove "
                        f"'{phrase}' \u2014 AI self-disclosure in authored prose is a critical tell."
                    )
                    count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> AIDisclosureRuleConfig:
        """Fit penalty from empirical AI-disclosure prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_matches = 0
        for sample in positive_samples:
            lower_text = sample.lower()
            if any(phrase in lower_text for phrase in _AI_DISCLOSURE_LITERALS):
                positive_matches += 1
                continue
            if _AI_DISCLOSURE_CUTOFF_RE.search(sample) is not None:
                positive_matches += 1
                continue
            if _AI_DISCLOSURE_JUST_AI_RE.search(sample) is not None:
                positive_matches += 1

        negative_matches = 0
        for sample in negative_samples:
            lower_text = sample.lower()
            if any(phrase in lower_text for phrase in _AI_DISCLOSURE_LITERALS):
                negative_matches += 1
                continue
            if _AI_DISCLOSURE_CUTOFF_RE.search(sample) is not None:
                negative_matches += 1
                continue
            if _AI_DISCLOSURE_JUST_AI_RE.search(sample) is not None:
                negative_matches += 1

        return AIDisclosureRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
