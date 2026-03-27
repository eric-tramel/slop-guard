"""Regression tests for agent-facing advice strings."""


import pytest

from slop_guard.analysis import HYPERPARAMETERS
from slop_guard.server import _analyze


def test_slop_word_advice_uses_category_specific_templates() -> None:
    """Slop-word advice should reflect the word's rhetorical role."""
    text = (
        "Remarkably, the innovative team shipped an innovative feature. "
        "The journey took months."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert (
        "Cut 'remarkably' — start the sentence directly or show the connection "
        "without announcing it."
    ) in result["advice"]
    assert (
        "Cut 'innovative' (2 occurrences) unless you can name the concrete "
        "property, metric, or consequence."
    ) in result["advice"]
    assert (
        "Replace 'journey' with the actual period, step, or change you observed."
    ) in result["advice"]


def test_repeated_slop_words_report_occurrence_counts_in_advice() -> None:
    """Grouped advice should say how many times a repeated slop word appears."""
    text = (
        "Innovative teams built innovative tools with innovative methods. "
        "Their innovative plan used innovative demos for innovative launches."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert result["advice"] == [
        "Cut 'innovative' (6 occurrences) unless you can name the concrete "
        "property, metric, or consequence."
    ]


def test_proper_name_surname_does_not_trigger_slop_word_violation() -> None:
    """Capitalized surnames after a given name should not count as slop words."""
    text = (
        "The bridge was designed by Norman Foster, one of the most celebrated "
        "architects in the world."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert result["score"] == HYPERPARAMETERS.score_max
    assert result["violations"] == []
    assert result["advice"] == []


def test_title_cased_brand_name_does_not_trigger_slop_word_violation() -> None:
    """A title-cased name phrase should not trip on its first token either."""
    text = (
        "Landscape Forms supplied the benches for the renovated plaza this year."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert result["score"] == HYPERPARAMETERS.score_max
    assert result["violations"] == []
    assert result["advice"] == []


def test_capitalized_sentence_initial_foster_still_triggers_slop_word_advice() -> None:
    """Sentence-initial ``Foster`` should still match the verb form."""
    text = "Foster stronger review habits by naming the concrete change each week."

    result = _analyze(text, HYPERPARAMETERS)

    assert any(
        violation["rule"] == "slop_word" and violation["match"] == "foster"
        for violation in result["violations"]
    )
    assert (
        "Replace 'foster' with the specific action, result, or evidence."
        in result["advice"]
    )


@pytest.mark.parametrize(
    "transition_word",
    (
        "however",
        "overall",
        "furthermore",
        "additionally",
        "moreover",
        "particularly",
        "notably",
        "importantly",
    ),
)
def test_standard_transition_words_do_not_trigger_slop_word_violations(
    transition_word: str,
) -> None:
    """Common transition words should not be treated as slop words."""
    text = (
        "The migration completed on schedule. "
        f"{transition_word.capitalize()}, three reports still need one indexed join."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert result["score"] == HYPERPARAMETERS.score_max
    assert result["violations"] == []
    assert result["advice"] == []


def test_rhythm_advice_reports_threshold_and_sentence_range() -> None:
    """Rhythm advice should report the current gap instead of a vague prompt."""
    text = (
        "One two three four. "
        "Five six seven eight. "
        "Nine ten eleven twelve. "
        "Thirteen fourteen fifteen sixteen. "
        "Seventeen eighteen nineteen twenty."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert result["advice"] == [
        "Sentence lengths are too uniform (CV=0.00 < 0.30; shortest 4 words, "
        "longest 4, mean 4.0). Add a much shorter or much longer sentence so "
        "the passage is not clustered around the same length; aim for roughly "
        "a 3x spread between the shortest and longest sentence."
    ]


def test_single_triadic_structural_violation_has_actionable_advice() -> None:
    """A single triadic structural hit should still tell the user what to change."""
    text = (
        "We support three output formats: JSON, YAML, and TOML. "
        "Each one is fully validated before writing. "
        "The default format is JSON because it has the broadest tool support."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert any(
        violation["rule"] == "structural" and violation["match"] == "triadic"
        for violation in result["violations"]
    )
    assert result["advice"] == [
        "Rewrite 'JSON, YAML, and TOML' as prose or restructure the list so "
        "the sentence does not hinge on a three-item cadence."
    ]


def test_repeated_triadic_structures_keep_aggregate_cadence_advice() -> None:
    """Repeated triads should still emit the aggregate cadence warning."""
    text = (
        "The platform is reliable, scalable, and maintainable in production. "
        "The rollout stayed measured, observable, and reversible overnight. "
        "The handoff remained clear, direct, and documented for operators."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert (
        "3 triadic structures ('X, Y, and Z') — vary your list cadence."
        in result["advice"]
    )


def test_overlapping_phrase_rules_share_one_canonical_edit_message() -> None:
    """Overlapping phrase and tone rules should deduplicate shared guidance."""
    text = (
        "The metrics looked stable at first today. "
        "This is where things get interesting. "
        "Let me know if you want the rollback details after tomorrow morning."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert (
        result["advice"].count(
            "Cut 'this is where things get interesting' — replace the announcement "
            "with the actual point."
        )
        == 1
    )
    assert (
        result["advice"].count(
            "Cut 'let me know if' — replace the invitation with the actual point."
        )
        == 1
    )


def test_contrast_and_pithy_fragment_advice_use_the_same_rewrite_direction() -> None:
    """Contrast and fragment rules should point toward the same edit action."""
    text = (
        "This is focus, not frenzy. "
        "It is clarity, not complexity. "
        "The deploy finished yesterday after two routine checks."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert (
        "Rewrite 'focus, not frenzy' as a plain sentence with the actual claim "
        "instead of an 'X, not Y' slogan."
    ) in result["advice"]
    assert (
        "Rewrite 'This is focus, not frenzy' as a plain sentence with the actual "
        "claim, or cut it if it adds no detail."
    ) in result["advice"]
    assert (
        "2 'X, not Y' contrasts — stop stacking slogan-like oppositions; rewrite "
        "at least one as a plain sentence with the actual tradeoff."
    ) in result["advice"]
    assert all("consider rephrasing" not in item for item in result["advice"])
    assert all("Expand or cut." not in item for item in result["advice"])


def test_contrast_pair_rule_detects_staged_not_only_but_patterns() -> None:
    """Contrast-pair counting should include staged ``not ... but ...`` forms."""
    text = (
        "The platform is not only fast but also reliable. "
        "It is not just affordable but truly cost-effective. "
        "The team achieved not only their goals but exceeded expectations. "
        "This approach is not only innovative but practical. "
        "The design is not merely functional but beautiful."
    )

    result = _analyze(text, HYPERPARAMETERS)
    contrast_violations = [
        violation
        for violation in result["violations"]
        if violation["rule"] == "contrast_pair"
    ]

    assert result["counts"]["contrast_pairs"] == 5
    assert [violation["match"] for violation in contrast_violations] == [
        "not only fast but also reliable",
        "not just affordable but truly cost-effective",
        "not only their goals but exceeded expectations",
        "not only innovative but practical",
        "not merely functional but beautiful",
    ]
    assert (
        "Rewrite 'not only fast but also reliable' as a direct sentence instead "
        "of staging it as a contrast."
    ) in result["advice"]
    assert (
        "5 contrast constructions — stop stacking staged oppositions; rewrite "
        "at least one as a plain sentence with the actual tradeoff."
    ) in result["advice"]
