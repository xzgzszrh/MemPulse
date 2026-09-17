"""Evaluation-only questions. Never imported by the memory service or its seed.

Authored from the fictional source histories before this evaluation; NOT blind,
human-labelled or a competition-provided test set. Indices and answer atoms are
specified here, not inferred from retrieval results.
"""

NEW_QUESTIONS = [
    ('library_sync', 'detail', '北岸断网后重新开机会把 sequence 清零，最终靠哪些字段保证不会重复入账？', [2], ['device_id', 'boot_id', 'sequence']),
    ('library_sync', 'cross_session', '北岸那次 1200 条补账，从发现乱序到修好，耗时变化是多少？', [4, 6], ['41 秒', '58 秒', '并发数从 4 降为 1']),
    ('library_sync', 'person', '北岸全馆补传放行后的正式发布由信息中心王磊在几点执行？', [9], ['21:30']),
    ('library_sync', 'detail', '北岸离线队列收到什么才能出队，重复请求保留多久？', [3], ['72 小时', '已落库记录', '收到确认后再出队']),
    ('library_access', 'confusion', '北岸的 A11 和 V3 分别指什么，能把它们当同一种版本号吗？', [4, 5], ['设备补丁', '验收清单.xlsx', 'V3']),
    ('library_access', 'cross_session', '北岸借还机无障碍那次签字，2 号机后来补签了吗，3 号机也算完成吗？', [9], ['签字', '3 号机支架', '另一个采购工单']),
    ('library_access', 'fallback_scope', '北岸闭馆前的 35% 音量设定可以套到所有设备吗？', [6], ['闭馆前一小时', '不是所有设备的全局偏好']),
    ('library_access', 'detail', '北岸 22 号字把失败提示截断后，是缩小字号还是改了排版？', [2], ['保留 22 号字', '两行提示']),
    ('lake_access', 'late_import', '湖东后来归档的邮件说用 22 号字，为什么当前仍应保留 20 号字？', [2, 8], ['20 号字', '8 月 30 日', '不替代']),
    ('lake_access', 'confusion', '湖东验收可以套用北岸的 V3 清单吗，交付凭证实际是什么？', [3, 9], ['V2', '英文附件']),
    ('lake_access', 'cross_session', '湖东那台没过验收的 D 机换屏了吗，最终触摸偏移与复测结果怎样？', [5, 6, 7], ['不换屏幕', '3 像素', '全部通过']),
    ('lake_access', 'detail', '湖东英文导览返回地图按钮最后缩写成了什么？', [4], ['Map']),
    ('kylin_package', 'detail', 'MemPulse 麒麟首包对中文路径验收用的样例目录叫什么？', [4], ['样例工程/一楼借还机']),
    ('kylin_package', 'confusion', 'MemPulse 首包签收是否也验证了麒麟 AI SDK 的输出一致性？', [8], ['不包含', 'SDK', '输出一致性']),
    ('kylin_package', 'cross_session', 'MemPulse 首包先遇到缺 GBM、后遇到记忆页报错，后一个错误是哪个打包环节遗漏？', [1, 2], ['libgbm.so.1', 'PyInstaller', '排除了推理依赖']),
    ('kylin_package', 'detail', 'MemPulse 的首包断网重启和首次安装依赖，对联网要求分别是什么？', [9], ['历史记忆可读', '首次依赖安装仍需联网']),
    ('kylin_retrieval', 'confusion', 'MemPulse 同一离线队列任务开了三个聊天窗口，应创建三个话题吗？', [0], ['三个新会话', '同一个离线队列任务', '不能直接等于话题']),
    ('kylin_retrieval', 'detail', 'MemPulse 的记忆定位流程里，TIDE 比较什么，文件和时间细节由谁检索？', [2], ['稳定任务概述', '结构化字段', '任务内证据检索']),
    ('kylin_retrieval', 'person', '何芸对 MemPulse 困难测试数据具体提出过哪四种混淆情形？', [4], ['同名王磊', '同名验收清单', '晚导入旧邮件', '跨工程相似任务']),
    ('kylin_retrieval', 'detail', 'MemPulse 检索优化任务目前为什么保留 FP32？', [3], ['向量对齐', '不通过', '保留 FP32']),
    ('campus_wifi', 'cross_session', '西桥三楼漫游在低负载改善后，为什么还不能结束整改，午间最终测到多少秒？', [4, 5, 7], ['80 人', '认证后端排队', '0.7 秒']),
    ('campus_wifi', 'detail', '西桥 AP-3F-07 后来用了什么信道和功率，能照搬到全楼吗？', [3], ['44', '17 dBm', '不批量修改全楼']),
    ('campus_wifi', 'fallback_scope', '西桥排障中备用 DNS 修复的是哪种失败，漫游有没有因此改善？', [2], ['没改善漫游', '解析失败']),
    ('campus_wifi', 'resource_move', '西桥 07 号 AP 的记录归档后，靠哪个不变的序列号确认还是原设备？', [8], ['WB3F07']),
    ('campus_guest', 'time', '西桥讲师提前一天申请的访客账号为什么会过早失效，新生效时间段是什么？', [2, 3], ['创建后 24 小时', '08:00', '22:00']),
    ('campus_guest', 'detail', '西桥访客网络能访问共享打印机所在的网段吗，具体网段是多少？', [5], ['不允许', '10.28.40.0/24']),
    ('campus_guest', 'person', '何芸批准西桥周末三名讲师入网，是否也批准共用同一个密码？', [6], ['没有批准共享一个密码']),
    ('campus_guest', 'detail', '西桥访客申请流程必须填哪些到访信息，身份证号要填吗？', [1], ['到访日期', '接待老师', '身份证号不采集']),
    ('lab_purchase', 'cross_session', '砺行两台工作站从第一次未税报价到最终发票，各是多少钱？', [1, 9], ['4.62 万元未税', '47600 元']),
    ('lab_purchase', 'detail', '砺行砍掉部分显卡预算时，有哪两项内存和保修要求仍必须保留？', [2, 4], ['64 GB', '三年上门']),
    ('lab_purchase', 'confusion', '砺行第一台工作站开箱为何不能签收，补件之后两台内存是多少？', [6, 7, 8], ['32 GB', '64 GB', 'LX-WS-041']),
    ('lab_purchase', 'person', '砺行工作站补送内存到货后，是谁拍照归档并完成配置签收？', [8], ['唐宁']),
    ('lab_migration', 'cross_session', '砺行数据迁移 8418 份校验通过后，剩下的三个文件为什么不一致、怎么解决的？', [5, 6], ['日志', '停止采集', '8421']),
    ('lab_migration', 'late_import', '砺行迁移草稿里的 1.8 TB 和正式数据量冲突，以哪个为准？', [9], ['1.86 TB']),
    ('lab_migration', 'detail', '砺行旧服务器停机之后，源盘能立刻格式化吗，规定保留多长时间？', [8], ['30 天', '不立即格式化']),
    ('lab_migration', 'fallback_scope', '砺行迁移时增加的 2.4 TB 配额是长期的吗，有效到什么时候？', [4], ['临时', '9 月 15 日']),
    ('seminar_expense', 'cross_session', '秋季交流会讲师差旅分两批处理后，三人总共报销多少，商务座差价算进来了吗？', [8], ['5474 元', '差价未列入']),
    ('seminar_expense', 'detail', '秋季交流会最先提交的两位讲师，住宿和交通费用分别多少？', [6], ['1800 元', '2026 元']),
    ('seminar_expense', 'person', '何芸允许交流会先报销两位讲师时，第三位应如何处理？', [5], ['第三位单独补单']),
    ('seminar_expense', 'detail', '秋季交流会讲师的酒店标准是每晚多少元，最多按几晚安排？', [0], ['450 元', '两晚']),
    ('seminar_av', 'cross_session', '秋季交流会的回声问题最终改了哪条回送，连续验证了多长时间？', [3, 5], ['USB 回送', '45 分钟']),
    ('seminar_av', 'confusion', '秋季交流会音响设备的结算金额是多少，是否包含讲师差旅？', [7], ['4000 元', '与差旅报销分开']),
    ('seminar_av', 'fallback_scope', '秋季交流会临借的 USB 麦后来还了吗，能由此记成长期设备偏好吗？', [2, 8], ['不代表以后优先选 USB 麦', '已归还']),
    ('seminar_av', 'detail', '秋季交流会租赁合同外另收多少调试费，最初由谁确认承担？', [6, 7], ['400 元', '主办方']),
    ('archive_translation', 'time', '城南开放日预约截止、最后一场讲解开始和闭馆分别是什么时间？', [0, 4], ['9 月 12 日 18:00', '15:40', '16:30']),
    ('archive_translation', 'late_import', '城南旧 R2 稿写的 8 毫米边距还能用吗，印前确认的边距是多少？', [5, 8], ['12 毫米', '不能覆盖']),
    ('archive_translation', 'detail', '城南开放日折页交印厂的是哪个文件，可编辑原稿有没有保留？', [6], ['brochure-open-day-R5.pdf', 'DOCX', '保留']),
    ('archive_translation', 'person', '周敏在城南折页里最终采用哪个英文术语表达档案查阅？', [1], ['archival consultation']),
]

NEGATIVE_QUESTIONS = [
    ('ambiguous', '王磊之前负责过哪些修复？'),
    ('ambiguous', '验收清单.xlsx 到底采用哪个版本？'),
    ('absent', '明河医院之前的无障碍项目谁签的字？'),
    ('absent', '沈宁最近审核过哪笔设备款？'),
    ('absent', '青石大学那次服务器迁移最后校验了多少文件？'),
    ('absent', '郑曼上次参与过什么项目？'),
]


def fresh_questions(cases):
    by_id = {case['id']: case for case in cases}
    rows = []
    for index, (case_id, kind, query, evidence, atoms) in enumerate(NEW_QUESTIONS):
        case = by_id[case_id]
        # The merged Kylin task also contains four earlier legacy events. Select
        # stable source IDs, not the position in its chronologically merged list.
        by_event = {event['event_id']: event for event in case['events']}
        sources = [by_event[f'demo:v4:sim:v3:{case_id}:{i:02d}'] for i in evidence]
        text = '\n'.join(event['content'] for event in sources)
        assert all(atom in text for atom in atoms), (case_id, atoms)
        rows.append({'id': f'fresh:{index + 1:03d}', 'split': 'fresh_authored', 'kind': kind,
                     'query': query, 'gold_topic': case_id,
                     'evidence_ids': [event['event_id'] for event in sources], 'answer_atoms': atoms})
    for index, (kind, query) in enumerate(NEGATIVE_QUESTIONS):
        rows.append({'id': f'fresh:negative:{index + 1}', 'split': 'fresh_authored', 'kind': kind,
                     'query': query, 'gold_topic': None, 'evidence_ids': [], 'answer_atoms': []})
    return rows
