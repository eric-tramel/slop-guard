"""Tests for empirical per-rule fitting behavior."""

from copy import deepcopy
from typing import TypeAlias

import pytest

from slop_guard.analysis import HYPERPARAMETERS
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
            "**Problem:** the first claim.",
            "**Result:** the second claim.",
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
            "> one\nnormal",
            "> two\nnormal",
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
            "---\ntext",
            "---\nmore text",
        ],
    ),
    (
        PhraseReuseRule,
        "repeated_ngram_min_n",
        [
            "alpha beta gamma alpha beta delta alpha beta epsilon alpha beta zeta",
            "alpha beta one alpha beta two alpha beta three alpha beta four",
        ],
    ),
)


def test_all_default_rules_override_base_fit_impl() -> None:
    """Each concrete default rule should override the base no-op fit path."""
    for rule in build_default_rules(HYPERPARAMETERS):
        assert type(rule)._fit is not Rule._fit


@pytest.mark.parametrize(("rule_cls", "field_name", "corpus"), FIT_CASES)
def test_fit_updates_rule_hyperparameters(
    rule_cls: RuleType, field_name: str, corpus: list[str]
) -> None:
    """Each rule fit call should update at least one empirical hyperparameter."""
    defaults = {type(rule): rule for rule in build_default_rules(HYPERPARAMETERS)}
    rule = deepcopy(defaults[rule_cls])
    before = getattr(rule.config, field_name)

    fitted = rule.fit(corpus)

    assert fitted is rule
    assert getattr(rule.config, field_name) != before
