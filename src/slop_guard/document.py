"""Document projections and text helpers for slop-guard rules."""

import re
from dataclasses import dataclass
from functools import cached_property

from .markdown import MarkdownCodeView

_SENTENCE_SPLIT_RE = re.compile(r"[.!?][\"'\u201D\u2019)\]]*(?:\s|$)")
_BULLET_LINE_RE = re.compile(r"^\s*[-*]\s|^\s*\d+[.)]\s")
_BOLD_TERM_BULLET_LINE_RE = re.compile(r"^\s*[-*]\s+\*\*|^\s*\d+[.)]\s+\*\*")
_MARKDOWN_TABLE_DELIMITER_CELL_RE = re.compile(r"^\s*:?-{3,}:?\s*$")
_WORD_TOKEN_RE = re.compile(r"\w+")
_EDGE_WORD_STRIP_RE = re.compile(r"^[^\w]+|[^\w]+$")


def word_count(text: str) -> int:
    """Return the whitespace-delimited word count for a text blob."""
    return len(text.split())


def context_around(
    text: str,
    start: int,
    end: int,
    width: int,
) -> str:
    """Extract a text snippet centered on the matched span."""
    mid = (start + end) // 2
    half = width // 2
    ctx_start = max(0, mid - half)
    ctx_end = min(len(text), mid + half)
    snippet = text[ctx_start:ctx_end].replace("\n", " ")
    prefix = "..." if ctx_start > 0 else ""
    suffix = "..." if ctx_end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def _split_sentences(text: str) -> tuple[str, ...]:
    """Return trimmed sentence-like spans from ``text``."""
    return tuple(s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip())


def _looks_like_markdown_table_row(line: str) -> bool:
    """Return whether ``line`` looks like a standard pipe-table row."""
    stripped = line.strip()
    if "|" not in stripped:
        return False

    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return len(cells) >= 2 and any(cell for cell in cells)


def _is_markdown_table_delimiter(line: str) -> bool:
    """Return whether ``line`` is a Markdown pipe-table delimiter row."""
    stripped = line.strip()
    if "|" not in stripped:
        return False

    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return len(cells) >= 2 and all(
        _MARKDOWN_TABLE_DELIMITER_CELL_RE.match(cell) is not None for cell in cells
    )


def _replace_markdown_tables_with_sentence_breaks(text: str) -> str:
    """Replace standard pipe tables with sentence separators."""
    lines = text.split("\n")
    normalized_lines: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if (
            index + 1 < len(lines)
            and _looks_like_markdown_table_row(line)
            and _is_markdown_table_delimiter(lines[index + 1])
        ):
            normalized_lines.append(".")
            index += 2
            while index < len(lines) and _looks_like_markdown_table_row(lines[index]):
                index += 1
            continue

        normalized_lines.append(line)
        index += 1

    return "\n".join(normalized_lines)


@dataclass(frozen=True)
class AnalysisDocument:
    """Precomputed text views consumed by rules in forward passes."""

    text: str
    lines: tuple[str, ...]
    sentences: tuple[str, ...]
    word_count: int
    markdown_code_view: MarkdownCodeView

    @classmethod
    def from_text(cls, text: str) -> "AnalysisDocument":
        """Build a document with line/sentence/word projections."""
        markdown_code_view = MarkdownCodeView.from_text(text)
        return cls(
            text=text,
            lines=tuple(text.split("\n")),
            sentences=_split_sentences(text),
            word_count=word_count(markdown_code_view.masked_text),
            markdown_code_view=markdown_code_view,
        )

    @cached_property
    def sentence_word_counts(self) -> tuple[int, ...]:
        """Return cached word counts aligned with ``sentences``."""
        return tuple(len(sentence.split()) for sentence in self.sentences)

    @cached_property
    def sentence_analysis_text(self) -> str:
        """Return sentence-analysis text with Markdown blocks replaced."""
        return _replace_markdown_tables_with_sentence_breaks(
            self.markdown_code_view.fenced_text_for_sentence_breaks
        )

    @cached_property
    def sentence_analysis_sentences(self) -> tuple[str, ...]:
        """Return markdown-sanitized sentences used by sentence-length rules."""
        return _split_sentences(self.sentence_analysis_text)

    @cached_property
    def sentence_analysis_word_counts(self) -> tuple[int, ...]:
        """Return word counts aligned with ``sentence_analysis_sentences``."""
        return tuple(
            len(sentence.split()) for sentence in self.sentence_analysis_sentences
        )

    @cached_property
    def lower_text(self) -> str:
        """Return cached lowercase text used by case-insensitive rules."""
        return self.text.lower()

    @cached_property
    def word_tokens_lower(self) -> tuple[str, ...]:
        """Return cached lowercase alphanumeric/underscore tokens."""
        return tuple(_WORD_TOKEN_RE.findall(self.lower_text))

    @cached_property
    def word_token_set_lower(self) -> frozenset[str]:
        """Return cached lowercase token set for fast membership checks."""
        return frozenset(self.word_tokens_lower)

    @cached_property
    def ngram_tokens_lower(self) -> tuple[str, ...]:
        """Return cached lowercase tokens with edge punctuation stripped."""
        stripped_tokens = (
            _EDGE_WORD_STRIP_RE.sub("", token).lower() for token in self.text.split()
        )
        return tuple(token for token in stripped_tokens if token)

    @cached_property
    def ngram_token_ids_and_base(self) -> tuple[tuple[int, ...], int]:
        """Return cached n-gram token ids and packing base."""
        token_to_id: dict[str, int] = {}
        ids: list[int] = []
        for token in self.ngram_tokens_lower:
            token_id = token_to_id.get(token)
            if token_id is None:
                token_id = len(token_to_id) + 1
                token_to_id[token] = token_id
            ids.append(token_id)
        return tuple(ids), len(token_to_id) + 1

    @cached_property
    def non_empty_lines(self) -> tuple[str, ...]:
        """Return cached lines containing non-whitespace characters."""
        return tuple(line for line in self.lines if line.strip())

    @cached_property
    def line_is_bullet(self) -> tuple[bool, ...]:
        """Return cached bullet-line flags aligned with ``lines``."""
        return tuple(_BULLET_LINE_RE.match(line) is not None for line in self.lines)

    @cached_property
    def line_is_bold_term_bullet(self) -> tuple[bool, ...]:
        """Return cached bold-term bullet flags aligned with ``lines``."""
        return tuple(
            _BOLD_TERM_BULLET_LINE_RE.match(line) is not None for line in self.lines
        )

    @cached_property
    def line_is_blockquote(self) -> tuple[bool, ...]:
        """Return cached blockquote-line flags aligned with ``lines``."""
        return tuple(line.startswith(">") for line in self.lines)

    @cached_property
    def non_empty_bullet_count(self) -> int:
        """Return cached count of non-empty lines matching bullet syntax."""
        return sum(
            1
            for line in self.non_empty_lines
            if _BULLET_LINE_RE.match(line) is not None
        )

    @cached_property
    def text_without_code_blocks(self) -> str:
        """Return cached text with fenced code blocks removed."""
        return self.markdown_code_view.text_without_fenced_code

    @cached_property
    def word_count_without_code_blocks(self) -> int:
        """Return cached word count of ``text_without_code_blocks``."""
        return word_count(self.text_without_code_blocks)

    @cached_property
    def text_with_markdown_code_masked(self) -> str:
        """Return cached text with Markdown code replaced by whitespace."""
        return self.markdown_code_view.masked_text

    @cached_property
    def lower_text_with_markdown_code_masked(self) -> str:
        """Return cached lowercase text with Markdown code masked out."""
        return self.text_with_markdown_code_masked.lower()

    @cached_property
    def word_tokens_lower_with_markdown_code_masked(self) -> tuple[str, ...]:
        """Return lowercase tokens from text with Markdown code masked out."""
        return tuple(_WORD_TOKEN_RE.findall(self.lower_text_with_markdown_code_masked))

    @cached_property
    def word_token_set_lower_with_markdown_code_masked(self) -> frozenset[str]:
        """Return cached token set from text with Markdown code masked out."""
        return frozenset(self.word_tokens_lower_with_markdown_code_masked)
