"""Authored fictional work histories, not customer-name substitutions.

Each case has a persistent goal, explicit exclusions, multiple sessions, stable
people/resources, changing state and independently specified evidence questions.
All names/organisations and events are synthetic; no human-review claim is made.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

PEOPLE = {
    'lin': ('p_lin_xiao', '林晓', ['林工'], 'executor'),
    'zhou': ('p_zhou_min', '周敏', ['周老师'], 'reviewer'),
    'supplier_wang': ('p_wang_lei_vendor', '王磊', ['供应商王磊', '设备方王工'], 'contact'),
    'it_wang': ('p_wang_lei_it', '王磊', ['信息中心王磊', '运维王工'], 'executor'),
    'chen': ('p_chen_lu', '陈璐', ['陈老师'], 'initiator'),
    'xu': ('p_xu_yan', '许妍', ['许会计'], 'reviewer'),
    'gao': ('p_gao_yuan', '高远', ['高工'], 'executor'),
    'lu': ('p_lu_jia', '陆佳', ['陆经理'], 'contact'),
    'tang': ('p_tang_ning', '唐宁', ['唐同学'], 'participant'),
    'he': ('p_he_yun', '何芸', ['何主任'], 'reviewer'),
    'song': ('p_song_jie', '宋杰', ['宋工'], 'executor'),
    'zhao': ('p_zhao_rui', '赵蕊', ['赵老师'], 'initiator'),
}
PROJECT_ALIASES = {
    '北岸图书馆改造': ['北岸', '北岸图书馆'], '湖东展馆导览更新': ['湖东', '湖东展馆'],
    'MemPulse 麒麟交付': ['MemPulse'], '西桥教学楼网络整治': ['西桥', '西桥教学楼'],
    '砺行实验室设备更新': ['砺行', '砺行实验室'], '秋季技术交流会': ['秋季交流会'],
    '城南档案馆开放日': ['城南', '城南档案馆'],
}

# event = date/time, people present, factual event text, optional structured fields.
CASES = [
  {
    'id': 'library_sync', 'project': '北岸图书馆改造', 'directory': '/projects/northbank-library',
    'title': '借还机离线流水补传', 'aliases': ['断网补账', '离线队列修复'],
    'goal': '保证北岸图书馆一楼借还机断网期间的借还流水恢复后只入账一次；包含队列、幂等和重放，不包含无障碍验收。',
    'keywords': ['离线补传', '幂等去重', '重放顺序'], 'resource': ('res:northbank-sync-spec', '补传约定.md'),
    'events': [
      ('08-26 09:20', ['chen','lin'], '陈璐确认先解决断网补账，不把界面字号问题放进这项任务；周五之前给出可回放的故障样本。', {}),
      ('08-26 15:40', ['lin'], '在 1 号机拔网线 7 分钟，恢复后出现 18 条重复借阅流水。服务端日志中的 request_id 每次重试都会变化。', {'source_type':'tool','status':'failed','tool':'replay-test'}),
      ('08-27 10:10', ['supplier_wang','lin'], '供应商王磊解释设备端 sequence 在重启后归零，不能单独作为幂等键。讨论后暂定 device_id、boot_id、sequence 三段组合。', {}),
      ('08-28 11:30', ['lin'], '补传约定.md 更新为 v0.3：同一幂等键保存 72 小时，服务端只确认已落库记录，客户端收到确认后再出队。', {'template_version':'v0.3'}),
      ('08-29 16:05', ['lin','it_wang'], '第一次压测 1200 条积压记录在 41 秒内补齐，但第 803 条之后有 2 条顺序倒置，尚不能验收。', {'source_type':'tool','status':'failed','tool':'queue-load-test'}),
      ('09-01 09:50', ['it_wang'], '信息中心王磊把测试机 NTP 从公网源切到校内时间源。时间戳只用于展示，顺序仍以设备队列号为准。', {}),
      ('09-02 14:15', ['lin'], '将单设备并发数从 4 降为 1，重测 1200 条全部入账，重复数 0，耗时 58 秒。跨设备仍允许并发。', {'source_type':'tool','tool':'queue-load-test','completed_steps':['幂等去重','单设备有序重放']}),
      ('09-03 17:10', ['chen','lin'], '陈璐批准先灰度到 1 号机和 3 号机，2 号机留作对照。观察期到 9 月 8 日，不代表全馆上线。', {'pending_steps':['完成灰度观察','全馆上线审批']}),
      ('09-05 10:25', ['lin'], '文档由 docs/补传约定.md 移到 docs/protocol/offline-ledger.md，资源 ID 保持不变，标题仍沿用补传约定。', {'resource_path':'docs/protocol/offline-ledger.md'}),
      ('09-08 16:40', ['chen','it_wang'], '两台灰度设备连续五天没有重复流水，陈璐同意全馆启用；信息中心王磊负责当天 21:30 的发布。', {'completed_steps':['灰度观察','全馆上线审批'],'pending_steps':['21:30 正式发布']}),
    ],
    'questions': [
      ('cross_session','北岸那个断网补账后来怎么样了，最后是谁负责上线？',[9]),
      ('detail','北岸借还机补传最后的幂等键由哪三个字段组成？',[2]),
      ('detail','北岸补传测试为什么把同一设备并发降成 1？',[4,6]),
      ('person','供应商王磊在北岸补传里提醒过哪个序号问题？',[2]),
      ('resource_move','北岸的补传约定文档搬到哪里了，还算同一份资源吗？',[8]),
      ('time','北岸补传在 9 月 3 日批准了哪些机器灰度？',[7]),
    ],
  },
  {
    'id':'library_access', 'project':'北岸图书馆改造', 'directory':'/projects/northbank-library',
    'title':'一楼借还机无障碍验收', 'aliases':['大字版验收'],
    'goal':'完成一楼两台借还机的轮椅可达性、大字显示与语音提示验收并签字；不调整离线队列协议。',
    'keywords':['无障碍适配','触控可达性','验收签字'], 'resource':('res:northbank-access-check','验收清单.xlsx'),
    'events':[
      ('08-27 13:30',['zhou','chen'],'周敏把无障碍验收限定为 1 号机和 2 号机；3 号机需要先更换支架，不纳入本批签字。',{}),
      ('08-28 09:15',['zhou','supplier_wang'],'现场实测底部确认按钮距地 128 厘米，轮椅使用者够不到。供应商王磊承诺先下移按钮，机柜暂不改。',{}),
      ('08-29 11:05',['lin'],'字号从 16 调到 22 后，“续借失败请到服务台”被截断。保留 22 号字，改为两行提示，不恢复小字。',{'source_type':'tool','status':'failed','tool':'visual-check'}),
      ('09-01 14:00',['zhou','lin'],'周敏用三种操作流程复测，按钮下移到 106 厘米后通过；语音提示仍比屏幕晚 1.8 秒。',{}),
      ('09-02 10:20',['supplier_wang'],'设备方补丁 A11 将语音延迟降到 0.4 秒。这个编号是设备补丁，不是验收模板版本。',{}),
      ('09-03 09:10',['zhou'],'验收清单.xlsx 从 V2 改为 V3，只增加“语音完成前是否重复触发”一列，周敏是模板审核人。',{'template_version':'V3'}),
      ('09-04 15:00',['chen','zhou'],'陈璐提出晚间模式的音量固定 35%，只是图书馆闭馆前一小时的场景要求，不是所有设备的全局偏好。',{'preference':{'key':'voice_volume','value':'35%','choice_type':'temporary'}}),
      ('09-05 16:30',['zhou','supplier_wang'],'周敏与供应商王磊在一楼共同验收，1 号机通过，2 号机耳机插孔松动，因此只签了 1 号机。',{}),
      ('09-08 10:45',['supplier_wang'],'2 号机更换耳机插孔，工单 NB-214 关闭；尚未补签，不等于无障碍验收全部完成。',{}),
      ('09-09 14:10',['zhou','chen'],'周敏补测 2 号机并签字，本批两台验收完成，3 号机支架仍在另一个采购工单中。',{'completed_steps':['1号机签字','2号机补测签字']}),
    ],
    'questions':[
      ('confusion','北岸大字版验收结束了吗？不要把补传上线当成验收完成。',[9]),
      ('detail','北岸无障碍验收里确认按钮最后离地多高？',[3]),
      ('version','北岸无障碍验收用的 V3 清单具体比 V2 多了什么？',[5]),
      ('time','9 月 5 日北岸无障碍验收为什么只签一台？',[7]),
      ('fallback_scope','北岸借还机的 35% 音量是全局偏好吗？',[6]),
      ('cross_session','上次说北岸 2 号机修好了但没补签，后来补签了吗？',[8,9]),
    ],
  },
  {
    'id':'lake_access', 'project':'湖东展馆导览更新', 'directory':'/projects/lake-exhibition',
    'title':'导览终端无障碍验收', 'aliases':['展馆大字版'],
    'goal':'完成湖东展馆四台导览终端的大字、双语切换及无障碍验收；不沿用北岸借还业务的签字结论。',
    'keywords':['无障碍适配','双语切换','交付验收'], 'resource':('res:lake-access-check','验收清单.xlsx'),
    'events':[
      ('08-28 16:00',['lu','lin'],'陆佳要求展馆验收覆盖 A、B、C、D 四台导览终端，中文和英文都要测。',{}),
      ('08-29 10:20',['lin'],'复用北岸的大字组件后，湖东英文展项说明的最后一行被底栏遮住，不能直接复用北岸验收结果。',{'source_type':'tool','status':'failed','tool':'visual-check'}),
      ('09-01 11:00',['lu','supplier_wang'],'陆佳选择 20 号字和更大的行距，拒绝北岸的 22 号字方案，因为展馆说明更长。',{'preference':{'key':'font_size','value':'20','choice_type':'explicit'}}),
      ('09-02 14:40',['lin'],'验收清单.xlsx 仍使用 V2，湖东另加英文溢出附件，不升级北岸的 V3 模板。',{'template_version':'V2'}),
      ('09-03 15:10',['lu'],'英文按钮“Back to exhibition map”统一改为“Map”，修改只涉及湖东导览页面。',{}),
      ('09-04 10:05',['lin','supplier_wang'],'A、B、C 三台通过，D 机触摸偏移 14 像素。供应商王磊建议重新校准，不换屏幕。',{}),
      ('09-05 14:20',['supplier_wang'],'D 机完成五点校准，偏移最大 3 像素；原工单 LE-083 继续保留，等陆佳复测。',{}),
      ('09-08 09:35',['lu','lin'],'陆佳复测四台终端后确认全部通过，9 月 9 日开馆前生效。',{'completed_steps':['四台双语与触摸复测']}),
      ('08-30 17:00',['lu'],'晚导入的 8 月 30 日邮件仍写“暂定 22 号字”。这封邮件在 9 月 10 日归档，不替代 9 月 1 日已确认的 20 号字。',{'observed_at':'09-10 09:00'}),
      ('09-11 16:00',['lu'],'陆佳要求保留 V2 清单与英文附件作为本批交付凭证；下一展季再讨论模板升级。',{}),
    ],
    'questions':[
      ('confusion','湖东和北岸都叫大字版，湖东实际采用的是多大字号？',[2]),
      ('version','湖东导览终端验收清单是 V2 还是北岸的 V3？',[3,9]),
      ('late_import','湖东 9 月 10 日才归档的旧邮件能把字号改回 22 吗？',[2,8]),
      ('person','湖东 D 机触摸偏移是谁建议校准而不是换屏？',[5]),
      ('time','湖东在 9 月 8 日的复测结论是什么？',[7]),
      ('detail','湖东 D 机校准前后最大的触摸偏移分别是多少？',[5,6]),
    ],
  },
  {
    'id':'kylin_package', 'project':'MemPulse 麒麟交付', 'directory':'/projects/mempulse-kylin',
    'title':'麒麟 x64 客户端首包交付', 'aliases':['国产系统首包'],
    'goal':'在麒麟 x86_64 桌面完成客户端、Python 记忆服务和 FP32 模型的首个可安装包及启动验收，不负责改进检索模型准确率。',
    'keywords':['麒麟适配','客户端打包','运行库依赖'], 'resource':('res:kylin-build-guide','BUILD.md'),
    'events':[
      ('08-29 09:00',['gao','song'],'高远确认目标机是 x86_64，不是 ARM；系统 Python 3.8 不能用于当前后端，另装 3.11 虚拟环境。',{}),
      ('09-01 10:30',['song'],'首次 Electron 启动缺少 libgbm.so.1，界面未出现；这不是模型加载失败。',{'source_type':'tool','status':'failed','tool':'launch-check','error_type':'missing_library'}),
      ('09-01 15:40',['gao'],'补齐 GBM 运行库后主窗口打开，但记忆页提示 onnxruntime 缺失，发现旧 PyInstaller 脚本排除了推理依赖。',{}),
      ('09-02 11:50',['song'],'带 ONNX 依赖的记忆服务单独通过 15 次查询，仍使用 FP32。构建包中的模型使用相对路径发现。',{'source_type':'tool','tool':'ipc-smoke'}),
      ('09-03 13:20',['gao','he'],'何芸要求先交目录包检查中文路径，再制作 DEB。测试路径包含“样例工程/一楼借还机”。',{}),
      ('09-04 16:15',['song'],'中文路径新建会话通过，切换工程后会话使用新目录；取消选择文件夹不会修改原选择。',{'source_type':'tool','tool':'ui-check'}),
      ('09-05 10:30',['gao'],'DEB 安装后图标正常，但普通用户启动日志目录归 root 所有；原因是先前用 sudo 运行过测试客户端。',{'status':'failed'}),
      ('09-08 14:10',['song'],'改为干净普通用户安装测试，记忆和日志都写入用户目录；没有把 --no-sandbox 加入启动脚本。',{}),
      ('09-09 11:00',['he','gao'],'何芸签收首包，要求回滚时保留用户数据。首包验收不包含麒麟 AI SDK 的模型输出一致性。',{'completed_steps':['目录包验收','DEB安装验收'],'pending_steps':['SDK专项验证']}),
      ('09-10 17:20',['song'],'BUILD.md 增加断网重启检查：模型与历史记忆可读；首次依赖安装仍需联网。',{}),
    ],
    'questions':[
      ('cross_session','MemPulse 国产系统首包最后交付了吗，还欠什么专项？',[8]),
      ('detail','MemPulse 麒麟客户端第一次窗口都没出现，缺的是哪个库？',[1]),
      ('confusion','MemPulse 麒麟首包里的记忆服务测试通过，是否代表模型准确率已经达标？',[3,8]),
      ('person','MemPulse 麒麟交付是谁要求先验目录包再做 DEB？',[4]),
      ('time','MemPulse 麒麟交付 9 月 5 日发现的权限问题原因是什么？',[6]),
      ('detail','MemPulse 麒麟首包为什么没有给启动脚本加 --no-sandbox？',[7]),
    ],
  },
  {
    'id':'kylin_retrieval', 'project':'MemPulse 麒麟交付', 'directory':'/projects/mempulse-kylin',
    'title':'持久任务检索评估与标签修订', 'aliases':['记忆定位复测'],
    'goal':'验证持久任务的跨会话定位、人物时间事实检索和标签生成质量；区分模型候选召回与最终证据检索，不负责 DEB 打包。',
    'keywords':['话题边界','标签生成','证据检索'], 'resource':('res:mempulse-eval-report','评估记录.md'),
    'events':[
      ('08-29 14:10',['lin','gao'],'林晓发现三个新会话被建成三个话题，尽管都在处理同一个离线队列任务。工程只能作定位线索，不能直接等于话题。',{}),
      ('09-01 09:25',['gao'],'把查询片段“可以再试一下吗”生成为标签属于错误抽取；词法分词可以用于 FTS，但不能直接写入标签图谱。',{}),
      ('09-02 16:20',['lin'],'确定 TIDE 先比较请求和稳定任务概述；人物、时间与文件细节交给结构化字段和任务内证据检索。',{}),
      ('09-03 10:30',['gao'],'FP32 与混合 INT8 的向量对齐在当前机器不通过，保留 FP32；不能只看 INT8 的速度优势就切换。',{}),
      ('09-04 14:45',['lin','he'],'何芸要求新测试集增加同名王磊、同名验收清单、晚导入旧邮件和跨工程相似任务，不能只换客户名。',{}),
      ('09-05 11:15',['gao'],'新标签策略允许开放词汇，但自动候选必须给原文证据；整句、寒暄、日期碎片和文件路径不能充当关键词标签。',{}),
      ('09-08 09:40',['lin'],'检索返回值改为按候选任务分组，不再把前几个任务的最新三条事件混成一个事实集合。',{}),
      ('09-09 15:10',['he'],'何芸确认所有新建、删除、合并和显式记忆写入需要前端确认，历史查询不弹确认框。',{}),
      ('09-10 10:50',['gao'],'评估记录.md 中的样本被标记为仿真，人物名均为虚构；没有把它们写成真实客户使用记录。',{}),
      ('09-11 16:35',['lin'],'还需独立人工复核困难负样本，自动归题阈值暂不启用。检索 Top-1 和证据命中率必须分别报告。',{'pending_steps':['困难样本人工复核','归题阈值留出验证']}),
    ],
    'questions':[
      ('confusion','MemPulse 的记忆定位复测和麒麟首包打包是一个话题吗？',[0,2]),
      ('detail','MemPulse 里 FTS 的切词结果为什么不能直接作为标签？',[1,5]),
      ('person','谁要求 MemPulse 测试集加入同名王磊和晚到旧邮件？',[4]),
      ('cross_session','MemPulse 那个先找哪件事再找细节的模型方案，后来落到什么检索方式？',[2,6]),
      ('time','MemPulse 9 月 9 日确认了哪些操作需要前端确认？',[7]),
      ('detail','MemPulse 的自动归题现在为什么还不能启用？',[9]),
    ],
  },
  {
    'id':'campus_wifi', 'project':'西桥教学楼网络整治', 'directory':'/projects/westbridge-network',
    'title':'三楼漫游掉线整改', 'aliases':['三楼 Wi-Fi 断流'],
    'goal':'解决西桥教学楼三楼移动设备跨 AP 漫游断流，完成课间高峰复测；不包含访客账号申请流程。',
    'keywords':['无线漫游','高峰断流','信道规划'], 'resource':('res:westbridge-radio-map','AP点位表.xlsx'),
    'events':[
      ('08-25 10:05',['it_wang','zhao'],'赵蕊报告在 305 到 307 教室之间移动时视频会议会断 8 秒，固定坐在 305 不会断。',{}),
      ('08-26 09:40',['it_wang'],'抓包发现 AP-3F-06 与 AP-3F-07 都占用信道 36，发射功率均为 23 dBm。',{'source_type':'tool','tool':'wireless-survey'}),
      ('08-27 16:10',['song'],'第一次改用备用 DNS 没改善漫游，只解决了测试机偶发解析失败；不能记成长期网络配置偏好。',{'is_fallback':True,'fallback_reason':'测试机DNS临时失效'}),
      ('08-28 11:20',['it_wang','gao'],'将 07 的信道改为 44，功率降到 17 dBm；只改这台 AP，不批量修改全楼。',{}),
      ('08-29 14:00',['zhao'],'赵蕊行走复测的断流降到 1.2 秒，但午间走廊 80 人时仍有卡顿。',{}),
      ('09-01 12:30',['song','it_wang'],'午间压测显示认证后端排队，新增的无线参数不是唯一瓶颈，保留两条独立故障证据。',{'source_type':'tool','status':'failed','tool':'roaming-load-test'}),
      ('09-02 16:00',['gao'],'认证缓存有效期从 30 秒调到 120 秒，仅对已完成校内认证的设备生效。',{}),
      ('09-04 12:20',['zhao','it_wang'],'午间 84 人测试通过，最大断流 0.7 秒；赵蕊同意结束三楼整改。',{'completed_steps':['行走复测','午间高峰复测']}),
      ('09-05 09:10',['song'],'AP点位表.xlsx 中 07 号设备路径变更到 archive/2026-09/，设备序列号 WB3F07 不变。',{}),
      ('09-08 10:00',['it_wang'],'一楼有人反馈访客密码过期，转入访客账号流程话题，不重新打开三楼漫游整改。',{}),
    ],
    'questions':[
      ('cross_session','西桥三楼移动时断流后来解决了吗，最后最大断流是多少？',[7]),
      ('detail','西桥三楼到底改了哪台 AP 的信道和功率？',[1,3]),
      ('fallback_scope','西桥网络整改时用过备用 DNS，是否应该以后都优先用它？',[2]),
      ('person','西桥三楼谁做了午间复测并同意结束整改？',[7]),
      ('time','西桥网络 9 月 1 日午间压测又发现了什么瓶颈？',[5]),
      ('confusion','西桥一楼访客密码过期为什么不算三楼漫游整改复发？',[9]),
    ],
  },
  {
    'id':'campus_guest', 'project':'西桥教学楼网络整治', 'directory':'/projects/westbridge-network',
    'title':'外来讲师访客账号流程', 'aliases':['临时上网账号'],
    'goal':'为西桥教学楼外来讲师建立带审批和失效时间的访客账号流程；不处理三楼无线漫游。',
    'keywords':['访客账号','有效期审批','权限范围'], 'resource':('res:westbridge-guest-form','访客申请表.docx'),
    'events':[
      ('08-28 09:00',['zhao','he'],'赵蕊提出外来讲师只需要一天网络权限，不能共用教职工账号。',{}),
      ('08-29 11:30',['he'],'何芸要求申请表包含到访日期和接待老师，身份证号不采集。',{}),
      ('09-01 13:45',['it_wang'],'首版把失效时间设为创建后 24 小时，导致提前一天申请的账号上课前失效。',{'status':'failed'}),
      ('09-02 09:10',['he','it_wang'],'改为到访日 08:00 生效、22:00 失效；跨天活动由接待老师另行申请，不能自动延长。',{}),
      ('09-03 15:20',['zhao'],'9 月 6 日周末讲座的账号由赵蕊担任接待老师，已提交三名讲师申请。',{}),
      ('09-04 10:05',['it_wang'],'访客网只能访问互联网，不允许访问打印机子网 10.28.40.0/24。',{}),
      ('09-05 16:30',['he'],'何芸批准周末三名讲师的申请，但没有批准共享一个密码。',{}),
      ('09-06 08:40',['zhao','it_wang'],'周末讲座现场三名讲师分别登录成功；其中一台电脑自动填充了旧密码，清除缓存后恢复。',{}),
      ('09-08 10:40',['it_wang'],'一楼访客账号过期符合到访日策略，处理方式是重新申请；不是三楼 AP 参数导致掉线。',{}),
      ('09-09 14:00',['he'],'访客申请表.docx 固定为 V1.2，接待老师字段必填；本次流程验收完成。',{'template_version':'V1.2'}),
    ],
    'questions':[
      ('detail','西桥临时上网账号改成几点生效、几点失效？',[3]),
      ('person','西桥周末讲座的三名讲师由谁接待，谁批准申请？',[4,6]),
      ('confusion','西桥访客账号过期和三楼 AP 信道调整有什么关系？',[8]),
      ('detail','西桥访客网络能访问打印机子网吗？',[5]),
      ('time','西桥 9 月 6 日有一台电脑登录失败，最后怎么恢复的？',[7]),
      ('version','西桥访客申请表最后固定在哪个版本，哪个字段必填？',[9]),
    ],
  },
  {
    'id':'lab_purchase', 'project':'砺行实验室设备更新', 'directory':'/projects/lixing-equipment',
    'title':'两台采集工作站采购', 'aliases':['GPU 工作站采购'],
    'goal':'为砺行实验室采购两台采集工作站，完成配置、含税报价和到货核对；不包含既有服务器的数据迁移。',
    'keywords':['采购审批','含税报价','到货核对'], 'resource':('res:lixing-workstation-quote','报价单.xlsx'),
    'events':[
      ('08-25 14:00',['chen','lu'],'陈璐提出两台工作站总预算 4.8 万元，必须含税和三年上门保修。',{}),
      ('08-26 10:30',['lu'],'陆佳发来的第一版报价是 4.62 万元未税，不能直接与预算比较。',{}),
      ('08-27 15:10',['xu','chen'],'许妍核算 13% 税后为 5.2206 万元，超出预算；要求降低显卡档位，内存仍保留 64 GB。',{}),
      ('08-28 09:40',['lu'],'第二版含税总价 4.76 万元，两台均为 64 GB 内存、2 TB NVMe、三年上门保修。',{}),
      ('08-29 16:00',['chen','xu'],'陈璐确认选第二版，不接受一年送修替代三年上门。许妍批准付款流程。',{}),
      ('09-02 11:20',['lu'],'供应商通知其中一台需延迟两天，原定 9 月 4 日改为 9 月 6 日；另一台日期不变。',{}),
      ('09-04 15:30',['gao','tang'],'首台到货序列号 LX-WS-041，开箱发现只有一条 32 GB 内存，暂不签收配置。',{'status':'failed'}),
      ('09-05 10:15',['lu'],'陆佳确认发货清单错误，9 月 6 日随第二台补送一条同型号 32 GB 内存。',{}),
      ('09-06 16:50',['gao','tang'],'第二台 LX-WS-042 与补送内存到齐，两台均识别 64 GB；唐宁拍照归档，完成配置签收。',{'completed_steps':['两台配置核对','序列号与保修归档']}),
      ('09-08 14:10',['xu'],'许妍核对发票总额 47600 元，与第二版报价一致，采购闭环完成。',{}),
    ],
    'questions':[
      ('detail','砺行工作站最终两台含税多少钱，保修条件是什么？',[3,4,9]),
      ('person','砺行工作站首版报价是谁发现税后超预算的？',[2]),
      ('time','砺行 9 月 4 日为什么没有签收首台配置？',[6]),
      ('cross_session','砺行那台只到了一条内存的工作站，后来补齐了吗？',[6,7,8]),
      ('detail','砺行两台工作站的序列号分别是什么？',[6,8]),
      ('confusion','砺行采购预算有没有靠把三年上门保修换成一年送修解决？',[4]),
    ],
  },
  {
    'id':'lab_migration', 'project':'砺行实验室设备更新', 'directory':'/projects/lixing-equipment',
    'title':'旧采集服务器数据迁移', 'aliases':['旧机退役前搬数据'],
    'goal':'将砺行旧采集服务器的实验原始数据迁移到 NAS，完成校验和恢复抽查后才能退役旧机；不改变新工作站采购配置。',
    'keywords':['数据迁移','校验和','备份恢复'], 'resource':('res:lixing-migration-map','迁移清单.csv'),
    'events':[
      ('08-27 09:30',['gao','chen'],'旧服务器有 1.86 TB 原始采集数据，陈璐要求原始文件只读，派生图表可以重建。',{}),
      ('08-28 14:00',['tang'],'迁移清单.csv 列出 8421 个文件，其中 16 个中文文件名存在组合字符差异。',{}),
      ('08-29 10:10',['gao'],'先做路径 NFC 规范化映射，保留原始路径列，不在源盘批量重命名。',{}),
      ('09-01 19:30',['song'],'第一次同步在 73% 时中断，原因是 NAS 配额不足；没有重新从头复制，也没有删除源数据。',{'source_type':'tool','status':'failed','tool':'rsync','error_type':'quota_exceeded'}),
      ('09-02 10:05',['chen'],'陈璐批准把项目配额临时提高到 2.4 TB，有效到 9 月 15 日清理派生缓存之后。',{}),
      ('09-03 20:40',['song'],'增量同步完成，8421 个文件校验通过 8418 个，剩余 3 个是在采集进程运行时被改写的日志。',{'source_type':'tool','tool':'checksum-check'}),
      ('09-04 18:00',['gao','tang'],'停止采集后重传 3 个日志，8421 个文件全部校验一致，仍需恢复抽查。',{}),
      ('09-05 11:00',['tang'],'唐宁从 NAS 随机恢复 20 份原始样本，分析脚本均可读取，抽查通过。',{}),
      ('09-08 15:20',['chen','gao'],'陈璐批准旧机停机，但源盘保留封存 30 天，不立即格式化。',{'completed_steps':['完整校验','恢复抽查'],'pending_steps':['30天封存期结束后复核']}),
      ('09-10 09:40',['song'],'迟到的 8 月 29 日同步草稿被导入，草稿写 1.8 TB 估算值，正式清单仍是 1.86 TB。',{'observed_at':'09-11 09:00'}),
    ],
    'questions':[
      ('cross_session','砺行旧机退役前搬数据最终校验通过了吗，源盘能格式化了吗？',[6,7,8]),
      ('detail','砺行迁移第一次为什么在 73% 中断，后来怎么续传？',[3,4,5]),
      ('person','砺行迁移是谁恢复抽查了多少份样本？',[7]),
      ('time','砺行 9 月 3 日没通过校验的三个文件是什么原因？',[5]),
      ('detail','砺行迁移中文文件名怎么处理，是否改了源盘名字？',[1,2]),
      ('confusion','砺行旧机迁移的 2.4 TB 是原始数据量还是临时配额？',[0,4]),
    ],
  },
  {
    'id':'seminar_expense', 'project':'秋季技术交流会', 'directory':'/projects/autumn-seminar',
    'title':'交流会讲师差旅报销', 'aliases':['讲师报销材料'],
    'goal':'完成秋季技术交流会三位讲师的交通住宿报销，核对票据与审批金额；不处理会场音视频设备结算。',
    'keywords':['费用报销','票据核对','差旅标准'], 'resource':('res:seminar-expenses','报销明细.xlsx'),
    'events':[
      ('08-28 10:20',['zhao','xu'],'赵蕊确认三位讲师由主办方报销高铁二等座和两晚住宿，酒店每晚标准 450 元。',{}),
      ('08-29 15:00',['xu'],'许妍提醒其中一位讲师自行升级商务座，升级差价由本人承担，不修改通用交通标准。',{}),
      ('09-01 09:30',['zhao'],'收到前两位讲师票据合计 3826 元，第三位尚缺返程票，不能按三人已齐全汇报。',{}),
      ('09-02 14:20',['xu'],'第二位讲师酒店发票多开了一晚，实际行程只住两晚，请酒店重开。',{'status':'pending'}),
      ('09-03 16:40',['zhao'],'酒店重开发票已收到，第三位返程票仍缺；暂不把整批报销作废。',{}),
      ('09-04 10:10',['zhao','he'],'何芸批准先报销资料完整的两位，第三位单独补单，不以票据上传时间改变实际出差日期。',{}),
      ('09-05 15:50',['xu'],'两位讲师报销 3826 元提交财务；其中住宿合计 1800 元，交通 2026 元。',{}),
      ('09-08 11:30',['zhao'],'第三位讲师补齐返程票，补单金额 1648 元，包含两晚住宿 900 元。',{}),
      ('09-09 14:00',['xu'],'三位讲师本次实际报销总额 5474 元，商务座升级差价未列入。',{}),
      ('09-11 09:20',['he'],'何芸确认两批付款均完成，原票据保留在财务归档目录，关闭本次报销任务。',{'completed_steps':['两批报销提交','两批付款核对']}),
    ],
    'questions':[
      ('detail','秋季交流会三位讲师实际报销总额是多少，商务座差价算进去了吗？',[8]),
      ('time','秋季交流会 9 月 4 日为什么可以先报两个人？',[5]),
      ('person','谁发现秋季交流会有一张酒店发票多开一晚？',[3]),
      ('cross_session','秋季交流会第三位讲师缺的返程票后来补了吗，补单多少？',[7]),
      ('detail','秋季交流会第一批 3826 元中交通和住宿各多少？',[6]),
      ('confusion','秋季交流会差旅报销包含会场音视频设备结算吗？',[0,8]),
    ],
  },
  {
    'id':'seminar_av', 'project':'秋季技术交流会', 'directory':'/projects/autumn-seminar',
    'title':'会场拾音改造与设备结算', 'aliases':['交流会麦克风问题'],
    'goal':'解决秋季交流会远端连线回声，完成设备租赁验收和结算；不涉及讲师的差旅报销。',
    'keywords':['回声消除','音视频联调','设备结算'], 'resource':('res:seminar-av-check','验收清单.xlsx'),
    'events':[
      ('08-27 16:00',['song','lu'],'宋杰发现远端说话会回传两次，陆佳确认租赁设备包括一台调音台和四支无线麦。',{}),
      ('08-28 11:10',['song'],'把会议软件和调音台的自动增益同时开启后回声更明显，先保留调音台增益，关闭软件自动增益。',{'source_type':'tool','status':'failed','tool':'audio-loopback'}),
      ('08-29 14:20',['lu'],'陆佳临时借来 USB 麦用于排查，借用不计入最终租赁清单，也不代表以后优先选 USB 麦。',{'is_fallback':True,'fallback_reason':'原无线麦接收机排查'}),
      ('09-01 10:50',['song','gao'],'找到调音台 USB 回送被重复送入会议总线，去掉回送通道后原无线麦可以正常使用。',{}),
      ('09-02 15:00',['he'],'何芸要求验收清单增加远端打断发言测试，沿用设备清单 V1，不借用讲师报销模板。',{'template_version':'V1'}),
      ('09-03 16:10',['song','lu'],'四支无线麦逐支测试通过，连续 45 分钟连线未再出现重复回声。',{'completed_steps':['四支麦逐支测试','45分钟远端连线']}),
      ('09-04 09:30',['lu'],'设备租赁合同金额 3600 元，额外半天调试费 400 元已单列，待主办方确认。',{}),
      ('09-05 17:00',['he','xu'],'何芸确认额外调试由主办方临时增加，许妍同意总计 4000 元结算，与差旅报销分开。',{}),
      ('09-08 10:00',['song'],'借来的 USB 麦已归还陆佳，原无线麦接收机没有更换。',{}),
      ('09-10 14:30',['xu'],'设备结算发票 4000 元已入账，验收清单与租赁合同一起归档。',{}),
    ],
    'questions':[
      ('detail','秋季交流会远端回声真正的原因是什么，最后换麦克风了吗？',[3,8]),
      ('fallback_scope','秋季交流会临时借过 USB 麦，能把它当长期设备偏好吗？',[2,8]),
      ('confusion','秋季交流会设备结算是 3600 还是 4000，和讲师报销混在一起了吗？',[6,7,9]),
      ('person','秋季交流会额外半天调试费是谁确认、谁同意结算的？',[7]),
      ('time','秋季交流会 9 月 3 日音视频联调测了多久？',[5]),
      ('cross_session','秋季交流会那支借来的麦后来归还了吗？',[8]),
    ],
  },
  {
    'id':'archive_translation', 'project':'城南档案馆开放日', 'directory':'/projects/south-archive',
    'title':'开放日双语导览折页定稿', 'aliases':['英文折页校对'],
    'goal':'完成城南档案馆开放日中英双语导览折页的术语、开放时间与印前版本校对；不负责志愿者排班。',
    'keywords':['双语校对','术语一致性','印前版本'], 'resource':('res:archive-leaflet','导览折页.docx'),
    'events':[
      ('08-28 14:30',['zhou','zhao'],'赵蕊给出开放日时间 9 月 13 日 09:00—16:30，预约截止时间是 9 月 12 日 18:00，两个时间不能混写。',{}),
      ('08-29 10:00',['zhou'],'周敏把“档案查阅”译为 archival consultation，不用 document search；该术语限定这份折页。',{}),
      ('09-01 15:20',['tang'],'英文页把预约截止日期误写为 9 月 13 日，唐宁在校对表标红，尚未提交印刷。',{'status':'failed'}),
      ('09-02 09:10',['zhou'],'导览折页.docx 修订为 R4，修正预约截止日期，中文页开放时间不变。',{'template_version':'R4'}),
      ('09-03 11:50',['zhao'],'赵蕊确认最后一场讲解 15:40 开始，不是闭馆时间 16:30；英文页应保留两个字段。',{}),
      ('09-04 16:20',['tang','zhou'],'打印样张边距不足，周敏把左右边距从 8 毫米改为 12 毫米，字号仍为 10.5 磅。',{}),
      ('09-05 14:00',['zhou'],'R5 通过印前校对，发给印厂的文件为 brochure-open-day-R5.pdf，原 DOCX 作为可编辑源文件保留。',{'template_version':'R5'}),
      ('09-08 10:15',['zhao'],'印厂回传 500 份纸质折页收货单，数量与订单一致；不再修改已印刷版本。',{}),
      ('08-29 17:00',['zhou'],'8 月 29 日 R2 旧稿在 9 月 9 日从邮件导入，其中仍写 8 毫米边距，不能覆盖已确认的 R5。',{'observed_at':'09-09 15:20'}),
      ('09-12 17:40',['zhao','tang'],'预约名单在截止前最后一次更新；折页正文不包含姓名名单，人员变动不重新生成折页话题。',{}),
    ],
    'questions':[
      ('detail','城南开放日预约截止和正式开放时间分别是什么？',[0]),
      ('version','城南英文折页最后送印的是哪一版，源 DOCX 还保留吗？',[6]),
      ('late_import','城南 9 月 9 日导入的 R2 旧稿能覆盖 R5 的边距吗？',[5,6,8]),
      ('person','城南折页是谁把预约截止日期写错的问题标红的？',[2]),
      ('time','城南折页 9 月 4 日样张改了什么，字号改了吗？',[5]),
      ('cross_session','城南英文折页说最后一场讲解和闭馆别写混了，两个时间是什么？',[0,4]),
    ],
  },
]


def timestamp(value):
    return datetime.strptime('2026-' + value, '%Y-%m-%d %H:%M').replace(tzinfo=timezone(timedelta(hours=8))).isoformat()


def seed_realistic(service):
    """Seed an isolated, explicitly synthetic workspace; never clear existing data."""
    mapping = {}
    for case in CASES:
        existing = next((topic for topic in service.store.list_topics(service.user_id)
                         if topic.metadata.get('scenario_id') == case['id']), None)
        if existing:
            mapping[case['id']] = existing.topic_id
            continue
        topic = service.core.create_topic(user_id=service.user_id, title=case['title'], goal=case['goal'],
            metadata={'scenario_id': case['id'], 'synthetic': True, 'identity_confirmed': True,
                      'identity_goal': case['goal'], 'identity_aliases': case['aliases'],
                      'project_name': case['project'], 'project_ref': case['directory'],
                      'project_aliases': PROJECT_ALIASES[case['project']]})
        mapping[case['id']] = topic.topic_id
        for index, (occurred, participants, content, extra) in enumerate(case['events']):
            resource_id, resource_name = case['resource']
            person_refs = [{'id': PEOPLE[person][0], 'name': PEOPLE[person][1], 'aliases': PEOPLE[person][2],
                            'role': PEOPLE[person][3]} for person in participants]
            metadata = {'synthetic': True, 'dataset': 'persistent-work-v3', 'scenario_id': case['id'],
                'keywords': case['keywords'] if index == 0 else [], 'keywords_confirmed': index == 0,
                'opencode_session_id': f'sim:{case["id"]}:session:{index//3+1}', 'opencode_directory': case['directory'],
                'resources': [{'id': resource_id, 'name': resource_name,
                               'path': case['directory'] + '/' + extra.get('resource_path', resource_name)}]}
            metadata.update({key: value for key, value in extra.items() if key in ('template_version', 'completed_steps', 'pending_steps')})
            if index == 0:
                metadata.update({'topic_identity_confirmation': True, 'input_files': [resource_name]})
            event_id = f'sim:v3:{case["id"]}:{index:02d}'
            service.ingest({'event_id': event_id, 'idempotency_key': event_id, 'topic_id': topic.topic_id,
                'content': content, 'source_type': extra.get('source_type', 'conversation'), 'status': extra.get('status', 'success'),
                'occurred_at': timestamp(occurred), 'observed_at': timestamp(extra.get('observed_at', occurred)),
                'app': 'OpenCode', 'tool': extra.get('tool'), 'is_fallback': extra.get('is_fallback', False),
                'fallback_reason': extra.get('fallback_reason'), 'person_refs': person_refs,
                'resource_ids': [resource_id], 'metadata': metadata})
            if extra.get('preference'):
                service.update_preference({**extra['preference'], 'scope_type': 'topic', 'scope_id': topic.topic_id,
                                           'evidence_event_id': event_id, 'observed_at': timestamp(occurred)})
    return {'dataset': 'persistent-work-v3', 'synthetic': True, 'independent_human_review': False,
            'topic_ids': mapping, 'topics': len(CASES), 'events': sum(len(case['events']) for case in CASES),
            'sessions': sum((len(case['events'])+2)//3 for case in CASES), 'people': len(PEOPLE)}


def questions():
    result = []
    for case in CASES:
        for index, (kind, query, evidence) in enumerate(case['questions']):
            result.append({'id': f'{case["id"]}:q{index}', 'kind': kind, 'query': query, 'gold_topic': case['id'],
                'evidence_ids': [f'sim:v3:{case["id"]}:{i:02d}' for i in evidence], 'context': {'reference_time': '2026-09-15T10:00:00+08:00'}})
    result.extend([
        {'id':'ambiguous:person','kind':'ambiguous','query':'王磊上次提醒过什么？','gold_topic':None,'evidence_ids':[],'expect_clarification':True},
        {'id':'ambiguous:file','kind':'ambiguous','query':'验收清单.xlsx 最后是什么版本？','gold_topic':None,'evidence_ids':[],'expect_clarification':True},
        {'id':'ambiguous:task','kind':'ambiguous','query':'继续上次那个验收。','gold_topic':None,'evidence_ids':[],'expect_clarification':True},
        {'id':'absent:customer','kind':'absent','query':'东辰医院影像服务器采购批复金额是多少？','gold_topic':None,'evidence_ids':[]},
        {'id':'absent:person','kind':'absent','query':'邵文博签过哪份合同？','gold_topic':None,'evidence_ids':[]},
        {'id':'absent:future','kind':'absent','query':'北岸图书馆 2026 年 12 月 20 日发生了哪些故障？','gold_topic':None,'evidence_ids':[]},
    ])
    return result
