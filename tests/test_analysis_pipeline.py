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


def test_analyze_repeated_literal_violations_get_distinct_offsets() -> None:
    """Repeated literal matches should serialize distinct character spans."""
    text = (
        "Alpha crucial beta gamma delta epsilon zeta eta theta iota kappa "
        "crucial lambda."
    )

    result = _analyze(text, HYPERPARAMETERS)
    crucial_violations = [
        violation
        for violation in result["violations"]
        if violation["rule"] == "slop_word" and violation["match"] == "crucial"
    ]

    assert len(crucial_violations) == 2
    spans = [
        (int(violation["start"]), int(violation["end"]))
        for violation in crucial_violations
    ]
    assert spans[0] != spans[1]
    assert [text[start:end].lower() for start, end in spans] == [
        "crucial",
        "crucial",
    ]


def test_analyze_aggregate_violations_fall_back_to_document_offsets() -> None:
    """Aggregate findings should still expose a deterministic edit span."""
    text = (
        "- alpha item\n"
        "- beta item\n"
        "- gamma item\n"
        "Summary line with enough filler words to avoid a short-text bypass.\n"
    )

    result = _analyze(text, HYPERPARAMETERS)
    bullet_density_violation = next(
        violation
        for violation in result["violations"]
        if violation["rule"] == "bullet_density"
    )

    assert (
        bullet_density_violation["start"],
        bullet_density_violation["end"],
    ) == (0, len(text))


def test_analyze_short_text_uses_clean_short_circuit() -> None:
    """Short text should preserve score and payload defaults."""
    result = _analyze("too short", HYPERPARAMETERS)
    assert result["score"] == HYPERPARAMETERS.score_max
    assert result["violations"] == []
    assert result["advice"] == []


def test_analyze_short_text_exposes_full_count_schema() -> None:
    """Short text should still expose the full active count schema."""
    result = _analyze("Hi there.", HYPERPARAMETERS)

    assert {
        "closing_aphorism",
        "copula_chain",
        "extreme_sentence",
        "paragraph_balance",
        "paragraph_cv",
    }.issubset(result["counts"])
    assert result["counts"]["closing_aphorism"] == 0
    assert result["counts"]["paragraph_cv"] == 0


def test_structural_subcategory_violations_use_specific_count_keys() -> None:
    """Structural subcategory violations should align with their count keys."""
    text = (
        "Intro line.\n"
        "- **Reliability** improved\n"
        "- **Scalability** improved\n"
        "- **Security** improved\n"
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert result["counts"]["bullet_density"] == 1
    assert result["counts"]["bold_bullet_list"] == 1
    assert any(v["rule"] == "bullet_density" for v in result["violations"])
    assert any(v["rule"] == "bold_bullet_list" for v in result["violations"])


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


def test_analysis_document_sentence_analysis_strips_markdown_blocks() -> None:
    """Sentence analysis should ignore fenced code blocks and pipe tables."""
    text = (
        "Intro sentence.\n\n"
        "```text\n"
        + " ".join(["code"] * 100)
        + "\n```\n\n"
        "| name | details |\n"
        "| --- | --- |\n"
        "| alpha | "
        + " ".join(["cell"] * 40)
        + " |\n"
        "| beta | "
        + " ".join(["cell"] * 40)
        + " |\n\n"
        "Closing sentence."
    )
    document = AnalysisDocument.from_text(text)

    assert any(word_count >= 80 for word_count in document.sentence_word_counts)
    assert document.sentence_analysis_sentences == (
        "Intro sentence",
        "Closing sentence",
    )
    assert document.sentence_analysis_word_counts == (2, 2)
