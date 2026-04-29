"""Regression tests for faux-deepness detection."""

import json
from pathlib import Path
from typing import Any, TypeAlias

from slop_guard.config import DEFAULT_HYPERPARAMETERS
from slop_guard.document import AnalysisDocument
from slop_guard.rules.sentence import FauxDeepnessRule, FauxDeepnessRuleConfig

FixtureRow: TypeAlias = dict[str, Any]

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "faux_deepness.jsonl"


def _build_rule() -> FauxDeepnessRule:
    """Construct the default faux-deepness rule used in the pipeline."""
    return FauxDeepnessRule(
        FauxDeepnessRuleConfig(
            penalty=DEFAULT_HYPERPARAMETERS.faux_deepness_penalty,
            record_cap=DEFAULT_HYPERPARAMETERS.faux_deepness_record_cap,
            advice_min=DEFAULT_HYPERPARAMETERS.faux_deepness_advice_min,
            context_window_chars=DEFAULT_HYPERPARAMETERS.context_window_chars,
        )
    )


def _load_fixture_rows() -> list[FixtureRow]:
    """Load faux-deepness fixture rows from JSONL."""
    rows: list[FixtureRow] = []
    for line in _FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise AssertionError("faux-deepness fixture rows must be objects")
        rows.append(payload)
    return rows


def test_faux_deepness_counts_quoted_and_unquoted_stack() -> None:
    """The rule should catch the motivating quoted and unquoted negations."""
    rule = _build_rule()
    text = (
        'Silence does not "settle". '
        'Words do not "hang in the air". '
        'Knowledge does not "sit in the room". '
        'History does not "press". '
        'A truth does not "land".'
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.count_deltas == {"faux_deepness": 5}
    assert [violation.match for violation in result.violations] == [
        'Silence does not "settle"',
        'Words do not "hang in the air"',
        'Knowledge does not "sit in the room"',
        'History does not "press"',
        'A truth does not "land"',
    ]
    assert any("5 faux-deepness negations" in item for item in result.advice)


def test_faux_deepness_fixture_rows_have_expected_match_counts() -> None:
    """The 20-row fixture should cover matched and non-matched variants."""
    rule = _build_rule()
    rows = _load_fixture_rows()

    assert len(rows) == 20

    for row in rows:
        text = row["text"]
        expected_matches = row["expected_matches"]
        if not isinstance(text, str) or not isinstance(expected_matches, int):
            raise AssertionError("fixture rows require text and expected_matches")

        result = rule.forward(AnalysisDocument.from_text(text))

        assert len(result.violations) == expected_matches, text


def test_faux_deepness_ignores_concrete_literal_negations() -> None:
    """Concrete subjects using the same verbs should not trigger the rule."""
    rule = _build_rule()
    text = (
        "The paint does not settle evenly in cold rooms. "
        "The invoice does not land until Friday. "
        "The team waited in silence while the room settled."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []
    assert result.count_deltas == {}


def test_faux_deepness_ignores_markdown_code_spans() -> None:
    """Markdown code examples should be masked before matching."""
    rule = _build_rule()
    text = (
        'Use `Silence does not "settle".` as an inline example.\n\n'
        "```text\n"
        'Words do not "hang in the air".\n'
        "```\n\n"
        "The surrounding explanation is plain prose with no faux-deepness hit."
    )

    result = rule.forward(AnalysisDocument.from_text(text))

    assert result.violations == []
    assert result.count_deltas == {}
