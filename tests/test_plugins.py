"""Metadata and launcher tests for the Claude and Codex plugins."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "slop-guard"
CLAUDE_CATALOG = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CODEX_CATALOG = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CLAUDE_MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
CODEX_MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
HOOK_MANIFEST = PLUGIN_ROOT / "hooks" / "hooks.json"
LAUNCHER = PLUGIN_ROOT / "scripts" / "launch.sh"

pytestmark = pytest.mark.skipif(
    os.name != "posix",
    reason="the plugin launcher intentionally targets POSIX /bin/sh",
)


def _load_object(path: Path) -> dict[str, Any]:
    """Load a JSON metadata file and require an object at its root."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _resolve_contained(root: Path, relative_path: str) -> Path:
    """Resolve one component path and assert that it remains under its root."""
    resolved_root = root.resolve()
    resolved = (resolved_root / relative_path).resolve()
    assert resolved.is_relative_to(resolved_root)
    return resolved


def _write_executable(path: Path, body: str) -> Path:
    """Create a deterministic fake installed console script."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _run_launcher(
    arguments: list[str],
    *,
    search_path: str,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the checked-in launcher without inheriting credentials or tool state."""
    environment = {
        "HOME": str(cwd),
        "LC_ALL": "C",
        "PATH": search_path,
    }
    if extra_env is not None:
        environment.update(extra_env)
    return subprocess.run(
        ["/bin/sh", str(LAUNCHER), *arguments],
        check=False,
        capture_output=True,
        cwd=cwd,
        env=environment,
        text=True,
    )


async def _call_tool_through_manifest(
    server: dict[str, Any],
    *,
    cwd: Path,
    env: dict[str, str],
) -> CallToolResult:
    """Call ``check_slop_file`` through the MCP command declared by Codex."""
    command = server["command"]
    arguments = server["args"]
    assert isinstance(command, str)
    assert isinstance(arguments, list)
    assert all(isinstance(argument, str) for argument in arguments)
    parameters = StdioServerParameters(
        command=command,
        args=cast(list[str], arguments),
        cwd=cwd,
        env=env,
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(
                "check_slop_file",
                arguments={"file_path": "sample.md"},
            )


def _assert_launcher_failure(
    completed: subprocess.CompletedProcess[str],
    stderr_fragment: str,
) -> None:
    """Assert the launcher's fail-closed runtime path and clean protocol stdout."""
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr.startswith("slop-guard plugin: ")
    assert stderr_fragment in completed.stderr


def test_catalogs_and_manifests_cross_reference_one_plugin_root() -> None:
    """Both marketplace catalogs should identify the matching client manifest."""
    claude_catalog = _load_object(CLAUDE_CATALOG)
    codex_catalog = _load_object(CODEX_CATALOG)
    claude_manifest = _load_object(CLAUDE_MANIFEST)
    codex_manifest = _load_object(CODEX_MANIFEST)
    hook_manifest = _load_object(HOOK_MANIFEST)

    assert claude_catalog["name"] == "slop-guard"
    assert codex_catalog["name"] == "slop-guard"
    claude_entries = claude_catalog["plugins"]
    codex_entries = codex_catalog["plugins"]
    assert isinstance(claude_entries, list) and len(claude_entries) == 1
    assert isinstance(codex_entries, list) and len(codex_entries) == 1
    claude_entry = cast(dict[str, Any], claude_entries[0])
    codex_entry = cast(dict[str, Any], codex_entries[0])
    assert isinstance(claude_entry, dict)
    assert isinstance(codex_entry, dict)

    assert claude_entry["name"] == claude_manifest["name"] == "slop-guard"
    assert codex_entry["name"] == codex_manifest["name"] == "slop-guard"
    assert claude_entry["source"] == "./plugins/slop-guard"
    assert codex_entry["source"] == {
        "source": "local",
        "path": "./plugins/slop-guard",
    }
    claude_root = _resolve_contained(REPO_ROOT, claude_entry["source"])
    codex_root = _resolve_contained(REPO_ROOT, codex_entry["source"]["path"])
    assert claude_root == codex_root == PLUGIN_ROOT.resolve()

    assert claude_manifest["version"] == codex_manifest["version"]
    assert set(claude_manifest["mcpServers"]) == {"slop-guard"}
    assert set(codex_manifest["mcpServers"]) == {"slop-guard"}
    assert "hooks" not in claude_manifest
    assert "hooks" not in codex_manifest
    assert set(hook_manifest["hooks"]) == {"Stop"}
    assert "SubagentStop" not in hook_manifest["hooks"]


def test_manifest_component_paths_are_contained_and_resolve() -> None:
    """Every local command component should resolve inside the plugin directory."""
    claude_manifest = _load_object(CLAUDE_MANIFEST)
    codex_manifest = _load_object(CODEX_MANIFEST)
    hook_manifest = _load_object(HOOK_MANIFEST)

    claude_mcp = claude_manifest["mcpServers"]["slop-guard"]
    claude_command = claude_mcp["command"]
    root_prefix = "${CLAUDE_PLUGIN_ROOT}/"
    assert claude_command.startswith(root_prefix)
    claude_launcher = _resolve_contained(
        PLUGIN_ROOT,
        claude_command.removeprefix(root_prefix),
    )

    codex_mcp = codex_manifest["mcpServers"]["slop-guard"]
    assert codex_mcp["command"] == "/bin/sh"
    assert codex_mcp["args"][:2] == ["-eu", "-c"]
    assert len(codex_mcp["args"]) == 3
    assert "cwd" not in codex_mcp
    hook_root_prefix = "$CLAUDE_PLUGIN_ROOT/"

    stop_groups = hook_manifest["hooks"]["Stop"]
    assert isinstance(stop_groups, list) and len(stop_groups) == 1
    stop_handlers = stop_groups[0]["hooks"]
    assert isinstance(stop_handlers, list) and len(stop_handlers) == 1
    command_parts = shlex.split(stop_handlers[0]["command"])
    assert command_parts[0] == "/bin/sh"
    assert command_parts[2:] == ["hook"]
    assert command_parts[1].startswith(hook_root_prefix)
    hook_launcher = _resolve_contained(
        PLUGIN_ROOT,
        command_parts[1].removeprefix(hook_root_prefix),
    )

    assert claude_launcher == hook_launcher == LAUNCHER.resolve()
    assert claude_launcher.is_file()
    assert os.access(claude_launcher, os.X_OK)


def test_claude_response_checks_default_off_and_codex_preserves_caller_cwd() -> None:
    """Client manifests should preserve distinct opt-in and working-dir contracts."""
    claude_manifest = _load_object(CLAUDE_MANIFEST)
    codex_manifest = _load_object(CODEX_MANIFEST)

    assert claude_manifest["userConfig"] == {
        "response_checks": {
            "type": "boolean",
            "title": "Check assistant responses",
            "description": (
                "Report Slop-Guard findings when Claude finishes responding."
            ),
            "default": False,
        }
    }
    codex_mcp = codex_manifest["mcpServers"]["slop-guard"]
    assert codex_mcp["command"] == "/bin/sh"
    assert codex_mcp["args"][:2] == ["-eu", "-c"]
    assert len(codex_mcp["args"]) == 3
    assert "cwd" not in codex_mcp


def test_codex_mcp_preserves_workspace_cwd_for_relative_file(
    tmp_path: Path,
) -> None:
    """The declared Codex command should read relative files from caller cwd."""
    workspace = tmp_path / "caller workspace"
    workspace.mkdir()
    sample = workspace / "sample.md"
    sample.write_text(
        "This is a crucial and groundbreaking paradigm that feels remarkably "
        "innovative and comprehensive overall.",
        encoding="utf-8",
    )
    tool_bin = tmp_path / "installed-tools" / "bin"
    record = tmp_path / "mcp-runtime-record.txt"
    runtime = _write_executable(
        tool_bin / "slop-guard",
        f"""#!/bin/sh
{{
    printf '%s\n' "$0"
    pwd
    printf '%s\n' "${{PYTHONPATH-<unset>}}"
    printf '%s\n' "${{PYTHONHOME-<unset>}}"
}} > "$RECORD_FILE"
exec {shlex.quote(sys.executable)} -c 'from slop_guard.apps.mcp import main; main()'
""",
    )
    codex_manifest = _load_object(CODEX_MANIFEST)
    server = cast(
        dict[str, Any],
        codex_manifest["mcpServers"]["slop-guard"],
    )
    environment = {
        "HOME": str(workspace),
        "LC_ALL": "C",
        "PATH": str(tool_bin),
        "PYTHONHOME": "/private/python-home",
        "PYTHONPATH": "/private/source-shadow",
        "RECORD_FILE": str(record),
    }

    result = asyncio.run(
        _call_tool_through_manifest(server, cwd=workspace, env=environment)
    )

    assert result.isError is False
    structured = result.structuredContent
    assert structured is not None
    violations = cast(list[dict[str, Any]], structured["violations"])
    assert any(
        violation["rule"] == "slop_word" and violation["match"] == "crucial"
        for violation in violations
    )
    assert record.read_text(encoding="utf-8").splitlines() == [
        str(runtime.resolve()),
        str(workspace.resolve()),
        "<unset>",
        "<unset>",
    ]


def test_hook_command_handles_metacharacters_in_installed_plugin_root(
    tmp_path: Path,
) -> None:
    """The shared hook command must pass an unusual install root as one argument."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sentinel = workspace / "injected"
    plugin_root = tmp_path / "plugin root;$(touch injected) '\" []"
    record = tmp_path / "hook-command-record.txt"
    fake_launcher = _write_executable(
        plugin_root / "scripts" / "launch.sh",
        """#!/bin/sh
printf '%s\n' "$0" "$1" > "$RECORD_FILE"
""",
    )
    hook_manifest = _load_object(HOOK_MANIFEST)
    command = hook_manifest["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert isinstance(command, str)

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=workspace,
        env={
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "HOME": str(workspace),
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
            "RECORD_FILE": str(record),
        },
        executable="/bin/sh",
        shell=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert record.read_text(encoding="utf-8").splitlines() == [
        str(fake_launcher),
        "hook",
    ]
    assert not sentinel.exists()


def test_launcher_mcp_executes_exact_runtime_in_spaced_path_and_cleans_env(
    tmp_path: Path,
) -> None:
    """MCP mode should exec the canonical runtime with protocol stdout untouched."""
    workspace = tmp_path / "unrelated workspace"
    workspace.mkdir()
    tool_bin = tmp_path / "installed tools with spaces" / "bin"
    record = tmp_path / "mcp record.txt"
    runtime = _write_executable(
        tool_bin / "slop-guard",
        """#!/bin/sh
{
    printf '%s\n' "$0"
    printf '%s\n' "${PYTHONPATH-<unset>}"
    printf '%s\n' "${PYTHONHOME-<unset>}"
} > "$RECORD_FILE"
printf '%s\n' '{"jsonrpc":"2.0","result":"ready"}'
""",
    )

    completed = _run_launcher(
        ["mcp"],
        search_path=str(tool_bin),
        cwd=workspace,
        extra_env={
            "PYTHONPATH": "/private/source-shadow",
            "PYTHONHOME": "/private/python-home",
            "RECORD_FILE": str(record),
        },
    )

    assert completed.returncode == 0
    assert completed.stdout == '{"jsonrpc":"2.0","result":"ready"}\n'
    assert completed.stderr == ""
    assert record.read_text(encoding="utf-8").splitlines() == [
        str(runtime.resolve()),
        "<unset>",
        "<unset>",
    ]


def test_launcher_hook_executes_exact_sibling_instead_of_path_shadow(
    tmp_path: Path,
) -> None:
    """Hook mode should derive ``sg-hook`` beside the canonical MCP runtime."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tool_bin = tmp_path / "tool-bin"
    shadow_bin = tmp_path / "shadow-bin"
    record = tmp_path / "hook-record.txt"
    shadow_record = tmp_path / "shadow-record.txt"
    _write_executable(tool_bin / "slop-guard", "#!/bin/sh\nexit 91\n")
    sibling = _write_executable(
        tool_bin / "sg-hook",
        """#!/bin/sh
{
    printf '%s\n' "$0"
    printf '%s\n' "${PYTHONPATH-<unset>}"
    printf '%s\n' "${PYTHONHOME-<unset>}"
} > "$RECORD_FILE"
printf '%s\n' '{"systemMessage":"sibling hook"}'
""",
    )
    _write_executable(
        shadow_bin / "sg-hook",
        "#!/bin/sh\nprintf '%s\n' shadow > \"$SHADOW_RECORD\"\n",
    )

    completed = _run_launcher(
        ["hook"],
        search_path=os.pathsep.join((str(tool_bin), str(shadow_bin))),
        cwd=workspace,
        extra_env={
            "PLUGIN_ROOT": str(PLUGIN_ROOT),
            "PYTHONPATH": "/private/source-shadow",
            "PYTHONHOME": "/private/python-home",
            "RECORD_FILE": str(record),
            "SHADOW_RECORD": str(shadow_record),
        },
    )

    assert completed.returncode == 0
    assert completed.stdout == '{"systemMessage":"sibling hook"}\n'
    assert completed.stderr == ""
    assert record.read_text(encoding="utf-8").splitlines() == [
        str(sibling.resolve()),
        "<unset>",
        "<unset>",
    ]
    assert not shadow_record.exists()


@pytest.mark.parametrize("claude_gate", ("unset", "false"))
def test_launcher_disabled_claude_hook_exits_before_runtime_lookup(
    claude_gate: str,
    tmp_path: Path,
) -> None:
    """Claude's default-off gate should precede PATH validation and execution."""
    workspace = tmp_path / "workspace"
    relative_bin = workspace / "relative-bin"
    record = tmp_path / "unexpected-execution.txt"
    _write_executable(
        relative_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' executed > \"$RECORD_FILE\"\n",
    )
    extra_env = {"RECORD_FILE": str(record)}
    if claude_gate == "false":
        extra_env.update(
            {
                "CLAUDE_PLUGIN_OPTION_RESPONSE_CHECKS": "false",
                "PLUGIN_ROOT": str(PLUGIN_ROOT),
            }
        )

    completed = _run_launcher(
        ["hook"],
        search_path="relative-bin",
        cwd=workspace,
        extra_env=extra_env,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert not record.exists()


@pytest.mark.parametrize(
    ("arguments", "stderr_fragment"),
    (
        ([], "expected exactly one operation"),
        (["mcp", "extra"], "expected exactly one operation"),
        (["unknown"], "unknown operation: unknown"),
    ),
)
def test_launcher_rejects_missing_extra_and_unknown_operations_cleanly(
    arguments: list[str],
    stderr_fragment: str,
    tmp_path: Path,
) -> None:
    """Operation errors should be status 1 diagnostics with no protocol output."""
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()

    completed = _run_launcher(
        arguments,
        search_path=str(empty_bin),
        cwd=tmp_path,
    )

    _assert_launcher_failure(completed, stderr_fragment)


def test_launcher_missing_runtime_fails_with_zero_stdout(tmp_path: Path) -> None:
    """A plugin install without the Python tool should fail loudly off stdout."""
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()

    completed = _run_launcher(
        ["mcp"],
        search_path=str(empty_bin),
        cwd=tmp_path,
    )

    _assert_launcher_failure(completed, "installed slop-guard not found")


def test_launcher_missing_hook_sibling_fails_with_zero_stdout(tmp_path: Path) -> None:
    """A release without ``sg-hook`` beside the runtime must not search elsewhere."""
    tool_bin = tmp_path / "tool-bin"
    _write_executable(tool_bin / "slop-guard", "#!/bin/sh\nexit 0\n")

    completed = _run_launcher(
        ["hook"],
        search_path=str(tool_bin),
        cwd=tmp_path,
        extra_env={"PLUGIN_ROOT": str(PLUGIN_ROOT)},
    )

    _assert_launcher_failure(completed, "installed sg-hook sibling not found")


@pytest.mark.parametrize("shadow_kind", ("empty", "relative"))
def test_launcher_rejects_empty_and_relative_path_executable_shadows(
    shadow_kind: str,
    tmp_path: Path,
) -> None:
    """Project-controlled PATH entries must not outrank an installed runtime."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    valid_bin = tmp_path / "trusted-bin"
    record = tmp_path / "execution-record.txt"
    _write_executable(
        valid_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' trusted > \"$RECORD_FILE\"\n",
    )
    if shadow_kind == "empty":
        shadow_bin = workspace
        search_path = os.pathsep.join(("", str(valid_bin)))
    else:
        shadow_bin = workspace / "relative-bin"
        search_path = os.pathsep.join(("relative-bin", str(valid_bin)))
    _write_executable(
        shadow_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' shadow > \"$RECORD_FILE\"\n",
    )

    completed = _run_launcher(
        ["mcp"],
        search_path=search_path,
        cwd=workspace,
        extra_env={"RECORD_FILE": str(record)},
    )

    _assert_launcher_failure(
        completed,
        "refusing slop-guard from an empty or relative PATH entry",
    )
    assert not record.exists()


def test_launcher_ignores_relative_directory_named_like_runtime(
    tmp_path: Path,
) -> None:
    """A relative directory is not an executable shadow and should be skipped."""
    workspace = tmp_path / "workspace"
    shadow = workspace / "relative-bin" / "slop-guard"
    shadow.mkdir(parents=True)
    trusted_bin = tmp_path / "trusted-bin"
    record = tmp_path / "execution-record.txt"
    _write_executable(
        trusted_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' trusted > \"$RECORD_FILE\"\n",
    )

    completed = _run_launcher(
        ["mcp"],
        search_path=os.pathsep.join(("relative-bin", str(trusted_bin))),
        cwd=workspace,
        extra_env={"RECORD_FILE": str(record)},
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert record.read_text(encoding="utf-8") == "trusted\n"


def test_launcher_stops_before_later_relative_executable(
    tmp_path: Path,
) -> None:
    """The first trusted absolute executable wins without scanning later shadows."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    trusted_bin = tmp_path / "trusted-bin"
    shadow_bin = workspace / "relative-bin"
    record = tmp_path / "execution-record.txt"
    shadow_record = tmp_path / "shadow-record.txt"
    _write_executable(
        trusted_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' trusted > \"$RECORD_FILE\"\n",
    )
    _write_executable(
        shadow_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' shadow > \"$SHADOW_RECORD\"\n",
    )

    completed = _run_launcher(
        ["mcp"],
        search_path=os.pathsep.join((str(trusted_bin), "relative-bin")),
        cwd=workspace,
        extra_env={
            "RECORD_FILE": str(record),
            "SHADOW_RECORD": str(shadow_record),
        },
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert record.read_text(encoding="utf-8") == "trusted\n"
    assert not shadow_record.exists()


def test_launcher_rejects_runtime_symlink_into_git_worktree(tmp_path: Path) -> None:
    """Canonical targets under a Git worktree are unsafe even through a symlink."""
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    real_bin = checkout / "bin"
    public_bin = tmp_path / "public-bin"
    public_bin.mkdir()
    record = tmp_path / "execution-record.txt"
    runtime = _write_executable(
        real_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' executed > \"$RECORD_FILE\"\n",
    )
    (public_bin / "slop-guard").symlink_to(runtime)

    completed = _run_launcher(
        ["mcp"],
        search_path=str(public_bin),
        cwd=tmp_path,
        extra_env={"RECORD_FILE": str(record)},
    )

    _assert_launcher_failure(completed, "refusing executable from a Git worktree")
    assert not record.exists()


def test_launcher_rejects_runtime_from_active_virtual_environment(
    tmp_path: Path,
) -> None:
    """An active project environment must not supply the persistent tool runtime."""
    virtual_environment = tmp_path / "active venv"
    tool_bin = virtual_environment / "bin"
    record = tmp_path / "execution-record.txt"
    _write_executable(
        tool_bin / "slop-guard",
        "#!/bin/sh\nprintf '%s\n' executed > \"$RECORD_FILE\"\n",
    )

    completed = _run_launcher(
        ["mcp"],
        search_path=str(tool_bin),
        cwd=tmp_path,
        extra_env={
            "RECORD_FILE": str(record),
            "VIRTUAL_ENV": str(virtual_environment),
        },
    )

    _assert_launcher_failure(
        completed,
        "refusing executable from active virtual environment",
    )
    assert not record.exists()


def test_launcher_accepts_safe_runtime_symlink_and_uses_target_sibling(
    tmp_path: Path,
) -> None:
    """A trusted runtime symlink should derive the hook from its real install."""
    real_bin = tmp_path / "real installation" / "bin"
    public_bin = tmp_path / "public-bin"
    public_bin.mkdir()
    record = tmp_path / "execution-record.txt"
    shadow_record = tmp_path / "shadow-record.txt"
    runtime = _write_executable(real_bin / "slop-guard", "#!/bin/sh\nexit 90\n")
    real_hook = _write_executable(
        real_bin / "sg-hook",
        """#!/bin/sh
printf '%s\n' "$0" > "$RECORD_FILE"
printf '%s\n' '{"systemMessage":"real sibling"}'
""",
    )
    (public_bin / "slop-guard").symlink_to(runtime)
    _write_executable(
        public_bin / "sg-hook",
        "#!/bin/sh\nprintf '%s\n' shadow > \"$SHADOW_RECORD\"\n",
    )

    completed = _run_launcher(
        ["hook"],
        search_path=str(public_bin),
        cwd=tmp_path,
        extra_env={
            "PLUGIN_ROOT": str(PLUGIN_ROOT),
            "RECORD_FILE": str(record),
            "SHADOW_RECORD": str(shadow_record),
        },
    )

    assert completed.returncode == 0
    assert completed.stdout == '{"systemMessage":"real sibling"}\n'
    assert completed.stderr == ""
    assert record.read_text(encoding="utf-8").strip() == str(real_hook.resolve())
    assert not shadow_record.exists()


def test_launcher_rejects_hook_symlink_outside_runtime_install(tmp_path: Path) -> None:
    """The derived hook's canonical target must remain a true runtime sibling."""
    tool_bin = tmp_path / "tool-bin"
    outside_bin = tmp_path / "outside-bin"
    record = tmp_path / "execution-record.txt"
    _write_executable(tool_bin / "slop-guard", "#!/bin/sh\nexit 90\n")
    outside_hook = _write_executable(
        outside_bin / "sg-hook",
        "#!/bin/sh\nprintf '%s\n' executed > \"$RECORD_FILE\"\n",
    )
    (tool_bin / "sg-hook").symlink_to(outside_hook)

    completed = _run_launcher(
        ["hook"],
        search_path=str(tool_bin),
        cwd=tmp_path,
        extra_env={
            "PLUGIN_ROOT": str(PLUGIN_ROOT),
            "RECORD_FILE": str(record),
        },
    )

    _assert_launcher_failure(completed, "is not a canonical sibling")
    assert not record.exists()
