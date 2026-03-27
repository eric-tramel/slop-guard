"""Reusable Markdown code-span detection and derived text views.

This module centralizes Markdown code handling so analysis paths can share one
scan of the source text and derive consistent masked or stripped views.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

Span: TypeAlias = tuple[int, int]

_NON_NEWLINE_RE = re.compile(r"[^\n]")


def _line_start_index(text: str, index: int) -> int:
    """Return the start index of the line containing ``index``.

    Args:
        text: Full source text.
        index: Character index inside ``text``.

    Returns:
        The zero-based index of the start of the containing line.
    """
    return text.rfind("\n", 0, index) + 1


def _backtick_run_length(text: str, index: int) -> int:
    """Return the number of consecutive backticks starting at ``index``.

    Args:
        text: Full source text.
        index: Zero-based character offset.

    Returns:
        The width of the backtick run that begins at ``index``.
    """
    end = index
    while end < len(text) and text[end] == "`":
        end += 1
    return end - index


def _looks_like_fenced_code_opener(text: str, index: int, backtick_count: int) -> bool:
    """Return whether a backtick run can open a fenced code block.

    Args:
        text: Full source text.
        index: Zero-based character offset of the backtick run.
        backtick_count: Width of the backtick run.

    Returns:
        ``True`` when the run looks like a Markdown fence opener.
    """
    if backtick_count < 3:
        return False
    line_start = _line_start_index(text, index)
    indent = text[line_start:index]
    return len(indent) <= 3 and indent.strip() == ""


def _find_fenced_code_block_end(
    text: str,
    opener_start: int,
    backtick_count: int,
) -> int:
    """Return the exclusive end index of a fenced code block.

    Args:
        text: Full source text.
        opener_start: Offset of the opening fence.
        backtick_count: Width of the opening fence.

    Returns:
        The exclusive end offset of the fenced block. If no closer exists, the
        end of the document is returned.
    """
    cursor = text.find("\n", opener_start)
    if cursor < 0:
        return len(text)
    cursor += 1

    while cursor < len(text):
        line_end = text.find("\n", cursor)
        if line_end < 0:
            line_end = len(text)
        line = text[cursor:line_end]
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        fence_width = _backtick_run_length(stripped, 0) if stripped else 0

        if (
            indent <= 3
            and fence_width >= backtick_count
            and stripped.startswith("`" * backtick_count)
            and stripped[fence_width:].strip() == ""
        ):
            return line_end if line_end == len(text) else line_end + 1

        cursor = line_end + 1

    return len(text)


def _find_inline_code_span_end(
    text: str,
    opener_start: int,
    backtick_count: int,
) -> int | None:
    """Return the exclusive end index of an inline code span.

    Args:
        text: Full source text.
        opener_start: Offset of the opening backtick run.
        backtick_count: Width of the opening run.

    Returns:
        The exclusive end offset of the matching inline span, or ``None`` when
        a closer does not exist on the same line.
    """
    cursor = opener_start + backtick_count
    line_end = text.find("\n", cursor)
    limit = len(text) if line_end < 0 else line_end

    while cursor < limit:
        if text[cursor] != "`":
            cursor += 1
            continue

        candidate_width = _backtick_run_length(text, cursor)
        if candidate_width == backtick_count:
            return cursor + backtick_count
        cursor += candidate_width

    return None


def _replace_spans(text: str, spans: tuple[Span, ...], replacement: str) -> str:
    """Replace each span in ``text`` with the same ``replacement`` string.

    Args:
        text: Full source text.
        spans: Sorted, non-overlapping spans to replace.
        replacement: Replacement text for each span.

    Returns:
        The transformed text.
    """
    if not spans:
        return text

    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(text[cursor:start])
        pieces.append(replacement)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _mask_spans_preserving_newlines(text: str, spans: tuple[Span, ...]) -> str:
    """Replace span contents with whitespace while preserving newlines.

    Args:
        text: Full source text.
        spans: Sorted, non-overlapping spans to mask.

    Returns:
        A string with the same length as ``text`` where masked characters are
        replaced by spaces, except newlines which are preserved.
    """
    if not spans:
        return text

    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(text[cursor:start])
        pieces.append(_NON_NEWLINE_RE.sub(" ", text[start:end]))
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


@dataclass(frozen=True)
class MarkdownCodeView:
    """Precomputed Markdown code-span projections for one text input.

    Attributes:
        all_spans: Fenced and inline code spans.
        fenced_spans: Fenced code spans only.
        masked_text: Full text with all code spans replaced by whitespace.
        text_without_fenced_code: Full text with fenced blocks removed.
        fenced_text_for_sentence_breaks: Full text with fenced blocks replaced
            by ``\\n.\\n`` to preserve sentence boundaries.
    """

    all_spans: tuple[Span, ...]
    fenced_spans: tuple[Span, ...]
    masked_text: str
    text_without_fenced_code: str
    fenced_text_for_sentence_breaks: str

    @classmethod
    def from_text(cls, text: str) -> MarkdownCodeView:
        """Build Markdown code-span views for ``text``.

        Args:
            text: Full source text.

        Returns:
            A reusable bundle of Markdown code projections.
        """
        all_spans: list[Span] = []
        fenced_spans: list[Span] = []
        cursor = 0

        while cursor < len(text):
            if text[cursor] != "`":
                cursor += 1
                continue

            backtick_count = _backtick_run_length(text, cursor)
            if _looks_like_fenced_code_opener(text, cursor, backtick_count):
                block_end = _find_fenced_code_block_end(text, cursor, backtick_count)
                span = (cursor, block_end)
                fenced_spans.append(span)
                all_spans.append(span)
                cursor = block_end
                continue

            inline_end = _find_inline_code_span_end(text, cursor, backtick_count)
            if inline_end is not None:
                all_spans.append((cursor, inline_end))
                cursor = inline_end
                continue

            cursor += backtick_count

        all_spans_tuple = tuple(all_spans)
        fenced_spans_tuple = tuple(fenced_spans)
        return cls(
            all_spans=all_spans_tuple,
            fenced_spans=fenced_spans_tuple,
            masked_text=_mask_spans_preserving_newlines(text, all_spans_tuple),
            text_without_fenced_code=_replace_spans(text, fenced_spans_tuple, ""),
            fenced_text_for_sentence_breaks=_replace_spans(
                text, fenced_spans_tuple, "\n.\n"
            ),
        )
