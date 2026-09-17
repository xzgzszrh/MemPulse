import pytest

from mempulse.desktop import DesktopService
from mempulse.models import Event, Topic
from mempulse.tags import event_tags, validate_topic_tags


@pytest.fixture
def desktop(tmp_path):
    service = DesktopService(tmp_path)
    service.dispatch('switch_workspace', {'workspace': 'personal'})
    yield service
    service.close()


def propose(desktop, kind='create_topic', **payload):
    if kind == 'create_topic':
        payload = {'title': '借还机离线补传', 'goal': '完成图书馆借还机离线记录补传，包含幂等去重与故障恢复。',
                   'project_ref': '/work/library', 'session_id': 's1', 'keywords': ['离线补传', '幂等去重'], **payload}
    return desktop.dispatch('propose_operation', {'kind': kind, 'payload': payload})


def confirm(desktop, operation):
    return desktop.dispatch('confirm_operation', {'operation_id': operation['id'], 'fingerprint': operation['fingerprint']})


def test_capture_does_not_create_or_infer_a_task_even_with_force_new(desktop):
    result = desktop.dispatch('capture_event', {'event_id': 'raw1', 'content': '你好，今天做什么？', 'session_id': 's1',
        'topic_title': 'New session', 'metadata': {'force_new': True, 'opencode_directory': '/work/library'}})
    assert result['topic_id'] is None
    assert desktop.service.list_topics()['topics'] == []
    assert desktop.dispatch('capture_inbox', {'session_id': 's1'})['events'][0]['metadata']['keywords'] == []


def test_proposal_is_readable_but_only_confirmation_creates_once(desktop):
    operation = propose(desktop)
    assert desktop.service.list_topics()['topics'] == []
    assert operation['preview']['fields']
    with pytest.raises(ValueError):
        desktop.dispatch('confirm_operation', {'operation_id': operation['id'], 'fingerprint': 'fake'})
    applied = confirm(desktop, operation)
    assert applied['status'] == 'applied'
    assert confirm(desktop, operation)['result'] == applied['result']
    assert len(desktop.service.list_topics()['topics']) == 1


def test_rejection_cannot_be_replayed_as_confirmation(desktop):
    operation = propose(desktop)
    desktop.dispatch('reject_operation', {'operation_id': operation['id']})
    with pytest.raises(ValueError):
        confirm(desktop, operation)
    assert not desktop.service.list_topics()['topics']


def test_multiple_sessions_can_share_one_confirmed_task(desktop):
    first = confirm(desktop, propose(desktop))['result']['topic_id']
    second = propose(desktop, 'bind_topic', topic_id=first, session_id='s2', project_ref='/work/library')
    assert desktop.session_topic('s2')['topic_id'] is None
    confirm(desktop, second)
    for session in ('s1', 's2'):
        desktop.dispatch('capture_event', {'event_id': session, 'content': '补传接口已完成幂等检查。', 'session_id': session,
            'metadata': {'opencode_directory': '/work/library'}})
        assert desktop.session_topic(session)['topic_id'] == first
    topic = desktop.service._topic(first)
    assert topic.title == '借还机离线补传'
    assert len(topic.event_ids) == 3


def test_same_project_can_hold_distinct_tasks_and_directory_is_not_fallback(desktop):
    first = confirm(desktop, propose(desktop))['result']['topic_id']
    second = confirm(desktop, propose(desktop, title='借还机无障碍验收', goal='完成轮椅使用者触屏操作的无障碍验收与签字，不包含离线补传。', session_id='s2'))['result']['topic_id']
    assert first != second
    assert desktop.session_topic('s3', '/work/library')['topic_id'] is None
    assert desktop.session_topic('s1', '/work/another')['topic_id'] is None


def test_binding_survives_restart_without_legacy_metadata_inference(tmp_path):
    service = DesktopService(tmp_path)
    service.dispatch('switch_workspace', {'workspace': 'personal'})
    topic_id = confirm(service, propose(service))['result']['topic_id']
    service.close()
    service = DesktopService(tmp_path)
    assert service.session_topic('s1')['topic_id'] == topic_id
    service.close()


def test_destructive_preview_is_stale_when_topic_changed(desktop):
    topic_id = confirm(desktop, propose(desktop))['result']['topic_id']
    operation = propose(desktop, 'forget', target_type='topic', target_id=topic_id)
    desktop.service.ingest({'content': '用户补充了验收范围。', 'topic_id': topic_id})
    with pytest.raises(ValueError, match='changed'):
        confirm(desktop, operation)
    assert desktop.service._topic(topic_id)


def test_keyword_generation_is_open_vocabulary_but_evidence_gated():
    event = Event('e1', 'u', '本阶段只处理电梯群控峰值削峰，周报文件另行整理。',
        metadata={'keyword_candidates': [
            {'value': '电梯群控峰值削峰', 'quote': '本阶段只处理电梯群控峰值削峰', 'confidence': .94},
            {'value': '无人机巡检', 'quote': '凭空补充', 'confidence': .99},
        ], 'keywords': ['你好', '为什么不能打开这个文件？', 'report.docx', '2026-09-15']})
    accepted, pending, _ = validate_topic_tags(Topic('t', 'u', '削峰'), event_tags(event))
    assert [tag.value for tag in accepted if tag.kind.value == 'keyword' and tag.status == 'accepted'] == ['电梯群控峰值削峰']
    assert any(tag.value == '无人机巡检' for tag in pending)
    assert all(tag.source_event_ids == ('e1',) for tag in accepted + pending)


def test_keyword_quantity_is_bounded_without_deleting_source_evidence():
    event = Event('e2', 'u', '用户确认的任务定位信息', metadata={'keywords_confirmed': True,
        'keywords': [f'业务锚点{i}' for i in range(20)]})
    accepted, _, _ = validate_topic_tags(Topic('t', 'u', '范围'), event_tags(event))
    assert len([tag for tag in accepted if tag.kind.value == 'keyword' and tag.status == 'accepted']) == 8
    assert len([tag for tag in accepted if tag.kind.value == 'keyword']) == 20


def test_only_selected_inbox_evidence_is_admitted(desktop):
    for event_id in ('keep','leave'):
        desktop.dispatch('capture_event', {'event_id':event_id,'content':'待确认的任务来源 '+event_id,
            'session_id':'s1','metadata':{'opencode_directory':'/work/library'}})
    topic_id=confirm(desktop,propose(desktop,event_ids=['keep']))['result']['topic_id']
    assert 'keep' in desktop.service._topic(topic_id).event_ids
    assert desktop.service.store.get_event('leave') is None
    assert [row['event_id'] for row in desktop.dispatch('capture_inbox',{'session_id':'s1'})['events']]==['leave']


def test_applied_receipt_does_not_duplicate_plaintext_memory(desktop):
    import json
    topic_id=confirm(desktop,propose(desktop))['result']['topic_id']
    operation=desktop.dispatch('propose_operation',{'kind':'remember','payload':{'topic_id':topic_id,'kind':'note','content':'仅在正式事件中保存的内容 ZXQ-823'}})
    receipt=confirm(desktop,operation)
    assert 'ZXQ-823' not in json.dumps(receipt)
    stored=desktop.service.store.conn.execute('SELECT payload,preview,result FROM mp_memory_operations WHERE id=?',(operation['id'],)).fetchone()
    assert 'ZXQ-823' not in ''.join(str(value) for value in stored)
    desktop.service.forget('event',receipt['result']['event_id'])
    assert desktop.service._topic(topic_id).title=='借还机离线补传'
    assert desktop.service._topic(topic_id).metadata['identity_confirmed']


def test_compound_remember_rolls_back_evidence_when_preference_fails(desktop,monkeypatch):
    topic_id=confirm(desktop,propose(desktop))['result']['topic_id']
    before=desktop.service._topic(topic_id).to_dict()
    operation=desktop.dispatch('propose_operation',{'kind':'remember','payload':{'topic_id':topic_id,'kind':'preference','key':'format','content':'中文'}})
    def fail(**kwargs): raise RuntimeError('simulated preference write failure')
    monkeypatch.setattr(desktop.service.governance,'record_preference',fail)
    with pytest.raises(RuntimeError): confirm(desktop,operation)
    assert desktop.service._topic(topic_id).to_dict()==before
    assert desktop.service.store.get_event(operation['id']+':evidence') is None


def test_field_forgetting_scrubs_confirmed_identity_derivatives(desktop):
    import json
    topic_id=confirm(desktop,propose(desktop,goal='通过分机 ZXQ-823 联系负责人，先复核再发布。'))['result']['topic_id']
    event=desktop.service.ingest({'topic_id':topic_id,'content':'通过分机 ZXQ-823 联系负责人，先复核再发布。','metadata':{'private_phone':'ZXQ-823'}})
    result=desktop.service.forget_field(event['event_id'],'metadata.private_phone')
    assert result['status']=='complete'
    topic=desktop.service.store.get_topic(topic_id)
    assert 'ZXQ-823' not in json.dumps(topic.to_dict())
    assert '先复核再发布' in topic.goal
