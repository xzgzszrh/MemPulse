"""Desktop transport: the methods the OpenCode client relies on beyond the facade."""
import pytest
from mempulse.desktop import DesktopService


@pytest.fixture
def desktop(tmp_path):
    service = DesktopService(tmp_path)
    service.dispatch("switch_workspace", {"workspace": "personal"})
    yield service
    service.close()


def host_event(session, n, text, **metadata):
    return {
        "event_id": f"opencode:{session}:message:{n}",
        "idempotency_key": f"opencode:{session}:message:{n}",
        "content": text,
        "topic_title": "OpenCode · demo",
        "source_type": "conversation",
        "app": "OpenCode",
        "metadata": {"opencode_session_id": session, "opencode_directory": "/tmp/demo", **metadata},
    }


def bind(desktop, topic_id, session_id):
    proposal = desktop.dispatch('propose_operation', {'kind': 'bind_topic', 'payload': {'topic_id': topic_id, 'session_id': session_id, 'project_ref': '/tmp/demo'}})
    desktop.dispatch('confirm_operation', {'operation_id': proposal['id'], 'fingerprint': proposal['fingerprint']})


def test_session_topic_binding_survives_without_client_state(desktop):
    first = desktop.dispatch("ingest", host_event("ses_1", 1, "整理甲客户交付报告", force_new=True))
    desktop.dispatch("ingest", {**host_event("ses_1", 2, "客户确认改用 V3 模板"), "topic_id": first["topic_id"]})
    assert desktop.dispatch("session_topic", {"session_id": "ses_1"})['topic_id'] is None
    bind(desktop, first['topic_id'], 'ses_1')
    bound = desktop.dispatch("session_topic", {"session_id": "ses_1"})
    assert bound["topic_id"] == first["topic_id"]
    assert bound["event_count"] == 2
    assert desktop.dispatch("session_topic", {"session_id": "ses_missing"})["topic_id"] is None


def test_explicit_rename_preserves_a_confirmed_binding(desktop):
    created = desktop.dispatch("ingest", host_event("ses_2", 1, "排查办公网络断连", force_new=True))
    bind(desktop, created["topic_id"], "ses_2")
    renamed = desktop.dispatch("rename_topic", {"topic_id": created["topic_id"], "title": "办公网络断连排查"})
    assert renamed["changed"] is True
    assert desktop.dispatch("session_topic", {"session_id": "ses_2"})["title"] == "办公网络断连排查"
    assert desktop.dispatch("rename_topic", {"topic_id": created["topic_id"], "title": "办公网络断连排查"})["changed"] is False
    with pytest.raises(ValueError):
        desktop.dispatch("rename_topic", {"topic_id": created["topic_id"], "title": "  "})


def test_agent_context_returns_contract_hits_and_preferences(desktop):
    own = desktop.dispatch("ingest", host_event("ses_3", 1, "继续整理甲客户交付报告", force_new=True))
    other = desktop.dispatch("ingest", host_event("ses_4", 1, "甲客户交付报告改用 V3 模板，保留旧版本", force_new=True))
    desktop.dispatch("preference", {"key": "output_language", "value": "中文", "choice_type": "explicit"})
    desktop.dispatch("preference", {"key": "dns", "value": "备用 DNS", "choice_type": "fallback", "scope_type": "topic", "scope_id": own["topic_id"]})

    bind(desktop, own["topic_id"], "ses_3")
    context = desktop.dispatch("agent_context", {"query": "甲客户交付报告", "session_id": "ses_3"})
    assert context["session_topic"]["topic_id"] == own["topic_id"]
    assert context["contract"]["topic_id"] == own["topic_id"]
    # The session's own events are in the contract, not repeated as cross-topic hits.
    assert {hit["topic_id"] for hit in context["hits"]} == {other["topic_id"]}
    assert context["hits"][0]["topic_title"] == "OpenCode · demo"
    assert context["route"]["route"] in {"RESUME", "AMBIGUOUS", "NEW"}
    assert all(candidate.get("title") for candidate in context["route"]["candidates"])
    # Fallback choices are evidence only and never reach the prompt.
    assert [pref["key"] for pref in context["preferences"]] == ["output_language"]
    assert context["stats"]["topics"] == 2

    cold = desktop.dispatch("agent_context", {"query": "", "session_id": "ses_none"})
    assert cold["route"] is None and cold["session_topic"] is None and cold["hits"] == []


def test_context_keeps_topic_preferences_scoped_and_restores_checkpoint(desktop):
    first = desktop.dispatch('ingest', host_event('scoped_a', 1, '整理甲客户说明', force_new=True))['topic_id']
    second = desktop.dispatch('ingest', host_event('scoped_b', 1, '整理乙客户说明', force_new=True))['topic_id']
    desktop.dispatch('preference', {'key': 'format', 'value': '中文', 'choice_type': 'explicit'})
    desktop.dispatch('preference', {'key': 'format', 'value': '英文', 'choice_type': 'temporary', 'scope_type': 'topic', 'scope_id': second})
    desktop.dispatch('checkpoint', {'topic_id': first})
    current = desktop.dispatch('agent_context', {'query': '', 'topic_id': first})
    assert current['contract']['checkpoint']
    assert [row['value'] for row in current['preferences'] if row['key'] == 'format'] == ['中文']
    other = desktop.dispatch('agent_context', {'query': '', 'topic_id': second})
    assert [row['value'] for row in other['preferences'] if row['key'] == 'format'] == ['英文']
    for _ in range(3):
        desktop.dispatch('checkpoint', {'topic_id': first})
    checkpoint = desktop.service.restore(topic_id=first)['checkpoint']['checkpoint']['payload']
    assert 'checkpoint' not in checkpoint
