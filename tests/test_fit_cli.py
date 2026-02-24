"""Tests for the ``sg-fit`` CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from slop_guard import fit_cli


class _FakePipeline:
    """Test double that records fit/output calls."""

    loaded_path: str | None = None
    last_samples: list[str] = []
    last_labels: list[int] = []
    output_path: Path | None = None

    @classmethod
    def from_jsonl(cls, path: str | None = None) -> "_FakePipeline":
        """Record the requested init config path and return a pipeline."""
        cls.loaded_path = path
        return cls()

    def fit(self, samples: list[str], labels: list[int] | None = None) -> "_FakePipeline":
        """Record fit inputs."""
        self.__class__.last_samples = list(samples)
        self.__class__.last_labels = [] if labels is None else list(labels)
        return self

    def to_jsonl(self, path: str | Path) -> None:
        """Record output target path."""
        self.__class__.output_path = Path(path)


def test_fit_main_uses_default_positive_labels_and_writes_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rows missing ``label`` should default to positive (1)."""
    dataset = tmp_path / "data.jsonl"
    dataset.write_text(
        "\n".join(
            [
                '{"text":"first target sample"}',
                '{"text":"second target sample","label":1}',
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "rules.fitted.jsonl"

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main([str(dataset), str(output)])

    assert exit_code == fit_cli.EXIT_OK
    assert _FakePipeline.loaded_path is None
    assert _FakePipeline.last_samples == [
        "first target sample",
        "second target sample",
    ]
    assert _FakePipeline.last_labels == [1, 1]
    assert _FakePipeline.output_path == output

    captured = capsys.readouterr()
    assert "fitted 2 samples" in captured.out
    assert captured.err == ""


def test_fit_main_supports_init_and_negative_dataset_normalization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Negative dataset rows should be normalized to label 0."""
    target = tmp_path / "target.jsonl"
    target.write_text(
        "\n".join(
            [
                '{"text":"target labeled","label":1}',
                '{"text":"target unlabeled"}',
            ]
        ),
        encoding="utf-8",
    )
    negative = tmp_path / "negative.jsonl"
    negative.write_text(
        "\n".join(
            [
                '{"text":"negative unlabeled"}',
                '{"text":"negative mislabeled positive","label":1}',
            ]
        ),
        encoding="utf-8",
    )
    init_config = tmp_path / "init.jsonl"
    init_config.write_text('{"rule_type":"x","config":{}}\n', encoding="utf-8")
    output = tmp_path / "rules.fitted.jsonl"

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main(
        [
            "--init",
            str(init_config),
            "--negative-dataset",
            str(negative),
            str(target),
            str(output),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert _FakePipeline.loaded_path == str(init_config)
    assert _FakePipeline.last_samples == [
        "target labeled",
        "target unlabeled",
        "negative unlabeled",
        "negative mislabeled positive",
    ]
    assert _FakePipeline.last_labels == [1, 1, 0, 0]
    assert _FakePipeline.output_path == output


def test_fit_main_returns_error_for_invalid_dataset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Invalid JSONL row schema should fail with exit code 2."""
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text('{"label":1}\n', encoding="utf-8")
    output = tmp_path / "rules.fitted.jsonl"

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main([str(invalid), str(output)])

    assert exit_code == fit_cli.EXIT_ERROR
    captured = capsys.readouterr()
    assert "missing string 'text' field" in captured.err
