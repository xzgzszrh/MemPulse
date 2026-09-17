"""Synthetic desktop examples, written through the production facade into a separate DB."""
from datetime import datetime, timedelta, timezone


LEGACY_SCENARIOS = [
    ('麒麟桌面环境适配', 'kylin', '适配验证清单.md', '林夏', ['确认银河麒麟 V10 适配范围，建立桌面验证清单。', '整理中文路径、窗口缩放与离线启动用例。', '完成本机存储检查，麒麟 embedding SDK 仍待目标机验证。', '记录异常日志，下一步开展目标机回归。']),
    ('甲客户 · 交付报告', 'acme', '甲客户交付说明.docx', '周宁', ['确认甲客户交付范围与验收口径。', '导入 V2 报告模板，整理需求清单。', '客户确认改用 V3 模板，保留旧版本溯源。', '生成交付初稿，等待项目负责人复核。', '保存当前工作进度，待完成验收签字。']),
    ('周报与输出偏好', 'weekly', '第37周工作周报.md', 'self', ['用户明确要求：周报使用中文，先给结论，再列行动项。', '本次会议临时要求英文摘要，不改变长期输出偏好。', '使用 Markdown 生成工作周报，保留来源记录。']),
    ('桌面网络故障排查', 'network', '网络诊断记录.txt', '陈川', ['记录办公网络间歇性断连，收集网关与 DNS 诊断结果。', '工具调用失败后临时使用备用 DNS，此选择属于被迫替代。', '恢复默认网络配置，将排查流程整理为可复用知识。']),
    ('乙客户 · 接口联调', 'beta', '乙客户接口清单.xlsx', '周宁', ['乙客户接口联调启动，与甲客户交付分别维护。', '完成字段映射，明确 API 回包和异常处理方式。', '记录联调结果，等待下一轮验收。']),
    ('会议资料与隐私整理', 'privacy', '会议材料索引.md', '林夏', ['导入会议材料，识别需要保留的工作流程。', '将联系方式与流程信息分别存储，便于定向遗忘。'])
]


def seed_desktop(service):
    conn = service.store.conn
    conn.execute('CREATE TABLE IF NOT EXISTS desktop_seed (version INTEGER PRIMARY KEY)')
    if conn.execute('SELECT 1 FROM desktop_seed WHERE version=1').fetchone():
        return
    scenarios = LEGACY_SCENARIOS
    topic_ids = []
    base = datetime.now(timezone.utc) - timedelta(days=5)
    for idx, (title, key, resource, person, contents) in enumerate(scenarios):
        tid = None
        event_ids = []
        for n, content in enumerate(contents):
            eid = f'desktop-demo:{key}:{n}'
            event = {'event_id': eid, 'idempotency_key': eid, 'content': content, 'topic_title': title,
                     'person_refs': [person+'@participant', 'self@initiator'], 'resource_ids': [resource],
                     'source_type': ['conversation', 'tool', 'configuration'][n % 3],
                     'occurred_at': (base + timedelta(days=idx, hours=n)).isoformat(),
                     'metadata': {'synthetic': True, 'keywords': [key, title], 'force_new': n == 0,
                                  'input_files': [resource], 'completed_steps': contents[:n+1],
                                  'pending_steps': ['等待审核确认'], 'template_version': 'V3',
                                  'output_preference': '中文 · 结论优先'}}
            if tid:
                event['topic_hint'] = tid
            out = service.ingest(event)
            tid = out['topic_id']
            event_ids.append(eid)
        topic_ids.append(tid)
        service.checkpoint(tid)
        if key == 'weekly':
            service.update_preference({'key': 'output_preference', 'value': '中文输出，先给结论，再列行动项', 'choice_type': 'explicit', 'evidence_event_id': event_ids[0]})
            service.update_preference({'key': 'output_preference', 'value': '本次会议使用英文摘要', 'choice_type': 'temporary', 'scope_type': 'topic', 'scope_id': tid, 'evidence_event_id': event_ids[1]})
        if key == 'network':
            service.update_preference({'key': 'dns_provider', 'value': '临时备用 DNS', 'choice_type': 'fallback', 'scope_type': 'topic', 'scope_id': tid, 'evidence_event_id': event_ids[1]})
            service.knowledge({'key': '网络排障流程', 'value': '检查链路 → 核验网关 → 检查 DNS → 恢复默认配置 → 留存日志', 'scope_id': tid, 'evidence_event_id': event_ids[2]})
        if key == 'acme':
            old = service.knowledge({'key': 'template_version', 'value': 'V2', 'scope_id': tid, 'evidence_event_id': event_ids[1], 'valid_from': (base-timedelta(days=10)).isoformat()})
            service.knowledge({'key': 'template_version', 'value': 'V3', 'scope_id': tid, 'supersedes': old['id'], 'evidence_event_id': event_ids[2]})
        if key == 'kylin':
            service.knowledge({'key': 'SDK 适配结论', 'value': '目标机验证尚未完成，不能声明 SDK 已适配', 'scope_id': tid, 'evidence_event_id': event_ids[2], 'disputed': True, 'dispute_reason': '缺少目标机器上的正式测试证据'})
    service.update_preference({'key': '安全策略', 'value': '凭据不进入记忆正文；敏感字段按需遗忘', 'choice_type': 'safety_constraint'})
    conn.execute('INSERT INTO desktop_seed(version) VALUES(1)')
    conn.commit()
