"""Tests for the ``slop-guard`` MCP server launcher CLI."""

from __future__ import annotations

import pytest

from slop_guard import server
from slop_guard.version import PACKAGE_VERSION


@pytest.fixture
def server_pipeline(patch_pipeline, recording_pipeline_cls):
    """Patch the server module to use the shared recording pipeline."""
    patch_pipeline(server)
    return recording_pipeline_cls


def test_main_version_flag_prints_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``slop-guard --version`` should print package version and exit cleanly."""
    with pytest.raises(SystemExit) as raised:
        server.main(["--version"])

    assert raised.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == PACKAGE_VERSION
    assert captured.err == ""


def test_main_loads_default_pipeline_when_config_not_provided(
    monkeypatch: pytest.MonkeyPatch,
    server_pipeline,
) -> None:
    """Server launch should load packaged pipeline defaults by default."""
    run_calls: list[bool] = []

    monkeypatch.setattr(server.mcp_server, "run", lambda: run_calls.append(True))

    server.main([])

    assert server_pipeline.loaded_paths == [None]
    assert run_calls == [True]
    assert server.ACTIVE_PIPELINE is server_pipeline.last_instance


def test_main_loads_custom_pipeline_when_config_is_provided(
    monkeypatch: pytest.MonkeyPatch,
    server_pipeline,
) -> None:
    """Server launch should load a custom pipeline when ``-c`` is passed."""
    run_calls: list[bool] = []
    config_path = "/tmp/custom-settings.jsonl"

    monkeypatch.setattr(server.mcp_server, "run", lambda: run_calls.append(True))

    server.main(["-c", config_path])

    assert server_pipeline.loaded_paths == [config_path]
    assert run_calls == [True]
    assert server.ACTIVE_PIPELINE is server_pipeline.last_instance
