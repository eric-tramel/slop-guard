"""CLI entry point for fitting slop-guard rule configs from JSONL corpora."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .rules import Pipeline

EXIT_OK = 0
EXIT_ERROR = 2


@dataclass(frozen=True)
class FitExample:
    """One training example used when fitting a rule pipeline.

    Attributes:
        text: Raw prose sample.
        label: Binary class label where 1 means target style and 0 means negative.
    """

    text: str
    label: int


def _build_parser() -> argparse.ArgumentParser:
    """Construct the ``sg-fit`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="sg-fit",
        description="Fit slop-guard rule settings from JSONL corpora.",
        epilog=(
            "Dataset rows must contain a string 'text' field and may include "
            "an integer 'label' field."
        ),
    )
    parser.add_argument(
        "target_corpus",
        metavar="TARGET_CORPUS",
        help="Path to JSONL corpus of target prose examples.",
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT",
        help="Path where the fitted rule JSONL should be written.",
    )
    parser.add_argument(
        "--init",
        default=None,
        metavar="JSONL",
        help="Initial rule JSONL config. Defaults to packaged settings.",
    )
    parser.add_argument(
        "--negative-dataset",
        default=None,
        metavar="JSONL",
        help=(
            "Optional JSONL corpus of negative examples. All rows are normalized "
            "to label 0."
        ),
    )
    return parser


def _coerce_binary_label(raw: object, path: Path, line_number: int) -> int:
    """Validate and return a binary integer label."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError(
            f"{path}:{line_number}: 'label' must be integer 0 or 1, got {type(raw).__name__}"
        )
    if raw not in (0, 1):
        raise ValueError(f"{path}:{line_number}: 'label' must be 0 or 1, got {raw}")
    return raw


def _load_dataset(
    path: Path,
    *,
    default_label: int | None,
    force_label: int | None = None,
) -> list[FitExample]:
    """Load JSONL examples from ``path``.

    Args:
        path: JSONL dataset path.
        default_label: Label assigned when a row omits ``label``.
        force_label: If set, overrides any row-provided label.

    Returns:
        List of parsed fit examples.
    """
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    examples: list[FitExample] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc

        if not isinstance(payload, dict):
            raise TypeError(f"{path}:{line_number}: row must be a JSON object")

        text_raw = payload.get("text")
        if not isinstance(text_raw, str):
            raise TypeError(f"{path}:{line_number}: missing string 'text' field")

        label: int
        if force_label is not None:
            label = force_label
        elif "label" in payload:
            label = _coerce_binary_label(payload["label"], path, line_number)
        elif default_label is not None:
            label = default_label
        else:
            raise ValueError(
                f"{path}:{line_number}: missing 'label' and no default label was provided"
            )

        examples.append(FitExample(text=text_raw, label=label))

    if not examples:
        raise ValueError(f"{path}: dataset contains no JSONL records")
    return examples


def fit_main(argv: list[str] | None = None) -> int:
    """Run ``sg-fit`` and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    target_corpus_path = Path(args.target_corpus)
    output_path = Path(args.output)
    negative_dataset_path = (
        None if args.negative_dataset is None else Path(args.negative_dataset)
    )

    try:
        pipeline = Pipeline.from_jsonl(args.init)
        examples = _load_dataset(target_corpus_path, default_label=1)
        if negative_dataset_path is not None:
            examples.extend(
                _load_dataset(
                    negative_dataset_path,
                    default_label=0,
                    force_label=0,
                )
            )

        samples = [example.text for example in examples]
        labels = [example.label for example in examples]

        pipeline.fit(samples, labels)
        pipeline.to_jsonl(output_path)
    except (OSError, TypeError, ValueError) as exc:
        print(f"sg-fit: {exc}", file=sys.stderr)
        return EXIT_ERROR

    negative_count = sum(1 for label in labels if label == 0)
    positive_count = len(labels) - negative_count
    init_source = args.init if args.init is not None else "<packaged default>"
    print(
        "fitted "
        f"{len(labels)} samples "
        f"(positive={positive_count}, negative={negative_count}) "
        f"using init={init_source} -> {output_path}"
    )
    return EXIT_OK


def main() -> None:
    """Call :func:`fit_main` and exit."""
    sys.exit(fit_main())
