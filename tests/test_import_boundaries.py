"""Tests for import boundaries and deleted module-path cleanup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SEARCH_ROOTS = (
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "benchmark",
    REPO_ROOT / "docs",
    REPO_ROOT / "README.md",
    REPO_ROOT / "pyproject.toml",
)
DELETED_PATH_MARKERS = tuple(
    ".".join(parts)
    for parts in (
        ("slop_guard", "analysis"),
        ("slop_guard", "server"),
        ("slop_guard", "cli"),
        ("slop_guard", "fit_cli"),
        ("rules", "helpers"),
        ("rules", "word_level"),
        ("rules", "sentence_level"),
        ("rules", "paragraph_level"),
        ("rules", "passage_level"),
    )
)


def _pythonpath_env() -> dict[str, str]:
    """Return an environment that imports the local ``src`` tree first."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(SRC_ROOT) if not existing else os.pathsep.join((str(SRC_ROOT), existing))
    )
    return env


def _probe_module_import(module_name: str) -> dict[str, object]:
    """Import one module in a subprocess and report any loaded ``mcp`` modules."""
    command = [
        sys.executable,
        "-c",
        (
            "import importlib, json, sys; "
            "importlib.import_module(sys.argv[1]); "
            "loaded = sorted(name for name in sys.modules "
            "if name == 'mcp' or name.startswith('mcp.')); "
            "print(json.dumps({'mcp_modules': loaded}))"
        ),
        module_name,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        cwd=REPO_ROOT,
        env=_pythonpath_env(),
        text=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    "module_name",
    (
        "slop_guard",
        "slop_guard.engine",
        "slop_guard.rules.base",
    ),
)
def test_import_boundary_modules_do_not_load_mcp(module_name: str) -> None:
    """Core package imports should not pull in MCP server dependencies."""
    payload = _probe_module_import(module_name)

    assert payload["mcp_modules"] == []


def test_repo_contains_no_deleted_module_paths() -> None:
    """No tracked source, test, benchmark, or doc file should mention deleted paths."""
    for root in SEARCH_ROOTS:
        paths = (root,) if root.is_file() else root.rglob("*")
        for path in paths:
            if path.is_dir():
                continue
            if path.suffix not in {
                ".py",
                ".md",
                ".toml",
                ".jsonl",
            } and not path.name.startswith("README"):
                continue
            text = path.read_text(encoding="utf-8")
            for marker in DELETED_PATH_MARKERS:
                assert marker not in text, f"{path} still references {marker}"
