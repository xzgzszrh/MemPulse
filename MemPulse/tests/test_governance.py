import sqlite3
import unittest

from mempulse.governance import Governance


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.gov = Governance(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_cpr_scope_and_non_promotion(self):
        explicit = self.gov.record_preference(
            user_id="u1", key="format", value="docx", evidence_event_id="e1"
        )
        fallback = self.gov.record_preference(
            user_id="u1",
            key="format",
            value="txt",
            choice_type="fallback",
            evidence_event_id="e2",
        )
        temporary = self.gov.record_preference(
            user_id="u1",
            key="format",
            value="pdf",
            scope_type="task",
            scope_id="task-1",
            choice_type="temporary",
            evidence_event_id="e3",
        )
        self.assertTrue(explicit["promoted"])
        self.assertFalse(fallback["promoted"])
        self.assertFalse(temporary["promoted"])
        self.assertEqual(
            self.gov.resolve_preference(user_id="u1", key="format")["value"], "docx"
        )
        task_pref = self.gov.resolve_preference(
            user_id="u1", key="format", task_id="task-1"
        )
        self.assertEqual(task_pref["value"], "pdf")
        self.assertEqual(task_pref["source"]["choice_type"], "temporary")

    def test_temporary_global_is_rejected(self):
        with self.assertRaises(ValueError):
            self.gov.record_preference(
                user_id="u1", key="format", value="pdf", choice_type="temporary"
            )

    def test_knowledge_valid_time_supersedes_and_disputed(self):
        v2 = self.gov.record_knowledge(
            user_id="u1",
            key="template",
            value="V2",
            scope_id="topic-1",
            valid_from="2026-08-01T00:00:00+00:00",
            observed_at="2026-08-01T01:00:00+00:00",
        )
        v3 = self.gov.record_knowledge(
            user_id="u1",
            key="template",
            value="V3",
            scope_id="topic-1",
            valid_from="2026-09-01T00:00:00+00:00",
            observed_at="2026-09-03T01:00:00+00:00",
            supersedes=v2["id"],
        )
        old = self.gov.resolve_knowledge(
            user_id="u1",
            key="template",
            scope_id="topic-1",
            valid_at="2026-08-15T00:00:00+00:00",
            known_at="2026-09-10T00:00:00+00:00",
        )
        current = self.gov.resolve_knowledge(
            user_id="u1",
            key="template",
            scope_id="topic-1",
            valid_at="2026-09-10T00:00:00+00:00",
            known_at="2026-09-10T00:00:00+00:00",
        )
        self.assertEqual(old["value"], "V2")
        self.assertEqual(current["value"], "V3")
        self.assertEqual(current["source"]["supersedes"], v2["id"])
        disputed = self.gov.record_knowledge(
            user_id="u1",
            key="owner",
            value="张三",
            scope_id="topic-1",
            disputed=True,
            dispute_reason="来源冲突",
        )
        result = self.gov.resolve_knowledge(
            user_id="u1", key="owner", scope_id="topic-1", include_disputed=True
        )
        self.assertEqual(result["status"], "disputed")
        self.assertEqual(result["source"]["id"], disputed["id"])

    def test_checkpoint_latest_and_pending_operations(self):
        first = self.gov.save_checkpoint(
            user_id="u1",
            topic_id="t1",
            payload={"done": ["outline"]},
            event_watermark="e10",
            pending_operation_keys=["send:42", "send:42"],
        )
        exact = self.gov.get_checkpoint(
            user_id="u1", topic_id="t1", checkpoint_id=first["id"]
        )
        self.assertTrue(exact["found"])
        self.assertEqual(exact["checkpoint"]["pending_operation_keys"], ["send:42"])
        second = self.gov.save_checkpoint(
            user_id="u1", topic_id="t1", payload={"done": ["draft"]}
        )
        latest = self.gov.get_checkpoint(user_id="u1", topic_id="t1")
        self.assertEqual(latest["checkpoint"]["id"], second["id"])

    def test_tombstone_returns_recursive_dependencies_and_is_idempotent(self):
        self.gov.add_derivation(
            derived_type="tag", derived_id="tag-1", source_id="event-1"
        )
        self.gov.add_derivation(
            derived_type="summary",
            derived_id="summary-1",
            source_type="tag",
            source_id="tag-1",
        )
        receipt = self.gov.create_tombstone(
            target_type="event",
            target_id="event-1",
            reason="删除手机号",
            requested_by="u1",
        )
        self.assertTrue(
            self.gov.is_tombstoned(target_type="event", target_id="event-1")
        )
        self.assertEqual(
            {item["id"] for item in receipt["dependencies"]}, {"tag-1", "summary-1"}
        )
        self.assertEqual(
            receipt, self.gov.create_tombstone(target_type="event", target_id="event-1")
        )
        outbox = self.conn.execute("SELECT task_type,status FROM mp_outbox").fetchall()
        self.assertEqual(outbox, [("forget_cleanup", "pending")])
        completed = self.gov.complete_tombstone(receipt["id"])
        self.assertEqual(completed["status"], "complete")

    def test_joint_participation_is_exact_scoped_and_paginated(self):
        def add(event, topic, person, time, scope="u1", status="confirmed"):
            self.gov.record_participation(
                event_id=event,
                topic_id=topic,
                person_id=person,
                occurred_at=time,
                user_scope=scope,
                status=status,
            )

        add("e1", "t1", "self", "2026-09-01T10:00:00+00:00")
        add("e1", "t1", "zhang", "2026-09-01T10:00:00+00:00")
        add("e2", "t2", "self", "2026-09-02T10:00:00+00:00")
        add("e2", "t2", "zhang", "2026-09-02T10:00:00+00:00")
        add("self-only", "t3", "self", "2026-09-03T10:00:00+00:00")
        add("private", "t4", "self", "2026-09-04T10:00:00+00:00", scope="u2")
        add("private", "t4", "zhang", "2026-09-04T10:00:00+00:00", scope="u2")
        add("pending", "t5", "self", "2026-09-05T10:00:00+00:00")
        add("pending", "t5", "zhang", "2026-09-05T10:00:00+00:00", status="pending")

        page1 = self.gov.enumerate_joint_participation(
            person_ids=["self", "zhang"], user_scope="u1", limit=1
        )
        self.assertFalse(page1["complete"])
        self.assertEqual([row["event_id"] for row in page1["results"]], ["e1"])
        self.assertEqual(page1["pending_evidence_count"], 1)
        page2 = self.gov.enumerate_joint_participation(
            person_ids=["self", "zhang"],
            user_scope="u1",
            limit=1,
            cursor=page1["next_cursor"],
        )
        self.assertTrue(page2["complete"])
        self.assertEqual([row["event_id"] for row in page2["results"]], ["e2"])
        self.assertEqual(page2["event_watermark"], page1["event_watermark"])

    def test_only_mp_prefixed_tables_are_created(self):
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        self.assertTrue(tables)
        self.assertTrue(all(name.startswith("mp_") for name in tables))


if __name__ == "__main__":
    unittest.main()
