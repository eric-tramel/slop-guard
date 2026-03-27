"""Tests for setup-resolution rule deduplication behavior."""


from slop_guard.analysis import AnalysisDocument, HYPERPARAMETERS
from slop_guard.rules.sentence_level import SetupResolutionRule, SetupResolutionRuleConfig


def _build_rule() -> SetupResolutionRule:
    """Construct the default setup-resolution rule used in the pipeline."""
    return SetupResolutionRule(
        SetupResolutionRuleConfig(
            penalty=HYPERPARAMETERS.setup_resolution_penalty,
            record_cap=HYPERPARAMETERS.setup_resolution_record_cap,
            context_window_chars=HYPERPARAMETERS.context_window_chars,
        )
    )


def test_setup_resolution_deduplicates_overlapping_pattern_matches() -> None:
    """Overlapping regex forms should emit one violation per span."""
    text = (
        "The system is not just fast, but also scalable. "
        "This is not about performance. It is about reliability. "
        "Studies show that holistic monitoring fosters better uptime."
    )

    result = _build_rule().forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"setup_resolution": 1}
    assert len(result.violations) == 1
    assert result.violations[0].rule == "setup_resolution"
    assert result.violations[0].match == "This is not about performance. It is"
    assert len(result.advice) == 1
