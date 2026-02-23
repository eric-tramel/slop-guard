"""Shared helper functions used by multiple rule modules."""


import re
from typing import TypeAlias

from slop_guard.analysis import Hyperparameters

NGramHit: TypeAlias = dict[str, int | str]

_FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_PUNCT_STRIP_RE = re.compile(r"^[^\w]+|[^\w]+$")
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "it",
        "that",
        "this",
        "with",
        "as",
        "by",
        "from",
        "was",
        "were",
        "are",
        "be",
        "been",
        "has",
        "have",
        "had",
        "not",
        "no",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "might",
        "if",
        "then",
        "than",
        "so",
        "up",
        "out",
        "about",
        "into",
        "over",
        "after",
        "before",
        "between",
        "through",
        "just",
        "also",
        "very",
        "more",
        "most",
        "some",
        "any",
        "each",
        "every",
        "all",
        "both",
        "few",
        "other",
        "such",
        "only",
        "own",
        "same",
        "too",
        "how",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
    }
)


def strip_code_blocks(text: str) -> str:
    """Remove fenced code block contents from text."""
    return _FENCED_CODE_BLOCK_RE.sub("", text)


def find_repeated_ngrams(text: str, hp: Hyperparameters) -> list[NGramHit]:
    """Find repeated multi-word phrases and keep only maximal spans."""
    raw_tokens = text.split()
    tokens = [_PUNCT_STRIP_RE.sub("", token).lower() for token in raw_tokens]
    tokens = [token for token in tokens if token]

    min_n = hp.repeated_ngram_min_n
    max_n = hp.repeated_ngram_max_n
    if len(tokens) < min_n:
        return []

    ngram_counts: dict[tuple[str, ...], int] = {}
    for n in range(min_n, max_n + 1):
        end = len(tokens) - n + 1
        for index in range(end):
            gram = tuple(tokens[index : index + n])
            ngram_counts[gram] = ngram_counts.get(gram, 0) + 1

    repeated = {
        gram: count
        for gram, count in ngram_counts.items()
        if count >= hp.repeated_ngram_min_count
        and not all(word in _STOPWORDS for word in gram)
    }
    if not repeated:
        return []

    to_remove: set[tuple[str, ...]] = set()
    sorted_grams = sorted(repeated.keys(), key=len, reverse=True)
    for index, longer in enumerate(sorted_grams):
        longer_str = " ".join(longer)
        for shorter in sorted_grams[index + 1 :]:
            if shorter in to_remove:
                continue
            shorter_str = " ".join(shorter)
            if shorter_str in longer_str and repeated[longer] >= repeated[shorter]:
                to_remove.add(shorter)

    results: list[NGramHit] = []
    for gram in sorted(repeated.keys(), key=lambda item: (-len(item), -repeated[item])):
        if gram in to_remove:
            continue
        results.append(
            {
                "phrase": " ".join(gram),
                "count": repeated[gram],
                "n": len(gram),
            }
        )
    return results
