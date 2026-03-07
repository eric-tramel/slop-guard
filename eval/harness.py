# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Evaluation harness for running writing tasks against AI agents.

Orchestrates A/B experiments: each writing task is executed under a control
condition (no slop-guard feedback) and a treatment condition (slop-guard
feedback loop with iterative revision). Results are persisted as JSONL for
downstream analysis.

Supports two agent backends:
    - Claude Code (via ``claude`` CLI with MCP)
    - Codex (via ``codex`` CLI with MCP)
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TypeAlias

from .metrics import QualityMetrics, compute_quality_metrics
from .prompts import WritingTask

SlopResult: TypeAlias = dict[str, object]
TrialRecord: TypeAlias = dict[str, object]


class Agent(Enum):
    """Supported agent backends."""

    CLAUDE_CODE = "claude_code"
    CODEX = "codex"


class Condition(Enum):
    """Experimental conditions."""

    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass(frozen=True)
class HarnessConfig:
    """Configuration for a single evaluation run."""

    agent: Agent
    max_revisions: int = 3
    target_score: int = 80
    timeout_seconds: int = 120
    output_dir: Path = Path("eval/output")
    slop_guard_config: Path | None = None


@dataclass(frozen=True)
class Draft:
    """A single draft produced during a trial, with its metrics."""

    revision: int
    text: str
    slop_result: SlopResult
    quality_metrics: QualityMetrics
    elapsed_seconds: float


@dataclass
class TrialResult:
    """Full result of running one task under one condition."""

    task_id: str
    agent: str
    condition: str
    drafts: list[Draft] = field(default_factory=list)

    @property
    def final_draft(self) -> Draft:
        """Return the last draft in the revision chain."""
        return self.drafts[-1]

    @property
    def revision_count(self) -> int:
        """Return number of revision rounds (0 for single-shot)."""
        return len(self.drafts) - 1

    @property
    def converged(self) -> bool:
        """Return whether the final draft reached the target score band."""
        score = self.final_draft.slop_result.get("score", 0)
        return isinstance(score, (int, float)) and score >= 80

    def to_record(self) -> TrialRecord:
        """Serialize the trial to a flat dictionary for JSONL output."""
        final = self.final_draft
        first = self.drafts[0]
        return {
            "task_id": self.task_id,
            "agent": self.agent,
            "condition": self.condition,
            "revision_count": self.revision_count,
            "converged": self.converged,
            "initial_score": first.slop_result.get("score", 0),
            "final_score": final.slop_result.get("score", 0),
            "score_delta": (
                final.slop_result.get("score", 0)  # type: ignore[operator]
                - first.slop_result.get("score", 0)  # type: ignore[operator]
            ),
            "initial_band": first.slop_result.get("band", ""),
            "final_band": final.slop_result.get("band", ""),
            "word_count": final.quality_metrics.word_count,
            "total_elapsed_seconds": sum(d.elapsed_seconds for d in self.drafts),
            "final_quality_metrics": final.quality_metrics.to_dict(),
            "initial_quality_metrics": first.quality_metrics.to_dict(),
            "final_slop_counts": final.slop_result.get("counts", {}),
            "final_violation_count": len(
                final.slop_result.get("violations", [])  # type: ignore[arg-type]
            ),
        }


def _run_agent_cli(
    agent: Agent,
    prompt: str,
    timeout: int,
    use_mcp: bool,
    slop_guard_config: Path | None,
) -> str:
    """Invoke an agent CLI and return its text output.

    Args:
        agent: Which agent backend to use.
        prompt: The full prompt to send.
        timeout: Maximum seconds to wait.
        use_mcp: Whether to enable slop-guard MCP server.
        slop_guard_config: Optional path to custom slop-guard JSONL config.

    Returns:
        The agent's text output.

    Raises:
        subprocess.TimeoutExpired: If the agent exceeds the timeout.
        subprocess.CalledProcessError: If the agent exits non-zero.
    """
    if agent == Agent.CLAUDE_CODE:
        cmd = ["claude", "--print"]
        if use_mcp:
            mcp_args = ["uvx", "slop-guard"]
            if slop_guard_config:
                mcp_args.extend(["-c", str(slop_guard_config)])
            cmd.extend(["--mcp", json.dumps({
                "mcpServers": {
                    "slop-guard": {"command": mcp_args[0], "args": mcp_args[1:]}
                }
            })])
        cmd.extend(["--prompt", prompt])
    elif agent == Agent.CODEX:
        cmd = ["codex", "--quiet"]
        if use_mcp:
            mcp_args = ["uvx", "slop-guard"]
            if slop_guard_config:
                mcp_args.extend(["-c", str(slop_guard_config)])
            cmd.extend(["--mcp", json.dumps({
                "mcpServers": {
                    "slop-guard": {"command": mcp_args[0], "args": mcp_args[1:]}
                }
            })])
        cmd.extend(["--prompt", prompt])
    else:
        raise ValueError(f"Unknown agent: {agent}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    result.check_returncode()
    return result.stdout.strip()


def _score_text(text: str) -> SlopResult:
    """Run slop-guard CLI on text and return the JSON result."""
    result = subprocess.run(
        ["uv", "run", "sg", "-j", text],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 2:
        raise RuntimeError(f"sg error: {result.stderr}")
    return json.loads(result.stdout)


def _build_control_prompt(task: WritingTask) -> str:
    """Build the prompt for the control condition (no slop-guard)."""
    return (
        f"{task.full_prompt}\n\n"
        f"Write between {task.min_words} and {task.max_words} words. "
        f"Output only the written content, no commentary."
    )


def _build_treatment_prompt(task: WritingTask) -> str:
    """Build the prompt for the treatment condition (with slop-guard)."""
    return (
        f"{task.full_prompt}\n\n"
        f"Write between {task.min_words} and {task.max_words} words. "
        f"Output only the written content, no commentary.\n\n"
        f"IMPORTANT: After writing your draft, use the check_slop tool to "
        f"analyze your text. If the score is below 80, revise your text based "
        f"on the advice provided and check again. Repeat until the score "
        f"reaches 80 or you have revised 3 times. Output your final draft."
    )


def _build_revision_prompt(text: str, slop_result: SlopResult) -> str:
    """Build a revision prompt from slop-guard feedback."""
    advice = slop_result.get("advice", [])
    score = slop_result.get("score", 0)
    advice_text = "\n".join(f"- {a}" for a in advice) if advice else "No specific advice."
    return (
        f"Your previous draft scored {score}/100 on prose quality. "
        f"Revise the following text to address these issues:\n\n"
        f"{advice_text}\n\n"
        f"---\n\n{text}\n\n---\n\n"
        f"Output only the revised text, no commentary."
    )


def run_trial_control(
    task: WritingTask,
    config: HarnessConfig,
) -> TrialResult:
    """Run a single task under the control condition (no feedback).

    Args:
        task: The writing task to execute.
        config: Harness configuration.

    Returns:
        A TrialResult with a single draft.
    """
    trial = TrialResult(
        task_id=task.id,
        agent=config.agent.value,
        condition=Condition.CONTROL.value,
    )

    prompt = _build_control_prompt(task)
    t0 = time.monotonic()
    text = _run_agent_cli(
        config.agent, prompt, config.timeout_seconds,
        use_mcp=False, slop_guard_config=None,
    )
    elapsed = time.monotonic() - t0

    slop_result = _score_text(text)
    quality = compute_quality_metrics(text)
    trial.drafts.append(Draft(
        revision=0, text=text, slop_result=slop_result,
        quality_metrics=quality, elapsed_seconds=elapsed,
    ))
    return trial


def run_trial_treatment(
    task: WritingTask,
    config: HarnessConfig,
) -> TrialResult:
    """Run a single task under the treatment condition (with feedback loop).

    The agent receives slop-guard as an MCP tool. If the agent does not
    self-revise internally, we fall back to an external revision loop: score
    the output, feed advice back, and ask for revision up to max_revisions
    times.

    Args:
        task: The writing task to execute.
        config: Harness configuration.

    Returns:
        A TrialResult with one or more drafts.
    """
    trial = TrialResult(
        task_id=task.id,
        agent=config.agent.value,
        condition=Condition.TREATMENT.value,
    )

    prompt = _build_treatment_prompt(task)
    t0 = time.monotonic()
    text = _run_agent_cli(
        config.agent, prompt, config.timeout_seconds,
        use_mcp=True, slop_guard_config=config.slop_guard_config,
    )
    elapsed = time.monotonic() - t0

    slop_result = _score_text(text)
    quality = compute_quality_metrics(text)
    trial.drafts.append(Draft(
        revision=0, text=text, slop_result=slop_result,
        quality_metrics=quality, elapsed_seconds=elapsed,
    ))

    # External revision loop if the agent did not self-correct
    for revision in range(1, config.max_revisions + 1):
        score = slop_result.get("score", 0)
        if isinstance(score, (int, float)) and score >= config.target_score:
            break

        revision_prompt = _build_revision_prompt(text, slop_result)
        t0 = time.monotonic()
        text = _run_agent_cli(
            config.agent, revision_prompt, config.timeout_seconds,
            use_mcp=True, slop_guard_config=config.slop_guard_config,
        )
        elapsed = time.monotonic() - t0

        slop_result = _score_text(text)
        quality = compute_quality_metrics(text)
        trial.drafts.append(Draft(
            revision=revision, text=text, slop_result=slop_result,
            quality_metrics=quality, elapsed_seconds=elapsed,
        ))

    return trial


def run_experiment(
    tasks: tuple[WritingTask, ...],
    config: HarnessConfig,
) -> list[TrialResult]:
    """Run all tasks under both conditions and return results.

    Args:
        tasks: Writing tasks to evaluate.
        config: Harness configuration.

    Returns:
        List of TrialResult objects, two per task (control + treatment).
    """
    config.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[TrialResult] = []

    for task in tasks:
        control = run_trial_control(task, config)
        results.append(control)

        treatment = run_trial_treatment(task, config)
        results.append(treatment)

    output_path = config.output_dir / f"results_{config.agent.value}.jsonl"
    with open(output_path, "w") as f:
        for result in results:
            f.write(json.dumps(result.to_record()) + "\n")

    return results
