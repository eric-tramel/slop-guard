"""Regression tests for staged contrast-pair detection."""


from slop_guard.analysis import AnalysisDocument, HYPERPARAMETERS
from slop_guard.rules.sentence_level import ContrastPairRule, ContrastPairRuleConfig


def _build_rule() -> ContrastPairRule:
    """Construct the default contrast-pair rule used in the pipeline."""
    return ContrastPairRule(
        ContrastPairRuleConfig(
            penalty=HYPERPARAMETERS.contrast_penalty,
            record_cap=HYPERPARAMETERS.contrast_record_cap,
            advice_min=HYPERPARAMETERS.contrast_advice_min,
            context_window_chars=HYPERPARAMETERS.context_window_chars,
        )
    )


def test_contrast_pair_counts_staged_not_only_not_just_not_merely_forms() -> None:
    """The rule should count the staged forms reported in issue 80."""
    rule = _build_rule()
    text = (
        "The platform is not only fast but also reliable. "
        "It is not just affordable but truly cost-effective. "
        "The team achieved not only their goals but exceeded expectations. "
        "This approach is not only innovative but practical. "
        "The design is not merely functional but beautiful."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"contrast_pairs": 5}
    assert [violation.match for violation in result.violations] == [
        "not only fast but also reliable",
        "not just affordable but truly cost-effective",
        "not only their goals but exceeded expectations",
        "not only innovative but practical",
        "not merely functional but beautiful",
    ]


def test_contrast_pair_counts_staged_forms_with_comma_before_but() -> None:
    """Common comma-separated staged contrasts should still be detected."""
    rule = _build_rule()
    text = (
        "The platform is not only fast, but also reliable. "
        "The design is not merely functional, but beautiful."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"contrast_pairs": 2}
    assert [violation.match for violation in result.violations] == [
        "not only fast, but also reliable",
        "not merely functional, but beautiful",
    ]
