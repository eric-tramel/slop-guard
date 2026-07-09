"""Report-only adapter for supported main-agent Stop hook events."""

import argparse
import json
import sys
from dataclasses import dataclass
from typing import NoReturn

from slop_guard.engine import analyze_text
from slop_guard.version import PACKAGE_VERSION

EXIT_OK = 0
EXIT_ERROR = 1
_MAX_RULE_NAMES = 5
_MAX_RULE_NAME_CHARS = 48
_MAX_ERROR_DETAIL_CHARS = 200


@dataclass(frozen=True)
class StopEvent:
    """Validated main-agent Stop event.

    Attributes:
        last_assistant_message: Final assistant text to analyze.
    """

    last_assistant_message: str


@dataclass(frozen=True)
class HookReport:
    """Safe summary of an analysis result for hook output.

    Attributes:
        score: Analyzer score from zero to one hundred.
        violation_count: Total number of violations found.
        rule_names: Bounded, deduplicated rule identifiers.
    """

    score: int
    violation_count: int
    rule_names: tuple[str, ...]


class HookArgumentError(ValueError):
    """Raised when ``sg-hook`` receives unsupported command arguments."""


class _HookArgumentParser(argparse.ArgumentParser):
    """Argument parser that never uses exit status 2 for usage errors."""

    def error(self, message: str) -> NoReturn:
        """Raise a catchable usage error instead of exiting with status 2."""
        raise HookArgumentError(message)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the ``sg-hook`` argument parser."""
    parser = _HookArgumentParser(
        prog="sg-hook",
        description="Analyze a supported final-answer Stop hook event from stdin.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=PACKAGE_VERSION,
        help="Show package version and exit.",
    )
    return parser


def _bounded_line(value: str, limit: int) -> str:
    """Collapse whitespace and truncate a value to one bounded line."""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def parse_stop_event(payload: str) -> StopEvent | None:
    """Parse one JSON payload as a supported main-agent Stop event.

    Unrelated object fields are ignored. Unsupported events and missing,
    malformed, active, null, or empty runtime fields are safe no-ops.

    Args:
        payload: Serialized hook input read from stdin.

    Returns:
        A validated Stop event, or ``None`` when the payload is unsupported.

    Raises:
        json.JSONDecodeError: The payload is not valid JSON.
    """
    raw: object = json.loads(payload)
    if not isinstance(raw, dict):
        return None
    if raw.get("hook_event_name") != "Stop":
        return None

    stop_hook_active = raw.get("stop_hook_active")
    if not isinstance(stop_hook_active, bool):
        return None

    last_assistant_message = raw.get("last_assistant_message")
    if last_assistant_message is not None and not isinstance(
        last_assistant_message, str
    ):
        return None
    if stop_hook_active or not last_assistant_message:
        return None
    if not last_assistant_message.strip():
        return None

    return StopEvent(last_assistant_message=last_assistant_message)


def analyze_stop_event(event: StopEvent) -> HookReport | None:
    """Analyze a validated Stop event and retain only safe report fields.

    Args:
        event: Validated Stop event containing final assistant text.

    Returns:
        A bounded report when violations exist, otherwise ``None``.
    """
    result = analyze_text(event.last_assistant_message)
    violations = result["violations"]
    if not violations:
        return None

    rule_names: list[str] = []
    seen: set[str] = set()
    for violation in violations:
        rule_name = _bounded_line(violation["rule"], _MAX_RULE_NAME_CHARS)
        if not rule_name or rule_name in seen:
            continue
        seen.add(rule_name)
        rule_names.append(rule_name)
        if len(rule_names) == _MAX_RULE_NAMES:
            break

    return HookReport(
        score=result["score"],
        violation_count=len(violations),
        rule_names=tuple(rule_names),
    )


def render_hook_response(report: HookReport) -> str:
    """Render one compact, report-only hook response.

    Args:
        report: Safe analysis summary with no source excerpts.

    Returns:
        Compact JSON containing only a ``systemMessage`` field.
    """
    violation_label = "violation" if report.violation_count == 1 else "violations"
    rules = ", ".join(report.rule_names) if report.rule_names else "not reported"
    message = (
        f"Slop-Guard score {report.score}/100; "
        f"{report.violation_count} {violation_label}; rules: {rules}. "
        "Call the Slop-Guard MCP tools for details and advice."
    )
    return json.dumps(
        {"systemMessage": message},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _emit_error(detail: str) -> None:
    """Write one bounded hook error to stderr."""
    bounded_detail = _bounded_line(detail, _MAX_ERROR_DETAIL_CHARS)
    sys.stderr.write(f"sg-hook: {bounded_detail}\n")


def hook_main(argv: list[str] | None = None) -> int:
    """Run the ``sg-hook`` adapter.

    Args:
        argv: Argument list, defaulting to ``sys.argv[1:]``.

    Returns:
        Zero for handled events and safe no-ops, or one for hook failures.
    """
    parser = _build_parser()
    try:
        parser.parse_args(argv)
    except HookArgumentError as exc:
        _emit_error(f"invalid arguments: {exc}")
        return EXIT_ERROR

    try:
        payload = sys.stdin.read()
        event = parse_stop_event(payload)
    except json.JSONDecodeError:
        _emit_error("invalid JSON input")
        return EXIT_ERROR
    except Exception as exc:
        error_type = _bounded_line(type(exc).__name__, 64)
        _emit_error(f"could not read or parse hook input ({error_type})")
        return EXIT_ERROR

    if event is None:
        return EXIT_OK

    try:
        report = analyze_stop_event(event)
        if report is None:
            return EXIT_OK
        response = render_hook_response(report)
    except Exception as exc:
        error_type = _bounded_line(type(exc).__name__, 64)
        _emit_error(f"analysis failed ({error_type})")
        return EXIT_ERROR

    try:
        sys.stdout.write(f"{response}\n")
    except Exception as exc:
        error_type = _bounded_line(type(exc).__name__, 64)
        _emit_error(f"could not write hook response ({error_type})")
        return EXIT_ERROR
    return EXIT_OK


def main() -> None:
    """Exit with the ``sg-hook`` adapter return code."""
    sys.exit(hook_main())
