"""Tests for the ``sg-fit`` CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from slop_guard import fit_cli
from slop_guard.version import PACKAGE_VERSION


class _FakePipeline:
    """Test double that records fit/output calls."""

    loaded_path: str | None = None
    last_samples: list[str] = []
    last_labels: list[int] = []
    last_calibrate_contrastive: bool | None = None
    output_path: Path | None = None

    @classmethod
    def from_jsonl(cls, path: str | None = None) -> "_FakePipeline":
        """Record the requested init config path and return a pipeline."""
        cls.loaded_path = path
        return cls()

    def fit(
        self,
        samples: list[str],
        labels: list[int] | None = None,
        *,
        calibrate_contrastive: bool = True,
    ) -> "_FakePipeline":
        """Record fit inputs."""
        self.__class__.last_samples = list(samples)
        self.__class__.last_labels = [] if labels is None else list(labels)
        self.__class__.last_calibrate_contrastive = calibrate_contrastive
        return self

    def to_jsonl(self, path: str | Path) -> None:
        """Record output target path."""
        self.__class__.output_path = Path(path)


@pytest.fixture(autouse=True)
def _reset_fake_pipeline_state() -> None:
    """Reset class-level recorder state before each test."""
    _FakePipeline.loaded_path = None
    _FakePipeline.last_samples = []
    _FakePipeline.last_labels = []
    _FakePipeline.last_calibrate_contrastive = None
    _FakePipeline.output_path = None


def test_fit_main_version_flag_prints_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``sg-fit --version`` should print package version and exit cleanly."""
    with pytest.raises(SystemExit) as raised:
        fit_cli.fit_main(["--version"])

    assert raised.value.code == fit_cli.EXIT_OK
    captured = capsys.readouterr()
    assert captured.out.strip() == PACKAGE_VERSION
    assert captured.err == ""


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
    assert _FakePipeline.last_calibrate_contrastive is True
    assert _FakePipeline.output_path == output

    captured = capsys.readouterr()
    assert "fitted 2 samples" in captured.out
    assert captured.err == ""


def test_fit_main_supports_multi_input_mode_with_output_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Multi-input mode should use ``--output`` and label text files as positives."""
    first = tmp_path / "first.txt"
    second = tmp_path / "second.md"
    first.write_text("first freeform text", encoding="utf-8")
    second.write_text("second markdown body", encoding="utf-8")
    output = tmp_path / "rules.fitted.jsonl"

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main(
        [
            "--output",
            str(output),
            str(first),
            str(second),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert _FakePipeline.last_samples == [
        "first freeform text",
        "second markdown body",
    ]
    assert _FakePipeline.last_labels == [1, 1]
    assert _FakePipeline.last_calibrate_contrastive is True
    assert _FakePipeline.output_path == output


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
            "--output",
            str(output),
            str(target),
            "--negative-dataset",
            str(negative),
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


def test_fit_main_expands_globs_for_train_and_negative_text_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Glob patterns should expand and text files should normalize into samples."""
    train_dir = tmp_path / "train" / "nested"
    negative_dir = tmp_path / "negative" / "nested"
    train_dir.mkdir(parents=True)
    negative_dir.mkdir(parents=True)

    train_txt = train_dir / "a.txt"
    train_md = train_dir / "b.md"
    negative_txt = negative_dir / "c.txt"
    negative_md = negative_dir / "d.md"

    train_txt.write_text("positive txt", encoding="utf-8")
    train_md.write_text("positive md", encoding="utf-8")
    negative_txt.write_text("negative txt", encoding="utf-8")
    negative_md.write_text("negative md", encoding="utf-8")

    output = tmp_path / "rules.fitted.jsonl"
    train_txt_glob = str(tmp_path / "train" / "**" / "*.txt")
    train_md_glob = str(tmp_path / "train" / "**" / "*.md")
    negative_txt_glob = str(tmp_path / "negative" / "**" / "*.txt")
    negative_md_glob = str(tmp_path / "negative" / "**" / "*.md")

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main(
        [
            "--output",
            str(output),
            train_txt_glob,
            train_md_glob,
            "--negative-dataset",
            negative_txt_glob,
            negative_md_glob,
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert _FakePipeline.last_samples == [
        "positive txt",
        "positive md",
        "negative txt",
        "negative md",
    ]
    assert _FakePipeline.last_labels == [1, 1, 0, 0]
    assert _FakePipeline.output_path == output


def test_fit_main_requires_output_for_multi_input_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without ``--output``, only legacy two-positional form is allowed."""
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    third = tmp_path / "third.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    third.write_text("three", encoding="utf-8")

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main([str(first), str(second), str(third)])

    assert exit_code == fit_cli.EXIT_ERROR
    captured = capsys.readouterr()
    assert "when --output is not set" in captured.err


def test_fit_main_supports_repeated_negative_dataset_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Repeated ``--negative-dataset`` groups should all be ingested."""
    target = tmp_path / "target.txt"
    negative_one = tmp_path / "negative_one.txt"
    negative_two = tmp_path / "negative_two.txt"
    output = tmp_path / "rules.fitted.jsonl"

    target.write_text("target body", encoding="utf-8")
    negative_one.write_text("negative one", encoding="utf-8")
    negative_two.write_text("negative two", encoding="utf-8")

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main(
        [
            "--output",
            str(output),
            str(target),
            "--negative-dataset",
            str(negative_one),
            "--negative-dataset",
            str(negative_two),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert _FakePipeline.last_samples == [
        "target body",
        "negative one",
        "negative two",
    ]
    assert _FakePipeline.last_labels == [1, 0, 0]
    assert _FakePipeline.output_path == output


def test_fit_main_can_disable_post_fit_calibration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--no-calibration`` should disable post-fit contrastive calibration."""
    target = tmp_path / "target.txt"
    output = tmp_path / "rules.fitted.jsonl"
    target.write_text("target body", encoding="utf-8")

    monkeypatch.setattr(fit_cli, "Pipeline", _FakePipeline)
    exit_code = fit_cli.fit_main(
        [
            "--no-calibration",
            "--output",
            str(output),
            str(target),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert _FakePipeline.last_calibrate_contrastive is False


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
