# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Writing task prompts for evaluating slop-guard effectiveness.

Each task defines a genre, a prompt, and expected output characteristics. Tasks
span technical documentation, blog posts, explanations, and creative prose to
cover the breadth of content AI agents are asked to produce.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class Genre(Enum):
    """Writing genre categories for stratified evaluation."""

    TECHNICAL_DOCS = "technical_docs"
    BLOG_POST = "blog_post"
    EXPLANATION = "explanation"
    README = "readme"
    PR_DESCRIPTION = "pr_description"
    COMMIT_MESSAGE = "commit_message"
    TUTORIAL = "tutorial"
    OPINION = "opinion"
    CHANGELOG = "changelog"
    DESIGN_DOC = "design_doc"


@dataclass(frozen=True)
class WritingTask:
    """A single writing prompt with evaluation metadata."""

    id: str
    genre: Genre
    prompt: str
    min_words: int
    max_words: int
    context: str = ""

    @property
    def full_prompt(self) -> str:
        """Return the prompt with any context prepended."""
        if self.context:
            return f"{self.context}\n\n{self.prompt}"
        return self.prompt


TaskSuite: TypeAlias = tuple[WritingTask, ...]


CORE_TASKS: TaskSuite = (
    # --- Technical Documentation ---
    WritingTask(
        id="tech-api-reference",
        genre=Genre.TECHNICAL_DOCS,
        prompt=(
            "Write API reference documentation for a Python HTTP client library "
            "that supports retry logic, connection pooling, and request "
            "interceptors. Cover the three main classes and their methods."
        ),
        min_words=400,
        max_words=1200,
    ),
    WritingTask(
        id="tech-config-guide",
        genre=Genre.TECHNICAL_DOCS,
        prompt=(
            "Write a configuration guide for a build system that supports "
            "YAML and TOML config files, environment variable overrides, "
            "and plugin hooks. Include examples of each mechanism."
        ),
        min_words=500,
        max_words=1500,
    ),
    # --- Blog Posts ---
    WritingTask(
        id="blog-testing-strategy",
        genre=Genre.BLOG_POST,
        prompt=(
            "Write a blog post about why most teams over-invest in unit tests "
            "and under-invest in integration tests. Draw on concrete examples "
            "from web application development."
        ),
        min_words=600,
        max_words=1500,
    ),
    WritingTask(
        id="blog-monorepo",
        genre=Genre.BLOG_POST,
        prompt=(
            "Write a blog post arguing for or against monorepo architectures "
            "for mid-size engineering teams (20-50 developers). Ground the "
            "argument in real tradeoffs, not hype."
        ),
        min_words=600,
        max_words=1500,
    ),
    # --- Explanations ---
    WritingTask(
        id="explain-raft",
        genre=Genre.EXPLANATION,
        prompt=(
            "Explain the Raft consensus algorithm to an engineer who "
            "understands distributed systems but has not read the paper. "
            "Focus on leader election and log replication."
        ),
        min_words=500,
        max_words=1200,
    ),
    WritingTask(
        id="explain-backpressure",
        genre=Genre.EXPLANATION,
        prompt=(
            "Explain backpressure in stream processing systems. Cover why it "
            "matters, the common strategies (buffering, dropping, signaling), "
            "and when each strategy is appropriate."
        ),
        min_words=400,
        max_words=1000,
    ),
    # --- READMEs ---
    WritingTask(
        id="readme-cli-tool",
        genre=Genre.README,
        prompt=(
            "Write a README for a command-line tool called 'dq' that queries "
            "CSV and Parquet files using SQL syntax. It supports JOINs across "
            "files, output to JSON/CSV, and streaming large files."
        ),
        min_words=300,
        max_words=800,
    ),
    # --- PR Descriptions ---
    WritingTask(
        id="pr-auth-refactor",
        genre=Genre.PR_DESCRIPTION,
        prompt=(
            "Write a pull request description for a change that replaces "
            "session-based authentication with JWT tokens in a Django REST "
            "application. The change touches 12 files, adds a token refresh "
            "endpoint, and deprecates the /login cookie flow."
        ),
        min_words=200,
        max_words=600,
    ),
    # --- Tutorials ---
    WritingTask(
        id="tutorial-docker-compose",
        genre=Genre.TUTORIAL,
        prompt=(
            "Write a step-by-step tutorial on setting up a local development "
            "environment with Docker Compose for a Python web app with "
            "PostgreSQL and Redis. Target developers who know Docker basics "
            "but have not used Compose."
        ),
        min_words=500,
        max_words=1200,
    ),
    # --- Design Docs ---
    WritingTask(
        id="design-rate-limiter",
        genre=Genre.DESIGN_DOC,
        prompt=(
            "Write a design document for adding per-tenant rate limiting to "
            "a multi-tenant SaaS API. Cover the sliding window algorithm, "
            "Redis-backed storage, and the HTTP response contract (429s, "
            "Retry-After headers). Include alternatives considered."
        ),
        min_words=600,
        max_words=1500,
    ),
    # --- Changelogs ---
    WritingTask(
        id="changelog-v2",
        genre=Genre.CHANGELOG,
        prompt=(
            "Write a changelog entry for version 2.0.0 of a data pipeline "
            "framework. Breaking changes: config format migrated from INI to "
            "TOML, Python 3.9 dropped. New features: parallel execution, "
            "built-in S3 sink, schema validation. Bug fixes: memory leak in "
            "CSV parser, timezone handling in cron scheduler."
        ),
        min_words=200,
        max_words=500,
    ),
    # --- Opinion ---
    WritingTask(
        id="opinion-ai-code-review",
        genre=Genre.OPINION,
        prompt=(
            "Write an opinion piece on whether AI-assisted code review will "
            "replace human reviewers within five years. Take a clear stance "
            "and defend it with specific reasoning."
        ),
        min_words=500,
        max_words=1200,
    ),
)


def tasks_by_genre(genre: Genre) -> TaskSuite:
    """Filter the core task suite to a single genre."""
    return tuple(task for task in CORE_TASKS if task.genre == genre)
