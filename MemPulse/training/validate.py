"""Strict structural and split validator for TopicShift-OS-G."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .generate import CATEGORIES, SPLITS


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(value)
    return rows


def validate_dataset(
    root: str | Path,
    *,
    expected_topics: int | None = None,
    expected_queries: int | None = None,
) -> dict[str, Any]:
    root = Path(root)
    topics = read_jsonl(root / "topics.jsonl")
    queries = read_jsonl(root / "queries.jsonl")
    pairs = (
        read_jsonl(root / "identity_pairs.jsonl")
        if (root / "identity_pairs.jsonl").exists()
        else []
    )
    errors: list[str] = []
    if expected_topics is not None and len(topics) != expected_topics:
        errors.append(f"topics={len(topics)} expected {expected_topics}")
    if expected_queries is not None and len(queries) != expected_queries:
        errors.append(f"queries={len(queries)} expected {expected_queries}")
    topic_ids = {row.get("topic_id") for row in topics}
    project_splits: dict[str, set[str]] = defaultdict(set)
    split_topics = Counter()
    for topic in topics:
        required = {"topic_id", "project_id", "split", "summary", "event_ids"}
        missing = required - topic.keys()
        if missing:
            errors.append(f"topic {topic.get('topic_id')}: missing {sorted(missing)}")
        split_topics[topic.get("split")] += 1
        project_splits[topic.get("project_id")].add(topic.get("split"))
    leaked_projects = [
        project for project, splits in project_splits.items() if len(splits) != 1
    ]
    if leaked_projects:
        errors.append(f"projects cross split: {leaked_projects[:5]}")
    category_counts = Counter()
    query_splits = Counter()
    seen_queries: set[str] = set()
    for query in queries:
        required = {
            "query_id",
            "project_id",
            "split",
            "category",
            "query_time",
            "allowed_context",
            "gold_topic_ids",
            "route",
        }
        missing = required - query.keys()
        if missing:
            errors.append(f"query {query.get('query_id')}: missing {sorted(missing)}")
        query_id = query.get("query_id")
        if query_id in seen_queries:
            errors.append(f"duplicate query_id: {query_id}")
        seen_queries.add(query_id)
        category_counts[query.get("category")] += 1
        query_splits[query.get("split")] += 1
        expected_routes = {
            "same_topic": "RESUME",
            "high_similarity": "RESUME",
            "relationship": "ENUMERATE",
            "version_history": "RESUME",
        }
        category = query.get("category")
        if (
            category in expected_routes
            and query.get("route") != expected_routes[category]
        ):
            errors.append(f"query {query_id}: route/category mismatch")
        if category == "new_ambiguous" and query.get("route") not in {
            "NEW",
            "AMBIGUOUS",
        }:
            errors.append(f"query {query_id}: invalid new_ambiguous route")
        for gold_id in query.get("gold_topic_ids", []):
            if gold_id not in topic_ids:
                errors.append(f"query {query_id}: unknown gold topic {gold_id}")
        if query.get("split") not in SPLITS:
            errors.append(f"query {query_id}: unknown split {query.get('split')}")
        if query.get("split") in SPLITS:
            gold_projects = {
                next(
                    (
                        row["project_id"]
                        for row in topics
                        if row.get("topic_id") == gold
                    ),
                    None,
                )
                for gold in query.get("gold_topic_ids", [])
            }
            if gold_projects - {None} and not gold_projects.issubset(
                {query.get("project_id")}
            ):
                errors.append(f"query {query_id}: gold topic crosses project")
    total_queries = len(queries)
    expected_categories = {
        name: int(total_queries * fraction) for name, fraction in CATEGORIES
    }
    if total_queries and sum(expected_categories.values()) != total_queries:
        expected_categories[CATEGORIES[0][0]] += total_queries - sum(
            expected_categories.values()
        )
    for category, expected in expected_categories.items():
        if category_counts[category] != expected:
            errors.append(
                f"category {category}={category_counts[category]} expected {expected}"
            )
    pair_topic_ids = {row.get("anchor_topic_id") for row in pairs}
    pair_categories = Counter()
    query_by_id = {row.get("query_id"): row for row in queries}
    for pair in pairs:
        source = query_by_id.get(pair.get("query_id"))
        if source is None:
            errors.append(f"pair {pair.get('pair_id')}: unknown query")
            continue
        pair_categories[source.get("category")] += 1
        if source.get("category") not in {
            "same_topic",
            "high_similarity",
            "version_history",
        }:
            errors.append(f"pair {pair.get('pair_id')}: non-identity category")
        forbidden = {pair.get("anchor_topic_id"), pair.get("positive_topic_id")}
        if forbidden & set(pair.get("hard_negative_topic_ids", [])):
            errors.append(f"pair {pair.get('pair_id')}: positive appears as negative")
    expected_pairs = sum(
        category_counts[name]
        for name in ("same_topic", "high_similarity", "version_history")
    )
    if len(pairs) != expected_pairs:
        errors.append(f"identity_pairs={len(pairs)} expected {expected_pairs}")
    result = {
        "ok": not errors,
        "topics": len(topics),
        "queries": len(queries),
        "identity_pairs": len(pairs),
        "split_topics": dict(split_topics),
        "split_projects": len(project_splits),
        "category_queries": dict(category_counts),
        "identity_pair_categories": dict(pair_categories),
        "errors": errors,
    }
    if errors:
        raise ValueError(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate TopicShift-OS-G structure")
    parser.add_argument("root", nargs="?", default="data/topicshift_os_g_v0")
    parser.add_argument("--topics", type=int)
    parser.add_argument("--queries", type=int)
    args = parser.parse_args(argv)
    result = validate_dataset(
        args.root, expected_topics=args.topics, expected_queries=args.queries
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
