# /// script
# requires-python = ">=3.11"
# dependencies = ["data-designer"]
# ///
"""Generate pure-slop benchmark text with Data Designer defaults.

This script intentionally generates low-quality, generic prose to benchmark slop
detectors. It uses Data Designer's default model/provider configuration and the
`nvidia-text` model alias by default.

Example:
    uv run benchmark/generate-pure-slop-data-designer.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypeAlias

from data_designer.config import (
    CategorySamplerParams,
    DataDesignerConfigBuilder,
    LLMTextColumnConfig,
    SamplerColumnConfig,
    SamplerType,
    SubcategorySamplerParams,
)
from data_designer.interface import DataDesigner

PromptTemplateValues: TypeAlias = tuple[str, ...]
TopicValuesByDomain: TypeAlias = dict[str, tuple[str, ...]]
JsonRecord: TypeAlias = dict[str, str]

DEFAULT_MODEL_ALIAS = "nvidia-text"
DEFAULT_NUM_RECORDS = 64
DEFAULT_DATASET_NAME = "pure_slop_data_designer"
DEFAULT_ARTIFACT_DIR = Path("benchmark/output/data_designer_pure_slop_artifacts")
DEFAULT_OUTPUT_PATH = Path("benchmark/output/data_designer_pure_slop.jsonl")

PROMPT_TEMPLATES: PromptTemplateValues = (
    "Write a blog about",
    "Explain",
    "Write a story about",
    "Give advice about",
    "Write a detailed post about",
    "Share insights on",
)

TOPICS_BY_DOMAIN: TopicValuesByDomain = {
    "career": (
        "becoming a thought leader on LinkedIn",
        "building a personal brand at work",
        "staying productive in a fast-paced environment",
        "leading high-impact meetings",
        "turning feedback into growth opportunities",
    ),
    "wellness": (
        "achieving peak morning energy",
        "finding balance in a busy life",
        "staying positive during stressful weeks",
        "creating a sustainable self-care routine",
        "improving your mindset for daily success",
    ),
    "technology": (
        "the future of AI in everyday business",
        "why automation is transforming modern teams",
        "how digital transformation drives innovation",
        "unlocking value with data-driven decision making",
        "the next wave of intelligent workflows",
    ),
    "lifestyle": (
        "building habits that spark long-term success",
        "designing a high-performance daily routine",
        "staying motivated while pursuing big goals",
        "maintaining work-life harmony in 2026",
        "upgrading your environment for better focus",
    ),
    "finance": (
        "building wealth through smart financial discipline",
        "creating momentum with long-term investing",
        "developing healthy money habits for growth",
        "planning for financial freedom with intention",
        "making confident choices in uncertain markets",
    ),
}

SLOP_SYSTEM_PROMPT = """You write intentionally low-quality AI slop.
Produce generic, repetitive, buzzword-heavy prose with vague claims, empty
insights, and broad platitudes. Avoid concrete details, data, citations, and
specific examples. Keep the tone confident and polished while saying very
little of substance."""

SLOP_USER_PROMPT = """{{ prompt_template }} {{ topic }}.

Output requirements:
- 3-5 paragraphs of pure AI slop prose.
- Include cliches, transitions, and broad motivational framing.
- Keep content generic and non-specific.
- No bullets, no markdown, no headings."""


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate slop-heavy text samples using Data Designer defaults and "
            "export them as JSONL."
        )
    )
    parser.add_argument(
        "--num-records",
        type=int,
        default=DEFAULT_NUM_RECORDS,
        help=f"Number of slop examples to generate (default: {DEFAULT_NUM_RECORDS}).",
    )
    parser.add_argument(
        "--model-alias",
        default=DEFAULT_MODEL_ALIAS,
        help=f"Data Designer model alias to use (default: {DEFAULT_MODEL_ALIAS}).",
    )
    parser.add_argument(
        "--dataset-name",
        default=DEFAULT_DATASET_NAME,
        help=f"Data Designer dataset name (default: {DEFAULT_DATASET_NAME}).",
    )
    parser.add_argument(
        "--artifact-dir",
        default=str(DEFAULT_ARTIFACT_DIR),
        help=f"Directory for Data Designer artifacts (default: {DEFAULT_ARTIFACT_DIR}).",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Path for JSONL output file (default: {DEFAULT_OUTPUT_PATH}).",
    )
    return parser.parse_args()


def build_config_builder(model_alias: str) -> DataDesignerConfigBuilder:
    """Create a Data Designer config with sampler-driven prompt construction."""
    config_builder = DataDesignerConfigBuilder()
    config_builder.add_column(
        SamplerColumnConfig(
            name="prompt_template",
            sampler_type=SamplerType.CATEGORY,
            params=CategorySamplerParams(values=list(PROMPT_TEMPLATES)),
            drop=True,
        )
    )
    config_builder.add_column(
        SamplerColumnConfig(
            name="topic_domain",
            sampler_type=SamplerType.CATEGORY,
            params=CategorySamplerParams(values=list(TOPICS_BY_DOMAIN)),
            drop=True,
        )
    )
    config_builder.add_column(
        SamplerColumnConfig(
            name="topic",
            sampler_type=SamplerType.SUBCATEGORY,
            params=SubcategorySamplerParams(
                category="topic_domain",
                values={domain: list(topics) for domain, topics in TOPICS_BY_DOMAIN.items()},
            ),
            drop=True,
        )
    )
    config_builder.add_column(
        LLMTextColumnConfig(
            name="text",
            prompt=SLOP_USER_PROMPT,
            system_prompt=SLOP_SYSTEM_PROMPT,
            model_alias=model_alias,
        )
    )
    return config_builder


def write_jsonl(path: Path, rows: list[JsonRecord]) -> None:
    """Write records as newline-delimited JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    """Generate slop text with Data Designer and write JSONL output."""
    args = parse_args()
    if args.num_records <= 0:
        raise ValueError("--num-records must be > 0")

    artifact_dir = Path(args.artifact_dir)
    output_path = Path(args.output)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    data_designer = DataDesigner(artifact_path=artifact_dir)
    config_builder = build_config_builder(model_alias=args.model_alias)

    data_designer.validate(config_builder)
    results = data_designer.create(
        config_builder=config_builder,
        num_records=args.num_records,
        dataset_name=args.dataset_name,
    )

    dataset = results.load_dataset()
    if "text" not in dataset.columns:
        raise KeyError("Generated dataset is missing required 'text' column")

    text_rows: list[JsonRecord] = [{"text": str(value)} for value in dataset["text"]]
    write_jsonl(path=output_path, rows=text_rows)

    print(f"Generated {len(text_rows):,} pure slop examples.")
    print(f"JSONL output: {output_path.resolve()}")
    print(f"Artifacts: {results.artifact_storage.base_dataset_path.resolve()}")


if __name__ == "__main__":
    main()
