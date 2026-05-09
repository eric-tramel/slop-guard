"""Detect passive voice constructions with a two-tier confidence model.

Objective: Flag passive voice while keeping false positives low. Tier 1
matches the unambiguous "was/were/is/are X by" agent pattern. Tier 2 counts
"be-verb + curated participle" matches and only flags when the document
contains at least ``tier_two_min_hits`` instances (density evidence rather
than a single accidental hit).

Example Rule Violations:
    - "The migration was approved by the architecture council."
      Tier 1: explicit agent makes the passive construction certain.
    - "The cache is invalidated. Logs are dropped. Errors are swallowed."
      Tier 2: three be-verb + participle pairs trip the density gate.

Example Non-Violations:
    - "The architecture council approved the migration."
      Active rewrite of the same claim.
    - "She was born in 1962." / "The pattern is known for X."
      Common false-positive idioms; participles deliberately excluded from
      the tier-2 list.

Severity: Medium per hit; passive voice often hides who did what.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_BE_VERBS = "was|were|is|are|been|being|am|be"

_TIER_ONE_RE = re.compile(
    rf"\b(?:{_BE_VERBS})\s+\w+(?:ed|en)\s+by\b",
    re.IGNORECASE,
)

_TIER_TWO_PARTICIPLES: tuple[str, ...] = (
    "approved",
    "rejected",
    "completed",
    "delivered",
    "executed",
    "deployed",
    "released",
    "shipped",
    "implemented",
    "designed",
    "developed",
    "tested",
    "verified",
    "validated",
    "reviewed",
    "audited",
    "measured",
    "observed",
    "recorded",
    "tracked",
    "monitored",
    "discussed",
    "considered",
    "examined",
    "investigated",
    "analyzed",
    "evaluated",
    "addressed",
    "resolved",
    "fixed",
    "patched",
    "deprecated",
    "removed",
    "replaced",
    "updated",
    "migrated",
    "configured",
    "scheduled",
    "triggered",
    "invoked",
    "invalidated",
    "dropped",
    "swallowed",
    "consumed",
    "produced",
    "generated",
    "computed",
    "rendered",
    "transmitted",
    "decoded",
    "encoded",
    "captured",
)
_TIER_TWO_RE = re.compile(
    rf"\b(?:{_BE_VERBS})\s+(?:" + "|".join(_TIER_TWO_PARTICIPLES) + r")\b",
    re.IGNORECASE,
)


@dataclass
class PassiveVoiceRuleConfig(RuleConfig):
    """Config for two-tier passive-voice detection."""

    penalty: int = field(
        metadata={
            "description": (
                "Penalty applied per tier-1 hit and per tier-2 hit when the "
                "tier-2 minimum-hits gate fires."
            )
        }
    )
    tier_two_min_hits: int = field(
        metadata={
            "description": (
                "Minimum number of tier-2 (be-verb + curated participle) "
                "matches required before any tier-2 violations are emitted."
            )
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each passive-voice violation."
            )
        }
    )


class PassiveVoiceRule(Rule[PassiveVoiceRuleConfig]):
    """Flag passive voice with high-confidence and density-gated tiers."""

    name = "passive_voice"
    count_key = "passive_voice"
    level = RuleLevel.SENTENCE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger passive-voice matches."""
        return [
            "The migration was approved by the architecture council.",
            "The cache is invalidated. Logs are dropped. Errors are swallowed.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid passive-voice matches."""
        return [
            "The architecture council approved the migration.",
            "She was born in 1962.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply tier-1 per-hit detection and gated tier-2 density detection."""
        text = document.text
        violations: list[Violation] = []

        for match in _TIER_ONE_RE.finditer(text):
            violations.append(
                Violation(
                    rule=self.name,
                    match=match.group(0).lower(),
                    context=context_around(
                        text,
                        match.start(),
                        match.end(),
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.penalty,
                    start=match.start(),
                    end=match.end(),
                )
            )

        tier_two_matches = list(_TIER_TWO_RE.finditer(text))
        if len(tier_two_matches) >= self.config.tier_two_min_hits:
            for match in tier_two_matches:
                violations.append(
                    Violation(
                        rule=self.name,
                        match=match.group(0).lower(),
                        context=context_around(
                            text,
                            match.start(),
                            match.end(),
                            width=self.config.context_window_chars,
                        ),
                        penalty=self.config.penalty,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        if not violations:
            return RuleResult()

        advice = ["Rewrite passive clauses in active voice — name who acted on what."]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> PassiveVoiceRuleConfig:
        """Fit penalty from passive-voice prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            if _TIER_ONE_RE.search(sample) is not None:
                return True
            return len(_TIER_TWO_RE.findall(sample)) >= self.config.tier_two_min_hits

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return PassiveVoiceRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            tier_two_min_hits=self.config.tier_two_min_hits,
            context_window_chars=self.config.context_window_chars,
        )
