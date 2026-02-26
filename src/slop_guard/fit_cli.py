"""CLI entry point for fitting slop-guard rule configs from JSONL corpora."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import TypeAlias

from .rules import Pipeline
from .version import PACKAGE_VERSION

EXIT_OK = 0
EXIT_ERROR = 2
_TEXT_DATASET_SUFFIXES = frozenset({".txt", ".md"})
FitSamplesAndLabels: TypeAlias = tuple[list[str], list[int]]


def _build_parser() -> argparse.ArgumentParser:
    """Construct the ``sg-fit`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="sg-fit",
        description="Fit slop-guard rule settings from JSONL corpora.",
        epilog=(
            "Inputs can be .jsonl, .txt, or .md. JSONL rows must contain a string "
            "'text' field and may include an integer 'label' field."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=PACKAGE_VERSION,
        help="Show package version and exit.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="INPUT",
        help=(
            "Training dataset input(s). Legacy mode expects TARGET_CORPUS OUTPUT. "
            "Multi-input mode requires --output."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="JSONL",
        help=(
            "Output path for fitted rules JSONL. Required when passing multiple "
            "training inputs."
        ),
    )
    parser.add_argument(
        "--init",
        default=None,
        metavar="JSONL",
        help="Initial rule JSONL config. Defaults to packaged settings.",
    )
    parser.add_argument(
        "--negative-dataset",
        nargs="+",
        action="append",
        default=None,
        metavar="INPUT",
        help=(
            "Optional negative dataset input(s) (.jsonl/.txt/.md). Can be repeated. "
            "All negative rows are normalized to label 0."
        ),
    )
    parser.add_argument(
        "--no-calibration",
        action="store_true",
        help=(
            "Skip post-fit contrastive penalty calibration. This speeds up fitting on "
            "large corpora."
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


def _load_jsonl_dataset(
    path: Path,
    *,
    default_label: int | None,
    force_label: int | None = None,
) -> FitSamplesAndLabels:
    """Load JSONL examples from ``path``.

    Args:
        path: JSONL dataset path.
        default_label: Label assigned when a row omits ``label``.
        force_label: If set, overrides any row-provided label.

    Returns:
        Two aligned lists: samples and labels.
    """
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    samples: list[str] = []
    labels: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
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

            samples.append(text_raw)
            labels.append(label)

    if not samples:
        raise ValueError(f"{path}: dataset contains no JSONL records")
    return samples, labels


def _flatten_inputs(groups: list[list[str]] | None) -> list[str]:
    """Flatten an ``argparse`` append+nargs structure into a single list."""
    if groups is None:
        return []
    return [item for group in groups for item in group]


def _resolve_train_inputs_and_output(args: argparse.Namespace) -> tuple[list[str], Path]:
    """Resolve train inputs/output while preserving legacy invocation.

    Supported forms:
      - ``sg-fit TARGET_CORPUS OUTPUT`` (legacy shorthand)
      - ``sg-fit --output OUTPUT TRAIN_INPUT [TRAIN_INPUT ...]``
    """
    if args.output is not None:
        return list(args.inputs), Path(args.output)
    if len(args.inputs) == 2:
        return [args.inputs[0]], Path(args.inputs[1])
    raise ValueError(
        "when --output is not set, expected exactly two positional arguments: "
        "TARGET_CORPUS OUTPUT"
    )


def _expand_input_paths(raw_inputs: list[str], *, role: str) -> list[Path]:
    """Expand shell-like globs and return an ordered de-duplicated path list."""
    if not raw_inputs:
        raise ValueError(f"{role}: no inputs provided")

    paths: list[Path] = []
    seen: set[str] = set()
    for raw in raw_inputs:
        raw_matches: list[str]
        if glob.has_magic(raw):
            raw_matches = sorted(glob.glob(raw, recursive=True))
            if not raw_matches:
                raise FileNotFoundError(f"{role}: no matches for pattern: {raw}")
        else:
            raw_matches = [raw]

        for match in raw_matches:
            path = Path(match)
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            paths.append(path)

    if not paths:
        raise ValueError(f"{role}: no input files after expansion")
    return paths


def _load_text_file(path: Path, *, label: int) -> FitSamplesAndLabels:
    """Load one text/markdown file as a single fit sample."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return [path.read_text(encoding="utf-8")], [label]


def _load_path_examples(
    path: Path,
    *,
    default_label: int | None,
    force_label: int | None = None,
) -> FitSamplesAndLabels:
    """Load examples from one dataset path based on file extension."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl_dataset(
            path,
            default_label=default_label,
            force_label=force_label,
        )
    if suffix in _TEXT_DATASET_SUFFIXES:
        label: int
        if force_label is not None:
            label = force_label
        elif default_label is not None:
            label = default_label
        else:
            raise ValueError(f"{path}: no default label available for text file")
        return _load_text_file(path, label=label)
    raise ValueError(
        f"{path}: unsupported dataset format '{suffix}'. "
        "Expected .jsonl, .txt, or .md"
    )


def _load_examples_from_paths(
    paths: list[Path],
    *,
    default_label: int | None,
    force_label: int | None = None,
) -> FitSamplesAndLabels:
    """Load and concatenate fit examples from multiple paths."""
    samples: list[str] = []
    labels: list[int] = []
    for path in paths:
        path_samples, path_labels = _load_path_examples(
            path,
            default_label=default_label,
            force_label=force_label,
        )
        samples.extend(path_samples)
        labels.extend(path_labels)
    if not samples:
        raise ValueError("dataset contains no records")
    return samples, labels


def fit_main(argv: list[str] | None = None) -> int:
    """Run ``sg-fit`` and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        train_inputs, output_path = _resolve_train_inputs_and_output(args)
        train_paths = _expand_input_paths(train_inputs, role="target dataset")
        negative_inputs = _flatten_inputs(args.negative_dataset)
        negative_paths = (
            _expand_input_paths(negative_inputs, role="negative dataset")
            if negative_inputs
            else []
        )

        pipeline = Pipeline.from_jsonl(args.init)
        samples, labels = _load_examples_from_paths(train_paths, default_label=1)
        if negative_paths:
            negative_samples, negative_labels = _load_examples_from_paths(
                negative_paths,
                default_label=0,
                force_label=0,
            )
            samples.extend(negative_samples)
            labels.extend(negative_labels)

        pipeline.fit(
            samples,
            labels,
            calibrate_contrastive=not args.no_calibration,
        )
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
        f"from {len(train_paths)} train files and {len(negative_paths)} negative files "
        f"using init={init_source} calibration="
        f"{'off' if args.no_calibration else 'on'} -> {output_path}"
    )
    return EXIT_OK


def main() -> None:
    """Call :func:`fit_main` and exit."""
    sys.exit(fit_main())
