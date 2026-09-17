from mempulse.service import TopicFacade
from mempulse.models import Topic


def test_vector_projection_is_persisted_and_scoped(tmp_path):
    f = TopicFacade(tmp_path / "v.db")
    topic = Topic(
        "semantic",
        "default",
        "目标",
        goal="原始描述",
        vector=(1.0, 0.0),
        metadata={"model_revision": "test"},
    )
    f.store.save_topic(topic)
    f.store.close()
    other = TopicFacade(tmp_path / "v.db")
    assert (
        other.store.vector_candidates((1.0, 0.0), "test", "default")[0][0].topic_id
        == "semantic"
    )
    assert other.store.vector_candidates((1.0, 0.0), "other", "default") == []
    assert other.store.vector_candidates((1.0, 0.0), "test", "other") == []
    topic.vector = None
    other.store.save_topic(topic)
    assert other.store.vector_candidates((1.0, 0.0), "test", "default") == []
    other.store.close()


def test_vector_recall_adds_candidate_outside_recent_topics(tmp_path):
    f = TopicFacade(tmp_path / "v.db", embed=lambda text: (1.0, 0.0), model_rev="test")
    target = Topic(
        "target",
        "default",
        "独特描述",
        goal="很早以前的目标",
        vector=(1.0, 0.0),
        metadata={"model_revision": "test"},
        updated_at="2020-01-01T00:00:00+00:00",
    )
    f.store.save_topic(target)
    for i in range(40):
        f.store.save_topic(Topic("t" + str(i), "default", "其它事情" + str(i)))
    candidates = f.core._candidate_topics(
        f.normalize_event({"content": "完全改写的请求"})
    )
    assert any(t.topic_id == "target" for t in candidates)
    f.store.close()


def test_aliases_are_scoped_and_ambiguous_aliases_fail(tmp_path):
    import pytest

    f = TopicFacade(tmp_path / "a.db")
    with f.store.transaction():
        f.store.add_alias(
            "resource", "file1", "old.docx", "res:stable", "e1", "default"
        )
    assert f.store.resolve_alias("resource", "old.docx") == "res:stable"
    assert f.store.resolve_alias("resource", "old.docx", "other") == "old.docx"
    with f.store.transaction():
        f.store.add_alias("resource", "file2", "old.docx", "res:other", "e2", "default")
    with pytest.raises(ValueError):
        f.store.resolve_alias("resource", "old.docx")
    f.store.close()
