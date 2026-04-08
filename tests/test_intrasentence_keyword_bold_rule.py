"""Regression tests for intra-sentence keyword bold detection."""

from slop_guard.config import DEFAULT_HYPERPARAMETERS
from slop_guard.document import AnalysisDocument
from slop_guard.rules.sentence import (
    IntrasentenceKeywordBoldRule,
    IntrasentenceKeywordBoldRuleConfig,
)


def _build_rule() -> IntrasentenceKeywordBoldRule:
    """Construct the rule with the default hyperparameters."""
    return IntrasentenceKeywordBoldRule(
        IntrasentenceKeywordBoldRuleConfig(
            penalty=DEFAULT_HYPERPARAMETERS.intrasentence_keyword_bold_penalty,
            record_cap=DEFAULT_HYPERPARAMETERS.intrasentence_keyword_bold_record_cap,
            advice_min=DEFAULT_HYPERPARAMETERS.intrasentence_keyword_bold_advice_min,
            max_words=DEFAULT_HYPERPARAMETERS.intrasentence_keyword_bold_max_words,
            context_window_chars=DEFAULT_HYPERPARAMETERS.context_window_chars,
        )
    )


def test_flags_mid_sentence_keyword_bold() -> None:
    """A short bold span inside flowing prose should be flagged."""
    rule = _build_rule()
    text = "We need to **carefully consider** every option before deciding."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"intrasentence_keyword_bold": 1}
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.match == "**carefully consider**"
    assert violation.start is not None and violation.end is not None
    assert text[violation.start : violation.end] == "**carefully consider**"


def test_flags_multiple_keyword_bolds_and_emits_summary() -> None:
    """Multiple matches drive count_deltas and emit summary advice."""
    rule = _build_rule()
    text = (
        "The plan is **highly ambitious** and the timeline is **very tight**. "
        "It also requires **strong alignment** across teams."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"intrasentence_keyword_bold": 3}
    assert any("mid-sentence keyword bolds" in line for line in result.advice)


def test_record_cap_limits_emitted_violations() -> None:
    """Violations cap at record_cap but count_deltas reports true prevalence."""
    rule = IntrasentenceKeywordBoldRule(
        IntrasentenceKeywordBoldRuleConfig(
            penalty=-2,
            record_cap=2,
            advice_min=10,
            max_words=5,
            context_window_chars=60,
        )
    )
    text = (
        "Use **fast paths** for **hot loops** and **cold caches**, "
        "and add **fresh metrics** for **new dashboards**."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    # All five mid-sentence bolds count toward the document's prevalence so
    # concentration amplification sees the true frequency, not the sample cap.
    assert result.count_deltas == {"intrasentence_keyword_bold": 5}
    assert len(result.violations) == 2


def test_label_form_at_line_start_is_ignored() -> None:
    """Lead-in ``**Term:**`` is covered by the structural rule."""
    rule = _build_rule()
    text = "**Problem:** the API is slow under load."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []
    assert result.count_deltas == {}


def test_label_form_anywhere_is_ignored() -> None:
    """``**Term:**`` forms are excluded even when not at the line start."""
    rule = _build_rule()
    text = "Earlier we added **Note:** to the doc without flagging it."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_bold_at_line_start_without_label_punctuation_is_ignored() -> None:
    """Bold spans beginning a line are not mid-sentence emphasis."""
    rule = _build_rule()
    text = "**Background** matters when scoping the change."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_bullet_line_bold_is_ignored() -> None:
    """Bold inside bullet lines is covered by the bold-term-bullet rule."""
    rule = _build_rule()
    text = "- **glossary term** with a definition that follows it."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_numbered_list_bold_is_ignored() -> None:
    """Bold inside numbered list items is covered by other rules."""
    rule = _build_rule()
    text = "1. **first step** which we always perform first."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_heading_with_bold_is_ignored() -> None:
    """Bold inside Markdown headings is typographic, not slop."""
    rule = _build_rule()
    text = "## The **important** section heading"

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_blockquote_bold_is_ignored() -> None:
    """Bold inside blockquoted citations is not flagged."""
    rule = _build_rule()
    text = "> The author argues that this is **deeply significant** evidence."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_numeric_only_bold_is_ignored() -> None:
    """Numeric data emphasis like ``**42%**`` or ``**$1.2M**`` is not slop."""
    rule = _build_rule()
    text = "Revenue grew by **42%** and total ARR reached **$1.2M** for the quarter."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_bold_inside_inline_code_is_ignored() -> None:
    """Bold markers inside inline code spans should not be matched."""
    rule = _build_rule()
    text = "Use the `**bold**` syntax to emphasize text in Markdown."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_bold_inside_fenced_code_block_is_ignored() -> None:
    """Bold markers inside fenced code blocks should not be matched."""
    rule = _build_rule()
    text = (
        "Run the snippet below.\n"
        "```python\n"
        'print("**carefully consider**")\n'
        "```\n"
        "Then review the output."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_bold_exceeding_max_words_is_ignored() -> None:
    """Long bold spans (full sentences or callouts) are out of scope."""
    rule = _build_rule()
    text = (
        "Earlier this week we noticed that "
        "**the pipeline drops every retried message after a partial outage** "
        "and we are still investigating."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_advice_min_threshold_emits_summary_only_when_met() -> None:
    """Summary advice fires only when match count >= advice_min."""
    rule = IntrasentenceKeywordBoldRule(
        IntrasentenceKeywordBoldRuleConfig(
            penalty=-2,
            record_cap=10,
            advice_min=2,
            max_words=5,
            context_window_chars=60,
        )
    )
    one_match_text = "We must **carefully plan** the rollout."
    two_match_text = (
        "We must **carefully plan** the rollout and **closely monitor** the metrics."
    )

    one_result = rule.forward(AnalysisDocument.from_text(one_match_text))
    two_result = rule.forward(AnalysisDocument.from_text(two_match_text))

    assert not any("mid-sentence keyword bolds" in line for line in one_result.advice)
    assert any("mid-sentence keyword bolds" in line for line in two_result.advice)


def test_soft_break_within_paragraph_is_flagged() -> None:
    """Soft-wrapped Markdown prose should still flag mid-sentence bolds."""
    rule = _build_rule()
    text = (
        "We must carefully review every change before\n"
        "**carefully shipping** to production users."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"intrasentence_keyword_bold": 1}
    assert len(result.violations) == 1
    assert result.violations[0].match == "**carefully shipping**"


def test_sentence_final_keyword_bold_is_flagged() -> None:
    """Sentence-final ``**phrase.**`` is not covered by the structural rule."""
    rule = _build_rule()
    text = "We acted with **careful planning.**"

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"intrasentence_keyword_bold": 1}
    assert len(result.violations) == 1
    assert result.violations[0].match == "**careful planning.**"


def test_label_form_with_continuation_is_ignored() -> None:
    """``**Term:**`` followed by continuation belongs to the structural rule."""
    rule = _build_rule()
    text = "Earlier we noted **Important:** for the migration plan."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_paragraph_break_resets_mid_sentence_check() -> None:
    """A bold span at the start of a new paragraph is not mid-sentence."""
    rule = _build_rule()
    text = (
        "Some prior context that ends a paragraph cleanly here.\n"
        "\n"
        "**Background** matters for scoping the upcoming change."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_soft_break_after_sentence_terminator_is_ignored() -> None:
    """A soft break after ``.``/``!``/``?`` starts a new sentence, not mid one."""
    rule = _build_rule()
    text = "We made the changes to the deploy.\n**Carefully reviewed** them later."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_inline_terminator_without_newline_is_ignored() -> None:
    """``Foo. **Bar**`` (no newline) is a new sentence, not mid-sentence."""
    rule = _build_rule()
    text = "We shipped the change. **Carefully reviewed** later that day."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_trailing_spaces_before_soft_break_are_skipped() -> None:
    """Trailing spaces before a soft break should not defeat the walk-back."""
    rule = _build_rule()
    # Two spaces precede the newline (a Markdown hard-break in some flavors)
    # but we still want to detect that the prior line continues into the bold.
    text = "We must carefully review every change before  \n**carefully shipping** to prod."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"intrasentence_keyword_bold": 1}
    assert len(result.violations) == 1


def test_soft_break_with_leading_whitespace_at_doc_start_is_ignored() -> None:
    """Whitespace + a soft break at the very top of a doc is paragraph start."""
    rule = _build_rule()
    text = "  \n**Background** matters when scoping the upcoming change."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_period_inside_inline_code_does_not_terminate_sentence() -> None:
    """A ``.`` inside inline code must not be mistaken for a sentence end."""
    rule = _build_rule()
    text = "Run `script.py.` **quickly** before midnight."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"intrasentence_keyword_bold": 1}
    assert len(result.violations) == 1
    assert result.violations[0].match == "**quickly**"


def test_crlf_soft_break_after_sentence_terminator_is_ignored() -> None:
    """Windows-style ``\\r\\n`` line endings should still detect sentence ends."""
    rule = _build_rule()
    text = "We made the changes to the deploy.\r\n**Carefully reviewed** them later."

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []


def test_fit_returns_self_with_contrastive_samples() -> None:
    """Contrastive fitting should return the same rule instance."""
    rule = _build_rule()
    samples = [
        "We must **carefully plan** every release before shipping it to users.",
        "The deploy completed without any last-minute escalations or drama.",
    ]
    labels = [1, 0]

    fitted = rule.fit(samples, labels)

    assert fitted is rule
    assert isinstance(fitted.config, IntrasentenceKeywordBoldRuleConfig)
    assert (
        fitted.config.max_words
        == DEFAULT_HYPERPARAMETERS.intrasentence_keyword_bold_max_words
    )


def test_fit_with_empty_positive_samples_keeps_config() -> None:
    """Fitting with no positive samples should leave config untouched."""
    rule = _build_rule()
    original_config = rule.config

    fitted = rule.fit([], None)

    assert fitted is rule
    assert fitted.config == original_config
