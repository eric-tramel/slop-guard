"""Tests for ``sg`` CLI argument and output behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from slop_guard import cli


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


def test_accepts_inline_text_input(capsys: pytest.CaptureFixture[str]) -> None:
    """Inline quoted text should be analyzed as prose input."""
    exit_code = cli.cli_main(["This is some test text"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_OK
    assert captured.err == ""
    assert captured.out.startswith("<text:1>: ")
    assert "/100 [" in captured.out


def test_concise_mode_prints_score_only(capsys: pytest.CaptureFixture[str]) -> None:
    """Concise mode should output only a numeric score."""
    exit_code = cli.cli_main(["-c", "This is some test text"])
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

    def fake_analyze_file(path: Path, _hyperparameters: object) -> dict[str, object]:
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


def test_rejects_legacy_glob_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """The removed ``--glob`` option should now fail argument parsing."""
    with pytest.raises(SystemExit) as raised:
        cli.cli_main(["--glob", "*.md"])

    assert raised.value.code == cli.EXIT_ERROR
    assert "unrecognized arguments: --glob" in capsys.readouterr().err
