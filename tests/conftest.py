"""Shared pytest fixtures for slop-guard test modules."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar, TypeAlias

import pytest

from slop_guard import server

ToolGetter: TypeAlias = Callable[[str], Any]
ToolRunner: TypeAlias = Callable[
    [str, dict[str, object]],
    tuple[list[object], dict[str, object]],
]
PipelinePatcher: TypeAlias = Callable[[Any], type["RecordingPipeline"]]
TextFileWriter: TypeAlias = Callable[[str, str], Path]
BytesFileWriter: TypeAlias = Callable[[str, bytes], Path]


@dataclass(frozen=True)
class FitCall:
    """Recorded fit invocation details for the shared pipeline test double."""

    samples: tuple[str, ...]
    labels: tuple[int, ...]
    calibrate_contrastive: bool


class RecordingPipeline:
    """Shared test double that records pipeline loading, fit, and output calls."""

    loaded_paths: ClassVar[list[str | None]] = []
    fit_calls: ClassVar[list[FitCall]] = []
    output_paths: ClassVar[list[Path]] = []
    last_instance: ClassVar["RecordingPipeline | None"] = None

    @classmethod
    def reset(cls) -> None:
        """Clear all class-level recorder state."""
        cls.loaded_paths = []
        cls.fit_calls = []
        cls.output_paths = []
        cls.last_instance = None

    @classmethod
    def from_jsonl(cls, path: str | None = None) -> "RecordingPipeline":
        """Record the requested config path and return a pipeline instance."""
        cls.loaded_paths.append(path)
        instance = cls()
        cls.last_instance = instance
        return instance

    def fit(
        self,
        samples: list[str],
        labels: list[int] | None = None,
        *,
        calibrate_contrastive: bool = True,
    ) -> "RecordingPipeline":
        """Record fit inputs and return self for fluent call sites."""
        self.__class__.fit_calls.append(
            FitCall(
                samples=tuple(samples),
                labels=tuple([] if labels is None else labels),
                calibrate_contrastive=calibrate_contrastive,
            )
        )
        return self

    def to_jsonl(self, path: str | Path) -> None:
        """Record the requested output path."""
        self.__class__.output_paths.append(Path(path))


@pytest.fixture(autouse=True)
def restore_active_pipeline() -> Iterator[None]:
    """Restore the active server pipeline after each test."""
    original_pipeline = server.ACTIVE_PIPELINE
    yield
    server.ACTIVE_PIPELINE = original_pipeline


@pytest.fixture
def recording_pipeline_cls() -> Iterator[type[RecordingPipeline]]:
    """Provide a reset shared pipeline recorder class."""
    RecordingPipeline.reset()
    yield RecordingPipeline
    RecordingPipeline.reset()


@pytest.fixture
def patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    recording_pipeline_cls: type[RecordingPipeline],
) -> PipelinePatcher:
    """Patch a module's ``Pipeline`` binding with the shared recorder double."""

    def _patch(module: Any) -> type[RecordingPipeline]:
        monkeypatch.setattr(module, "Pipeline", recording_pipeline_cls)
        return recording_pipeline_cls

    return _patch


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


@pytest.fixture
def write_text_file(tmp_path: Path) -> TextFileWriter:
    """Write a UTF-8 text file below ``tmp_path`` and return its path."""

    def _write(relative_path: str, content: str) -> Path:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_bytes_file(tmp_path: Path) -> BytesFileWriter:
    """Write a binary file below ``tmp_path`` and return its path."""

    def _write(relative_path: str, content: bytes) -> Path:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    return _write
