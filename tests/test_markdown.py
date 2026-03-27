"""Tests for reusable Markdown code-span views."""

from slop_guard.markdown import MarkdownCodeView


def test_markdown_code_view_tracks_fenced_and_inline_code_separately() -> None:
    """The shared view should expose both all-code and fenced-only projections."""
    text = (
        "Intro `robust journey` example.\n\n"
        "```python\n"
        "navigate_landscape()\n"
        "```\n\n"
        "Closing line."
    )

    view = MarkdownCodeView.from_text(text)

    assert len(view.all_spans) == 2
    assert len(view.fenced_spans) == 1
    assert len(view.masked_text) == len(text)
    assert "robust journey" not in view.masked_text
    assert "navigate_landscape" not in view.masked_text
    assert "`robust journey`" in view.text_without_fenced_code
    assert "navigate_landscape" not in view.text_without_fenced_code
    assert "\n.\n" in view.fenced_text_for_sentence_breaks
