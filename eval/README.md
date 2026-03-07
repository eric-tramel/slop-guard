# slop-guard Evaluation Harness

Measure whether slop-guard feedback actually improves AI-written prose, or whether agents learn to game the linter without genuine quality gains.

## Experimental Design

Each writing task runs under two conditions:

| Condition | Setup | What it measures |
|-----------|-------|------------------|
| **Control** | Agent writes without slop-guard | Baseline AI writing quality |
| **Treatment** | Agent writes with slop-guard MCP + revision loop | Effect of slop-guard feedback |

Tasks span 10 genres (API docs, blog posts, READMEs, design docs, etc.) to avoid genre-specific bias.

## Metrics

### Internal (slop-guard)

- **Score** (0–100): The tool's own quality assessment
- **Violation counts** by rule category
- **Convergence rate**: % of tasks reaching "clean" band (≥80) within N revisions
- **Revision count**: How many feedback rounds the agent needed

### External (independent of slop-guard)

These prevent Goodhart's Law — if the agent games slop-guard but these degrade, the tool is teaching pattern avoidance rather than better writing.

| Metric | What it captures |
|--------|-----------------|
| Type-token ratio | Lexical diversity |
| Hapax ratio | % of words used exactly once |
| Sentence length CV | Rhythm variation |
| Flesch-Kincaid grade | Readability |
| Gunning fog index | Complexity |
| Paragraph length CV | Structural variation |

### Gaming Detection

A **gaming flag** is raised when:
1. Slop-guard score improves by ≥10 points, AND
2. Two or more external metrics degrade beyond threshold

This catches the failure mode where agents learn to avoid slop-guard patterns while producing blander, less diverse text.

### Effect Size

All paired comparisons report **Cohen's d** to distinguish meaningful improvements from noise.

## Usage

### Run an experiment

```bash
# Full suite against Claude Code
uv run eval/cli.py run --agent claude_code

# Single genre, more revisions
uv run eval/cli.py run --agent codex --genre blog_post --max-revisions 5

# Custom slop-guard config
uv run eval/cli.py run --agent claude_code --config fitted_rules.jsonl
```

### Generate a report

```bash
uv run eval/cli.py report eval/output/results_claude_code.jsonl
uv run eval/cli.py report eval/output/results_claude_code.jsonl --json
```

### Compare agents

```bash
uv run eval/cli.py compare \
    eval/output/results_claude_code.jsonl \
    eval/output/results_codex.jsonl
```

## Output Format

Results are stored as JSONL in `eval/output/`. Each line is a trial record:

```json
{
    "task_id": "blog-testing-strategy",
    "agent": "claude_code",
    "condition": "treatment",
    "revision_count": 2,
    "converged": true,
    "initial_score": 52,
    "final_score": 84,
    "score_delta": 32,
    "final_quality_metrics": {
        "type_token_ratio": 0.6234,
        "hapax_ratio": 0.4102,
        "sentence_length_cv": 0.4512,
        "flesch_kincaid_grade": 9.2,
        "gunning_fog_index": 11.4
    }
}
```

## Architecture

```
eval/
├── prompts.py    # 12 writing tasks across 10 genres
├── metrics.py    # External quality metrics (TTR, readability, etc.)
├── harness.py    # Agent invocation, revision loop, trial collection
├── analyze.py    # Paired comparisons, convergence, gaming detection
└── cli.py        # sg-eval CLI entry point
```

## Interpreting Results

**Good outcome**: Treatment scores higher on both slop-guard AND external metrics. No gaming flags.

**Concerning outcome**: Treatment scores higher on slop-guard but external metrics are flat or declining. Gaming flags raised. This means the agent learned to avoid slop-guard patterns without improving actual prose quality.

**Key questions the harness answers**:
1. Does slop-guard feedback raise writing quality (not just the score)?
2. How many revision rounds does convergence take?
3. Do agents game the linter?
4. Which agent (Claude Code vs Codex) responds better to feedback?
5. Which writing genres benefit most from slop-guard?
