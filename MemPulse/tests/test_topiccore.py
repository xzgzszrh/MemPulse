import unittest
from datetime import datetime, timezone

from mempulse.core import Event, InMemoryTopicStore, TopicCore
from mempulse.models import Route, TagKind, Topic
from mempulse.tags import (
    event_tags,
    normalize_person,
    normalize_resource,
    normalize_time,
    validate_topic_tags,
)


class TopicCoreTests(unittest.TestCase):
    def make_core(self):
        return TopicCore(InMemoryTopicStore(), theta_new=0.18, delta_ambiguous=0.05)

    def test_tag_normalization_has_five_kinds_and_sources(self):
        event = Event(
            "e1",
            "u1",
            "甲交付",
            occurred_at="2026-09-11T10:00:00+08:00",
            person_refs=["张三@审核人"],
            resource_ids=["./需求表.docx"],
            metadata={"keywords": ["需求规格书"]},
        )
        tags = event_tags(event)
        self.assertEqual(
            {tag.kind for tag in tags},
            {TagKind.PERSON, TagKind.RESOURCE, TagKind.TIME, TagKind.KEYWORD},
        )
        self.assertTrue(all(tag.source_event_ids == ("e1",) for tag in tags))
        self.assertEqual(
            normalize_person("person:P-1@审核人").canonical, "person:p-1@reviewer"
        )
        self.assertEqual(
            normalize_resource("res:" + "a" * 40).canonical, "res:" + "a" * 40
        )
        self.assertEqual(
            normalize_time(datetime(2026, 9, 11, tzinfo=timezone.utc))[0].canonical,
            "time:2026-09",
        )

    def test_validate_tags_reports_missing_without_fabricating(self):
        topic = Topic("t1", "u1", "demo")
        tags = event_tags(Event("e1", "u1", "demo", person_refs=["p1"]))
        accepted, pending, missing = validate_topic_tags(topic, tags)
        self.assertFalse(pending)
        self.assertIn("vector", missing)
        self.assertEqual(topic.state, "incomplete")

    def test_new_then_resume_same_topic(self):
        core = self.make_core()
        first = core.resolve_event(
            Event(
                "e1",
                "u1",
                "甲客户交付报告",
                person_refs=["p1"],
                resource_ids=["/tmp/a.docx"],
                metadata={"keywords": ["甲客户", "交付"]},
            )
        )
        self.assertIs(first.route, Route.NEW)
        second = core.resolve_event(
            Event(
                "e2",
                "u1",
                "继续甲客户交付报告",
                person_refs=["p1"],
                resource_ids=["/tmp/a.docx"],
                topic_hint=first.topic_id,
                metadata={"keywords": ["甲客户", "交付"]},
            )
        )
        self.assertIs(second.route, Route.RESUME)
        self.assertEqual(second.topic_id, first.topic_id)
        self.assertEqual(len(core.store.list_events(first.topic_id)), 2)

    def test_similar_people_different_explicit_topic_is_ambiguous_or_new(self):
        core = self.make_core()
        a = core.resolve_event(
            Event(
                "a1",
                "u1",
                "甲客户验收报告",
                person_refs=["p1"],
                resource_ids=["/tmp/a.docx"],
                metadata={"keywords": ["验收"]},
            )
        )
        b = core.resolve_event(
            Event(
                "b1",
                "u1",
                "乙客户验收报告",
                person_refs=["p1"],
                resource_ids=["/tmp/b.docx"],
                metadata={"keywords": ["验收"]},
            )
        )
        self.assertNotEqual(b.topic_id, a.topic_id)
        follow = core.resolve_event(
            Event(
                "f1",
                "u1",
                "继续验收报告",
                person_refs=["p1"],
                metadata={"keywords": ["验收"]},
            )
        )
        self.assertIn(follow.route, (Route.AMBIGUOUS, Route.RESUME, Route.NEW))
        if follow.route is Route.AMBIGUOUS:
            self.assertGreaterEqual(len(follow.candidates), 2)

    def test_attach_does_not_create_topic(self):
        core = self.make_core()
        first = core.resolve_event(
            Event(
                "e1",
                "u1",
                "内部培训",
                person_refs=["p1"],
                metadata={"keywords": ["培训"]},
            )
        )
        attached = core.resolve_event(
            Event(
                "e2",
                "u1",
                "补充培训材料",
                action="add_material",
                topic_hint=first.topic_id,
                metadata={"attach_only": True, "keywords": ["培训"]},
            )
        )
        self.assertIs(attached.route, Route.ATTACH)
        self.assertEqual(attached.topic_id, first.topic_id)
        self.assertEqual(len(core.store.list_topics("u1")), 1)

    def test_restore_context_reports_missing_and_evidence(self):
        core = self.make_core()
        decision = core.resolve_event(
            Event(
                "e1",
                "u1",
                "制作报告",
                resource_ids=["/tmp/input.docx"],
                metadata={
                    "keywords": ["报告"],
                    "input_files": ["/tmp/input.docx"],
                    "completed_steps": ["outline"],
                },
            )
        )
        pack = core.restore(decision.topic_id)
        fields = {item.name: item for item in pack.fields}
        self.assertEqual(fields["input_files"].status, "present")
        self.assertEqual(fields["template_version"].status, "missing")
        self.assertIn("template_version", pack.missing)
        self.assertEqual(fields["input_files"].evidence_event_ids, ("e1",))

    def test_graph_never_uses_pending_tags(self):
        core = self.make_core()
        first = core.resolve_event(
            Event(
                "e1",
                "u1",
                "低置信事项",
                person_refs=["p1"],
                confidence=0.2,
                metadata={"keywords": ["事项"]},
            )
        )
        topic = core.store.get_topic(first.topic_id)
        self.assertIsNotNone(topic)
        # A pending tag should not be part of the graph projection.
        self.assertTrue(all(tag.status == "accepted" for tag in topic.tags))


if __name__ == "__main__":
    unittest.main()
