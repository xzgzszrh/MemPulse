import tempfile
import unittest
from pathlib import Path

from training.generate import build_queries, build_topics, generate, make_pairs
from training.train import build_batches, prepare
from training.validate import validate_dataset


class TrainingDataTests(unittest.TestCase):
    def test_smoke_generation_and_split_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = generate(root, topics=20, queries=200, seed=7)
            self.assertEqual(manifest["topics"], 20)
            self.assertEqual(manifest["queries"], 200)
            result = validate_dataset(root, expected_topics=20, expected_queries=200)
            self.assertTrue(result["ok"])
            self.assertEqual(
                result["split_topics"], {"train": 12, "validation": 4, "test": 4}
            )
            self.assertEqual(
                result["category_queries"],
                {
                    "same_topic": 60,
                    "high_similarity": 50,
                    "relationship": 40,
                    "new_ambiguous": 30,
                    "version_history": 20,
                },
            )

    def test_query_fields_and_identity_subset_ratio(self):
        topics = build_topics(8, 9)
        queries = build_queries(topics, 9)
        pairs = make_pairs(topics, queries)
        self.assertEqual(len(queries), 80)
        self.assertEqual(len(pairs), 52)  # 30% + 25% + 10% = 65%
        for query in queries:
            self.assertIn("query_time", query)
            self.assertIn("allowed_context", query)
            self.assertIn("gold_topic_ids", query)
            self.assertIn("route", query)

    def test_batches_have_unique_anchor_topics_and_no_positive_negative_collision(self):
        topics = build_topics(20, 9)
        pairs = make_pairs(topics, build_queries(topics, 9))
        batches = build_batches(pairs, batch_size=8, seed=3)
        for batch in batches:
            self.assertEqual(
                len(batch["anchor_topic_ids"]), len(set(batch["anchor_topic_ids"]))
            )
            for record in batch["records"]:
                self.assertNotIn(
                    record["positive_topic_id"], record["hard_negative_topic_ids"]
                )
                self.assertNotIn(
                    record["anchor_topic_id"], record["hard_negative_topic_ids"]
                )
                self.assertTrue(
                    set(record["hard_negative_topic_ids"]).isdisjoint(
                        batch["anchor_topic_ids"]
                    )
                )

    def test_training_prepare_is_not_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            output = Path(temp) / "run"
            generate(root, topics=8, queries=80, seed=10)
            config = prepare(root, output, batch_size=4)
            self.assertEqual(config["status"], "NOT_RUN")
            self.assertTrue((output / "training_config.json").exists())
            self.assertTrue((output / "batch_manifest.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
