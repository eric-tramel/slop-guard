"""Tests for MCP tool behavior exposed by the slop-guard server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from slop_guard import server

def test_check_slop_tool_returns_structured_output(mcp_tool, run_mcp_tool) -> None:
    """``check_slop`` should expose structured MCP output without a wrapper key."""
    content, structured = run_mcp_tool("check_slop", {"text": "Hello world"})
    tool = mcp_tool("check_slop")

    assert len(content) == 1
    assert structured["score"] == 100
    assert structured["band"] == "clean"
    assert structured["word_count"] == 2
    assert "result" not in structured
    assert "score" in tool.output_schema["properties"]


def test_check_slop_tool_includes_violation_offsets(run_mcp_tool) -> None:
    """``check_slop`` violations should include direct character offsets."""
    text = (
        "Alpha crucial beta gamma delta epsilon zeta eta theta iota kappa "
        "crucial lambda."
    )

    _content, structured = run_mcp_tool("check_slop", {"text": text})

    violation = next(
        item for item in structured["violations"] if item["rule"] == "slop_word"
    )

    assert isinstance(violation["start"], int)
    assert isinstance(violation["end"], int)
    assert text[violation["start"] : violation["end"]].lower() == violation["match"]


def test_check_slop_file_tool_returns_structured_output(
    write_text_file,
    run_mcp_tool,
) -> None:
    """``check_slop_file`` should include the source path in structured output."""
    target = write_text_file("sample.txt", "Hello world")

    content, structured = run_mcp_tool("check_slop_file", {"file_path": str(target)})

    assert len(content) == 1
    assert structured["file"] == str(target)
    assert structured["score"] == 100
    assert "result" not in structured


@pytest.mark.parametrize(
    ("file_path", "message"),
    [
        ("", "File path must not be empty."),
        ("/tmp/does-not-exist-slop-guard.txt", "File not found: /tmp/does-not-exist-slop-guard.txt"),
    ],
)
def test_check_slop_file_tool_raises_mcp_errors_for_invalid_paths(
    file_path: str,
    message: str,
    mcp_tool,
) -> None:
    """Invalid file paths should fail through the MCP tool error channel."""
    tool = mcp_tool("check_slop_file")

    with pytest.raises(ToolError, match=message):
        asyncio.run(tool.run({"file_path": file_path}, convert_result=True))


def test_check_slop_file_tool_rejects_directories(
    tmp_path: Path,
    mcp_tool,
) -> None:
    """Directory targets should raise a precise MCP tool error."""
    tool = mcp_tool("check_slop_file")

    with pytest.raises(
        ToolError,
        match=f"Path is a directory, not a file: {tmp_path}",
    ):
        asyncio.run(tool.run({"file_path": str(tmp_path)}, convert_result=True))


def test_read_analysis_file_normalizes_os_path_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OS-level path failures should surface as stable validation errors."""

    def raise_name_too_long(_: Path) -> bool:
        raise OSError(63, "File name too long")

    monkeypatch.setattr(server.Path, "is_dir", raise_name_too_long)

    with pytest.raises(ValueError, match="Invalid file path: File name too long"):
        server._read_analysis_file("a" * 5000)


def test_check_slop_file_tool_normalizes_decode_errors(
    write_bytes_file,
    mcp_tool,
) -> None:
    """Binary inputs should fail through the normalized MCP read-error path."""
    target = write_bytes_file("binary.bin", b"\xff\xfe\xfa")

    tool = mcp_tool("check_slop_file")

    with pytest.raises(
        ToolError,
        match=r"Could not read file: .*utf-8.*can't decode byte 0xff",
    ):
        asyncio.run(tool.run({"file_path": str(target)}, convert_result=True))
