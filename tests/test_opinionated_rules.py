"""Targeted tests for the opinionated writing rules.

The generic framework test in ``test_rule_framework.py`` already exercises each
rule's ``example_violations`` and ``example_non_violations``. These tests cover
the rule-specific behaviors the generic test cannot: replacement-aware advice,
cap enforcement, density thresholds, the passive-voice tier-two gate, and the
fit paths.
"""

from slop_guard.document import AnalysisDocument
from slop_guard.rules.paragraph.narrative_heading import (
    NarrativeHeadingRule,
    NarrativeHeadingRuleConfig,
)
from slop_guard.rules.passage.emoji_in_prose import (
    EmojiInProseRule,
    EmojiInProseRuleConfig,
)
from slop_guard.rules.passage.exclamation_density import (
    ExclamationDensityRule,
    ExclamationDensityRuleConfig,
)
from slop_guard.rules.passage.long_sentence import (
    LongSentenceRule,
    LongSentenceRuleConfig,
)
from slop_guard.rules.sentence.cliche_phrase import (
    ClichePhraseRule,
    ClichePhraseRuleConfig,
)
from slop_guard.rules.sentence.foreign_phrase import (
    ForeignPhraseRule,
    ForeignPhraseRuleConfig,
)
from slop_guard.rules.sentence.over_explanation import (
    OverExplanationRule,
    OverExplanationRuleConfig,
)
from slop_guard.rules.sentence.passive_voice import (
    PassiveVoiceRule,
    PassiveVoiceRuleConfig,
)
from slop_guard.rules.sentence.redundant_pair import (
    RedundantPairRule,
    RedundantPairRuleConfig,
)
from slop_guard.rules.sentence.throat_clearing import (
    ThroatClearingRule,
    ThroatClearingRuleConfig,
)
from slop_guard.rules.sentence.verbose_phrase import (
    VerbosePhraseRule,
    VerbosePhraseRuleConfig,
)
from slop_guard.rules.word.ecstatic_adjective import (
    EcstaticAdjectiveRule,
    EcstaticAdjectiveRuleConfig,
)
from slop_guard.rules.word.pretentious_word import (
    PretentiousWordRule,
    PretentiousWordRuleConfig,
)
from slop_guard.rules.word.qualifier_word import (
    QualifierWordRule,
    QualifierWordRuleConfig,
)


def _doc(text: str) -> AnalysisDocument:
    """Return an AnalysisDocument for ``text``."""
    return AnalysisDocument.from_text(text)


# Replacements -----------------------------------------------------------------


def test_verbose_phrase_advice_cites_concise_replacement() -> None:
    """Verbose-phrase advice should name the concise replacement."""
    rule = VerbosePhraseRule(
        VerbosePhraseRuleConfig(penalty=-2, context_window_chars=60)
    )
    result = rule.forward(_doc("We migrated in order to reduce cost."))
    assert any("'in order to'" in line and "'to'" in line for line in result.advice)


def test_pretentious_word_advice_cites_plain_replacement() -> None:
    """Pretentious-word advice should name the plain-English replacement."""
    rule = PretentiousWordRule(
        PretentiousWordRuleConfig(penalty=-2, context_window_chars=60)
    )
    result = rule.forward(_doc("We will utilize the new approach."))
    assert any("'utilize'" in line and "'use'" in line for line in result.advice)


def test_foreign_phrase_advice_cites_plain_replacement() -> None:
    """Foreign-phrase advice should name the plain-English replacement."""
    rule = ForeignPhraseRule(
        ForeignPhraseRuleConfig(penalty=-1, context_window_chars=60)
    )
    result = rule.forward(_doc("Per se, the rollout was successful."))
    assert any("'per se'" in line and "'by itself'" in line for line in result.advice)


# Cap and threshold semantics --------------------------------------------------


def test_long_sentence_rule_honors_max_hits_cap() -> None:
    """Long-sentence rule should never emit more than max_hits violations."""
    rule = LongSentenceRule(LongSentenceRuleConfig(min_words=5, max_hits=2, penalty=-2))
    long_sentence = " ".join(["alpha"] * 6) + "."
    text = (long_sentence + " ") * 5
    result = rule.forward(_doc(text))
    assert len(result.violations) == 2


def test_passive_voice_tier_two_gate_requires_min_hits() -> None:
    """Tier-two density should not fire below the configured minimum."""
    rule = PassiveVoiceRule(
        PassiveVoiceRuleConfig(penalty=-2, tier_two_min_hits=3, context_window_chars=60)
    )

    below_threshold = _doc("The migration is approved. The release is shipped.")
    assert rule.forward(below_threshold).violations == []

    at_threshold = _doc(
        "The migration is approved. The release is shipped. Logs are dropped."
    )
    assert len(rule.forward(at_threshold).violations) >= 3


def test_passive_voice_tier_one_fires_per_instance() -> None:
    """Tier-one 'was X by' pattern should fire on every match without gating."""
    rule = PassiveVoiceRule(
        PassiveVoiceRuleConfig(
            penalty=-2, tier_two_min_hits=99, context_window_chars=60
        )
    )
    result = rule.forward(_doc("The plan was approved by the council."))
    assert len(result.violations) == 1


def test_exclamation_density_under_threshold_does_not_fire() -> None:
    """Sub-threshold exclamation density should not emit violations."""
    rule = ExclamationDensityRule(
        ExclamationDensityRuleConfig(
            words_basis=150.0, density_threshold=1.0, penalty=-3
        )
    )
    text = " ".join(["word"] * 200) + "!"
    assert rule.forward(_doc(text)).violations == []


def test_exclamation_density_over_threshold_fires_once() -> None:
    """Above-threshold exclamation density should emit exactly one violation."""
    rule = ExclamationDensityRule(
        ExclamationDensityRuleConfig(
            words_basis=150.0, density_threshold=1.0, penalty=-3
        )
    )
    text = "Wow! Yes! Indeed! Amazing!"
    result = rule.forward(_doc(text))
    assert len(result.violations) == 1


# Per-instance match emission --------------------------------------------------


def test_emoji_in_prose_emits_one_violation_per_emoji() -> None:
    """Emoji rule should emit one violation per emoji character matched."""
    rule = EmojiInProseRule(EmojiInProseRuleConfig(penalty=-3, context_window_chars=60))
    result = rule.forward(
        _doc("We shipped \U0001f680 and the team is happy \U0001f389.")
    )
    assert len(result.violations) == 2


def test_qualifier_word_matches_multi_word_phrases() -> None:
    """Qualifier rule should match multi-word qualifiers like 'sort of'."""
    rule = QualifierWordRule(
        QualifierWordRuleConfig(penalty=-1, context_window_chars=60)
    )
    result = rule.forward(_doc("The result was sort of unclear and a bit late."))
    matches = {violation.match for violation in result.violations}
    assert "sort of" in matches
    assert "a bit" in matches


def test_ecstatic_adjective_matches_hyphenated_terms() -> None:
    """Ecstatic-adjective rule should match hyphenated terms like 'mind-blowing'."""
    rule = EcstaticAdjectiveRule(
        EcstaticAdjectiveRuleConfig(penalty=-1, context_window_chars=60)
    )
    result = rule.forward(_doc("The change was mind-blowing."))
    assert any(violation.match == "mind-blowing" for violation in result.violations)


def test_narrative_heading_matches_markdown_heading_at_any_depth() -> None:
    """Narrative-heading rule should match `##`, `###`, etc. equally."""
    rule = NarrativeHeadingRule(
        NarrativeHeadingRuleConfig(penalty=-4, context_window_chars=60)
    )
    text = "# The Power of caching\n\n### The Art of Indexes\n\nbody text"
    result = rule.forward(_doc(text))
    assert len(result.violations) == 2


def test_redundant_pair_matches_word_boundary() -> None:
    """Redundant-pair rule should require word-boundary matches."""
    rule = RedundantPairRule(
        RedundantPairRuleConfig(penalty=-1, context_window_chars=60)
    )
    result = rule.forward(_doc("The end result was clear."))
    assert any(violation.match == "end result" for violation in result.violations)


def test_cliche_phrase_emits_advice_naming_phrase() -> None:
    """Cliché advice should name the matched phrase explicitly."""
    rule = ClichePhraseRule(ClichePhraseRuleConfig(penalty=-2, context_window_chars=60))
    result = rule.forward(_doc("Let's think outside the box."))
    assert any("think outside the box" in line for line in result.advice)


def test_throat_clearing_advice_names_phrase() -> None:
    """Throat-clearing advice should name the matched phrase explicitly."""
    rule = ThroatClearingRule(
        ThroatClearingRuleConfig(penalty=-2, context_window_chars=60)
    )
    result = rule.forward(_doc("Truth be told, the cache is unused."))
    assert any("truth be told" in line for line in result.advice)


def test_over_explanation_advice_names_phrase() -> None:
    """Over-explanation advice should name the matched phrase explicitly."""
    rule = OverExplanationRule(
        OverExplanationRuleConfig(penalty=-2, context_window_chars=60)
    )
    result = rule.forward(_doc("Needless to say, retries should be idempotent."))
    assert any("needless to say" in line for line in result.advice)


# Fit paths --------------------------------------------------------------------


def test_qualifier_word_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = QualifierWordRule(
        QualifierWordRuleConfig(penalty=-1, context_window_chars=60)
    )
    fitted = rule.fit(["The fix is very fast.", "Throughput rose 3.4x."], [1, 0])
    assert fitted is rule


def test_pretentious_word_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = PretentiousWordRule(
        PretentiousWordRuleConfig(penalty=-2, context_window_chars=60)
    )
    fitted = rule.fit(["Utilize the new method.", "Use the new method."], [1, 0])
    assert fitted is rule


def test_ecstatic_adjective_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = EcstaticAdjectiveRule(
        EcstaticAdjectiveRuleConfig(penalty=-1, context_window_chars=60)
    )
    fitted = rule.fit(["A wonderful release.", "A 12% throughput gain."], [1, 0])
    assert fitted is rule


def test_verbose_phrase_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = VerbosePhraseRule(
        VerbosePhraseRuleConfig(penalty=-2, context_window_chars=60)
    )
    fitted = rule.fit(
        ["We migrated in order to reduce cost.", "We migrated to reduce cost."],
        [1, 0],
    )
    assert fitted is rule


def test_throat_clearing_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = ThroatClearingRule(
        ThroatClearingRuleConfig(penalty=-2, context_window_chars=60)
    )
    fitted = rule.fit(
        ["Truth be told, retries are needed.", "Retries are needed."],
        [1, 0],
    )
    assert fitted is rule


def test_over_explanation_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = OverExplanationRule(
        OverExplanationRuleConfig(penalty=-2, context_window_chars=60)
    )
    fitted = rule.fit(
        ["Needless to say, x.", "x."],
        [1, 0],
    )
    assert fitted is rule


def test_redundant_pair_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = RedundantPairRule(
        RedundantPairRuleConfig(penalty=-1, context_window_chars=60)
    )
    fitted = rule.fit(
        ["The end result is x.", "The result is x."],
        [1, 0],
    )
    assert fitted is rule


def test_cliche_phrase_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = ClichePhraseRule(ClichePhraseRuleConfig(penalty=-2, context_window_chars=60))
    fitted = rule.fit(
        ["Let's think outside the box.", "Let's batch writes."],
        [1, 0],
    )
    assert fitted is rule


def test_foreign_phrase_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = ForeignPhraseRule(
        ForeignPhraseRuleConfig(penalty=-1, context_window_chars=60)
    )
    fitted = rule.fit(
        ["Per se, the change is fine.", "By itself, the change is fine."],
        [1, 0],
    )
    assert fitted is rule


def test_passive_voice_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = PassiveVoiceRule(
        PassiveVoiceRuleConfig(penalty=-2, tier_two_min_hits=3, context_window_chars=60)
    )
    fitted = rule.fit(
        [
            "The plan was approved by the council.",
            "The council approved the plan.",
        ],
        [1, 0],
    )
    assert fitted is rule


def test_long_sentence_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = LongSentenceRule(LongSentenceRuleConfig(min_words=5, max_hits=5, penalty=-2))
    long_sample = " ".join(["alpha"] * 8) + "."
    short_sample = "alpha. beta."
    fitted = rule.fit([long_sample, short_sample], [1, 0])
    assert fitted is rule


def test_exclamation_density_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = ExclamationDensityRule(
        ExclamationDensityRuleConfig(
            words_basis=10.0, density_threshold=0.0, penalty=-3
        )
    )
    fitted = rule.fit(["Wow! Yes! Amazing!", "Wow. Yes. Amazing."], [1, 0])
    assert fitted is rule


def test_emoji_in_prose_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = EmojiInProseRule(EmojiInProseRuleConfig(penalty=-3, context_window_chars=60))
    fitted = rule.fit(
        ["We shipped it \U0001f680.", "We shipped it."],
        [1, 0],
    )
    assert fitted is rule


def test_narrative_heading_fit_returns_self() -> None:
    """Fit should return self after fitting and apply penalty changes."""
    rule = NarrativeHeadingRule(
        NarrativeHeadingRuleConfig(penalty=-4, context_window_chars=60)
    )
    fitted = rule.fit(
        ["## The Journey of Caching", "## Caching strategy"],
        [1, 0],
    )
    assert fitted is rule


def test_long_sentence_fit_returns_unchanged_with_no_positive_samples() -> None:
    """Fit on no positives should return existing config unchanged."""
    rule = LongSentenceRule(LongSentenceRuleConfig(min_words=5, max_hits=5, penalty=-2))
    rule.fit([], [])
    assert rule.config.penalty == -2


def test_exclamation_density_fit_handles_empty_positive_ratios() -> None:
    """Fit should keep config when no positive sample yields a valid ratio."""
    rule = ExclamationDensityRule(
        ExclamationDensityRuleConfig(
            words_basis=150.0, density_threshold=1.0, penalty=-3
        )
    )
    rule.fit(["", ""], [1, 0])
    assert rule.config.density_threshold == 1.0
