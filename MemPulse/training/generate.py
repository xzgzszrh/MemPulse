"""Deterministic synthetic TopicShift-OS-G generator.

The generator uses scenario structure to assign labels. No model is called and
no external data is downloaded. The default corpus follows the technical plan:
2,000 topics / 20,000 queries, grouped 1,600 / 200 / 200 by parent project.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CATEGORIES = (
    ("same_topic", 0.30),
    ("high_similarity", 0.25),
    ("relationship", 0.20),
    ("new_ambiguous", 0.15),
    ("version_history", 0.10),
)
SPLITS = {"train": 0.80, "validation": 0.10, "test": 0.10}


@dataclass(frozen=True)
class TopicRecord:
    topic_id: str
    project_id: str
    customer: str
    task: str
    stage: str
    people: tuple[str, ...]
    resource: str
    created_at: str

    def as_dict(self, split: str) -> dict[str, Any]:
        title = f"{self.customer}{self.task}{self.stage}"
        return {
            "topic_id": self.topic_id,
            "project_id": self.project_id,
            "split": split,
            "title": title,
            "goal": f"完成{self.customer}{self.task}",
            "summary": f"{self.customer}的{self.task}，当前阶段为{self.stage}",
            "customer": self.customer,
            "task": self.task,
            "stage": self.stage,
            "people": list(self.people),
            "resource_ids": [self.resource],
            "created_at": self.created_at,
            "event_ids": [f"{self.topic_id}:event:{index}" for index in range(1, 9)],
            "tags": {
                "person": list(self.people),
                "resource": [self.resource],
                "time": [self.created_at[:7]],
                "keyword": [self.task, self.stage],
            },
        }


def _counts(total: int) -> dict[str, int]:
    raw = {name: int(total * fraction) for name, fraction in CATEGORIES}
    remainder = total - sum(raw.values())
    raw[CATEGORIES[0][0]] += remainder
    return raw


def _split_projects(project_count: int, seed: int) -> dict[str, str]:
    projects = [f"project-{index:04d}" for index in range(project_count)]
    random.Random(seed).shuffle(projects)
    train_n = int(project_count * SPLITS["train"])
    val_n = int(project_count * SPLITS["validation"])
    test_n = project_count - train_n - val_n
    # Keep all three labels visible in smoke corpora with at least three
    # projects, while preserving the exact 80/10/10 counts at scale.
    if project_count >= 3:
        val_n = max(1, val_n)
        test_n = max(1, test_n)
        train_n = project_count - val_n - test_n
    return {
        project: (
            "train" if i < train_n else "validation" if i < train_n + val_n else "test"
        )
        for i, project in enumerate(projects)
    }


def build_topics(topic_count: int, seed: int) -> list[dict[str, Any]]:
    if topic_count < 1:
        raise ValueError("topic_count must be positive")
    topics_per_project = 4
    project_count = (topic_count + topics_per_project - 1) // topics_per_project
    split_by_project = _split_projects(project_count, seed)
    customers = ("甲客户", "乙客户", "丙客户", "丁客户")
    tasks = ("交付报告", "需求评审", "验收测试", "故障排查", "培训材料", "费用报销")
    stages = ("准备", "执行", "审核", "收尾")
    records: list[dict[str, Any]] = []
    for index in range(topic_count):
        project_index = index // topics_per_project
        variant = index % topics_per_project
        project_id = f"project-{project_index:04d}"
        record = TopicRecord(
            topic_id=f"topic-{index:05d}",
            project_id=project_id,
            customer=f"客户{project_index:04d}",
            task=tasks[(project_index + variant) % len(tasks)],
            stage=stages[variant],
            people=(
                f"person-{project_index % 37:03d}",
                f"person-{(project_index + variant + 1) % 53:03d}",
            ),
            resource=f"res:project-{project_index:04d}:artifact-{variant}",
            created_at=f"2026-{(project_index % 12) + 1:02d}-{(variant + 1):02d}T09:00:00+00:00",
        )
        records.append(record.as_dict(split_by_project[project_id]))
    return records


def _topic_index(topics: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {topic["topic_id"]: topic for topic in topics}


def build_queries(topics: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    """Create ten labelled queries per topic with exact category totals."""
    rng = random.Random(seed + 1)
    by_project: dict[str, list[dict[str, Any]]] = {}
    for topic in topics:
        by_project.setdefault(topic["project_id"], []).append(topic)
    for values in by_project.values():
        values.sort(key=lambda item: item["topic_id"])
    topic_map = _topic_index(topics)
    category_counts = _counts(len(topics) * 10)
    category_sequence: list[str] = []
    for category, count in category_counts.items():
        category_sequence.extend([category] * count)
    rng.shuffle(category_sequence)
    cursors = {topic["topic_id"]: 0 for topic in topics}
    queries: list[dict[str, Any]] = []
    for query_index, category in enumerate(category_sequence):
        # Round-robin assignment keeps every topic represented while retaining
        # exact global category proportions.
        topic = topics[query_index % len(topics)]
        topic_id = topic["topic_id"]
        sequence = cursors[topic_id]
        cursors[topic_id] += 1
        project_topics = by_project[topic["project_id"]]
        sibling = project_topics[
            (project_topics.index(topic) + 1) % len(project_topics)
        ]
        query_time = (
            datetime.fromisoformat(topic["created_at"]) + timedelta(days=8 + sequence)
        ).isoformat()
        base = {
            "query_id": f"query-{query_index:05d}",
            "project_id": topic["project_id"],
            "split": topic["split"],
            "category": category,
            "query_time": query_time,
            "allowed_context": [
                {"type": "topic_overview", "id": topic_id},
                {
                    "type": "event",
                    "id": topic["event_ids"][sequence % len(topic["event_ids"])],
                },
            ],
            "gold_topic_ids": [topic_id],
            "route": "RESUME",
            "hard_negative_topic_ids": [],
        }
        if category == "same_topic":
            base["text"] = f"继续{topic['customer']}的{topic['task']}"
        elif category == "high_similarity":
            base["text"] = f"处理{topic['customer']}的{topic['task']}，使用相同报告模板"
            base["hard_negative_topic_ids"] = [sibling["topic_id"]]
        elif category == "relationship":
            base["text"] = f"我和{topic['people'][1]}共同参与过哪些事项"
            base["gold_topic_ids"] = [
                item["topic_id"]
                for item in project_topics
                if topic["people"][1] in item["people"]
            ]
            base["route"] = "ENUMERATE"
            base["allowed_context"] = [{"type": "person", "id": topic["people"][1]}]
        elif category == "new_ambiguous":
            if query_index % 2:
                base["text"] = "开始一个新的客户交付事项"
                base["gold_topic_ids"] = []
                base["route"] = "NEW"
            else:
                base["text"] = f"继续{topic['task']}"
                base["gold_topic_ids"] = [topic_id, sibling["topic_id"]]
                base["route"] = "AMBIGUOUS"
                base["allowed_context"] = [
                    {"type": "topic_overview", "id": topic_id},
                    {"type": "topic_overview", "id": sibling["topic_id"]},
                ]
        elif category == "version_history":
            base["text"] = (
                f"{topic['customer']}{topic['task']}当前使用哪个模板，旧版本是什么"
            )
            base["allowed_context"] = [
                {"type": "event", "id": topic["event_ids"][0]},
                {"type": "event", "id": topic["event_ids"][-1]},
            ]
        queries.append(base)
    # A topic id remains in the same split as its parent project by construction.
    assert all(
        topic_map[item["gold_topic_ids"][0]]["split"] == item["split"]
        for item in queries
        if item["gold_topic_ids"]
    )
    return queries


def make_pairs(
    topics: list[dict[str, Any]], queries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the 65% identity subset: same, hard-similar and version queries."""
    topic_map = _topic_index(topics)
    pairs: list[dict[str, Any]] = []
    eligible = {"same_topic", "high_similarity", "version_history"}
    for query in queries:
        if query["category"] not in eligible or len(query["gold_topic_ids"]) != 1:
            continue
        positive_id = query["gold_topic_ids"][0]
        topic = topic_map[positive_id]
        negatives = list(query.get("hard_negative_topic_ids", []))
        if not negatives:
            # Select only within the same split. The source project is used for
            # hard negatives because the project has counterfactual tasks.
            siblings = [
                candidate["topic_id"]
                for candidate in topics
                if candidate["project_id"] == topic["project_id"]
                and candidate["topic_id"] != positive_id
            ]
            negatives = siblings[:7]
        pairs.append(
            {
                "pair_id": f"pair-{len(pairs):05d}",
                "query_id": query["query_id"],
                "split": query["split"],
                "anchor": query["text"],
                "anchor_topic_id": positive_id,
                "positive": topic["summary"],
                "positive_topic_id": positive_id,
                "hard_negative_topic_ids": negatives,
                "route": query["route"],
            }
        )
    return pairs


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def generate(
    output: str | Path,
    *,
    topics: int = 2000,
    queries: int = 20000,
    seed: int = 20260911,
    overwrite: bool = False,
) -> dict[str, Any]:
    if queries != topics * 10:
        raise ValueError(
            "the generator assigns exactly ten queries per topic; queries must equal topics * 10"
        )
    root = Path(output)
    if root.exists() and any(root.iterdir()):
        if not overwrite:
            raise FileExistsError(f"output directory is not empty: {root}")
        for child in root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    root.mkdir(parents=True, exist_ok=True)
    topic_rows = build_topics(topics, seed)
    query_rows = build_queries(topic_rows, seed)
    pair_rows = make_pairs(topic_rows, query_rows)
    topic_count = write_jsonl(root / "topics.jsonl", topic_rows)
    query_count = write_jsonl(root / "queries.jsonl", query_rows)
    pair_count = write_jsonl(root / "identity_pairs.jsonl", pair_rows)
    manifest = {
        "dataset": "TopicShift-OS-G",
        "generator": "mempulse.training.generate",
        "seed": seed,
        "topics": topic_count,
        "queries": query_count,
        "identity_pairs": pair_count,
        "split_topics": {
            split: sum(row["split"] == split for row in topic_rows) for split in SPLITS
        },
        "category_queries": {
            category: sum(row["category"] == category for row in query_rows)
            for category, _ in CATEGORIES
        },
        "labels": "script-derived; no model judgement",
        "readiness": "schema_smoke_only; human review and realistic trace expansion required",
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate TopicShift-OS-G without model downloads"
    )
    parser.add_argument("--output", default="data/topicshift_os_g_v0")
    parser.add_argument("--topics", type=int, default=2000)
    parser.add_argument("--queries", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260911)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    manifest = generate(
        args.output,
        topics=args.topics,
        queries=args.queries,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
