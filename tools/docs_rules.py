"""Generate the rule library docs — one page per rule plus an index.

This helper introspects each rule class listed in
:mod:`slop_guard.rules.catalog`, parses its module docstring for the
common ``Objective`` / ``Example Rule Violations`` / ``Example
Non-Violations`` / ``Severity`` sections, pulls default config values out
of ``assets/default.jsonl``, and writes one Markdown page per rule under
``docs/rules/`` plus an ``index.md`` overview that links to them.
"""

from __future__ import annotations

import argparse
import html
import inspect
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, TypeAlias

from slop_guard.rules.base import Rule
from slop_guard.rules.catalog import DEFAULT_RULE_PATHS

RulePath: TypeAlias = str
ConfigMap: TypeAlias = dict[str, Any]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "docs" / "rules"
_REPO_SOURCE_REPO = "eric-tramel/slop-guard"
_REPO_SOURCE_URL = f"https://github.com/{_REPO_SOURCE_REPO}/blob/main"
_KNOWN_SECTIONS: frozenset[str] = frozenset(
    {
        "_summary",
        "Objective",
        "Severity",
        "Example Rule Violations",
        "Example Non-Violations",
    }
)
_BOT_LOGINS: frozenset[str] = frozenset(
    {"web-flow", "github-actions[bot]", "dependabot[bot]"}
)
_GH_ICON_SVG = (
    '<svg class="sg-source-chip__icon" viewBox="0 0 24 24" width="14" '
    'height="14" aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 '
    "9.39 7.86 10.91.58.11.79-.25.79-.56v-2.02c-3.2.7-3.87-1.54-3.87-1.54-"
    ".52-1.32-1.28-1.67-1.28-1.67-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 "
    "1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-"
    "5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.47.11-3.06 "
    "0 0 .97-.31 3.18 1.18.92-.26 1.9-.39 2.88-.4.98.01 1.96.14 2.88.4 "
    "2.2-1.49 3.17-1.18 3.17-1.18.64 1.59.24 2.77.12 3.06.74.81 1.19 1.84 "
    "1.19 3.1 0 4.43-2.69 5.4-5.26 5.68.41.36.78 1.06.78 2.15v3.19c0 .31"
    ".21.68.8.56 4.57-1.52 7.85-5.83 7.85-10.91C23.5 5.73 18.27.5 12 .5Z"
    '"/></svg>'
)

_LEVEL_ORDER: tuple[str, ...] = ("word", "sentence", "paragraph", "passage")
_LEVEL_LABEL: dict[str, str] = {
    "word": "Word",
    "sentence": "Sentence",
    "paragraph": "Paragraph",
    "passage": "Passage",
}
_LEVEL_BLURB: dict[str, str] = {
    "word": (
        "Single-token checks. These are the cheapest rules and fire on "
        "individual AI-associated words."
    ),
    "sentence": (
        "One sentence at a time. Catches canned phrases, disclosures, tone "
        "markers, and templated pivots."
    ),
    "paragraph": (
        "Adjacent-line structure. Catches bullet runs, blockquotes, "
        "horizontal rules, and listicle layouts."
    ),
    "passage": (
        "Whole-document signals. Catches rhythm, density, and repetition "
        "across the full text."
    ),
}
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


@dataclass(frozen=True)
class Example:
    """One parsed docstring example with its inline rationale."""

    text: str
    note: str


@dataclass(frozen=True)
class ExtraSection:
    """A free-form ``Heading: body`` section lifted from a rule docstring."""

    title: str
    body: str


@dataclass(frozen=True)
class Contributor:
    """A rule-file contributor resolved from ``git log`` + ``gh api``."""

    login: str
    name: str


@dataclass(frozen=True)
class ParsedDocstring:
    """Structured view of a rule module's docstring sections."""

    summary: str
    objective: str
    example_violations: tuple[Example, ...]
    example_non_violations: tuple[Example, ...]
    severity: str
    extras: tuple[ExtraSection, ...]


@dataclass(frozen=True)
class RuleDoc:
    """Everything the template needs to render one rule page."""

    rule_type: type[Rule[Any]]
    dotted_path: RulePath
    source_path: Path
    relative_source_path: Path
    parsed: ParsedDocstring
    defaults: ConfigMap
    slug: str
    title: str
    contributors: tuple[Contributor, ...]


def _load_default_configs() -> dict[str, ConfigMap]:
    """Return default config dicts keyed by the fully-qualified rule path."""
    raw_text = (
        files("slop_guard.rules")
        .joinpath("assets/default.jsonl")
        .read_text(encoding="utf-8")
    )
    configs: dict[str, ConfigMap] = {}
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        configs[payload["rule_type"]] = dict(payload["config"])
    return configs


def _dedent_lines(lines: list[str]) -> list[str]:
    """Drop common leading whitespace from a block of docstring lines."""
    stripped_for_indent = [line for line in lines if line.strip()]
    if not stripped_for_indent:
        return lines
    indent = min(len(line) - len(line.lstrip(" ")) for line in stripped_for_indent)
    return [line[indent:] if line.strip() else "" for line in lines]


def _split_sections(docstring: str) -> dict[str, list[str]]:
    """Split a rule docstring into labeled sections.

    A section header is any zero-indent line matching ``Title: remainder``
    where the title starts with a capital letter. Subsequent indented or
    continuation lines accumulate under that title.
    """
    lines = docstring.splitlines()
    sections: dict[str, list[str]] = {"_summary": []}
    current = "_summary"
    header_pattern = re.compile(r"^([A-Z][A-Za-z][A-Za-z &\-]*?):\s*(.*)$")
    for raw_line in lines:
        match = header_pattern.match(raw_line)
        if match and not raw_line.startswith(" "):
            current = match.group(1).strip()
            remainder = match.group(2).strip()
            sections[current] = [remainder] if remainder else []
            continue
        sections.setdefault(current, []).append(raw_line)
    return sections


def _join_paragraph(lines: list[str]) -> str:
    """Collapse a dedented multi-line block into a single paragraph."""
    dedented = _dedent_lines(lines)
    cleaned = [line.strip() for line in dedented if line.strip()]
    return " ".join(cleaned)


def _parse_examples(lines: list[str]) -> tuple[Example, ...]:
    """Parse ``- primary\\n  note`` example pairs into ``Example`` records."""
    dedented = _dedent_lines(lines)
    examples: list[tuple[str, list[str]]] = []
    for raw_line in dedented:
        if raw_line.startswith("- "):
            examples.append((raw_line[2:].strip(), []))
        elif raw_line.strip() and examples:
            examples[-1][1].append(raw_line.strip())
    return tuple(
        Example(text=primary, note=" ".join(notes).strip())
        for primary, notes in examples
    )


def _parse_docstring(docstring: str) -> ParsedDocstring:
    """Parse the shared rule docstring format into structured fields."""
    sections = _split_sections(docstring)
    summary = _join_paragraph(sections.get("_summary", []))
    objective = _join_paragraph(sections.get("Objective", []))
    severity = _join_paragraph(sections.get("Severity", []))
    example_violations: tuple[Example, ...] = ()
    example_non_violations: tuple[Example, ...] = ()
    extras: list[ExtraSection] = []
    for key, lines in sections.items():
        if key == "Example Rule Violations":
            example_violations = _parse_examples(lines)
        elif key == "Example Non-Violations":
            example_non_violations = _parse_examples(lines)
        elif key in _KNOWN_SECTIONS:
            continue
        else:
            body = _join_paragraph(lines)
            if body:
                extras.append(ExtraSection(title=key, body=body))
    return ParsedDocstring(
        summary=summary,
        objective=objective,
        example_violations=example_violations,
        example_non_violations=example_non_violations,
        severity=severity,
        extras=tuple(extras),
    )


def _slug(name: str) -> str:
    """Build a stable anchor slug from any name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _rule_title(rule_type: type[Rule[Any]]) -> str:
    """Return a human-readable title derived from the class name."""
    class_name = rule_type.__name__
    trimmed = class_name[:-4] if class_name.endswith("Rule") else class_name
    return _CAMEL_SPLIT_RE.sub(" ", trimmed)


def _rule_slug(rule_type: type[Rule[Any]]) -> str:
    """Return a stable unique slug derived from the class name."""
    class_name = rule_type.__name__
    trimmed = class_name[:-4] if class_name.endswith("Rule") else class_name
    return _slug(_CAMEL_SPLIT_RE.sub("-", trimmed))


_LOGIN_CACHE: dict[str, str | None] = {}


def _resolve_github_login(commit_sha: str, email: str) -> str | None:
    """Return the GitHub login for a commit author, cached by email."""
    if email in _LOGIN_CACHE:
        return _LOGIN_CACHE[email]
    try:
        proc = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{_REPO_SOURCE_REPO}/commits/{commit_sha}",
                "--jq",
                ".author.login",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        login = proc.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        login = None
    _LOGIN_CACHE[email] = login
    return login


def _load_contributors(relative_path: Path) -> tuple[Contributor, ...]:
    """Aggregate unique GitHub contributors to a source file via ``git log``."""
    try:
        proc = subprocess.run(
            [
                "git",
                "log",
                "--follow",
                "--format=%an|%ae|%H",
                "--",
                str(relative_path),
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ()

    first_seen: dict[str, tuple[str, str]] = {}
    for line in reversed(proc.stdout.splitlines()):
        if not line.strip():
            continue
        name, email, sha = line.split("|", 2)
        first_seen.setdefault(email, (name, sha))

    contributors: list[Contributor] = []
    seen_logins: set[str] = set()
    for email, (name, sha) in first_seen.items():
        login = _resolve_github_login(sha, email)
        if not login or login in _BOT_LOGINS or login in seen_logins:
            continue
        seen_logins.add(login)
        contributors.append(Contributor(login=login, name=name))
    return tuple(contributors)


def _load_rule_doc(dotted_path: str, defaults: dict[str, ConfigMap]) -> RuleDoc:
    """Import one rule class and gather everything needed to render it."""
    module_name, _, class_name = dotted_path.rpartition(".")
    module = import_module(module_name)
    rule_type = getattr(module, class_name)
    source_path = Path(inspect.getsourcefile(module) or module.__file__ or "")
    relative_source_path = source_path.resolve().relative_to(_REPO_ROOT)
    parsed = _parse_docstring(module.__doc__ or "")
    return RuleDoc(
        rule_type=rule_type,
        dotted_path=dotted_path,
        source_path=source_path,
        relative_source_path=relative_source_path,
        parsed=parsed,
        defaults=defaults.get(dotted_path, {}),
        slug=_rule_slug(rule_type),
        title=_rule_title(rule_type),
        contributors=_load_contributors(relative_source_path),
    )


def _format_inline(text: str) -> str:
    """Escape for HTML and lift ``**bold**`` into ``<strong>`` spans."""
    escaped = html.escape(text, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _render_header(doc: RuleDoc, summary: str, source_url: str) -> str:
    """Render the top eyebrow + title + source chip + lede block."""
    level = doc.rule_type.level.value
    level_label = _LEVEL_LABEL[level].upper()
    title = html.escape(doc.title)
    lines = [
        f'<header class="sg-rule-page__header sg-rule-page__header--{level}">',
        f'  <div class="sg-rule-page__eyebrow">{level_label}</div>',
        '  <div class="sg-rule-page__titlebar">',
        f'    <h1 class="sg-rule-page__title">{title}</h1>',
        f'    <a class="sg-source-chip" href="{html.escape(source_url)}">'
        f"{_GH_ICON_SVG}<span>source</span></a>",
        "  </div>",
    ]
    if summary:
        lines.append(
            '  <p class="sg-rule-page__lede" markdown>'
            f"{summary}</p>"
        )
    lines.append("</header>")
    return "\n".join(lines)


def _render_meta_row(doc: RuleDoc) -> str:
    """Render the three-column Class / Rule name / Count key strip."""
    items = [
        ("Class", doc.rule_type.__name__),
        ("Rule name", doc.rule_type.name),
        ("Count key", doc.rule_type.count_key),
    ]
    parts = ['<dl class="sg-rule-meta">']
    for label, value in items:
        parts.append(
            '  <div class="sg-rule-meta__item">'
            f"<dt>{html.escape(label)}</dt>"
            f"<dd><code>{html.escape(value)}</code></dd>"
            "</div>"
        )
    parts.append("</dl>")
    return "\n".join(parts)


def _render_behavior_table(doc: RuleDoc) -> str:
    """Render the combined Triggers/Non-triggers table with status cells."""
    rows: list[str] = []
    for item in doc.parsed.example_violations:
        rows.append(_render_behavior_row("flag", "Flag", item))
    for item in doc.parsed.example_non_violations:
        rows.append(_render_behavior_row("pass", "Pass", item))
    if not rows:
        return "_No behavior examples documented._"
    return "\n".join(
        [
            '<table class="sg-behavior">',
            "  <thead>",
            "    <tr>"
            '<th class="sg-behavior__th-result">Result</th>'
            "<th>Input text</th>"
            "<th>Why</th>"
            "</tr>",
            "  </thead>",
            "  <tbody>",
            *[f"    {row}" for row in rows],
            "  </tbody>",
            "</table>",
        ]
    )


def _render_behavior_row(variant: str, label: str, item: Example) -> str:
    """Render one row of the behavior table."""
    text_html = _format_inline(item.text)
    note_html = _format_inline(item.note) if item.note else ""
    return (
        f'<tr class="sg-behavior__row sg-behavior__row--{variant}">'
        '<td class="sg-behavior__result">'
        f'<span class="sg-status sg-status--{variant}">'
        '<span class="sg-status__dot" aria-hidden="true"></span>'
        f"{label}</span></td>"
        f'<td><code class="sg-behavior__input">{text_html}</code></td>'
        f'<td class="sg-behavior__why">{note_html}</td>'
        "</tr>"
    )


def _render_defaults(defaults: ConfigMap) -> str:
    """Render the default-configuration grid."""
    if not defaults:
        return "_No configurable parameters._"
    parts = ['<div class="sg-defaults">']
    for key in sorted(defaults):
        value = defaults[key]
        parts.append(
            '  <div class="sg-defaults__item">'
            f'<span class="sg-defaults__label">{html.escape(key)}</span>'
            f'<span class="sg-defaults__value">{html.escape(str(value))}</span>'
            "</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def _render_contributors(contributors: tuple[Contributor, ...]) -> str:
    """Render the blame-derived contributor chips."""
    if not contributors:
        return "_No contributors detected._"
    parts = ['<div class="sg-contributors">']
    for c in contributors:
        avatar = f"https://github.com/{c.login}.png?size=72"
        parts.append(
            f'  <a class="sg-contrib" href="https://github.com/{c.login}">'
            f'<img class="sg-contrib__avatar" src="{avatar}" '
            'alt="" loading="lazy" width="24" height="24" />'
            f'<span class="sg-contrib__name">@{c.login}</span>'
            "</a>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def _group_by_level(docs: list[RuleDoc]) -> dict[str, list[RuleDoc]]:
    """Group rule docs by level and preserve catalog order within each group."""
    groups: dict[str, list[RuleDoc]] = {}
    for doc in docs:
        groups.setdefault(doc.rule_type.level.value, []).append(doc)
    return groups


def render_rule_page(doc: RuleDoc) -> str:
    """Render a single rule's standalone Markdown page."""
    source_url = f"{_REPO_SOURCE_URL}/{doc.relative_source_path.as_posix()}"
    summary = doc.parsed.summary or doc.parsed.objective or ""

    lines: list[str] = [
        "---",
        "icon: lucide/shield-check",
        f"title: {doc.title}",
        f"description: {summary}",
        "---",
        "",
        '<div class="sg-rule-page" markdown>',
        "",
        _render_header(doc, summary, source_url),
        "",
        _render_meta_row(doc),
        "",
        "## Behavior",
        "",
        _render_behavior_table(doc),
        "",
    ]
    if doc.parsed.severity:
        lines.extend(["## Severity", "", doc.parsed.severity, ""])
    for extra in doc.parsed.extras:
        lines.extend([f"## {extra.title}", "", extra.body, ""])
    lines.extend(
        [
            "## Default configuration",
            "",
            _render_defaults(doc.defaults),
            "",
        ]
    )
    if doc.contributors:
        lines.extend(
            [
                "## Contributors",
                "",
                _render_contributors(doc.contributors),
                "",
            ]
        )
    lines.append("</div>")
    return "\n".join(lines).rstrip() + "\n"


def _render_index_card(doc: RuleDoc) -> str:
    """Render one rule as a compact card on the landing page."""
    summary = doc.parsed.summary or doc.parsed.objective or ""
    return "\n".join(
        [
            '<div class="sg-rule-card">',
            f'  <a class="sg-rule-card__link" href="{doc.slug}.md">',
            f'    <div class="sg-rule-card__head">'
            f'<span class="sg-rule-card__title">{doc.title}</span></div>',
            f'    <p class="sg-rule-card__summary">{summary}</p>',
            "  </a>",
            "</div>",
        ]
    )


def render_index_page(docs: list[RuleDoc]) -> str:
    """Render the rule library overview page with per-level card grids."""
    groups = _group_by_level(docs)
    total = len(docs)
    header = [
        "---",
        "icon: lucide/list-checks",
        "title: Rule library",
        "description: Catalog of the rules that slop-guard runs on every check.",
        "---",
        "",
        "# Rule library",
        "",
        "`slop-guard` ships a pipeline of small, independently scored rules. "
        "Each rule targets one formulaic pattern, flags the exact matching "
        "spans, and contributes a penalty toward the final score.",
        "",
        f"The default pipeline runs **{total} rules** across four scopes. "
        "Open a card to read the full rule page, including example "
        "violations, default thresholds, and a link to the source file.",
        "",
    ]
    body: list[str] = []
    for level in _LEVEL_ORDER:
        level_docs = groups.get(level)
        if not level_docs:
            continue
        body.append(f"## {_LEVEL_LABEL[level]} rules")
        body.append("")
        body.append(_LEVEL_BLURB[level])
        body.append("")
        body.append('<div class="sg-rule-grid">')
        for doc in level_docs:
            body.append(_render_index_card(doc))
        body.append("</div>")
        body.append("")
    return "\n".join(header + body).rstrip() + "\n"


def _reset_output_dir(output_dir: Path) -> None:
    """Remove the generated rule directory so stale pages are cleaned up."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def build_rule_docs() -> list[RuleDoc]:
    """Return parsed rule docs for every rule in the default catalog."""
    defaults = _load_default_configs()
    return [_load_rule_doc(path, defaults) for path in DEFAULT_RULE_PATHS]


def nav_entries(docs: list[RuleDoc]) -> list[dict[str, Any]]:
    """Return a TOML-friendly nav structure for the rule library."""
    groups = _group_by_level(docs)
    entries: list[dict[str, Any]] = [{"Overview": "rules/index.md"}]
    for level in _LEVEL_ORDER:
        level_docs = groups.get(level)
        if not level_docs:
            continue
        children: list[dict[str, str]] = [
            {doc.title: f"rules/{doc.slug}.md"} for doc in level_docs
        ]
        entries.append({f"{_LEVEL_LABEL[level]} rules": children})
    return entries


def main() -> None:
    """Write the rule index and one page per rule to the docs tree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory that will contain the generated rule pages.",
    )
    args = parser.parse_args()

    docs = build_rule_docs()
    _reset_output_dir(args.output_dir)

    index_path = args.output_dir / "index.md"
    index_path.write_text(render_index_page(docs), encoding="utf-8")
    for doc in docs:
        (args.output_dir / f"{doc.slug}.md").write_text(
            render_rule_page(doc), encoding="utf-8"
        )
    print(f"wrote {len(docs)} rule pages and an index to {args.output_dir}")


if __name__ == "__main__":  # pragma: no cover
    main()
