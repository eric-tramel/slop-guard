"""Integration tests for rule-pipeline based analysis output."""


from slop_guard.analysis import AnalysisDocument, HYPERPARAMETERS, word_count
from slop_guard.server import _analyze


def test_analyze_runs_instantiated_rule_pipeline() -> None:
    """Analyze should emit expected schema and detect rule hits."""
    text = (
        "This is a crucial and groundbreaking paradigm that feels remarkably "
        "innovative and comprehensive overall."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert set(result) == {
        "score",
        "band",
        "word_count",
        "violations",
        "counts",
        "total_penalty",
        "weighted_sum",
        "density",
        "advice",
    }
    assert result["counts"]["slop_words"] >= 1
    assert any(v["rule"] == "slop_word" for v in result["violations"])


def test_analyze_short_text_uses_clean_short_circuit() -> None:
    """Short text should preserve score and payload defaults."""
    result = _analyze("too short", HYPERPARAMETERS)
    assert result["score"] == HYPERPARAMETERS.score_max
    assert result["violations"] == []
    assert result["advice"] == []


def test_analysis_document_cached_views() -> None:
    """AnalysisDocument should expose stable cached projections for reuse."""
    text = (
        "Alpha beta. Gamma delta.\n"
        "- bullet one\n"
        "> quote line\n"
        "\n"
        "```python\n"
        "code: true\n"
        "- inside code\n"
        "```\n"
        "- bullet two\n"
    )
    document = AnalysisDocument.from_text(text)

    assert document.sentence_word_counts == tuple(
        len(sentence.split()) for sentence in document.sentences
    )
    assert document.non_empty_lines == tuple(
        line for line in document.lines if line.strip()
    )
    assert len(document.line_is_bullet) == len(document.lines)
    assert len(document.line_is_bold_term_bullet) == len(document.lines)
    assert len(document.line_is_blockquote) == len(document.lines)
    assert document.non_empty_bullet_count == 3
    assert "code: true" not in document.text_without_code_blocks
    assert document.word_count_without_code_blocks == word_count(
        document.text_without_code_blocks
    )
