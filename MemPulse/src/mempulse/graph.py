"""Deterministic tag graph and bounded path evidence."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from .models import Tag, TagKind, Topic


@dataclass(frozen=True)
class GraphPath:
    topic_id: str
    tags: tuple[str, ...]
    score: float

    def to_dict(self) -> dict[str, object]:
        return {"topic_id": self.topic_id, "tags": list(self.tags), "score": self.score}


class TagGraph:
    """In-memory projection; a SQLite implementation can mirror these methods."""

    def __init__(self) -> None:
        self.tag_to_topics: dict[str, set[str]] = defaultdict(set)
        self.topic_to_tags: dict[str, set[str]] = defaultdict(set)
        self.topic_vectors: dict[str, tuple[float, ...]] = {}

    def upsert_topic(self, topic: Topic) -> None:
        self.remove_topic(topic.topic_id)
        if topic.state == 'archived':
            return
        for tag in topic.tags:
            if tag.status != "accepted":
                continue
            self.tag_to_topics[tag.canonical].add(topic.topic_id)
            self.topic_to_tags[topic.topic_id].add(tag.canonical)
        if topic.vector:
            self.topic_vectors[topic.topic_id] = tuple(topic.vector)

    def remove_topic(self, topic_id: str) -> None:
        for tag in self.topic_to_tags.pop(topic_id, set()):
            topics = self.tag_to_topics.get(tag)
            if topics:
                topics.discard(topic_id)
                if not topics:
                    self.tag_to_topics.pop(tag, None)
        self.topic_vectors.pop(topic_id, None)

    def exact_candidates(self, tags: Iterable[Tag], *, include_attributes: bool = False) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = defaultdict(list)
        for tag in tags:
            if tag.status == "attribute" and not include_attributes:
                continue
            for topic_id in self.tag_to_topics.get(tag.canonical, ()):
                result[topic_id].append(tag.canonical)
        return {topic_id: tuple(sorted(set(values))) for topic_id, values in result.items()}

    def paths_from_tags(self, tags: Iterable[Tag], *, max_hops: int = 2,
                        max_nodes: int = 200, max_edges: int = 1000) -> tuple[dict[str, float], dict[str, tuple[str, ...]], bool]:
        """Traverse topic↔tag↔topic links with hard budgets.

        The return value is ``scores, evidence_tags, truncated``. Degree-based
        attenuation suppresses hubs such as ``kw:报告``.
        """
        starts = [tag.canonical for tag in tags if tag.status == "accepted"]
        queue: deque[tuple[str, int, float, tuple[str, ...]]] = deque()
        for tag in starts:
            degree = max(1, len(self.tag_to_topics.get(tag, ())))
            queue.append((tag, 0, 1.0 / math.log(2 + degree), (tag,)))
        visited_tags: set[str] = set(starts)
        scores: dict[str, float] = defaultdict(float)
        evidence: dict[str, tuple[str, ...]] = {}
        nodes = 0
        edges = 0
        truncated = False
        while queue:
            tag, depth, path_score, path_tags = queue.popleft()
            if depth >= max_hops:
                continue
            topics = sorted(self.tag_to_topics.get(tag, ()))
            for topic_id in topics:
                edges += 1
                nodes += 1
                if edges > max_edges or nodes > max_nodes:
                    truncated = True
                    return dict(scores), evidence, truncated
                score = path_score * (0.7 ** depth)
                scores[topic_id] = max(scores[topic_id], score)
                evidence.setdefault(topic_id, path_tags)
                for next_tag in sorted(self.topic_to_tags.get(topic_id, ())):
                    if next_tag in visited_tags:
                        continue
                    visited_tags.add(next_tag)
                    next_degree = max(1, len(self.tag_to_topics.get(next_tag, ())))
                    queue.append((next_tag, depth + 1,
                                  score / math.log(2 + next_degree),
                                  path_tags + (next_tag,)))
        return dict(scores), evidence, truncated

    def vector_candidates(self, vector: tuple[float, ...], *, limit: int = 30) -> list[tuple[str, float]]:
        scored = [(topic_id, cosine(vector, candidate))
                  for topic_id, candidate in self.topic_vectors.items()]
        return sorted(scored, key=lambda item: (-item[1], item[0]))[:limit]


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denom = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    if denom == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / denom
