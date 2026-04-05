"""Tests for docs-site Markdown mirror publishing."""

from __future__ import annotations

import contextlib
import sys
import types
from pathlib import Path

import pytest

import slop_guard.docs_site as docs_site
from slop_guard.docs_site import markdown_mirror_targets, publish_markdown_mirrors


def test_markdown_mirror_targets_preserve_standard_markdown_paths() -> None:
    """Non-index Markdown pages should keep a single mirrored site path."""
    docs_dir = Path("/tmp/docs")
    site_dir = Path("/tmp/site")

    targets = markdown_mirror_targets(docs_dir / "guide.md", docs_dir, site_dir)

    assert targets == (site_dir / "guide.md",)


def test_markdown_mirror_targets_add_slug_alias_for_nested_index_pages() -> None:
    """Section index pages should also publish a sibling ``.md`` slug file."""
    docs_dir = Path("/tmp/docs")
    site_dir = Path("/tmp/site")

    targets = markdown_mirror_targets(
        docs_dir / "guides" / "install" / "index.md",
        docs_dir,
        site_dir,
    )

    assert targets == (
        site_dir / "guides" / "install" / "index.md",
        site_dir / "guides" / "install.md",
    )


def test_publish_markdown_mirrors_writes_source_bytes_to_all_targets(
    tmp_path: Path,
) -> None:
    """Mirror publishing should copy source Markdown to every exported path."""
    docs_dir = tmp_path / "docs"
    site_dir = tmp_path / "site"
    nested_dir = docs_dir / "guides" / "install"
    nested_dir.mkdir(parents=True)
    guide_path = docs_dir / "guide.md"
    guide_path.write_text("# Guide\n", encoding="utf-8")
    index_path = nested_dir / "index.md"
    index_path.write_text("# Install\n", encoding="utf-8")

    written = publish_markdown_mirrors(docs_dir, site_dir)

    assert written == (
        site_dir / "guide.md",
        site_dir / "guides" / "install" / "index.md",
        site_dir / "guides" / "install.md",
    )
    assert (site_dir / "guide.md").read_text(encoding="utf-8") == "# Guide\n"
    assert (site_dir / "guides" / "install" / "index.md").read_text(
        encoding="utf-8"
    ) == "# Install\n"
    assert (site_dir / "guides" / "install.md").read_text(encoding="utf-8") == (
        "# Install\n"
    )


def test_resolve_config_file_prefers_explicit_path(tmp_path: Path) -> None:
    """Explicit config paths should bypass repository auto-discovery."""
    config_path = tmp_path / "zensical.toml"
    config_path.write_text("", encoding="utf-8")

    resolved = docs_site.resolve_config_file(str(config_path))

    assert resolved == config_path.resolve()


def test_resolve_config_file_discovers_default_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-discovery should return the first supported config present."""
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "zensical.toml"
    config_path.write_text("", encoding="utf-8")

    resolved = docs_site.resolve_config_file(None)

    assert resolved == config_path.resolve()


def test_resolve_config_file_raises_when_no_supported_file_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto-discovery should fail loudly when no config file exists."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        docs_site.resolve_config_file(None)


def test_load_docs_layout_reads_paths_from_mike_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Docs layout loading should resolve docs and site directories from Mike."""
    fake_utils = types.SimpleNamespace(
        load_config=lambda _: {
            "docs_dir": "docs",
            "site_dir": str(tmp_path / "site"),
        }
    )
    monkeypatch.setitem(sys.modules, "mike", types.SimpleNamespace(utils=fake_utils))
    config_path = tmp_path / "zensical.toml"
    config_path.write_text("", encoding="utf-8")

    docs_dir, site_dir, config = docs_site._load_docs_layout(config_path)

    assert docs_dir == (tmp_path / "docs").resolve()
    assert site_dir == (tmp_path / "site").resolve()
    assert config["docs_dir"] == "docs"


def test_load_docs_layout_requires_string_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Docs layout loading should reject non-string config paths."""
    fake_utils = types.SimpleNamespace(
        load_config=lambda _: {
            "docs_dir": object(),
            "site_dir": str(tmp_path / "site"),
        }
    )
    monkeypatch.setitem(sys.modules, "mike", types.SimpleNamespace(utils=fake_utils))
    config_path = tmp_path / "zensical.toml"
    config_path.write_text("", encoding="utf-8")

    with pytest.raises(TypeError):
        docs_site._load_docs_layout(config_path)


def test_run_zensical_build_sets_or_clears_docs_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build invocation should manage the Mike docs-version environment."""
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(
        command: list[str],
        *,
        check: bool,
        env: dict[str, str],
    ) -> None:
        assert check is True
        calls.append((command, env))

    monkeypatch.setattr(docs_site.subprocess, "run", fake_run)
    monkeypatch.setenv("MIKE_DOCS_VERSION", "stale")
    config_path = tmp_path / "zensical.toml"

    docs_site._run_zensical_build(config_path, "1.2.3")
    docs_site._run_zensical_build(config_path, None)

    assert calls[0][0] == [
        "zensical",
        "build",
        "--clean",
        "--config-file",
        str(config_path),
    ]
    assert calls[0][1]["MIKE_DOCS_VERSION"] == "1.2.3"
    assert "MIKE_DOCS_VERSION" not in calls[1][1]


def test_build_site_runs_build_then_exports_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Site building should run Zensical and then publish Markdown mirrors."""
    config_path = tmp_path / "zensical.toml"
    docs_dir = tmp_path / "docs"
    site_dir = tmp_path / "site"
    build_calls: list[tuple[Path, str | None]] = []

    monkeypatch.setattr(docs_site, "resolve_config_file", lambda _: config_path)
    monkeypatch.setattr(
        docs_site,
        "_run_zensical_build",
        lambda path, version: build_calls.append((path, version)),
    )
    monkeypatch.setattr(
        docs_site,
        "_load_docs_layout",
        lambda _: (docs_dir, site_dir, {}),
    )
    monkeypatch.setattr(
        docs_site,
        "publish_markdown_mirrors",
        lambda docs_root, site_root: (site_root / "guide.md",),
    )

    written = docs_site.build_site(None, docs_version="dev")

    assert build_calls == [(config_path, "dev")]
    assert written == (site_dir / "guide.md",)


def test_deploy_site_wraps_build_with_mike_deploy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deployment should export mirrors before Mike commits the built site."""
    config_path = tmp_path / "zensical.toml"
    build_calls: list[tuple[str | None, str | None]] = []
    update_calls: list[tuple[str, str]] = []
    push_calls: list[tuple[str, str]] = []
    deploy_records: list[tuple[object, ...]] = []
    context_state = {"entered": False}

    @contextlib.contextmanager
    def fake_deploy(*args: object, **kwargs: object):
        deploy_records.append(args + (kwargs,))
        context_state["entered"] = True
        yield
        context_state["entered"] = False

    fake_commands = types.SimpleNamespace(
        AliasType=types.SimpleNamespace(symlink="symlink"),
        deploy=fake_deploy,
    )
    fake_git_utils = types.SimpleNamespace(
        update_from_upstream=lambda remote, branch: update_calls.append(
            (remote, branch)
        ),
        push_branch=lambda remote, branch: push_calls.append((remote, branch)),
    )
    monkeypatch.setitem(
        sys.modules,
        "mike",
        types.SimpleNamespace(commands=fake_commands, git_utils=fake_git_utils),
    )
    monkeypatch.setattr(docs_site, "resolve_config_file", lambda _: config_path)
    monkeypatch.setattr(
        docs_site,
        "_load_docs_layout",
        lambda _: (tmp_path / "docs", tmp_path / "site", {"site_dir": "site"}),
    )

    def fake_build_site(
        config_file: str | None, docs_version: str | None
    ) -> tuple[Path]:
        assert context_state["entered"] is True
        build_calls.append((config_file, docs_version))
        return (tmp_path / "site" / "guide.md",)

    monkeypatch.setattr(docs_site, "build_site", fake_build_site)

    docs_site.deploy_site(
        None,
        "1.2.3",
        ("latest",),
        "v1.2.3",
        True,
        "gh-pages",
        "origin",
        True,
        "docs",
    )

    assert update_calls == [("origin", "gh-pages")]
    assert push_calls == [("origin", "gh-pages")]
    assert build_calls == [(str(config_path), "1.2.3")]
    assert deploy_records == [
        (
            {"site_dir": "site"},
            "1.2.3",
            "v1.2.3",
            ["latest"],
            True,
            "symlink",
            None,
            {"branch": "gh-pages", "deploy_prefix": "docs"},
        )
    ]


def test_main_dispatches_build_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI main should route the build subcommand to ``build_site``."""
    build_calls: list[str | None] = []
    monkeypatch.setattr(sys, "argv", ["docs_site.py", "build", "--config-file", "cfg"])
    monkeypatch.setattr(
        docs_site,
        "build_site",
        lambda config_file: build_calls.append(config_file),
    )

    docs_site.main()

    assert build_calls == ["cfg"]


def test_main_dispatches_deploy_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI main should route the deploy subcommand to ``deploy_site``."""
    deploy_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "docs_site.py",
            "deploy",
            "1.2.3",
            "latest",
            "--title",
            "v1.2.3",
            "--update-aliases",
            "--branch",
            "gh-pages",
            "--remote",
            "origin",
            "--push",
            "--deploy-prefix",
            "docs",
        ],
    )
    monkeypatch.setattr(
        docs_site,
        "deploy_site",
        lambda *args: deploy_calls.append(args),
    )

    docs_site.main()

    assert deploy_calls == [
        (
            None,
            "1.2.3",
            ["latest"],
            "v1.2.3",
            True,
            "gh-pages",
            "origin",
            True,
            "docs",
        )
    ]
