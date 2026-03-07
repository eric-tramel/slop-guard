"""Tests for the evaluation prompts module."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval.prompts import CORE_TASKS, Genre, WritingTask, tasks_by_genre


class TestWritingTask:
    """Tests for WritingTask."""

    def test_full_prompt_no_context(self) -> None:
        task = WritingTask(
            id="test", genre=Genre.BLOG_POST,
            prompt="Write something.", min_words=100, max_words=500,
        )
        assert task.full_prompt == "Write something."

    def test_full_prompt_with_context(self) -> None:
        task = WritingTask(
            id="test", genre=Genre.BLOG_POST,
            prompt="Write something.", min_words=100, max_words=500,
            context="You are an expert.",
        )
        assert task.full_prompt.startswith("You are an expert.")
        assert "Write something." in task.full_prompt

    def test_frozen(self) -> None:
        task = WritingTask(
            id="test", genre=Genre.BLOG_POST,
            prompt="Write.", min_words=100, max_words=500,
        )
        try:
            task.id = "other"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass


class TestCoreTasks:
    """Tests for the CORE_TASKS suite."""

    def test_non_empty(self) -> None:
        assert len(CORE_TASKS) >= 10

    def test_unique_ids(self) -> None:
        ids = [t.id for t in CORE_TASKS]
        assert len(ids) == len(set(ids))

    def test_word_bounds_valid(self) -> None:
        for task in CORE_TASKS:
            assert task.min_words > 0
            assert task.max_words > task.min_words

    def test_multiple_genres(self) -> None:
        genres = {t.genre for t in CORE_TASKS}
        assert len(genres) >= 5


class TestTasksByGenre:
    """Tests for tasks_by_genre."""

    def test_filter(self) -> None:
        blog_tasks = tasks_by_genre(Genre.BLOG_POST)
        assert all(t.genre == Genre.BLOG_POST for t in blog_tasks)
        assert len(blog_tasks) >= 1

    def test_empty_genre(self) -> None:
        # COMMIT_MESSAGE genre has no tasks in CORE_TASKS
        commit_tasks = tasks_by_genre(Genre.COMMIT_MESSAGE)
        assert len(commit_tasks) == 0
