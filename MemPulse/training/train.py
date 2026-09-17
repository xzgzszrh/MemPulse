"""Optional TIDE training preparation and guarded execution entry point.

This module never downloads a model and never starts training unless the caller
explicitly passes ``--run``. The default action only validates data and writes
the exact proposed configuration. It also emits a batch manifest where every
batch has unique anchor topics and explicit hard negatives; gradient
accumulation is not treated as a larger negative-sample batch.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from .generate import write_jsonl
from .validate import read_jsonl, validate_dataset


TRAIN_CONFIG: dict[str, Any] = {
    "base_model": "BAAI/bge-base-zh-v1.5",
    "framework": "PyTorch + FlagEmbedding",
    "query_max_tokens": 128,
    "topic_max_tokens": 384,
    "max_tokens": 512,
    "optimizer": "AdamW",
    "learning_rate": 2e-5,
    "warmup_ratio": 0.10,
    "weight_decay": 0.01,
    "positives_per_query": 1,
    "explicit_negatives_per_query": 7,
    "groups_per_step": 64,
    "temperature": 0.02,
    "epochs_max": 5,
    "validation_every_steps": 100,
    "export": {"onnx_opset": 17, "formats": ["fp32", "int8"]},
    "identity_categories": ["same_topic", "high_similarity", "version_history"],
    "status": "NOT_RUN",
}


def build_batches(
    pairs: list[dict[str, Any]],
    *,
    batch_size: int = 64,
    negatives_per_query: int = 7,
    seed: int = 20260911,
) -> list[dict[str, Any]]:
    """Build explicit batches without cross-batch negative ambiguity.

    Each batch has at most one anchor per topic. Negatives are sampled from
    topics outside all anchors in that batch, and are written into the batch
    manifest rather than inferred from gradient accumulation.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    rng = random.Random(seed)
    batches: list[dict[str, Any]] = []
    # Never mix split-specific topics in one batch. This keeps project and
    # counterfactual boundaries meaningful even when the caller passes all
    # three split files together.
    by_split: dict[str, list[dict[str, Any]]] = {}
    for pair in pairs:
        by_split.setdefault(pair.get("split", "train"), []).append(pair)
    for split, split_pairs in sorted(by_split.items()):
        ordered = list(split_pairs)
        rng.shuffle(ordered)
        split_topics = sorted({row["positive_topic_id"] for row in ordered})
        pending = ordered
        max_anchors = min(batch_size, max(1, len(split_topics) - negatives_per_query))
        while pending:
            selected = []
            used_topics = set()
            deferred = []
            for pair in pending:
                topic_id = pair["anchor_topic_id"]
                if topic_id in used_topics or len(selected) >= max_anchors:
                    deferred.append(pair)
                else:
                    used_topics.add(topic_id)
                    selected.append(pair)
            pending = deferred
            # Compute the full anchor set before sampling negatives, so a
            # negative never accidentally becomes a later anchor in this batch.
            chunk: list[dict[str, Any]] = []
            for pair in selected:
                topic_id = pair["anchor_topic_id"]
                negatives = [
                    candidate
                    for candidate in pair.get("hard_negative_topic_ids", [])
                    if candidate not in used_topics and candidate != topic_id
                ]
                pool = [
                    candidate
                    for candidate in split_topics
                    if candidate not in used_topics and candidate != topic_id
                ]
                for candidate in pool:
                    if candidate not in negatives:
                        negatives.append(candidate)
                    if len(negatives) >= negatives_per_query:
                        break
                chunk.append(
                    {
                        "pair_id": pair["pair_id"],
                        "split": split,
                        "anchor_topic_id": topic_id,
                        "positive_topic_id": pair["positive_topic_id"],
                        "hard_negative_topic_ids": negatives[:negatives_per_query],
                    }
                )
            if chunk:
                batches.append(
                    {
                        "batch_id": f"batch-{len(batches):05d}",
                        "split": split,
                        "anchor_topic_ids": sorted(used_topics),
                        "records": chunk,
                        "negative_policy": "explicit_per_query; no gradient-accumulation negatives",
                    }
                )
    return batches


def prepare(
    data_root: str | Path,
    output_root: str | Path,
    *,
    batch_size: int = 64,
    seed: int = 20260911,
) -> dict[str, Any]:
    data_root, output_root = Path(data_root), Path(output_root)
    validation = validate_dataset(data_root)
    all_pairs = read_jsonl(data_root / "identity_pairs.jsonl")
    # Validation/test identity pairs are retained for evaluation but never
    # enter the training batch manifest.
    pairs = [pair for pair in all_pairs if pair.get("split") == "train"]
    output_root.mkdir(parents=True, exist_ok=True)
    batches = build_batches(pairs, batch_size=batch_size, seed=seed)
    batch_rows = []
    for batch in batches:
        for row in batch["records"]:
            batch_rows.append(
                {
                    **row,
                    "batch_id": batch["batch_id"],
                    "batch_anchor_topic_ids": batch["anchor_topic_ids"],
                }
            )
    batch_count = write_jsonl(output_root / "batch_manifest.jsonl", batch_rows)
    config = {
        **TRAIN_CONFIG,
        "batch_size": batch_size,
        "seed": seed,
        "data_root": str(data_root),
        "validation": validation,
        "identity_pair_count": len(pairs),
        "identity_pair_counts_by_split": {
            split: sum(pair.get("split") == split for pair in all_pairs)
            for split in ("train", "validation", "test")
        },
        "batch_count": len(batches),
        "batch_record_count": batch_count,
        "status": "NOT_RUN",
        "reason": "Preparation only; use training.run_torch for actual local-weight training.",
    }
    (output_root / "training_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return config


def guarded_run(config_path: str | Path) -> dict[str, Any]:
    """Check optional dependencies without downloading or training."""
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for module in ("torch", "FlagEmbedding"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        config.update(
            {
                "status": "NOT_RUN",
                "reason": f"missing optional dependencies: {', '.join(missing)}",
            }
        )
    else:
        config.update(
            {
                "status": "NOT_RUN",
                "reason": "Dependencies detected; long training is intentionally not started by this entry point.",
            }
        )
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare guarded TIDE training")
    parser.add_argument("--data", default="data/topicshift_os_g_v0")
    parser.add_argument("--output", default="runs/tide_prepare")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260911)
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check optional deps; actual training uses training.run_torch",
    )
    args = parser.parse_args(argv)
    config = prepare(args.data, args.output, batch_size=args.batch_size, seed=args.seed)
    if args.check_deps:
        config = guarded_run(Path(args.output) / "training_config.json")
    print(
        json.dumps(
            {
                "status": config["status"],
                "output": args.output,
                "identity_pair_count": config["identity_pair_count"],
                "reason": config.get("reason"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
