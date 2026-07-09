"""Behavior tests for the report-only ``sg-hook`` adapter."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _pytest.capture import CaptureResult

from slop_guard.apps import hook
from slop_guard.version import PACKAGE_VERSION

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "hooks"
VIOLATING_TEXT = (
    "This is a crucial and groundbreaking paradigm that feels remarkably "
    "innovative and comprehensive overall."
)


def _invoke_hook(
    payload: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str] | None = None,
) -> tuple[int, CaptureResult[str]]:
    """Run the adapter against one stdin payload and capture its protocol streams."""
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(payload))
    exit_code = hook.hook_main([] if argv is None else argv)
    return exit_code, capsys.readouterr()


@pytest.mark.parametrize(
    ("fixture_name", "expected_fields"),
    (
        (
            "claude-stop.json",
            {
                "session_id",
                "transcript_path",
                "cwd",
                "permission_mode",
                "hook_event_name",
                "stop_hook_active",
                "last_assistant_message",
                "background_tasks",
                "session_crons",
            },
        ),
        (
            "codex-stop.json",
            {
                "cwd",
                "hook_event_name",
                "last_assistant_message",
                "model",
                "permission_mode",
                "session_id",
                "stop_hook_active",
                "transcript_path",
                "turn_id",
            },
        ),
    ),
)
def test_exact_client_stop_fixtures_emit_one_compact_report(
    fixture_name: str,
    expected_fields: set[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exact Claude and Codex Stop shapes should reach the same safe adapter."""
    serialized = (FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8")
    fixture = json.loads(serialized)

    assert set(fixture) == expected_fields
    assert fixture["last_assistant_message"] == VIOLATING_TEXT

    exit_code, captured = _invoke_hook(serialized, monkeypatch, capsys)

    assert exit_code == hook.EXIT_OK
    assert captured.err == ""
    response = json.loads(captured.out)
    assert set(response) == {"systemMessage"}
    assert captured.out == (
        json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    assert "Slop-Guard score" in response["systemMessage"]
    assert "slop_word" in response["systemMessage"]
    assert VIOLATING_TEXT not in captured.out


@pytest.mark.parametrize(
    "payload",
    (
        None,
        [],
        {},
        {"hook_event_name": "SessionEnd"},
        {
            "hook_event_name": 7,
            "stop_hook_active": False,
            "last_assistant_message": VIOLATING_TEXT,
        },
        {
            "hook_event_name": "Stop",
            "last_assistant_message": VIOLATING_TEXT,
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": "false",
            "last_assistant_message": VIOLATING_TEXT,
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": None,
            "last_assistant_message": VIOLATING_TEXT,
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": [VIOLATING_TEXT],
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": None,
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": "",
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": " \n\t ",
        },
        {
            "hook_event_name": "Stop",
            "stop_hook_active": True,
            "last_assistant_message": VIOLATING_TEXT,
        },
    ),
    ids=(
        "null-payload",
        "wrong-payload-type",
        "missing-event",
        "unsupported-event",
        "wrong-event-type",
        "missing-active-flag",
        "missing-message",
        "wrong-active-type",
        "null-active-flag",
        "wrong-message-type",
        "null-message",
        "empty-message",
        "blank-message",
        "already-active",
    ),
)
def test_unsupported_or_malformed_fields_are_silent_noops(
    payload: object,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unsupported events and malformed runtime fields must not run analysis."""

    def fail_if_analyzed(_text: str) -> dict[str, object]:
        pytest.fail("unsupported hook payload reached the analyzer")

    monkeypatch.setattr(hook, "analyze_text", fail_if_analyzed)

    exit_code, captured = _invoke_hook(json.dumps(payload), monkeypatch, capsys)

    assert exit_code == hook.EXIT_OK
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    "message",
    (
        "All done.",
        (
            "The cache returned the stored record. The handler sent that record "
            "to the caller without another database query."
        ),
    ),
    ids=("short", "clean"),
)
def test_short_and_clean_messages_are_silent_noops(
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A supported Stop event with no findings should emit zero protocol bytes."""
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": message,
        }
    )

    exit_code, captured = _invoke_hook(payload, monkeypatch, capsys)

    assert exit_code == hook.EXIT_OK
    assert captured.out == ""
    assert captured.err == ""


def test_violating_message_emits_only_the_compact_system_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A finding should use the client protocol's compact report-only response."""
    monkeypatch.setattr(
        hook,
        "analyze_text",
        lambda _text: {
            "score": 37,
            "violations": [
                {"rule": "slop_word"},
                {"rule": "triadic"},
            ],
        },
    )
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": VIOLATING_TEXT,
        }
    )

    exit_code, captured = _invoke_hook(payload, monkeypatch, capsys)

    assert exit_code == hook.EXIT_OK
    assert captured.err == ""
    assert captured.out == (
        '{"systemMessage":"Slop-Guard score 37/100; 2 violations; rules: '
        'slop_word, triadic. Call the Slop-Guard MCP tools for details and advice."}\n'
    )


def test_rule_count_names_and_lengths_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reports retain the total count but expose at most five bounded rule IDs."""
    long_name = "long rule name with whitespace " + ("x" * 80)
    violations = [
        {"rule": "first"},
        {"rule": "first"},
        {"rule": long_name},
        {"rule": "third\nrule"},
        {"rule": "fourth"},
        {"rule": "fifth"},
        {"rule": "sixth"},
        {"rule": "seventh"},
    ]
    monkeypatch.setattr(
        hook,
        "analyze_text",
        lambda _text: {"score": 12, "violations": violations},
    )

    report = hook.analyze_stop_event(hook.StopEvent(VIOLATING_TEXT))

    assert report is not None
    assert report.violation_count == len(violations)
    assert report.rule_names == (
        "first",
        f"{long_name[:47].rstrip()}…",
        "third rule",
        "fourth",
        "fifth",
    )
    assert all(len(name) <= 48 and "\n" not in name for name in report.rule_names)


def test_report_does_not_leak_source_match_context_or_analyzer_advice(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Only safe aggregate fields may cross the hook output boundary."""
    secrets = {
        "source": "PRIVATE_SOURCE_781",
        "match": "PRIVATE_MATCH_782",
        "context": "PRIVATE_CONTEXT_783",
        "advice": "PRIVATE_ADVICE_784",
    }
    monkeypatch.setattr(
        hook,
        "analyze_text",
        lambda _text: {
            "score": 41,
            "source": secrets["source"],
            "advice": [secrets["advice"]],
            "violations": [
                {
                    "rule": "safe_rule_name",
                    "match": secrets["match"],
                    "context": secrets["context"],
                    "advice": secrets["advice"],
                }
            ],
        },
    )
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": secrets["source"],
        }
    )

    exit_code, captured = _invoke_hook(payload, monkeypatch, capsys)

    assert exit_code == hook.EXIT_OK
    assert captured.err == ""
    assert set(json.loads(captured.out)) == {"systemMessage"}
    assert "safe_rule_name" in captured.out
    assert all(secret not in captured.out for secret in secrets.values())


@pytest.mark.parametrize("payload", ("", "{", '"unterminated'))
def test_malformed_json_exits_one_with_zero_stdout(
    payload: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid JSON should fail open without emitting a client decision."""
    exit_code, captured = _invoke_hook(payload, monkeypatch, capsys)

    assert exit_code == hook.EXIT_ERROR
    assert exit_code != 2
    assert captured.out == ""
    assert captured.err == "sg-hook: invalid JSON input\n"


def test_analyzer_failure_exits_one_without_leaking_details_or_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Analyzer exceptions should become bounded generic diagnostics."""

    def fail_analysis(_text: str) -> dict[str, object]:
        raise RuntimeError("PRIVATE_ANALYZER_FAILURE_DETAIL")

    monkeypatch.setattr(hook, "analyze_text", fail_analysis)
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": VIOLATING_TEXT,
        }
    )

    exit_code, captured = _invoke_hook(payload, monkeypatch, capsys)

    assert exit_code == hook.EXIT_ERROR
    assert exit_code != 2
    assert captured.out == ""
    assert captured.err == "sg-hook: analysis failed (RuntimeError)\n"
    assert "PRIVATE_ANALYZER_FAILURE_DETAIL" not in captured.err


@pytest.mark.parametrize("argv", (["--unknown"], ["unexpected"], ["--version=yes"]))
def test_argument_errors_exit_one_with_zero_stdout(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Usage mistakes should never use argparse's exit-2 or stdout paths."""
    exit_code, captured = _invoke_hook("{}", monkeypatch, capsys, argv)

    assert exit_code == hook.EXIT_ERROR
    assert exit_code != 2
    assert captured.out == ""
    assert captured.err.startswith("sg-hook: invalid arguments: ")


def test_help_prints_usage_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The installed hook entry point should expose conventional help."""
    with pytest.raises(SystemExit) as raised:
        hook.hook_main(["--help"])

    assert raised.value.code == hook.EXIT_OK
    captured = capsys.readouterr()
    assert captured.out.startswith("usage: sg-hook ")
    assert "Stop hook event from stdin" in captured.out
    assert captured.err == ""


def test_version_prints_package_version_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The installed hook entry point should expose the package version."""
    with pytest.raises(SystemExit) as raised:
        hook.hook_main(["--version"])

    assert raised.value.code == hook.EXIT_OK
    captured = capsys.readouterr()
    assert captured.out == f"{PACKAGE_VERSION}\n"
    assert captured.err == ""
