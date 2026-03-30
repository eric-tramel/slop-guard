"""MCP server for prose linting with modular rule execution."""

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from slop_guard.config import DEFAULT_HYPERPARAMETERS
from slop_guard.engine import analyze_text
from slop_guard.models import AnalysisPayload
from slop_guard.rules.pipeline import Pipeline
from slop_guard.version import PACKAGE_VERSION

MCP_SERVER_NAME = "slop-guard"
mcp_server = FastMCP(MCP_SERVER_NAME)
DEFAULT_PIPELINE = Pipeline.from_jsonl()
ACTIVE_PIPELINE = DEFAULT_PIPELINE


@mcp_server.tool()
def check_slop(text: str) -> AnalysisPayload:
    """Analyze text for AI slop patterns.

    Returns a JSON object with a score (0-100), band label, list of specific
    violations with context and character offsets, and actionable advice for
    each issue found.
    """
    return analyze_text(
        text,
        hyperparameters=DEFAULT_HYPERPARAMETERS,
        pipeline=ACTIVE_PIPELINE,
    )


def _read_analysis_file(file_path: str) -> str:
    """Read an analysis target file and raise MCP-safe path errors."""
    if not file_path:
        raise ToolError("File path must not be empty.")

    path = Path(file_path)
    try:
        if path.is_dir():
            raise ToolError(f"Path is a directory, not a file: {file_path}")
        if not path.is_file():
            raise ToolError(f"File not found: {file_path}")
    except OSError as exc:
        detail = exc.strerror or str(exc)
        raise ToolError(f"Invalid file path: {detail}") from exc

    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        detail = getattr(exc, "strerror", None) or str(exc)
        raise ToolError(f"Could not read file: {detail}") from exc


@mcp_server.tool()
def check_slop_file(file_path: str) -> AnalysisPayload:
    """Analyze a file for AI slop patterns.

    Reads the file at the given path and runs the same analysis as check_slop.
    Returns a JSON object with a score (0-100), band label, list of specific
    violations with context and character offsets, and actionable advice for
    each issue found.
    """
    text = _read_analysis_file(file_path)
    return analyze_text(
        text,
        hyperparameters=DEFAULT_HYPERPARAMETERS,
        pipeline=ACTIVE_PIPELINE,
    )


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
        "-c",
        "--config",
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
