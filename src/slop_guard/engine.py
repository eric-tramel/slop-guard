"""Core analyzer entrypoints for slop-guard."""

from .config import DEFAULT_HYPERPARAMETERS, Hyperparameters
from .document import AnalysisDocument
from .models import AnalysisPayload
from .rules.pipeline import Pipeline
from .scoring import (
    band_for_score,
    compute_weighted_sum,
    deduplicate_advice,
    initial_counts,
    score_from_density,
    serialize_violations,
    short_text_result,
)

_DEFAULT_PIPELINE: Pipeline | None = None


def _packaged_default_pipeline() -> Pipeline:
    """Return the lazily loaded packaged default pipeline."""
    global _DEFAULT_PIPELINE
    if _DEFAULT_PIPELINE is None:
        _DEFAULT_PIPELINE = Pipeline.from_jsonl()
    return _DEFAULT_PIPELINE


def analyze_document(
    document: AnalysisDocument,
    *,
    hyperparameters: Hyperparameters = DEFAULT_HYPERPARAMETERS,
    pipeline: Pipeline | None = None,
) -> AnalysisPayload:
    """Run all configured rules and return score, diagnostics, and advice."""
    active_pipeline = _packaged_default_pipeline() if pipeline is None else pipeline
    count_keys = getattr(active_pipeline, "count_keys", None)
    emits_categories = bool(getattr(active_pipeline, "emits_categories", False))

    if document.word_count < hyperparameters.short_text_word_count:
        payload = short_text_result(
            document.word_count,
            initial_counts(count_keys),
            hyperparameters,
        )
        if emits_categories:
            payload["category_counts"] = {}
        return payload

    state = active_pipeline.forward(document)
    total_penalty = sum(violation.penalty for violation in state.violations)
    weighted_sum = compute_weighted_sum(
        list(state.violations),
        state.counts,
        hyperparameters,
    )
    density = (
        weighted_sum / (document.word_count / hyperparameters.density_words_basis)
        if document.word_count > 0
        else 0.0
    )
    score = score_from_density(density, hyperparameters)
    band = band_for_score(score, hyperparameters)

    payload: AnalysisPayload = {
        "score": score,
        "band": band,
        "word_count": document.word_count,
        "violations": serialize_violations(
            state.violations,
            document.text,
            hyperparameters.context_window_chars,
            include_category=emits_categories,
        ),
        "counts": state.counts,
        "total_penalty": total_penalty,
        "weighted_sum": round(weighted_sum, 2),
        "density": round(density, 2),
        "advice": deduplicate_advice(list(state.advice)),
    }
    if emits_categories:
        category_counts: dict[str, int] = {}
        for violation in state.violations:
            category_counts[violation.category] = (
                category_counts.get(violation.category, 0) + 1
            )
        payload["category_counts"] = category_counts
    return payload


def analyze_text(
    text: str,
    *,
    hyperparameters: Hyperparameters = DEFAULT_HYPERPARAMETERS,
    pipeline: Pipeline | None = None,
) -> AnalysisPayload:
    """Analyze one raw text input."""
    return analyze_document(
        AnalysisDocument.from_text(text),
        hyperparameters=hyperparameters,
        pipeline=pipeline,
    )
