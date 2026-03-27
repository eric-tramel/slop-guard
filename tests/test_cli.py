"""Tests for ``sg`` CLI argument and output behavior."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pytest

from slop_guard.analysis import word_count
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


def test_rejects_empty_string_input(
    capsys: pytest.CaptureFixture[str],
    cli_pipeline,
) -> None:
    """An empty quoted input should fail with a direct validation error."""
    exit_code = cli.cli_main([""])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_ERROR
    assert captured.out == ""
    assert "sg: input 1 is empty" in captured.err
    assert "No such file" not in captured.err
    assert cli_pipeline.loaded_paths == []


def test_rejects_empty_string_input_after_valid_argument(
    capsys: pytest.CaptureFixture[str],
    cli_pipeline,
    write_text_file,
) -> None:
    """Any empty positional argument should fail before analysis begins."""
    sample = write_text_file("sample.md", "alpha")

    exit_code = cli.cli_main([str(sample), ""])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_ERROR
    assert captured.out == ""
    assert "sg: input 2 is empty" in captured.err
    assert cli_pipeline.loaded_paths == []


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


def test_long_inline_text_falls_back_from_path_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inline prose should stay inline when ``Path.is_file()`` raises ``OSError``."""
    long_text = "This is a long inline prose sample. " * 16

    def fake_is_file(self: Path) -> bool:
        if self == Path(long_text):
            raise OSError(63, "File name too long")
        return False

    monkeypatch.setattr(Path, "is_file", fake_is_file)

    targets = cli._resolve_inputs(argparse.Namespace(inputs=[long_text]))

    assert targets == [
        cli.InputTarget(kind="text", value=long_text, display_label="<text:1>")
    ]


def test_existing_file_with_spaces_still_resolves_as_file(write_text_file) -> None:
    """Existing file paths should outrank inline-text detection."""
    spaced_file = write_text_file("notes with spaces.md", "alpha")

    targets = cli._resolve_inputs(argparse.Namespace(inputs=[str(spaced_file)]))

    assert targets == [
        cli.InputTarget(
            kind="file",
            value=spaced_file,
            display_label=str(spaced_file),
        )
    ]


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


def test_json_mode_rejects_empty_string_input(
    capsys: pytest.CaptureFixture[str],
    cli_pipeline,
) -> None:
    """JSON mode should still reject an empty quoted input."""
    exit_code = cli.cli_main(["--json", ""])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_ERROR
    assert captured.out == ""
    assert "sg: input 1 is empty" in captured.err
    assert cli_pipeline.loaded_paths == []


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


def test_json_mode_ignores_markdown_code_for_slop_word_counts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON mode should exclude Markdown code from slop-word counts."""
    text = (
        "The snippet below is only an implementation example for the guide.\n\n"
        "`navigate(\"landscape\")` and `robust journey` are code samples.\n\n"
        "```python\n"
        "result = navigate(\"landscape\")\n"
        "return robust_framework.journey()\n"
        "```\n\n"
        "The actual rollout detail is crucial for operators today."
    )
    prose_only = (
        "The snippet below is only an implementation example for the guide.\n\n"
        "and are code samples.\n\n"
        "The actual rollout detail is crucial for operators today."
    )

    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(text))

    exit_code = cli.cli_main(["--json", "-"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    matches = [
        violation["match"]
        for violation in payload["violations"]
        if violation["rule"] == "slop_word"
    ]

    assert exit_code == cli.EXIT_OK
    assert captured.err == ""
    assert payload["source"] == text
    assert payload["word_count"] == word_count(prose_only)
    assert payload["counts"]["slop_words"] == 1
    assert matches == ["crucial"]


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


def test_missing_config_path_reports_clean_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing ``-c/--config`` should fail cleanly with exit code 2."""
    missing_config = tmp_path / "missing.jsonl"

    exit_code = cli.cli_main(["-c", str(missing_config), "This is some test text"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_ERROR
    assert captured.out == ""
    assert captured.err.strip() == f"sg: {missing_config}: No such file"
    assert "Traceback" not in captured.err


def test_directory_config_path_reports_clean_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Directory ``-c/--config`` paths should fail cleanly with exit code 2."""
    config_dir = tmp_path / "config-dir"
    config_dir.mkdir()

    exit_code = cli.cli_main(["-c", str(config_dir), "This is some test text"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_ERROR
    assert captured.out == ""
    assert captured.err.strip() == f"sg: {config_dir}: Is a directory"
    assert "Traceback" not in captured.err


def test_invalid_utf8_config_path_reports_clean_error(
    write_bytes_file,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid UTF-8 ``-c/--config`` files should fail cleanly with exit code 2."""
    config_file = write_bytes_file("invalid.jsonl", b"\x80broken-jsonl")

    exit_code = cli.cli_main(["-c", str(config_file), "This is some test text"])
    captured = capsys.readouterr()

    assert exit_code == cli.EXIT_ERROR
    assert captured.out == ""
    assert captured.err.strip() == f"sg: {config_file}: Invalid UTF-8"
    assert "Traceback" not in captured.err


def test_rejects_legacy_glob_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """The removed ``--glob`` option should now fail argument parsing."""
    with pytest.raises(SystemExit) as raised:
        cli.cli_main(["--glob", "*.md"])

    assert raised.value.code == cli.EXIT_ERROR
    assert "unrecognized arguments: --glob" in capsys.readouterr().err
