"""Versioned synthetic office memories and traceable engineering-evaluation queries."""
from datetime import datetime, timedelta, timezone

CUSTOMERS = [('澄海园区', 'chenghai'), ('北麓实验室', 'beilu'), ('栖川工厂', 'qichuan')]
TASKS = [
    ('delivery', '交付验收报告', '验收报告.docx', '周宁',
     ['确认设备交付范围和验收签字要求', '导入第二版报告模板并整理验收清单', '客户批准第三版模板，第二版作为历史版本保留', '交付初稿已完成，等待负责人审核并签字'],
     ['验收文档现在要使用哪个版本？', '那份需要负责人签字的交付材料进展如何？', '继续整理设备交付后的验收说明']),
    ('api', '接口鉴权联调', '接口清单.xlsx', '林夏',
     ['确认库存接口的字段映射和访问令牌范围', '复现签名失效导致的四零一错误', '统一请求时间戳和签名算法，测试恢复通过', '联调结果已记录，等待对方确认异常回包格式'],
     ['接口为什么返回鉴权失败？', '上次令牌校验不通过后来怎么解决的？', '继续对接库存系统的请求签名']),
    ('network', '办公网络间歇断连', '网络诊断记录.txt', '陈川',
     ['工作站每隔十分钟掉线，需要收集链路和域名解析日志', '工具失败后临时更换备用域名服务器，只是应急替代', '定位交换机端口协商异常，调整链路后恢复默认配置', '网络已稳定，后续需要观察整晚并保存监控记录'],
     ['办公网总是隔一阵断开该怎么处理？', '临时换的域名服务器算长期偏好吗？', '继续昨天的掉线问题观察']),
    ('backup', '文件备份恢复演练', '恢复演练清单.md', '周宁',
     ['为项目资料创建离线快照并记录校验值', '在隔离目录执行文件恢复，不覆盖现有材料', '恢复后的哈希与原始清单一致，抽样文件可正常打开', '演练验证完成，等待归档恢复记录'],
     ['如何确认还原的资料没有损坏？', '之前做的数据还原校验结果是什么？', '继续完成离线快照演练的收尾']),
    ('printing', '共享打印机驱动适配', '打印测试记录.md', '陈川',
     ['共享打印队列堆积，中文文档无法输出', '记录旧驱动版本并保存可回退配置', '替换签名驱动后队列恢复，完成双面和中文字体测试', '待补充大页数文件与断电重连的回归测试'],
     ['中文材料打印不出来的处理进展？', '换了驱动后还有哪些打印用例没测？', '继续验证共享输出设备的兼容性']),
    ('training', '新员工操作培训', '培训讲义.pptx', '林夏',
     ['安排新员工熟悉桌面操作和资料归档规则', '完成讲义初稿，明确文件分类与命名约定', '演示中文路径检索和误删除恢复，收集学员反馈', '培训答疑已整理，等待发布修订讲义'],
     ['新同事上手课程的资料在哪里？', '入职操作讲解后有哪些待处理事项？', '继续修订桌面使用培训讲义']),
    ('expense', '差旅费用报销', '费用明细.xlsx', '许岚',
     ['收集出差交通和住宿发票，核对费用日期', '发现一张发票抬头错误，已联系开票方更正', '更正票据已到齐，费用明细与审批单一致', '报销材料待财务复核，原始票据单独归档'],
     ['出差的票据补齐了吗？', '费用申请卡在什么环节？', '继续提交交通住宿的报销资料']),
    ('procurement', '工作站采购比选', '采购比选表.xlsx', '许岚',
     ['整理三家供应商的工作站配置与交货周期', '核验内存容量、接口数量和售后服务期限', '确定备选机型，采购价格仍待负责人审批', '保存比选证据，等待预算确认后下单'],
     ['办公电脑的机型确定了没有？', '硬件采购现在还需要谁确认？', '继续完成工作站供应商对比']),
    ('security', '审计日志脱敏归档', '日志字段策略.md', '林夏',
     ['核对审计日志字段，只保留排障所需最小信息', '将联系信息与操作步骤拆成独立字段', '完成示例日志脱敏，验证敏感字段可单独遗忘', '归档策略待安全负责人审核，未授权对外共享'],
     ['排障记录里的联系信息怎样处理？', '删掉敏感字段后操作流程还保留吗？', '继续完善审计记录的脱敏规则']),
    ('water', '夜间用水分时核算', '用水分时台账.xlsx', '陈川',
     ['按生产和保洁用途分别采集夜间水表读数', '核实夜班清洁发生在二十二点至次日六点', '清洁用水计入夜间保洁时段，不混入日间生产消耗', '分时核算表已更新，待值班主管确认'],
     ['夜班打扫用掉的水应该算到哪里？', '晚上的保洁消耗能并到白天生产吗？', '继续核对凌晨的水表分摊']),
    ('schedule', '设备停机检修排期', '检修排期表.xlsx', '周宁',
     ['与生产负责人确认设备停机检修窗口', '将检修安排在周末夜间，提前准备备用设备', '备件已到货，检修人员和安全检查名单确认完毕', '等待生产负责人签发停机许可后执行'],
     ['机器维护安排在什么时候？', '停机前的人和备件都准备好了吗？', '继续确认设备检修的执行条件']),
    ('translation', '双语使用手册修订', '使用手册.docx', '许岚',
     ['为设备使用手册准备中文正文和英文摘要', '统一术语表，产品名称及型号保持原样', '完成章节校对，修复图表编号与交叉引用', '双语版本等待技术负责人审阅后发布'],
     ['英文概述要不要翻译产品型号？', '说明书两种语言的校对进展如何？', '继续整理双语手册发布前的问题']),
]


def scenarios():
    rows = []
    for customer_index, (customer, customer_key) in enumerate(CUSTOMERS):
        for task_index, (key, title, resource, person, contents, queries) in enumerate(TASKS):
            ident = f'{customer_key}:{key}'
            rows.append({
                'id': ident, 'customer': customer, 'key': key, 'title': f'{customer} · {title}',
                'resource': f'/demo/{customer_key}/{key}/{resource}', 'person': person,
                'contents': [f'{customer}：{content}。' for content in contents],
                'queries': [f'{customer}，{query}' for query in queries],
                'day': customer_index * 3 + task_index % 3,
            })
    return rows


def seed_rich_demo(service, *, prefix='desktop-rich-v2'):
    created = 0
    duplicates = 0
    topic_ids = {}
    base = datetime(2026, 9, 1, 9, tzinfo=timezone.utc)
    for row in scenarios():
        topic_id = None
        event_ids = []
        for turn, content in enumerate(row['contents']):
            event_id = f'{prefix}:{row["id"]}:{turn}'
            event = {
                'event_id': event_id, 'idempotency_key': event_id,
                'content': content + (' 本话题使用中文输出，先给结论。' if turn == 0 else ''), 'topic_title': row['title'],
                'person_refs': [row['person'] + '@participant', 'self@initiator'],
                'resource_ids': [row['resource']], 'source_type': ['conversation', 'tool', 'configuration', 'conversation'][turn],
                'occurred_at': (base + timedelta(days=row['day'], hours=turn)).isoformat(),
                'metadata': {
                    'synthetic': True, 'dataset_version': 'office-memory-v2', 'customer': row['customer'],
                    'force_new': turn == 0, 'keywords': [row['customer'], row['key']],
                    'input_files': [row['resource']], 'completed_steps': row['contents'][:turn+1],
                    'pending_steps': [row['contents'][-1]],
                    'output_preference': '中文，结论优先',
                },
            }
            if topic_id:
                event['topic_id'] = topic_id
            result = service.ingest(event)
            topic_id = result['topic_id']
            event_ids.append(event_id)
            duplicates += int(result.get('duplicate', False))
            created += int(not result.get('duplicate', False))
        topic_ids[row['id']] = topic_id
        # Avoid duplicate governance records when enriching the same workspace again.
        marker = f'{prefix}:governance:{row["id"]}'
        service.store.conn.execute('CREATE TABLE IF NOT EXISTS demo_enrichment (id TEXT PRIMARY KEY)')
        if service.store.conn.execute('SELECT 1 FROM demo_enrichment WHERE id=?', (marker,)).fetchone():
            continue
        service.checkpoint(topic_id)
        service.update_preference({'key': 'output_preference', 'value': '中文，结论优先', 'choice_type': 'explicit', 'scope_type': 'topic', 'scope_id': topic_id, 'evidence_event_id': event_ids[0]})
        if row['key'] == 'network':
            service.update_preference({'key': 'dns_provider', 'value': '应急备用解析服务', 'choice_type': 'fallback', 'scope_type': 'topic', 'scope_id': topic_id, 'evidence_event_id': event_ids[1]})
        if row['key'] == 'delivery':
            old = service.knowledge({'key': 'template_version', 'value': 'V2', 'scope_id': topic_id, 'valid_from': '2026-08-20T00:00:00+00:00', 'evidence_event_id': event_ids[1]})
            service.knowledge({'key': 'template_version', 'value': 'V3', 'scope_id': topic_id, 'valid_from': '2026-09-01T00:00:00+00:00', 'supersedes': old['id'], 'evidence_event_id': event_ids[2]})
        else:
            service.knowledge({'key': '处理结论', 'value': row['contents'][2], 'scope_id': topic_id, 'evidence_event_id': event_ids[2]})
        service.store.conn.execute('INSERT INTO demo_enrichment VALUES(?)', (marker,))
        service.store.conn.commit()
    return {'dataset': 'office-memory-v2', 'synthetic': True, 'topics': len(topic_ids), 'events_created': created, 'events_already_present': duplicates, 'topic_ids': topic_ids}
