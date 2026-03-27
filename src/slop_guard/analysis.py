"""Core analysis models and scoring helpers for slop-guard."""


import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Literal, TypeAlias, TypedDict

Counts: TypeAlias = dict[str, int]
BandLabel: TypeAlias = Literal["clean", "light", "moderate", "heavy", "saturated"]


class ViolationPayload(TypedDict):
    """Structured violation payload returned to CLI and MCP consumers."""

    type: Literal["Violation"]
    rule: str
    match: str
    context: str
    penalty: int
    start: int
    end: int


class AnalysisPayload(TypedDict):
    """Structured analyzer result produced by the core analyzer."""

    score: int
    band: BandLabel
    word_count: int
    violations: list[ViolationPayload]
    counts: Counts
    total_penalty: int
    weighted_sum: float
    density: float
    advice: list[str]


class SourceAnalysisPayload(AnalysisPayload):
    """Structured analyzer result augmented with a source label."""

    source: str


@dataclass(frozen=True)
class Hyperparameters:
    """Tunable thresholds, caps, and penalties used by the analyzer."""

    concentration_alpha: float = 2.5
    decay_lambda: float = 0.04
    claude_categories: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"contrast_pairs", "pithy_fragment", "setup_resolution"}
        )
    )

    context_window_chars: int = 60
    short_text_word_count: int = 10

    repeated_ngram_min_n: int = 4
    repeated_ngram_max_n: int = 8
    repeated_ngram_min_count: int = 3

    slop_word_penalty: int = -2
    slop_phrase_penalty: int = -3
    structural_bold_header_min: int = 3
    structural_bold_header_penalty: int = -5
    structural_bullet_run_min: int = 6
    structural_bullet_run_penalty: int = -3
    triadic_record_cap: int = 5
    triadic_penalty: int = -1
    triadic_advice_min: int = 3
    tone_penalty: int = -3
    sentence_opener_penalty: int = -2
    weasel_penalty: int = -2
    ai_disclosure_penalty: int = -10
    placeholder_penalty: int = -5
    rhythm_min_sentences: int = 5
    rhythm_cv_threshold: float = 0.3
    rhythm_penalty: int = -5
    em_dash_words_basis: float = 150.0
    em_dash_density_threshold: float = 1.0
    em_dash_penalty: int = -3
    contrast_record_cap: int = 5
    contrast_penalty: int = -1
    contrast_advice_min: int = 2
    setup_resolution_record_cap: int = 5
    setup_resolution_penalty: int = -3
    colon_words_basis: float = 150.0
    colon_density_threshold: float = 1.5
    colon_density_penalty: int = -3
    pithy_max_sentence_words: int = 6
    pithy_record_cap: int = 3
    pithy_penalty: int = -2
    bullet_density_threshold: float = 0.40
    bullet_density_penalty: int = -8
    blockquote_min_lines: int = 3
    blockquote_free_lines: int = 2
    blockquote_cap: int = 4
    blockquote_penalty_step: int = -3
    bold_bullet_run_min: int = 3
    bold_bullet_run_penalty: int = -5
    horizontal_rule_min: int = 4
    horizontal_rule_penalty: int = -3
    phrase_reuse_record_cap: int = 5
    phrase_reuse_penalty: int = -1

    density_words_basis: float = 1000.0
    score_min: int = 0
    score_max: int = 100
    band_clean_min: int = 80
    band_light_min: int = 60
    band_moderate_min: int = 40
    band_heavy_min: int = 20


HYPERPARAMETERS = Hyperparameters()


@dataclass(frozen=True)
class Violation:
    """Canonical violation record emitted by a rule."""

    rule: str
    match: str
    context: str
    penalty: int
    start: int | None = None
    end: int | None = None

    def explicit_span(self) -> tuple[int, int] | None:
        """Return the exact rule-provided span when one exists."""
        if self.start is None or self.end is None:
            return None
        return (self.start, self.end)

    def to_payload(self, start: int, end: int) -> ViolationPayload:
        """Serialize a typed violation for tool output."""
        return {
            "type": "Violation",
            "rule": self.rule,
            "match": self.match,
            "context": self.context,
            "penalty": self.penalty,
            "start": start,
            "end": end,
        }


_SENTENCE_SPLIT_RE = re.compile(r"[.!?][\"'\u201D\u2019)\]]*(?:\s|$)")
_BULLET_LINE_RE = re.compile(r"^\s*[-*]\s|^\s*\d+[.)]\s")
_BOLD_TERM_BULLET_LINE_RE = re.compile(r"^\s*[-*]\s+\*\*|^\s*\d+[.)]\s+\*\*")
_FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_MARKDOWN_TABLE_DELIMITER_CELL_RE = re.compile(r"^\s*:?-{3,}:?\s*$")
_WORD_TOKEN_RE = re.compile(r"\w+")
_EDGE_WORD_STRIP_RE = re.compile(r"^[^\w]+|[^\w]+$")


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

    @classmethod
    def from_text(cls, text: str) -> "AnalysisDocument":
        """Build a document with line/sentence/word projections."""
        return cls(
            text=text,
            lines=tuple(text.split("\n")),
            sentences=_split_sentences(text),
            word_count=word_count(text),
        )

    @cached_property
    def sentence_word_counts(self) -> tuple[int, ...]:
        """Return cached word counts aligned with ``sentences``."""
        return tuple(len(sentence.split()) for sentence in self.sentences)

    @cached_property
    def sentence_analysis_text(self) -> str:
        """Return sentence-analysis text with Markdown blocks replaced."""
        text_without_code_blocks = _FENCED_CODE_BLOCK_RE.sub("\n.\n", self.text)
        return _replace_markdown_tables_with_sentence_breaks(text_without_code_blocks)

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
        return _FENCED_CODE_BLOCK_RE.sub("", self.text)

    @cached_property
    def word_count_without_code_blocks(self) -> int:
        """Return cached word count of ``text_without_code_blocks``."""
        return word_count(self.text_without_code_blocks)


@dataclass
class RuleResult:
    """Output payload emitted by a single rule invocation."""

    violations: list[Violation] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    count_deltas: Counts = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisState:
    """Immutable accumulator carrying merged rule output."""

    violations: tuple[Violation, ...]
    advice: tuple[str, ...]
    counts: Counts

    @classmethod
    def initial(cls, count_keys: Iterable[str] | None = None) -> "AnalysisState":
        """Construct an empty state with canonical counts initialized to zero."""
        return cls(violations=(), advice=(), counts=initial_counts(count_keys))

    def merge(self, result: RuleResult) -> "AnalysisState":
        """Merge one rule result into a new state instance."""
        merged_counts = dict(self.counts)
        for key, delta in result.count_deltas.items():
            if delta:
                merged_counts[key] = merged_counts.get(key, 0) + delta

        return AnalysisState(
            violations=self.violations + tuple(result.violations),
            advice=self.advice + tuple(result.advice),
            counts=merged_counts,
        )


_COUNT_KEYS: tuple[str, ...] = (
    "slop_words",
    "slop_phrases",
    "structural",
    "tone",
    "weasel",
    "ai_disclosure",
    "placeholder",
    "rhythm",
    "em_dash",
    "contrast_pairs",
    "setup_resolution",
    "colon_density",
    "pithy_fragment",
    "bullet_density",
    "blockquote_density",
    "bold_bullet_list",
    "horizontal_rules",
    "phrase_reuse",
    "copula_chain",
    "extreme_sentence",
    "closing_aphorism",
    "paragraph_balance",
    "paragraph_cv",
)


def initial_counts(count_keys: Iterable[str] | None = None) -> Counts:
    """Create the canonical per-rule counter map used by the analyzer."""
    keys = _COUNT_KEYS if count_keys is None else tuple(dict.fromkeys(count_keys))
    return {key: 0 for key in keys}


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


def _literal_span_candidates(text: str, match: str) -> tuple[tuple[int, int], ...]:
    """Return case-insensitive exact-text match spans for ``match``."""
    if not match:
        return ()
    return tuple(
        (occurrence.start(), occurrence.end())
        for occurrence in re.finditer(re.escape(match), text, flags=re.IGNORECASE)
    )


def _context_core(context: str) -> str:
    """Return the searchable body of a context snippet without ellipses."""
    start = 3 if context.startswith("...") else 0
    end = len(context) - 3 if context.endswith("...") else len(context)
    return context[start:end]


def _context_span_candidates(
    normalized_text: str,
    context: str,
) -> tuple[tuple[int, int], ...]:
    """Return spans where the normalized context snippet occurs in ``text``."""
    core = _context_core(context)
    if not core:
        return ()

    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = normalized_text.find(core, start)
        if index < 0:
            return tuple(spans)
        spans.append((index, index + len(core)))
        start = index + 1


def _select_unused_span(
    candidates: tuple[tuple[int, int], ...],
    used_spans: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """Return the first candidate span not already used, else the first match."""
    for span in candidates:
        if span not in used_spans:
            return span
    return candidates[0] if candidates else None


def _resolve_violation_span(
    violation: Violation,
    text: str,
    normalized_text: str,
    context_window_chars: int,
    used_spans: set[tuple[int, int]],
) -> tuple[int, int]:
    """Resolve a best-effort character span for a violation payload."""
    explicit_span = violation.explicit_span()
    if explicit_span is not None:
        return explicit_span

    literal_candidates = _literal_span_candidates(text, violation.match)
    context_matched_literal_candidates = tuple(
        span
        for span in literal_candidates
        if context_around(text, span[0], span[1], context_window_chars) == violation.context
    )
    literal_span = _select_unused_span(context_matched_literal_candidates, used_spans)
    if literal_span is not None:
        return literal_span

    if violation.match.casefold() in violation.context.casefold():
        literal_span = _select_unused_span(literal_candidates, used_spans)
        if literal_span is not None:
            return literal_span

    context_span = _select_unused_span(
        _context_span_candidates(normalized_text, violation.context),
        used_spans,
    )
    if context_span is not None:
        return context_span

    return (0, len(text))


def serialize_violations(
    violations: Iterable[Violation],
    text: str,
    context_window_chars: int,
) -> list[ViolationPayload]:
    """Serialize violations and attach resolved character offsets."""
    normalized_text = text.replace("\n", " ")
    used_spans: set[tuple[int, int]] = set()
    payloads: list[ViolationPayload] = []

    for violation in violations:
        start, end = _resolve_violation_span(
            violation,
            text,
            normalized_text,
            context_window_chars,
            used_spans,
        )
        used_spans.add((start, end))
        payloads.append(violation.to_payload(start, end))

    return payloads


def word_count(text: str) -> int:
    """Return the whitespace-delimited word count for a text blob."""
    return len(text.split())


def short_text_result(
    word_count_value: int,
    counts: Counts,
    hp: Hyperparameters,
) -> AnalysisPayload:
    """Build the fixed response shape for short texts that are skipped."""
    return {
        "score": hp.score_max,
        "band": "clean",
        "word_count": word_count_value,
        "violations": [],
        "counts": counts,
        "total_penalty": 0,
        "weighted_sum": 0.0,
        "density": 0.0,
        "advice": [],
    }


def compute_weighted_sum(
    violations: list[Violation], counts: Counts, hp: Hyperparameters
) -> float:
    """Compute weighted penalties with concentration amplification."""
    weighted_sum = 0.0
    for violation in violations:
        rule = violation.rule
        penalty = abs(violation.penalty)
        cat_count = counts.get(rule, 0) or counts.get(rule + "s", 0)
        count_key = (
            rule
            if rule in hp.claude_categories
            else (rule + "s" if (rule + "s") in hp.claude_categories else None)
        )
        if count_key and count_key in hp.claude_categories and cat_count > 1:
            weight = penalty * (1 + hp.concentration_alpha * (cat_count - 1))
        else:
            weight = penalty
        weighted_sum += weight
    return weighted_sum


def band_for_score(score: int, hp: Hyperparameters) -> str:
    """Map a numeric score into the configured severity band."""
    if score >= hp.band_clean_min:
        return "clean"
    if score >= hp.band_light_min:
        return "light"
    if score >= hp.band_moderate_min:
        return "moderate"
    if score >= hp.band_heavy_min:
        return "heavy"
    return "saturated"


def deduplicate_advice(advice: list[str]) -> list[str]:
    """Return advice entries preserving order while removing duplicates."""
    seen: set[str] = set()
    unique: list[str] = []
    for item in advice:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def score_from_density(density: float, hp: Hyperparameters) -> int:
    """Compute bounded integer score from weighted density."""
    raw_score = hp.score_max * math.exp(-hp.decay_lambda * density)
    return max(hp.score_min, min(hp.score_max, round(raw_score)))
