"""Regression tests for the substantial-prose style guide checks."""

from __future__ import annotations

import pytest

from slop_guard.config import DEFAULT_HYPERPARAMETERS
from slop_guard.document import AnalysisDocument
from slop_guard.engine import analyze_text
from slop_guard.rules.passage.substantial_prose_style import (
    SubstantialProseStyleRule,
    SubstantialProseStyleRuleConfig,
)

_CLEAN_PASSAGE = (
    "The operator opens the report after the import finishes. She compares each "
    "row with its source record and notes missing values. The reviewer checks the "
    "totals, asks the author about unclear entries, and records the answer beside "
    "the affected row. The author updates the report after that review, then sends "
    "it back for a final accuracy check."
)


def _rule(*, min_words: int = 50) -> SubstantialProseStyleRule:
    return SubstantialProseStyleRule(
        SubstantialProseStyleRuleConfig(
            min_words=min_words,
            penalty=-3,
            record_cap=20,
            context_window_chars=60,
        )
    )


def _matches(text: str, *, min_words: int = 50) -> list[str]:
    result = _rule(min_words=min_words).forward(AnalysisDocument.from_text(text))
    return [violation.match for violation in result.violations]


def test_clean_substantial_passage_has_no_style_guide_findings() -> None:
    """Plain, process-oriented prose should pass the style-guide rule."""
    assert _matches(_CLEAN_PASSAGE) == []


def test_clean_substantial_passage_still_requires_semantic_review() -> None:
    """A deterministic pass should preserve the unresolved semantic checks."""
    result = _rule().forward(AnalysisDocument.from_text(_CLEAN_PASSAGE))

    assert result.violations == []
    assert len(result.review_requirements) == 1
    requirement = result.review_requirements[0]
    assert requirement.rule == "substantial_prose_style"
    assert {criterion.key for criterion in requirement.criteria} >= {
        "process_orientation",
        "context_and_deixis",
        "contextual_vocabulary",
        "plain_english",
        "current_context",
        "rewrite_method",
    }


def test_rule_skips_prose_below_the_substantial_word_threshold() -> None:
    """Short snippets should remain outside the substantial-writing check."""
    text = "Straight answer: the artifact ships tomorrow."

    result = _rule().forward(AnalysisDocument.from_text(text))

    assert result.violations == []
    assert result.review_requirements == []


@pytest.mark.parametrize(
    "problematic_text, expected_match",
    [
        ("Straight answer: ", "Straight answer:"),
        ("Short version: ", "Short version:"),
        ("Here is the thing. ", "Here is the thing"),
        ("The fundamental insight appears below. ", "fundamental insight"),
        ("To summarize, the import completed. ", "To summarize"),
        ("The real question is whether the total matches. ", "real question is"),
    ],
)
def test_rule_flags_announced_structure_and_editorial_signposts(
    problematic_text: str,
    expected_match: str,
) -> None:
    """The guide's named rhetorical templates should produce findings."""
    matches = _matches(problematic_text + _CLEAN_PASSAGE)

    assert any(expected_match.casefold() in match.casefold() for match in matches)


@pytest.mark.parametrize(
    "term",
    [
        "artifact",
        "footgun",
        "hydration",
        "inflight",
        "plumbing",
        "preflight",
        "provenance",
        "runbook",
        "honest",
        "genuine",
        "fair",
        "pushback",
        "today",
        "tomorrow",
    ],
)
def test_rule_flags_prohibited_jargon_and_editorial_terms(term: str) -> None:
    """Explicitly prohibited vocabulary should be reported as whole words."""
    matches = _matches(f"The note uses the word {term}. " + _CLEAN_PASSAGE)

    assert term in [match.casefold() for match in matches]


def test_rule_matches_prohibited_terms_as_whole_words() -> None:
    """A prohibited token should not match as part of an unrelated word."""
    text = "The fairness metric remains available. " + _CLEAN_PASSAGE

    assert "fair" not in [match.casefold() for match in _matches(text)]


@pytest.mark.parametrize("mark", ["\u2014", "\u2013", "\u2728", "\U0001f680"])
def test_rule_flags_prohibited_typographic_characters(mark: str) -> None:
    """Dashes, decorative symbols, and emoji should produce exact spans."""
    text = (
        f"The first review finished {mark} the second review started. " + _CLEAN_PASSAGE
    )
    document = AnalysisDocument.from_text(text)

    result = _rule().forward(document)
    violation = next(item for item in result.violations if item.match == mark)

    assert violation.explicit_span() is not None
    start, end = violation.explicit_span() or (0, 0)
    assert text[start:end] == mark


@pytest.mark.parametrize(
    "heading",
    [
        "## What the importer reads",
        "### Why the review runs twice",
        "# How operators correct a row",
    ],
)
def test_rule_flags_question_word_markdown_headings(heading: str) -> None:
    """Question-word headings should be replaced with direct noun phrases."""
    matches = _matches(f"{heading}\n\n{_CLEAN_PASSAGE}")

    assert heading in matches


@pytest.mark.parametrize(
    "claim",
    [
        "Three interfaces, one underlying structure.",
        "Two findings, and one is worse than it looks.",
        "One migration: every account moves together.",
    ],
)
def test_rule_flags_counting_claims_used_as_advertising_copy(claim: str) -> None:
    """Number-led slogans should be reported without flagging ordinary counts."""
    matches = _matches(f"{claim} {_CLEAN_PASSAGE}")

    assert claim in matches


def test_rule_flags_a_counting_claim_after_another_sentence() -> None:
    """Number-led slogans should match at sentence boundaries within a paragraph."""
    claim = "Three interfaces, one underlying structure."
    text = f"The operator finishes the review. {claim} {_CLEAN_PASSAGE}"

    assert claim in _matches(text)


@pytest.mark.parametrize(
    "sentence",
    [
        "The code knows which record belongs here.",
        "This change buys a simpler review.",
        "The trigger names no moment in the import.",
        "The workflow wants another retry.",
        "The patch lands after review.",
        "The parser surfaces an error for the operator.",
    ],
)
def test_rule_flags_abstractions_used_as_agents(sentence: str) -> None:
    """Inanimate technical subjects should not receive human actions."""
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert sentence.rstrip(".") in matches


@pytest.mark.parametrize(
    "sentence",
    [
        "Picking generates the next record.",
        "Caching creates the response before the reviewer arrives.",
    ],
)
def test_rule_flags_process_descriptions_used_as_sentence_agents(
    sentence: str,
) -> None:
    """Gerund subjects should be rewritten around the people or systems acting."""
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert sentence.rstrip(".") in matches


def test_rule_flags_a_process_subject_at_the_start_of_a_new_line() -> None:
    """A new Markdown line should start a fresh sentence-level check."""
    sentence = "Picking generates the next record."
    text = f"Operations\n{sentence} {_CLEAN_PASSAGE}"

    assert sentence.rstrip(".") in _matches(text)


def test_rule_flags_one_used_where_an_article_is_plainly_sufficient() -> None:
    """Procedural prose should use an article instead of a promotional numeral."""
    sentence = "The importer fetches one provided URL."
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert "fetches one provided URL" in matches


def test_rule_flags_restricted_relative_clauses() -> None:
    """The style guide requires direct clauses instead of restricted relatives."""
    sentence = "The reviewer opens the report that contains the disputed total."
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert "the report that contains" in [match.casefold() for match in matches]


def test_rule_flags_negative_clauses_tacked_onto_a_statement() -> None:
    """A comma-plus-negative addendum should become a direct positive account."""
    sentence = "The importer reads each file, and does not update the source."
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert "and does not update the source" in [match.casefold() for match in matches]


def test_rule_flags_polysyndeton_inside_one_sentence() -> None:
    """Repeated conjunctions in one sentence should be split or tightened."""
    sentence = (
        "The reviewer opens the file and checks the rows and compares the total "
        "and records the result."
    )
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert sentence.rstrip(".") in matches


def test_rule_flags_rhetorical_identity_formulas() -> None:
    """A short ``The A is the B`` formula should become a concrete statement."""
    sentence = "The interface is the contract."
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert sentence.rstrip(".").casefold() in [match.casefold() for match in matches]


def test_rule_flags_question_words_used_to_start_declarative_noun_phrases() -> None:
    """Question words should introduce questions rather than declarative phrases."""
    sentence = "What touches the record: the import callback."
    matches = _matches(f"{sentence} {_CLEAN_PASSAGE}")

    assert sentence.rstrip(".") in matches


def test_rule_allows_a_question_that_ends_with_a_question_mark() -> None:
    """Actual questions should remain available when the prose needs one."""
    text = "What did the operator change? " + _CLEAN_PASSAGE

    assert _matches(text) == []


def test_rule_allows_a_temporal_clause_that_begins_with_when() -> None:
    """A temporal subordinate clause should not count as a noun-phrase opening."""
    text = "When the import finishes, the operator checks the report. " + _CLEAN_PASSAGE

    assert _matches(text) == []


def test_rule_flags_parenthetical_comma_chains() -> None:
    """Long parenthetical comma chains should move into typographic structure."""
    chain = "(username, avatar, signature, privacy)"
    matches = _matches(
        f"The reviewer checks the profile fields {chain}. {_CLEAN_PASSAGE}"
    )

    assert chain in matches


def test_rule_flags_semicolons_after_the_second_occurrence() -> None:
    """The rule should tolerate occasional semicolons and report overuse."""
    text = (
        "The operator opens the report; the reviewer checks each row; the author "
        "corrects the total; the reviewer records the result. " + _CLEAN_PASSAGE
    )
    result = _rule().forward(AnalysisDocument.from_text(text))
    semicolon_findings = [item for item in result.violations if item.match == ";"]

    assert len(semicolon_findings) == 1


def test_rule_allows_two_semicolons_in_substantial_prose() -> None:
    """The semicolon check should measure overuse rather than ban the mark."""
    text = (
        "The operator opens the report; the reviewer checks each row; the author "
        "corrects the total. " + _CLEAN_PASSAGE
    )

    assert ";" not in _matches(text)


def test_rule_allows_an_ordinary_numbered_fact() -> None:
    """A concrete count should not match the number-led slogan pattern."""
    text = "Two reviewers compare each report. " + _CLEAN_PASSAGE

    assert _matches(text) == []


def test_rule_allows_two_counts_in_an_ordinary_quantitative_fact() -> None:
    """Multiple quantities should remain distinct from a count-led slogan."""
    text = "Two reviewers compare three reports. " + _CLEAN_PASSAGE

    assert _matches(text) == []


def test_rule_allows_generated_metadata_labels() -> None:
    """A field label should not look like an abstraction performing an action."""
    text = "Rule name\n\nsubstantial_prose_style\n\n" + _CLEAN_PASSAGE

    assert _matches(text) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "The tool uses the totals to summarize the report.",
        "The operators bring up the service before checking the report.",
    ],
)
def test_rule_leaves_context_sensitive_phrases_for_semantic_review(
    sentence: str,
) -> None:
    """Operational phrases should not receive an unconditional substring match."""
    text = f"{sentence} {_CLEAN_PASSAGE}"

    assert _matches(text) == []


@pytest.mark.parametrize("symbol", ["\N{DEGREE SIGN}", "\N{COPYRIGHT SIGN}"])
def test_rule_allows_semantic_unicode_symbols(symbol: str) -> None:
    """Technical and legal symbols should remain available in ordinary prose."""
    text = f"The reviewer records 200 {symbol}C in the report. {_CLEAN_PASSAGE}"

    assert _matches(text) == []


def test_rule_counts_all_findings_beyond_the_record_cap() -> None:
    """Output bounds should not hide the total number of style findings."""
    text = "Honest, genuine, fair, and golden. " + _CLEAN_PASSAGE
    rule = SubstantialProseStyleRule(
        SubstantialProseStyleRuleConfig(
            min_words=50,
            penalty=-3,
            record_cap=2,
            context_window_chars=60,
        )
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert len(result.violations) == 2
    assert result.count_deltas[rule.count_key] == 4


def test_rule_ignores_style_examples_inside_markdown_code() -> None:
    """Code examples should stay available for tests and documentation."""
    text = (
        "```text\n"
        "Straight answer: The artifact ships tomorrow. \U0001f680\n"
        "## What the importer reads\n"
        "```\n\n" + _CLEAN_PASSAGE
    )

    assert _matches(text) == []


def test_rule_ignores_style_examples_inside_generated_html_code() -> None:
    """Generated rule examples should remain outside prose analysis."""
    text = (
        '<code class="sg-behavior__input">'
        '"Straight answer: the workflow knows which record belongs here."'
        "</code>\n\n" + _CLEAN_PASSAGE
    )

    assert _matches(text) == []


def test_default_slop_guard_check_runs_the_substantial_style_rule() -> None:
    """The packaged default pipeline should enforce the new style checks."""
    result = analyze_text(
        "Straight answer: " + _CLEAN_PASSAGE,
        hyperparameters=DEFAULT_HYPERPARAMETERS,
    )

    assert result["counts"]["substantial_prose_style"] >= 1
    assert any(
        violation["rule"] == "substantial_prose_style"
        for violation in result["violations"]
    )
    assert result["review_requirements"][0]["rule"] == "substantial_prose_style"
