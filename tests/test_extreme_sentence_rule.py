"""Tests for Markdown-aware extreme sentence detection."""


from slop_guard.analysis import AnalysisDocument
from slop_guard.rules.passage_level import ExtremeSentenceRule, ExtremeSentenceRuleConfig


def _build_rule(min_words: int = 20) -> ExtremeSentenceRule:
    """Build an extreme-sentence rule with a low threshold for regression tests."""
    return ExtremeSentenceRule(
        ExtremeSentenceRuleConfig(
            min_words=min_words,
            penalty=-5,
        )
    )


def test_extreme_sentence_ignores_fenced_code_blocks() -> None:
    """Code fences should not create run-on sentence violations."""
    rule = _build_rule()
    text = (
        "Intro sentence.\n\n"
        "```text\n"
        + " ".join(["code"] * 100)
        + "\n```\n\n"
        "Closing sentence."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []
    assert result.count_deltas == {}


def test_extreme_sentence_ignores_markdown_tables() -> None:
    """Pipe tables should not count as prose sentences."""
    rule = _build_rule()
    rows = "\n".join(
        f"| row {index} | {' '.join(['cell'] * 8)} |" for index in range(8)
    )
    text = (
        "Intro sentence.\n\n"
        "| column | details |\n"
        "| --- | --- |\n"
        f"{rows}\n\n"
        "Closing sentence."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []
    assert result.count_deltas == {}


def test_extreme_sentence_still_flags_long_prose_sentence() -> None:
    """Actual long prose sentences should still be flagged."""
    rule = _build_rule()
    text = " ".join(["word"] * 25) + "."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert len(result.violations) == 1
    assert result.violations[0].rule == "extreme_sentence"
    assert result.count_deltas == {"extreme_sentence": 1}


def test_extreme_sentence_fit_ignores_markdown_noise() -> None:
    """Rule fitting should use the same Markdown-sanitized sentence analysis."""
    rule = _build_rule()
    samples = [
        "Short sentence.",
        "```text\n" + " ".join(["code"] * 100) + "\n```",
    ]

    fitted_rule = rule.fit(samples, [1, 0])

    assert fitted_rule.config.penalty == 0
