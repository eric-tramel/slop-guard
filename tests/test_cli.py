"""Tests for ``sg`` CLI argument and output behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from slop_guard import cli
from slop_guard.version import PACKAGE_VERSION


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


def test_streams_file_results_as_each_file_finishes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-JSON output should emit per-file results in processing order."""
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")

    events: list[str] = []

    def fake_analyze_file(
        path: Path,
        _hyperparameters: object,
        _pipeline: object,
    ) -> dict[str, object]:
        events.append(f"analyze:{path.name}")
        return _fake_result(str(path))

    def fake_emit_result(result: dict[str, object], _args: object) -> None:
        events.append(f"emit:{result['source']}")

    monkeypatch.setattr(cli, "_analyze_file", fake_analyze_file)
    monkeypatch.setattr(cli, "_emit_result", fake_emit_result)

    exit_code = cli.cli_main([str(first), str(second)])

    assert exit_code == cli.EXIT_OK
    assert events == [
        f"analyze:{first.name}",
        f"emit:{first}",
        f"analyze:{second.name}",
        f"emit:{second}",
    ]


def test_config_option_loads_pipeline_from_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Passing ``-c/--config`` should load the requested JSONL pipeline."""
    sample_file = tmp_path / "sample.md"
    sample_file.write_text("alpha", encoding="utf-8")
    config_file = tmp_path / "custom.jsonl"
    config_file.write_text("{}", encoding="utf-8")

    loaded_paths: list[str | None] = []

    class _FakePipeline:
        @classmethod
        def from_jsonl(cls, path: str | None = None) -> "_FakePipeline":
            loaded_paths.append(path)
            return cls()

    def fake_analyze_file(
        path: Path,
        _hyperparameters: object,
        _pipeline: object,
    ) -> dict[str, object]:
        return _fake_result(str(path))

    monkeypatch.setattr(cli, "Pipeline", _FakePipeline)
    monkeypatch.setattr(cli, "_analyze_file", fake_analyze_file)

    exit_code = cli.cli_main(["-c", str(config_file), str(sample_file)])

    assert exit_code == cli.EXIT_OK
    assert loaded_paths == [str(config_file)]


def test_rejects_legacy_glob_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """The removed ``--glob`` option should now fail argument parsing."""
    with pytest.raises(SystemExit) as raised:
        cli.cli_main(["--glob", "*.md"])

    assert raised.value.code == cli.EXIT_ERROR
    assert "unrecognized arguments: --glob" in capsys.readouterr().err
