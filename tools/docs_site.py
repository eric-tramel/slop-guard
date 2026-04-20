"""Build and deploy the documentation site with raw Markdown mirrors.

This helper is intentionally repo-local so the published library does not ship
documentation-only build logic.
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeAlias, cast

ConfigMap: TypeAlias = dict[str, Any]

_CONFIG_CANDIDATES: tuple[str, ...] = ("zensical.toml", "mkdocs.yml", "mkdocs.yaml")
_INDEX_FILENAMES: frozenset[str] = frozenset({"index.md", "README.md"})


def resolve_config_file(config_file: str | None) -> Path:
    """Resolve the documentation config file from the current working tree.

    Args:
        config_file: Explicit config path, or ``None`` to search default names.

    Returns:
        The resolved absolute config path.

    Raises:
        FileNotFoundError: No supported config file exists.
    """
    if config_file is not None:
        return Path(config_file).resolve()

    for candidate in _CONFIG_CANDIDATES:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return candidate_path.resolve()

    raise FileNotFoundError("No docs config file found.")


def markdown_mirror_targets(
    source_path: Path,
    docs_dir: Path,
    site_dir: Path,
) -> tuple[Path, ...]:
    """Return the site targets that should mirror one source Markdown page.

    Args:
        source_path: Source Markdown file inside ``docs_dir``.
        docs_dir: Root documentation source directory.
        site_dir: Built site root directory.

    Returns:
        The raw Markdown targets to write into the built site.
    """
    relative_path = source_path.relative_to(docs_dir)
    targets = [site_dir / relative_path]

    if relative_path.name in _INDEX_FILENAMES and relative_path.parent != Path("."):
        slug_target = (
            site_dir / relative_path.parent.parent / (f"{relative_path.parent.name}.md")
        )
        targets.append(slug_target)

    return tuple(targets)


def publish_markdown_mirrors(docs_dir: Path, site_dir: Path) -> tuple[Path, ...]:
    """Copy source Markdown pages into crawlable site mirror paths.

    Args:
        docs_dir: Root documentation source directory.
        site_dir: Built site root directory.

    Returns:
        The site paths written during export.
    """
    written_paths: list[Path] = []
    for source_path in sorted(docs_dir.rglob("*.md")):
        payload = source_path.read_bytes()
        for target_path in markdown_mirror_targets(source_path, docs_dir, site_dir):
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(payload)
            written_paths.append(target_path)
    return tuple(written_paths)


def _load_docs_layout(config_file: Path) -> tuple[Path, Path, ConfigMap]:
    """Load the docs and site directories from the active Zensical config."""
    mike_utils = cast(Any, importlib.import_module("mike.utils"))
    config = cast(ConfigMap, mike_utils.load_config(str(config_file)))
    docs_dir_value = config["docs_dir"]
    if not isinstance(docs_dir_value, str):
        raise TypeError("docs_dir must resolve to a string path.")
    site_dir_value = config["site_dir"]
    if not isinstance(site_dir_value, str):
        raise TypeError("site_dir must resolve to a string path.")

    docs_dir = (config_file.parent / docs_dir_value).resolve()
    site_dir = Path(site_dir_value).resolve()
    return docs_dir, site_dir, config


def _run_zensical_build(config_file: Path, docs_version: str | None) -> None:
    """Run a clean docs build with an optional Mike docs version."""
    env = dict(os.environ)
    if docs_version is None:
        env.pop("MIKE_DOCS_VERSION", None)
    else:
        env["MIKE_DOCS_VERSION"] = docs_version

    subprocess.run(
        [
            "zensical",
            "build",
            "--clean",
            "--config-file",
            str(config_file),
        ],
        check=True,
        env=env,
    )


def build_site(
    config_file: str | None, docs_version: str | None = None
) -> tuple[Path, ...]:
    """Build the docs site and export raw Markdown mirrors.

    Args:
        config_file: Explicit docs config path, or ``None`` for auto-discovery.
        docs_version: Optional Mike version injected during the build.

    Returns:
        The mirror files written into the site output.
    """
    resolved_config = resolve_config_file(config_file)
    _run_zensical_build(resolved_config, docs_version)
    docs_dir, site_dir, _ = _load_docs_layout(resolved_config)
    return publish_markdown_mirrors(docs_dir, site_dir)


def deploy_site(
    config_file: str | None,
    version: str,
    aliases: Sequence[str],
    title: str | None,
    update_aliases: bool,
    branch: str,
    remote: str,
    push: bool,
    deploy_prefix: str,
) -> None:
    """Deploy versioned docs after exporting raw Markdown mirrors.

    Args:
        config_file: Explicit docs config path, or ``None`` for auto-discovery.
        version: Version identifier to deploy.
        aliases: Mike aliases that should point at ``version``.
        title: Display title for the version selector.
        update_aliases: Whether existing aliases should be reassigned.
        branch: Target docs branch.
        remote: Remote containing the target docs branch.
        push: Whether to push after committing the deployment.
        deploy_prefix: Subdirectory inside the docs branch for the site.
    """
    mike_commands = cast(Any, importlib.import_module("mike.commands"))
    mike_git_utils = cast(Any, importlib.import_module("mike.git_utils"))
    resolved_config = resolve_config_file(config_file)
    _, _, config = _load_docs_layout(resolved_config)
    mike_git_utils.update_from_upstream(remote, branch)

    with mike_commands.deploy(
        config,
        version,
        title,
        list(aliases),
        update_aliases,
        mike_commands.AliasType.symlink,
        None,
        branch=branch,
        allow_empty=True,
        deploy_prefix=deploy_prefix,
    ):
        build_site(str(resolved_config), docs_version=version)

    if push:
        mike_git_utils.push_branch(remote, branch)


def _build_parser() -> argparse.ArgumentParser:
    """Build the module command-line parser."""
    parser = argparse.ArgumentParser(
        description="Build or deploy docs with raw Markdown mirrors."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "build",
        help="Build the local docs site and export Markdown mirrors.",
    )
    build_parser.add_argument(
        "--config-file",
        default=None,
        help="Path to the docs config file.",
    )

    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Deploy versioned docs and export Markdown mirrors.",
    )
    deploy_parser.add_argument("version", help="Version to deploy.")
    deploy_parser.add_argument("aliases", nargs="*", help="Aliases for the version.")
    deploy_parser.add_argument("--config-file", default=None, help="Docs config file.")
    deploy_parser.add_argument("--title", default=None, help="Display title.")
    deploy_parser.add_argument(
        "--update-aliases",
        action="store_true",
        help="Repoint aliases that already exist.",
    )
    deploy_parser.add_argument(
        "--branch",
        default="gh-pages",
        help="Target branch for versioned docs.",
    )
    deploy_parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote for the docs branch.",
    )
    deploy_parser.add_argument(
        "--push",
        action="store_true",
        help="Push the docs branch after deployment.",
    )
    deploy_parser.add_argument(
        "--deploy-prefix",
        default="",
        help="Subdirectory inside the docs branch for the site.",
    )

    return parser


def main() -> None:
    """Run the docs site helper CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "build":
        build_site(args.config_file)
        return

    if args.command == "deploy":
        deploy_site(
            args.config_file,
            args.version,
            args.aliases,
            args.title,
            args.update_aliases,
            args.branch,
            args.remote,
            args.push,
            args.deploy_prefix,
        )
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":  # pragma: no cover
    main()
