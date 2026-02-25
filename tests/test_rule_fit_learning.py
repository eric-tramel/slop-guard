"""Tests for empirical per-rule fitting behavior."""

from copy import deepcopy
from typing import TypeAlias

import pytest

from slop_guard.analysis import AnalysisDocument
from slop_guard.rules import Rule, build_default_rules
from slop_guard.rules.paragraph_level import (
    BlockquoteDensityRule,
    BoldTermBulletRunRule,
    BulletDensityRule,
    HorizontalRuleOveruseRule,
    StructuralPatternRule,
)
from slop_guard.rules.passage_level import (
    ColonDensityRule,
    EmDashDensityRule,
    PhraseReuseRule,
    RhythmRule,
)
from slop_guard.rules.sentence_level import (
    AIDisclosureRule,
    ContrastPairRule,
    PithyFragmentRule,
    PlaceholderRule,
    SetupResolutionRule,
    SlopPhraseRule,
    ToneMarkerRule,
    WeaselPhraseRule,
)
from slop_guard.rules.word_level import SlopWordRule

RuleType: TypeAlias = type[Rule]
FitCase: TypeAlias = tuple[RuleType, str, list[str]]

FIT_CASES: tuple[FitCase, ...] = (
    (
        SlopWordRule,
        "penalty",
        [
            "This is crucial, robust, and groundbreaking.",
            "An innovative and seamless approach.",
        ],
    ),
    (
        SlopPhraseRule,
        "penalty",
        [
            "It's worth noting that this is direct.",
            "At the end of the day, this matters.",
        ],
    ),
    (
        StructuralPatternRule,
        "bold_header_min",
        [
            (
                "**Problem:** first\n"
                "**Cause:** second\n"
                "**Fix:** third\n"
                "**Impact:** fourth\n"
                "**Scope:** fifth"
            ),
            (
                "**Input:** first\n"
                "**Process:** second\n"
                "**Output:** third\n"
                "**Risk:** fourth\n"
                "**Control:** fifth"
            ),
        ],
    ),
    (
        ToneMarkerRule,
        "tone_penalty",
        [
            "Would you like me to shorten this?",
            "Then something interesting happened.",
        ],
    ),
    (
        WeaselPhraseRule,
        "penalty",
        [
            "Many believe this is enough.",
            "Studies show this improves outcomes.",
        ],
    ),
    (
        AIDisclosureRule,
        "penalty",
        [
            "As an AI language model, I cannot browse the web.",
            "As of my cutoff, I do not know that event.",
        ],
    ),
    (
        PlaceholderRule,
        "penalty",
        [
            "[insert source citation] before publishing.",
            "Contact [your email here] for follow-up.",
        ],
    ),
    (
        RhythmRule,
        "min_sentences",
        [
            "One two. Three four. Five six. Seven eight. Nine ten. "
            "Eleven twelve. Thirteen fourteen. Fifteen sixteen.",
            "Alpha beta. Gamma delta. Epsilon zeta. Eta theta. Iota kappa. "
            "Lambda mu. Nu xi. Omicron pi.",
        ],
    ),
    (
        EmDashDensityRule,
        "density_threshold",
        [
            "one -- two -- three -- four -- five -- six -- seven -- eight.",
            "alpha -- beta -- gamma -- delta -- epsilon -- zeta -- eta.",
        ],
    ),
    (
        ContrastPairRule,
        "record_cap",
        [
            "focus, not frenzy.",
            "clarity, not complexity.",
        ],
    ),
    (
        SetupResolutionRule,
        "record_cap",
        [
            "This is not random. It is deliberate.",
            "It's not guesswork; it's method.",
        ],
    ),
    (
        ColonDensityRule,
        "density_threshold",
        [
            "Plan: retry: backoff: log: alert: learn.",
            "Checklist: draft: review: revise: publish: archive.",
        ],
    ),
    (
        PithyFragmentRule,
        "max_sentence_words",
        [
            "Simple, but powerful. Fast, yet reliable.",
            "Clear, and direct. Lean, not bloated.",
        ],
    ),
    (
        BulletDensityRule,
        "ratio_threshold",
        [
            "- one\n- two\n- three",
            "- four\n- five\n- six",
        ],
    ),
    (
        BlockquoteDensityRule,
        "min_lines",
        [
            "> one\n> two\n> three\n> four\n> five\nnormal",
            "> six\n> seven\n> eight\n> nine\n> ten\nnormal",
        ],
    ),
    (
        BoldTermBulletRunRule,
        "min_run_length",
        [
            "- **One** a\n- **Two** b\n- **Three** c\n- **Four** d\n- **Five** e",
            "- **Alpha** a\n- **Beta** b\n- **Gamma** c\n- **Delta** d\n- **Eta** e",
        ],
    ),
    (
        HorizontalRuleOveruseRule,
        "min_count",
        [
            "---\n---\n---\n---\n---\ntext",
            "---\n---\n---\n---\n---\nmore text",
        ],
    ),
    (
        PhraseReuseRule,
        "repeated_ngram_min_n",
        [
            (
                "alpha beta gamma delta epsilon zeta "
                "alpha beta gamma delta epsilon zeta "
                "alpha beta gamma delta epsilon zeta"
            ),
            (
                "one two three four five six seven "
                "one two three four five six seven "
                "one two three four five six seven"
            ),
        ],
    ),
)


def test_all_default_rules_override_base_fit_impl() -> None:
    """Each concrete default rule should override the base no-op fit path."""
    for rule in build_default_rules():
        assert type(rule)._fit is not Rule._fit


@pytest.mark.parametrize(("rule_cls", "field_name", "corpus"), FIT_CASES)
def test_fit_updates_rule_hyperparameters(
    rule_cls: RuleType, field_name: str, corpus: list[str]
) -> None:
    """Each rule fit call should update at least one empirical hyperparameter."""
    defaults = {type(rule): rule for rule in build_default_rules()}
    rule = deepcopy(defaults[rule_cls])
    before = getattr(rule.config, field_name)

    fitted = rule.fit(corpus)

    assert fitted is rule
    assert getattr(rule.config, field_name) != before


def test_fit_uses_negative_labels_for_contrastive_adjustment() -> None:
    """Negative-labeled samples should influence fitted contrastive thresholds."""
    defaults = {type(rule): rule for rule in build_default_rules()}
    positive_corpus = [
        "focus, not frenzy.",
        "clarity, not complexity.",
    ]
    negative_sample = (
        "focus, not frenzy. clarity, not complexity. speed, not haste. "
        "signal, not noise. quality, not quantity. craft, not chaos."
    )
    negative_corpus = [negative_sample] * 30

    positive_only = deepcopy(defaults[ContrastPairRule]).fit(positive_corpus)
    contrastive = deepcopy(defaults[ContrastPairRule]).fit(
        positive_corpus + negative_corpus,
        [1] * len(positive_corpus) + [0] * len(negative_corpus),
    )

    assert contrastive.config.record_cap > positive_only.config.record_cap
    assert contrastive.config.penalty != positive_only.config.penalty


def test_fit_thresholds_align_with_inclusive_count_based_rules() -> None:
    """Inclusive ``>=`` count rules should preserve contrastive separation."""
    defaults = {type(rule): rule for rule in build_default_rules()}
    rule = deepcopy(defaults[HorizontalRuleOveruseRule])

    positive_corpus = ["---\n---\ntext"] * 20
    negative_corpus = ["---\n---\n---\ntext"] * 20
    fitted = rule.fit(
        positive_corpus + negative_corpus,
        [1] * len(positive_corpus) + [0] * len(negative_corpus),
    )

    positive_hits = sum(
        1
        for sample in positive_corpus
        if fitted.forward(AnalysisDocument.from_text(sample)).violations
    )
    negative_hits = sum(
        1
        for sample in negative_corpus
        if fitted.forward(AnalysisDocument.from_text(sample)).violations
    )

    assert negative_hits > positive_hits
    assert fitted.config.penalty < 0
