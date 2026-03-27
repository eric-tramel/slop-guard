"""Shared pytest fixtures for slop-guard test modules."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from typing import Any, TypeAlias

import pytest

from slop_guard import server

ToolGetter: TypeAlias = Callable[[str], Any]
ToolRunner: TypeAlias = Callable[
    [str, dict[str, object]],
    tuple[list[object], dict[str, object]],
]


@pytest.fixture(autouse=True)
def restore_active_pipeline() -> Iterator[None]:
    """Restore the active server pipeline after each test."""
    original_pipeline = server.ACTIVE_PIPELINE
    yield
    server.ACTIVE_PIPELINE = original_pipeline


@pytest.fixture
def mcp_tool() -> ToolGetter:
    """Return an MCP tool by name and fail loudly if it is missing."""

    def _get(name: str) -> Any:
        tool = server.mcp_server._tool_manager.get_tool(name)
        assert tool is not None, f"missing MCP tool: {name}"
        return tool

    return _get


@pytest.fixture
def run_mcp_tool(mcp_tool: ToolGetter) -> ToolRunner:
    """Run an MCP tool and return its content plus structured payload."""

    def _run(
        name: str,
        arguments: dict[str, object],
    ) -> tuple[list[object], dict[str, object]]:
        tool = mcp_tool(name)
        content, structured = asyncio.run(tool.run(arguments, convert_result=True))
        assert isinstance(content, list)
        assert isinstance(structured, dict)
        return content, structured

    return _run
