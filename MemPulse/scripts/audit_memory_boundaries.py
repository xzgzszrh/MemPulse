"""Small adversarial boundary probes; records failures without changing production.

These hand-authored probes diagnose behavior, not an accuracy estimate. All data
are synthetic and stored in a fresh output directory. No model/API calls needed.
"""
import argparse
import hashlib
import json
from pathlib import Path

from mempulse.desktop import DesktopService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new directory')
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    source_files = [*sorted((root/'src/mempulse').rglob('*.py')), Path(__file__).resolve()]
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    directory = args.output/'data'
    directory.mkdir()
    (directory/'desktop-settings.json').write_text('{"workspace":"personal"}')
    desktop = DesktopService(directory)
    rows = []

    def record(name, expectation, passed, actual):
        rows.append({'name': name, 'expectation': expectation, 'passed': bool(passed), 'actual': actual})

    def propose(operation_kind, **payload):
        return desktop.dispatch('propose_operation', {'kind': operation_kind, 'payload': payload})

    def approve(operation):
        return desktop.dispatch('confirm_operation', {'operation_id': operation['id'], 'fingerprint': operation['fingerprint']})

    def capture(event_id, session, content, **metadata):
        return desktop.dispatch('capture_event', {'event_id': event_id, 'session_id': session, 'content': content,
                                'metadata': {'opencode_directory': '/probe/library', **metadata}})

    try:
        capture('before-confirm', 'first-session', '先修北岸借还机离线补传，晚点讨论界面。')
        record('capture_requires_identity_confirmation', '未确认的话题不因新会话或首条消息而建立',
               not desktop.service.list_topics()['topics'], desktop.service.list_topics())
        op = propose('create_topic', title='北岸借还机离线补传', goal='完成北岸借还机离线补传协议修复和上线审批。',
                     project_ref='/probe/library', session_id='first-session', event_ids=['before-confirm'])
        record('proposal_does_not_write_topic', '提出创建方案时不提前写入话题', not desktop.service.list_topics()['topics'], {'operation_status': op['status']})
        topic = approve(op)['result']['topic_id']
        binding = propose('bind_topic', topic_id=topic, session_id='second-session', project_ref='/probe/library')
        approve(binding)
        capture('progress-1', 'first-session', '协议实现完成，等待灰度验收。', completed_steps=['协议实现'], pending_steps=['灰度验收'])
        capture('progress-2', 'second-session', '灰度验收和正式上线均完成，没有待办了。',
                completed_steps=['协议实现', '灰度验收', '正式上线'], pending_steps=[])
        record('multi_session_one_task', '两个明确绑定的会话继续同一持久任务',
               desktop.session_topic('first-session')['topic_id'] == desktop.session_topic('second-session')['topic_id']
               and len(desktop.service.list_topics()['topics']) == 1,
               {'topics': len(desktop.service.list_topics()['topics']), 'events': desktop.service._topic(topic).event_ids})
        pack = desktop.dispatch('restore', {'topic_id': topic})
        pending = next(f for f in pack['fields'] if f['name'] == 'pending_steps')
        record('completed_task_clears_pending_steps', '最新证据显式 pending_steps=[] 应清除旧待办',
               pending.get('value') in (None, []), pending)
        desktop.close()
        desktop = DesktopService(directory)
        record('binding_survives_restart', '持久绑定在记忆服务重启后保留', desktop.session_topic('second-session')['topic_id'] == topic,
               desktop.session_topic('second-session'))

        remember = propose('remember', topic_id=topic, kind='preference', key='report_format', content='后续周报使用 DOCX。')
        before = desktop.service.resolve_preference(key='report_format', topic_id=topic)
        approve(remember)
        after = desktop.service.resolve_preference(key='report_format', topic_id=topic)
        record('preference_requires_confirmation', '偏好提案确认前不生效，确认后生效',
               not before['found'] and after['value'] == '后续周报使用 DOCX。', {'before': before, 'after': after})

        # Natural-language capture is transport-only; report observations, not
        # a 0% NLP score when the host LLM/tool extraction stage is not exercised.
        capture('raw-preference', 'second-session', '以后导出的表格都用 UTF-8 编码，别再用 GBK。')
        rows.append({'name': 'natural_language_extraction_stage', 'passed': None,
                     'expectation': '自然语言到候选偏好需要单独测试宿主 Agent；仅捕获不能代替抽取评测',
                     'actual': {'preference_rows': len(desktop.governance()['preferences']),
                                'pending_operations': len(desktop.operations.pending()), 'host_agent_exercised': False}})

        note = approve(propose('remember', topic_id=topic, kind='note', content='联系标记 PROBE-CONTACT-827；上线后保留离线对账流程。'))
        note_id = note['result']['event_id']
        delete = propose('forget', target_type='event', target_id=note_id)
        desktop.dispatch('reject_operation', {'operation_id': delete['id']})
        record('rejected_forget_retains_evidence', '取消遗忘保留原记忆', 'PROBE-CONTACT-827' in desktop.service.store.get_event(note_id).content,
               {'event_id': note_id})
        approve(propose('forget', target_type='event', target_id=note_id))
        surfaces = {'restore': desktop.dispatch('restore', {'topic_id': topic}),
                    'search': desktop.dispatch('search', {'query': 'PROBE-CONTACT-827', 'limit': 10}),
                    'context': desktop.dispatch('agent_context', {'query': 'PROBE-CONTACT-827', 'topic_id': topic}),
                    'bootstrap': desktop.dispatch('bootstrap')}
        # Inspect content-bearing fields instead of all JSON: query/plan fields
        # deliberately echo the user's request and aren't stored evidence.
        retained_text = json.dumps({'restore': surfaces['restore'], 'hits': surfaces['context']['hits'],
                                   'results': surfaces['search']['results'], 'bootstrap': surfaces['bootstrap']}, ensure_ascii=False)
        record('confirmed_forget_public_surfaces', '确认遗忘后 restore/search/context/bootstrap 不再返回目标原文',
               'PROBE-CONTACT-827' not in retained_text,
               {'leaked': 'PROBE-CONTACT-827' in retained_text, 'remaining_topics': len(desktop.service.list_topics()['topics'])})

        marker = 'RECOVERY-CODE-7349'
        long_result = '北岸离线补传测试日志。' + '队列记录逐条校验通过；'*40 + '最后的恢复编号为 '+marker+'。'
        desktop.service.ingest({'event_id': 'long-tool', 'topic_id': topic, 'source_type': 'tool', 'content': long_result})
        found = desktop.dispatch('search', {'query': '北岸离线补传最后的恢复编号', 'topic_id': topic, 'limit': 10})
        context = desktop.dispatch('agent_context', {'query': '北岸离线补传最后的恢复编号', 'topic_id': topic})
        context_text = json.dumps({'hits': context['hits'], 'contract': context['contract']}, ensure_ascii=False)
        record('long_tool_tail_survives_context', '检索命中的关键尾部细节应进入上下文，或明确提示需读取完整事件',
               marker in context_text,
               {'source_chars': len(long_result), 'search_contains_marker': marker in json.dumps(found, ensure_ascii=False),
                'context_contains_marker': marker in context_text, 'context': context})

        gov = desktop.service.governance
        gov.record_preference(user_id='probe-safety', key='external_upload', value='禁止外发', choice_type='safety_constraint')
        gov.record_preference(user_id='probe-safety', key='external_upload', value='允许外发', scope_type='topic', scope_id=topic)
        resolved = gov.resolve_preference(user_id='probe-safety', key='external_upload', topic_id=topic)
        record('safety_constraint_not_overridden_by_taste', '未明确撤销的安全约束不应被普通话题偏好静默覆盖',
               resolved.get('value') == '禁止外发', resolved)
        gov.record_knowledge(user_id='probe-timezone', key='release', value='已上线', scope_id=topic,
                             valid_from='2026-09-15T10:00:00+08:00', observed_at='2026-09-15T10:00:00+08:00')
        resolved = gov.resolve_knowledge(user_id='probe-timezone', key='release', scope_id=topic,
                                         valid_at='2026-09-15T03:00:00+00:00', known_at='2026-09-15T03:00:00+00:00')
        record('equivalent_timezone_knowledge', '10:00+08 的事实在 03:00 UTC 查询时已经生效且已知',
               resolved.get('value') == '已上线', resolved)
        gov.record_preference(user_id='probe-timezone', key='format', value='PDF',
                              valid_from='2026-09-15T10:00:00+08:00', observed_at='2026-09-15T10:00:00+08:00')
        resolved = gov.resolve_preference(user_id='probe-timezone', key='format', at='2026-09-15T03:00:00+00:00')
        record('equivalent_timezone_preference', '偏好有效时间按同一时刻比较，不能按时区字符串排序',
               resolved.get('value') == 'PDF', resolved)

        privacy_inputs = [
            ('credential_in_prose', {'content': '测试占位密钥 sk-SYNTHETIC123456789'}, 'sk-SYNTHETIC123456789'),
            ('top_level_secret_metadata', {'content': '凭据来自测试夹具', 'metadata': {'password': 'TEST-ONLY-PW-827'}}, 'TEST-ONLY-PW-827'),
            ('nested_secret_metadata', {'content': '凭据来自测试夹具', 'metadata': {'auth': {'password': 'TEST-ONLY-PW-828'}}}, 'TEST-ONLY-PW-828'),
            ('password_in_prose', {'content': '测试占位密码 password=TEST-ONLY-PW-829'}, 'TEST-ONLY-PW-829'),
        ]
        for name, payload, secret in privacy_inputs:
            event = desktop.service.normalize_event(payload)
            record('ingress_filter:'+name, '明确标记的凭据字段应在事件标准化入口过滤（全为虚构测试串）',
                   secret not in json.dumps(event.to_dict(), ensure_ascii=False),
                   {'input': payload, 'normalized': event.to_dict()})
        tool_result = desktop.service.run_tool('probe-auth', 'diagnose', topic_id=topic,
                                               args_json={'password': 'TEST-ONLY-PW-831'},
                                               result_json={'access_token': 'TEST-ONLY-TOKEN-830'})
        stored = desktop.service.store.get_event(tool_result['event_id']).to_dict()
        record('tool_call_credential_copies', '真实 run_tool 接口应过滤 content、args_ref、result_ref 内的凭据副本',
               'TEST-ONLY-' not in json.dumps(stored), {'event': stored})
        approve(propose('forget', target_type='event', target_id=tool_result['event_id']))
        stored = desktop.service.store.get_event(tool_result['event_id']).to_dict()
        record('forgotten_tool_payload_references', '显式遗忘整个工具事件后，存储中不能在参数/结果副本保留被遗忘原文',
               'TEST-ONLY-' not in json.dumps(stored), {'event': stored,
               'scope': 'logical stored event payload; not physical SQLite/WAL zeroization or backups'})
    finally:
        desktop.close()
    assert hashes == {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    result = {'synthetic': True, 'formal_acceptance': False, 'host_agent_tested': False,
              'scope': 'Adversarial diagnostic probes; no population-level pass-rate claim', 'source_sha256': hashes,
              'probes': rows}
    (args.output/'boundaries.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps([{'name': row['name'], 'passed': row['passed']} for row in rows], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
