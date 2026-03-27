"""Tests for the ``sg-fit`` CLI."""

from __future__ import annotations

import pytest

from slop_guard import fit_cli
from slop_guard.version import PACKAGE_VERSION


@pytest.fixture
def fit_pipeline(patch_pipeline, recording_pipeline_cls):
    """Patch the fit CLI module to use the shared recording pipeline."""
    patch_pipeline(fit_cli)
    return recording_pipeline_cls


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
    write_text_file,
    fit_pipeline,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Rows missing ``label`` should default to positive (1)."""
    dataset = write_text_file(
        "data.jsonl",
        "\n".join(
            [
                '{"text":"first target sample"}',
                '{"text":"second target sample","label":1}',
            ]
        ),
    )
    output = write_text_file("rules.fitted.jsonl", "")
    exit_code = fit_cli.fit_main([str(dataset), str(output)])

    assert exit_code == fit_cli.EXIT_OK
    assert fit_pipeline.loaded_paths == [None]
    assert len(fit_pipeline.fit_calls) == 1
    assert fit_pipeline.fit_calls[0].samples == (
        "first target sample",
        "second target sample",
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 1)
    assert fit_pipeline.fit_calls[0].calibrate_contrastive is True
    assert fit_pipeline.output_paths == [output]

    captured = capsys.readouterr()
    assert "fitted 2 samples" in captured.out
    assert captured.err == ""


def test_fit_main_supports_multi_input_mode_with_output_flag(
    write_text_file,
    fit_pipeline,
) -> None:
    """Multi-input mode should use ``--output`` and label text files as positives."""
    first = write_text_file("first.txt", "first freeform text")
    second = write_text_file("second.md", "second markdown body")
    output = write_text_file("rules.fitted.jsonl", "")
    exit_code = fit_cli.fit_main(
        [
            "--output",
            str(output),
            str(first),
            str(second),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert fit_pipeline.fit_calls[0].samples == (
        "first freeform text",
        "second markdown body",
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 1)
    assert fit_pipeline.fit_calls[0].calibrate_contrastive is True
    assert fit_pipeline.output_paths == [output]


def test_fit_main_supports_init_and_negative_dataset_normalization(
    write_text_file,
    fit_pipeline,
) -> None:
    """Negative dataset rows should be normalized to label 0."""
    target = write_text_file(
        "target.jsonl",
        "\n".join(
            [
                '{"text":"target labeled","label":1}',
                '{"text":"target unlabeled"}',
            ]
        ),
    )
    negative = write_text_file(
        "negative.jsonl",
        "\n".join(
            [
                '{"text":"negative unlabeled"}',
                '{"text":"negative mislabeled positive","label":1}',
            ]
        ),
    )
    init_config = write_text_file("init.jsonl", '{"rule_type":"x","config":{}}\n')
    output = write_text_file("rules.fitted.jsonl", "")
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
    assert fit_pipeline.loaded_paths == [str(init_config)]
    assert fit_pipeline.fit_calls[0].samples == (
        "target labeled",
        "target unlabeled",
        "negative unlabeled",
        "negative mislabeled positive",
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 1, 0, 0)
    assert fit_pipeline.output_paths == [output]


def test_fit_main_allows_negative_dataset_before_positional_input(
    write_text_file,
    fit_pipeline,
) -> None:
    """A leading negative dataset flag should not consume the train input."""
    target = write_text_file("target.txt", "target body")
    negative = write_text_file("negative.txt", "negative body")
    output = write_text_file("rules.fitted.jsonl", "")

    exit_code = fit_cli.fit_main(
        [
            "--output",
            str(output),
            "--negative-dataset",
            str(negative),
            str(target),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert fit_pipeline.fit_calls[0].samples == (
        "target body",
        "negative body",
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 0)
    assert fit_pipeline.output_paths == [output]


def test_fit_main_allows_negative_dataset_before_positional_input_with_inline_output(
    write_text_file,
    fit_pipeline,
) -> None:
    """Inline ``--output=...`` should still preserve the train input."""
    target = write_text_file("target.txt", "target body")
    negative = write_text_file("negative.txt", "negative body")
    output = write_text_file("rules.fitted.jsonl", "")

    exit_code = fit_cli.fit_main(
        [
            f"--output={output}",
            "--negative-dataset",
            str(negative),
            str(target),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert fit_pipeline.fit_calls[0].samples == (
        "target body",
        "negative body",
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 0)
    assert fit_pipeline.output_paths == [output]


def test_fit_main_allows_negative_dataset_before_legacy_positionals(
    write_text_file,
    fit_pipeline,
) -> None:
    """Legacy target/output positionals should survive a leading negative flag."""
    target = write_text_file("target.txt", "target body")
    negative = write_text_file("negative.txt", "negative body")
    output = write_text_file("rules.fitted.jsonl", "")

    exit_code = fit_cli.fit_main(
        [
            "--negative-dataset",
            str(negative),
            str(target),
            str(output),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert fit_pipeline.fit_calls[0].samples == (
        "target body",
        "negative body",
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 0)
    assert fit_pipeline.output_paths == [output]


def test_fit_main_expands_globs_for_train_and_negative_text_inputs(
    tmp_path,
    write_text_file,
    fit_pipeline,
) -> None:
    """Glob patterns should expand and text files should normalize into samples."""
    train_txt = write_text_file("train/nested/a.txt", "positive txt")
    train_md = write_text_file("train/nested/b.md", "positive md")
    negative_txt = write_text_file("negative/nested/c.txt", "negative txt")
    negative_md = write_text_file("negative/nested/d.md", "negative md")

    output = write_text_file("rules.fitted.jsonl", "")
    train_txt_glob = str(tmp_path / "train" / "**" / "*.txt")
    train_md_glob = str(tmp_path / "train" / "**" / "*.md")
    negative_txt_glob = str(tmp_path / "negative" / "**" / "*.txt")
    negative_md_glob = str(tmp_path / "negative" / "**" / "*.md")

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
    assert fit_pipeline.fit_calls[0].samples == (
        train_txt.read_text(encoding="utf-8"),
        train_md.read_text(encoding="utf-8"),
        negative_txt.read_text(encoding="utf-8"),
        negative_md.read_text(encoding="utf-8"),
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 1, 0, 0)
    assert fit_pipeline.output_paths == [output]


def test_fit_main_requires_output_for_multi_input_mode(
    write_text_file,
    fit_pipeline,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without ``--output``, only legacy two-positional form is allowed."""
    first = write_text_file("first.txt", "one")
    second = write_text_file("second.txt", "two")
    third = write_text_file("third.txt", "three")

    exit_code = fit_cli.fit_main([str(first), str(second), str(third)])

    assert exit_code == fit_cli.EXIT_ERROR
    captured = capsys.readouterr()
    assert "when --output is not set" in captured.err


def test_fit_main_supports_repeated_negative_dataset_flags(
    write_text_file,
    fit_pipeline,
) -> None:
    """Repeated ``--negative-dataset`` groups should all be ingested."""
    target = write_text_file("target.txt", "target body")
    negative_one = write_text_file("negative_one.txt", "negative one")
    negative_two = write_text_file("negative_two.txt", "negative two")
    output = write_text_file("rules.fitted.jsonl", "")
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
    assert fit_pipeline.fit_calls[0].samples == (
        "target body",
        "negative one",
        "negative two",
    )
    assert fit_pipeline.fit_calls[0].labels == (1, 0, 0)
    assert fit_pipeline.output_paths == [output]


def test_fit_main_can_disable_post_fit_calibration(
    write_text_file,
    fit_pipeline,
) -> None:
    """``--no-calibration`` should disable post-fit contrastive calibration."""
    target = write_text_file("target.txt", "target body")
    output = write_text_file("rules.fitted.jsonl", "")

    exit_code = fit_cli.fit_main(
        [
            "--no-calibration",
            "--output",
            str(output),
            str(target),
        ]
    )

    assert exit_code == fit_cli.EXIT_OK
    assert fit_pipeline.fit_calls[0].calibrate_contrastive is False


def test_fit_main_returns_error_for_invalid_dataset(
    write_text_file,
    fit_pipeline,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid JSONL row schema should fail with exit code 2."""
    invalid = write_text_file("invalid.jsonl", '{"label":1}\n')
    output = write_text_file("rules.fitted.jsonl", "")

    exit_code = fit_cli.fit_main([str(invalid), str(output)])

    assert exit_code == fit_cli.EXIT_ERROR
    captured = capsys.readouterr()
    assert "missing string 'text' field" in captured.err
