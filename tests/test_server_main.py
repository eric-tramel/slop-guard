"""Tests for the ``slop-guard`` MCP server launcher CLI."""

from __future__ import annotations

from slop_guard import server


def test_main_loads_default_pipeline_when_config_not_provided(
    monkeypatch,
) -> None:
    """Server launch should load packaged pipeline defaults by default."""
    loaded_paths: list[str | None] = []
    sentinel_pipeline = object()
    run_calls: list[bool] = []

    def fake_from_jsonl(cls, path: str | None = None):  # noqa: ANN001
        loaded_paths.append(path)
        return sentinel_pipeline

    monkeypatch.setattr(server.Pipeline, "from_jsonl", classmethod(fake_from_jsonl))
    monkeypatch.setattr(server.mcp_server, "run", lambda: run_calls.append(True))

    server.main([])

    assert loaded_paths == [None]
    assert run_calls == [True]
    assert server.ACTIVE_PIPELINE is sentinel_pipeline


def test_main_loads_custom_pipeline_when_config_is_provided(
    monkeypatch,
) -> None:
    """Server launch should load a custom pipeline when ``-c`` is passed."""
    loaded_paths: list[str | None] = []
    sentinel_pipeline = object()
    run_calls: list[bool] = []
    config_path = "/tmp/custom-settings.jsonl"

    def fake_from_jsonl(cls, path: str | None = None):  # noqa: ANN001
        loaded_paths.append(path)
        return sentinel_pipeline

    monkeypatch.setattr(server.Pipeline, "from_jsonl", classmethod(fake_from_jsonl))
    monkeypatch.setattr(server.mcp_server, "run", lambda: run_calls.append(True))

    server.main(["-c", config_path])

    assert loaded_paths == [config_path]
    assert run_calls == [True]
    assert server.ACTIVE_PIPELINE is sentinel_pipeline
