"""Measure SQL-bounded candidate routing at the design scale; no model claims."""

import argparse, statistics, time, tempfile
from pathlib import Path
from mempulse.models import Topic, Tag, TagKind
from mempulse.sqlite_store import SQLiteTopicStore
from mempulse.service import TopicFacade


def main(n=10000):
    with tempfile.TemporaryDirectory() as d:
        store = SQLiteTopicStore(Path(d) / "scale.db")
        with store.transaction():
            for i in range(n):
                topic = Topic(
                    f"topic-{i}", "default", f"客户{i % 100}交付任务{i}", "目标"
                )
                topic.tags = [
                    Tag(
                        TagKind.KEYWORD,
                        f"kw:任务{i % 40}",
                        f"任务{i % 40}",
                        source_event_ids=(),
                    )
                ]
                store.save_topic(topic)
        f = TopicFacade(Path(d) / "scale.db")
        times = []
        for _ in range(100):
            t = time.perf_counter()
            f.resolve("继续客户交付任务")
            times.append((time.perf_counter() - t) * 1000)
        times.sort()
        print(
            {
                "topics": n,
                "queries": len(times),
                "p50_ms": statistics.median(times),
                "p95_ms": times[94],
                "max_ms": max(times),
                "embedding": "unloaded",
                "claim": False,
            }
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--topics", type=int, default=10000)
    main(p.parse_args().topics)
