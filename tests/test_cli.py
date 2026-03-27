"""Tests for ``sg`` CLI argument and output behavior."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from slop_guard import cli
from slop_guard.version import PACKAGE_VERSION


@pytest.fixture
def cli_pipeline(patch_pipeline, recording_pipeline_cls):
    """Patch the CLI module to use the shared recording pipeline."""
    patch_pipeline(cli)
    return recording_pipeline_cls


def _fake_result(source: str, score: int = 75) -> dict[str, object]:
    """Build a minimal analysis payload used in CLI tests."""
    return {
        "source": source,
        "score": score,
        "band": "light",
        "word_count": 4,
        "violations": [],
        "advice": [],
        "counts": {},
    }


def test_requires_at_least_one_input(capsys: pytest.CaptureFixture[str]) -> None:
    """Running ``sg`` with no args should exit with an argument error."""
    with pytest.raises(SystemExit) as raised:
        cli.cli_main([])

    assert raised.value.code == cli.EXIT_ERROR
    assert "the following arguments are required: INPUT" in capsys.readouterr().err


def test_version_flag_prints_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--version`` should print package version and exit cleanly."""
    with pytest.raises(SystemExit) as raised:
        cli.cli_main(["--version"])

    assert raised.value.code == cli.EXIT_OK
    captured = capsys.readouterr()
    assert captured.out.strip() == PACKAGE_VERSION
    assert captured.err == ""


def test_accepts_inline_text_input(capsys: pytest.CaptureFixture[str]) -> None:
    """Inline quoted text should be analyzed as prose input."""
    exit_code = cli.cli_main(["This is some test text"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_OK
    assert captured.err == ""
    assert captured.out.startswith("<text:1>: ")
    assert "/100 [" in captured.out


def test_score_only_mode_prints_score_only(capsys: pytest.CaptureFixture[str]) -> None:
    """Score-only mode should output only a numeric score."""
    exit_code = cli.cli_main(["-s", "This is some test text"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_OK
    assert captured.err == ""
    assert captured.out.strip().isdigit()


def test_json_mode_includes_source_field(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON mode should expose the raw inline input through ``source``."""
    exit_code = cli.cli_main(["--json", "This is some test text"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == cli.EXIT_OK
    assert captured.err == ""
    assert payload["source"] == "This is some test text"
    assert payload["score"] == 100


def test_json_mode_uses_stdin_text_as_source(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON mode should expose the piped stdin text through ``source``."""
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("stdin payload"))

    exit_code = cli.cli_main(["--json", "-"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == cli.EXIT_OK
    assert captured.err == ""
    assert payload["source"] == "stdin payload"
    assert payload["score"] == 100


def test_streams_file_results_as_each_file_finishes(
    monkeypatch: pytest.MonkeyPatch,
    write_text_file,
    cli_pipeline,
) -> None:
    """Non-JSON output should emit per-file results in processing order."""
    first = write_text_file("first.md", "alpha")
    second = write_text_file("second.md", "beta")

    events: list[str] = []

    def fake_analyze_file(
        path: Path,
        _hyperparameters: object,
        _pipeline: object,
    ) -> dict[str, object]:
        events.append(f"analyze:{path.name}")
        return _fake_result(str(path))

    def fake_emit_result(
        display_label: str,
        result: dict[str, object],
        _args: object,
    ) -> None:
        events.append(f"emit:{display_label}")
        events.append(f"json-source:{result['source']}")

    monkeypatch.setattr(cli, "_analyze_file", fake_analyze_file)
    monkeypatch.setattr(cli, "_emit_result", fake_emit_result)

    exit_code = cli.cli_main([str(first), str(second)])

    assert exit_code == cli.EXIT_OK
    assert cli_pipeline.loaded_paths == [None]
    assert events == [
        f"analyze:{first.name}",
        f"emit:{first}",
        f"json-source:{first}",
        f"analyze:{second.name}",
        f"emit:{second}",
        f"json-source:{second}",
    ]


def test_config_option_loads_pipeline_from_path(
    monkeypatch: pytest.MonkeyPatch,
    write_text_file,
    cli_pipeline,
) -> None:
    """Passing ``-c/--config`` should load the requested JSONL pipeline."""
    sample_file = write_text_file("sample.md", "alpha")
    config_file = write_text_file("custom.jsonl", "{}")

    def fake_analyze_file(
        path: Path,
        _hyperparameters: object,
        _pipeline: object,
    ) -> dict[str, object]:
        return _fake_result(str(path))

    monkeypatch.setattr(cli, "_analyze_file", fake_analyze_file)

    exit_code = cli.cli_main(["-c", str(config_file), str(sample_file)])

    assert exit_code == cli.EXIT_OK
    assert cli_pipeline.loaded_paths == [str(config_file)]


def test_rejects_legacy_glob_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """The removed ``--glob`` option should now fail argument parsing."""
    with pytest.raises(SystemExit) as raised:
        cli.cli_main(["--glob", "*.md"])

    assert raised.value.code == cli.EXIT_ERROR
    assert "unrecognized arguments: --glob" in capsys.readouterr().err
