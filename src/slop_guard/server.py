"""MCP server for prose linting with modular rule execution."""


import argparse
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .analysis import (
    AnalysisDocument,
    HYPERPARAMETERS,
    Hyperparameters,
    band_for_score,
    compute_weighted_sum,
    deduplicate_advice,
    initial_counts,
    score_from_density,
    short_text_result,
)
from .rules import Pipeline
from .version import PACKAGE_VERSION

MCP_SERVER_NAME = "slop-guard"
mcp_server = FastMCP(MCP_SERVER_NAME)
DEFAULT_PIPELINE = Pipeline.from_jsonl()
ACTIVE_PIPELINE = DEFAULT_PIPELINE


def _analyze(
    text: str,
    hyperparameters: Hyperparameters,
    pipeline: Pipeline | None = None,
) -> dict:
    """Run all configured rules and return score, diagnostics, and advice."""
    document = AnalysisDocument.from_text(text)

    if document.word_count < hyperparameters.short_text_word_count:
        return short_text_result(
            document.word_count,
            initial_counts(),
            hyperparameters,
        )

    active_pipeline = ACTIVE_PIPELINE if pipeline is None else pipeline
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

    return {
        "score": score,
        "band": band,
        "word_count": document.word_count,
        "violations": [violation.to_payload() for violation in state.violations],
        "counts": state.counts,
        "total_penalty": total_penalty,
        "weighted_sum": round(weighted_sum, 2),
        "density": round(density, 2),
        "advice": deduplicate_advice(list(state.advice)),
    }


@mcp_server.tool()
def check_slop(text: str) -> str:
    """Analyze text for AI slop patterns.

    Returns a JSON object with a score (0-100), band label, list of specific
    violations with context, and actionable advice for each issue found.
    """
    result = _analyze(text, HYPERPARAMETERS)
    return json.dumps(result, indent=2)


@mcp_server.tool()
def check_slop_file(file_path: str) -> str:
    """Analyze a file for AI slop patterns.

    Reads the file at the given path and runs the same analysis as check_slop.
    Returns a JSON object with a score (0-100), band label, list of specific
    violations with context, and actionable advice for each issue found.
    """
    path = Path(file_path)
    if not path.is_file():
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - returning tool-safe error payload
        return json.dumps({"error": f"Could not read file: {exc}"})

    result = _analyze(text, HYPERPARAMETERS)
    result["file"] = file_path
    return json.dumps(result, indent=2)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the MCP server CLI parser."""
    parser = argparse.ArgumentParser(
        prog="slop-guard",
        description="Run the slop-guard MCP server on stdio.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=PACKAGE_VERSION,
        help="Show package version and exit.",
    )
    parser.add_argument(
        "-c", "--config",
        default=None,
        metavar="JSONL",
        help="Path to JSONL rule configuration. Defaults to packaged settings.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the slop-guard MCP server on stdio."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    global ACTIVE_PIPELINE
    ACTIVE_PIPELINE = Pipeline.from_jsonl(args.config)
    mcp_server.run()
