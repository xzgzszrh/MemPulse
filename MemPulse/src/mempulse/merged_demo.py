"""Curated demo v4: legacy evidence plus authored persistent task histories.

Only known, wholly synthetic source topics can be archived. Their raw events
remain in SQLite; mixed or personal topics are left untouched. Every new event
has a stable source mapping. No unrelated tasks are merged merely by project.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from .demo_scenarios import TASKS, scenarios
from .desktop_seed import LEGACY_SCENARIOS
from .realistic_scenarios import CASES, PEOPLE, PROJECT_ALIASES, questions, timestamp

DATASET = 'persistent-demo-v4'
LEGACY_PEOPLE = {'周宁': 'p_legacy_zhou_ning', '林夏': 'p_legacy_lin_xia',
                 '陈川': 'p_legacy_chen_chuan', '许岚': 'p_legacy_xu_lan'}
KEYWORDS = {
    'delivery': ['交付验收','模板替代','签字审核'], 'api': ['接口鉴权','字段映射','异常回包'],
    'network': ['链路协商','间歇断连','故障观察'], 'backup': ['备份恢复','校验和','恢复抽查'],
    'printing': ['打印驱动','中文输出','断电重连'], 'training': ['桌面操作培训','资料归档','讲义修订'],
    'expense': ['费用报销','票据更正','财务复核'], 'procurement': ['采购比选','交货周期','预算审批'],
    'security': ['日志脱敏','字段遗忘','来源审计'], 'water': ['用水分摊','夜间保洁','时段核算'],
    'schedule': ['停机许可','检修排期','备件核对'], 'translation': ['双语校对','术语一致性','交叉引用'],
}
BASIC = {
    'acme': ('青禾客户交付报告', '青禾自动化交付', '/projects/legacy-qinghe', ['甲客户'], ['交付验收','模板替代','签字审核']),
    'weekly': ('研发周报编写与格式约定', '研发工作周报', '/projects/legacy-weekly', ['周报'], ['工作周报','格式约定','行动项']),
    'network': ('办公工作站网络故障复盘', '桌面设备维护', '/projects/legacy-desktop', ['桌面网络'], ['间歇断连','故障复盘','配置恢复']),
    'beta': ('恒达库存接口联调', '恒达系统接入', '/projects/legacy-hengda', ['乙客户'], ['字段映射','接口联调','异常回包']),
    'privacy': ('会议资料归档与联系方式分离', '会议资料治理', '/projects/legacy-archive', ['会议隐私整理'], ['资料归档','字段遗忘','来源索引']),
}
BASIC_GOALS = {
    'acme':'持续完成青禾客户交付报告的模板选用、初稿复核与验收签字，保留版本替代依据。',
    'weekly':'持续编写研发工作周报，维护常规输出格式，区分单次会议的临时要求。',
    'network':'解决办公工作站间歇断连并保留诊断与配置恢复依据，形成可复用的故障复盘。',
    'beta':'完成恒达库存系统的接口字段映射、异常回包约定与联调验收。',
    'privacy':'整理会议资料的检索索引，将联系方式与工作流程分开保存，以支持后续字段级遗忘。',
}
NEW_TAG_SOURCES = {
    'library_sync': [[0,3],[2,3,6],[4,6]], 'library_access': [[0,3,7,9],[1,3],[7,9]],
    'lake_access': [[0,1,7],[0,3,4],[5,7,9]], 'kylin_package': [[0,3,8],[3,4,8],[1,2]],
    'kylin_retrieval': [[0,2],[1,5],[2,6,9]], 'campus_wifi': [[0,4,7],[0,5,7],[1,3]],
    'campus_guest': [[0,2,3],[1,3,6],[0,5]], 'lab_purchase': [[0,4],[1,2,3,9],[6,8]],
    'lab_migration': [[0,3,5],[2,5,6],[0,7,8]], 'seminar_expense': [[0,5,8],[1,2,3,7],[0,1]],
    'seminar_av': [[0,1,3],[3,5],[6,7,9]], 'archive_translation': [[1,2,6],[1,4],[3,5,6,8]],
}
LEGACY_TAG_SOURCES = {
    'delivery': [[0,3],[1,2],[0,3]], 'api': [[1,2],[0],[3]], 'network': [[2],[0],[3]],
    'backup': [[0,1],[0,2],[2]], 'printing': [[1,2],[0,2],[3]], 'training': [[0,2],[0,1],[1,3]],
    'expense': [[0,3],[1,2],[3]], 'procurement': [[0,2],[0],[2,3]], 'security': [[0,2],[1,2],[0,3]],
    'water': [[0,2],[0,1,2],[1,2,3]], 'schedule': [[3],[0,1],[1,2]], 'translation': [[0,2],[1],[2]],
}
LEGACY_QUERY_EVIDENCE = {
    'delivery': [[2],[3],[3]], 'api': [[1,2],[2],[3]], 'network': [[2],[1],[3]],
    'backup': [[2],[2],[3]], 'printing': [[2],[3],[3]], 'training': [[1],[3],[3]],
    'expense': [[2],[3],[3]], 'procurement': [[2],[2,3],[3]], 'security': [[1],[2],[3]],
    'water': [[2],[2],[3]], 'schedule': [[1],[2],[3]], 'translation': [[1],[2],[3]],
}


def _event(source, occurred, content, people, resource, directory, *, keywords=(), extra=None, session=None):
    extra = dict(extra or {})
    resource_id, name = resource
    metadata = {'synthetic': True, 'dataset': DATASET, 'source_event_id': source,
        'source_dataset': 'persistent-work-v3' if source.startswith('sim:v3:') else 'legacy-demo',
        'keywords': list(keywords), 'keywords_confirmed': bool(keywords),
        'opencode_session_id': session or ('demo:v4:' + source), 'opencode_directory': directory,
        'resources': [{'id': resource_id, 'name': name, 'path': directory + '/' + extra.get('resource_path', name)}]}
    metadata['keyword_evidence'] = [{'value': word, 'quote': content, 'source': 'authored_scenario_annotation'} for word in keywords]
    metadata.update({key:value for key,value in extra.items() if key in ('template_version','completed_steps','pending_steps')})
    if keywords:
        metadata.update({'input_files': [name]})
    return {'event_id': 'demo:v4:' + source, 'content': content, 'person_refs': people,
        'resource_ids': [resource_id], 'source_type': extra.get('source_type','conversation'),
        'status': extra.get('status','success'), 'tool': extra.get('tool'),
        'occurred_at': occurred, 'observed_at': extra.get('observed_at') or occurred,
        'is_fallback': extra.get('is_fallback',False), 'fallback_reason': extra.get('fallback_reason'),
        'app': 'OpenCode', 'metadata': metadata,
        'curated_preference': extra.get('preference')}


def merged_cases():
    result = []
    for case in CASES:
        events = []
        for index,(date,participants,content,extra) in enumerate(case['events']):
            people = [{'id': PEOPLE[key][0], 'name': PEOPLE[key][1], 'aliases': PEOPLE[key][2], 'role': PEOPLE[key][3]} for key in participants]
            events.append(_event(f'sim:v3:{case["id"]}:{index:02d}',timestamp(date),content,people,case['resource'],case['directory'],
                keywords=[word for word,indices in zip(case['keywords'],NEW_TAG_SOURCES[case['id']]) if index in indices],
                extra={**extra,'observed_at':timestamp(extra.get('observed_at',date))}, session=f'sim:{case["id"]}:session:{index//3+1}'))
        result.append({**deepcopy(case), 'project_aliases':PROJECT_ALIASES[case['project']], 'events':events})
    base = datetime(2026,9,1,9,tzinfo=timezone(timedelta(hours=8)))
    for row in scenarios():
        ident = 'legacy_' + row['id'].replace(':','_')
        directory = '/projects/' + row['id'].split(':')[0] + '/office-handover'
        resource = ('res:legacy:' + row['id'], row['resource'].split('/')[-1])
        events = []
        for index,content in enumerate(row['contents']):
            extra = {}
            if index == 3:
                extra['pending_steps'] = [content]
            if row['key'] == 'delivery' and index in (1,2):
                extra['template_version'] = 'V2' if index==1 else 'V3'
            if row['key'] == 'network' and index==1:
                extra.update({'source_type':'tool','status':'failed','tool':'network-diagnosis',
                    'is_fallback':True,'fallback_reason':'诊断工具失败后的临时 DNS 替代',
                    'preference':{'key':'dns_provider','value':'临时备用解析服务','choice_type':'fallback'}})
            event = _event(f'desktop-rich-v2:{row["id"]}:{index}',(base+timedelta(days=row['day']+index)).isoformat(),
                content,[{'id':LEGACY_PEOPLE[row['person']],'name':row['person'],'role':'participant'}],resource,directory,
                keywords=[word for word,indices in zip(KEYWORDS[row['key']],LEGACY_TAG_SOURCES[row['key']]) if index in indices],extra=extra,
                session=f'legacy:{row["id"]}:session:{index//2+1}')
            event['metadata']['resources'][0]['aliases'] = [row['resource']]
            event['metadata']['curation'] = 'legacy facts retained; generic self/customer/internal-code tags and ungrounded completed-state defaults removed'
            events.append(event)
        result.append({'id':ident,'title':row['title'],'goal':f'持续推进{row["customer"]}的{row["title"].split(" · ")[-1]}，保留处理依据、当前进展和待确认事项。',
            'project':row['customer'],'directory':directory,'project_aliases':[row['customer'][:2]],'aliases':[],
            'keywords':KEYWORDS[row['key']], 'events':events})
    for index,(title,key,name,person,contents) in enumerate(LEGACY_SCENARIOS):
        target = next(case for case in result if case['id']=='kylin_package') if key=='kylin' else None
        if target:
            project,directory,aliases,keywords = target['project'],target['directory'],['麒麟桌面环境适配'],['麒麟适配','桌面验证']
            new_title = target['title']
        else:
            new_title,project,directory,aliases,keywords = BASIC[key]
        people = [] if person=='self' else [{'id':LEGACY_PEOPLE[person],'name':person,'role':'participant'}]
        events=[]
        for turn,content in enumerate(contents):
            content=content.replace('甲客户','青禾客户').replace('乙客户','恒达客户')
            extra={}
            if key=='acme' and turn in (1,2): extra['template_version']='V2' if turn==1 else 'V3'
            if key=='network' and turn==1:
                extra.update({'is_fallback':True,'fallback_reason':'工具失败后的临时替代',
                    'preference':{'key':'dns_provider','value':'临时备用 DNS','choice_type':'fallback'}})
            if key=='weekly' and turn in (0,1):
                extra['preference']={'key':'output_preference','value':'中文，结论与行动项优先' if turn==0 else '本次会议英文摘要',
                    'choice_type':'explicit' if turn==0 else 'temporary', **({'valid_to':'2026-09-07T23:59:59+08:00'} if turn==1 else {})}
            events.append(_event(f'desktop-demo:{key}:{turn}',(datetime(2026,9,7,9+turn,tzinfo=timezone(timedelta(hours=8))) if key=='weekly' else datetime(2026,8,20+index,9+turn,tzinfo=timezone(timedelta(hours=8)))).isoformat(),
                content,people,('res:legacy-basic:'+key,name.replace('甲客户','青禾客户').replace('乙客户','恒达客户')),directory,
                keywords=keywords if turn==0 else (),extra=extra,session=f'legacy:basic:{key}:session:{turn//2+1}'))
        if target:
            target['events'] = events + target['events']
            target['aliases'].extend(aliases)
        else:
            result.append({'id':'legacy_basic_'+key,'title':new_title,'goal':BASIC_GOALS[key],
                'project':project,'directory':directory,'project_aliases':aliases,'aliases':[title],'keywords':keywords,'events':events})
    return result


def merge_preview(service):
    cases = merged_cases()
    known = {event['metadata']['source_event_id'] for case in cases for event in case['events']}
    archives=[]
    for topic in service.store.list_topics(service.user_id):
        if topic.state=='archived' or topic.metadata.get('curated_dataset')==DATASET:
            continue
        events=service.store.list_events(topic.topic_id)
        if events and all(event.event_id in known and event.metadata.get('synthetic') is True for event in events):
            archives.append({'topic_id':topic.topic_id,'title':topic.title,'events':len(events),'revision':topic.revision})
    existing={topic.metadata.get('curation_key') for topic in service.store.list_topics(service.user_id) if topic.metadata.get('curated_dataset')==DATASET}
    return {'dataset':DATASET,'topics':len(cases),'events':sum(len(case['events']) for case in cases),
            'new_topics':sum(case['id'] not in existing for case in cases),'archive_topics':archives,
            'source_events':len(known),'identity_merges':[{'from':'desktop-demo:kylin','to':'kylin_package','reason':'same persistent desktop adaptation and delivery task'}]}


def seed_merged_demo(service, *, archive_legacy=True):
    # Bulk admission is already based on reviewed scenario identities. Encode
    # each completed prototype once, rather than encoding every source event.
    encoder=service.core.embed
    service.core.embed=None
    try:
        result=_seed_merged_demo(service,archive_legacy=archive_legacy)
    finally:
        service.core.embed=encoder
    if encoder:
        targets=[topic_id for topic_id in result['topic_ids'].values() if service.store.get_topic(topic_id).vector is None]
        if targets: result['index']=service.reindex(topic_ids=targets)
    return result


def _seed_merged_demo(service, *, archive_legacy=True):
    preview=merge_preview(service)
    mapping={}
    created=0
    skipped=[]
    for case in merged_cases():
        topic=next((topic for topic in service.store.list_topics(service.user_id)
                    if topic.metadata.get('curated_dataset')==DATASET and topic.metadata.get('curation_key')==case['id']),None)
        if topic is None:
            if any(service.store.get_event(event['event_id']) for event in case['events']):
                skipped.append(case['id'])
                continue
            visible=[event for event in case['events'] if not _forgotten_source(service,event['metadata']['source_event_id'])]
            if not visible:
                skipped.append(case['id'])
                continue
            topic=service.core.create_topic(user_id=service.user_id,title=case['title'],goal=case['goal'],
                metadata={'synthetic':True,'curated_dataset':DATASET,'curation_key':case['id'],
                    'identity_confirmed':True,'identity_goal':case['goal'],'identity_aliases':case['aliases'],
                    'project_name':case['project'],'project_ref':case['directory'],'project_aliases':case['project_aliases']})
        mapping[case['id']]=topic.topic_id
        for event in case['events']:
            if _forgotten_source(service,event['metadata']['source_event_id']):
                continue
            record=deepcopy(event)
            preference=record.pop('curated_preference',None)
            source=service.store.get_event(record['metadata']['source_event_id'])
            if source:
                record['metadata']['legacy_source_times']={'occurred_at':source.occurred_at,'observed_at':source.observed_at}
            result=service.ingest({**record,'topic_id':topic.topic_id,'idempotency_key':record['event_id']})
            if result.get('duplicate'): continue
            created+=1
            if preference:
                service.update_preference({**preference,'scope_type':'topic','scope_id':topic.topic_id,
                    'evidence_event_id':record['event_id'],'observed_at':record['observed_at']})
    if archive_legacy:
        with service.store.transaction():
            for item in preview['archive_topics']:
                topic=service._topic(item['topic_id'])
                topic.state='archived'
                topic.metadata['superseded_by_dataset']=DATASET
                topic.vector=None
                topic.revision+=1
                service.store.save_topic(topic)
                for event_id in topic.event_ids:
                    service.store.conn.execute("UPDATE mp_preferences SET status='superseded' WHERE user_id=? AND evidence_event_id=?",(service.user_id,event_id))
                    service.store.conn.execute("UPDATE mp_knowledge SET status='superseded' WHERE user_id=? AND evidence_event_id=?",(service.user_id,event_id))
    service.core._rebuild_graph()
    return {**preview,'topic_ids':mapping,'events_created':created,'synthetic':True,'independent_human_review':False,
            'sessions':len({event['metadata']['opencode_session_id'] for case in merged_cases() for event in case['events']}),
            'people':len({person['id'] for case in merged_cases() for event in case['events'] for person in event['person_refs']}),
            'archived_topics':len(preview['archive_topics']) if archive_legacy else 0,'skipped_modified_or_forgotten_cases':skipped}


def _forgotten_source(service, event_id):
    if service._hidden_event(event_id): return True
    source=service.store.get_event(event_id)
    if source and source.content=='[FORGOTTEN]': return True
    topic_id=service.store.event_topic(event_id) if source else None
    return bool(topic_id and service.governance.is_tombstoned(target_type='topic',target_id=topic_id))


def ensure_desktop_demo(service):
    """New installations start with v4; existing workspaces require explicit import."""
    conn=service.store.conn
    conn.execute('CREATE TABLE IF NOT EXISTS desktop_seed(version INTEGER PRIMARY KEY)')
    if conn.execute('SELECT 1 FROM desktop_seed LIMIT 1').fetchone(): return
    seed_merged_demo(service,archive_legacy=False)
    with service.store.transaction():
        conn.execute('INSERT INTO desktop_seed VALUES(4)')


def merged_questions():
    result=[{**query,'evidence_ids':['demo:v4:'+event_id for event_id in query['evidence_ids']]} for query in questions()]
    for row in scenarios():
        for index,query in enumerate(row['queries']):
            result.append({'id':'legacy:'+row['id']+':q'+str(index),'kind':'legacy_cross_session' if index==2 else 'legacy_detail',
                'query':query,'gold_topic':'legacy_'+row['id'].replace(':','_'),
                'evidence_ids':['demo:v4:desktop-rich-v2:'+row['id']+':'+str(turn) for turn in LEGACY_QUERY_EVIDENCE[row['key']][index]],
                'context':{'reference_time':(datetime(2026,9,1,9,tzinfo=timezone(timedelta(hours=8)))+timedelta(days=row['day']+4)).isoformat()}})
    for key,query,indices in [
        ('acme','青禾客户交付报告当前应使用哪个模板？',[2]),
        ('weekly','研发周报的中文约定会被一次英文摘要要求覆盖吗？',[0,1]),
        ('network','桌面网络排查用过备用 DNS，那是长期偏好吗？',[1,2]),
        ('beta','恒达库存接口联调目前还在等什么？',[2]),
        ('privacy','会议隐私整理中联系方式为什么要和流程分开？',[1]),
        ('kylin','麒麟桌面早期验证是否已经证明了目标机 embedding SDK 可用？',[2]),
    ]:
        result.append({'id':'legacy-basic:'+key,'kind':'legacy_boundary','query':query,
            'gold_topic':'kylin_package' if key=='kylin' else 'legacy_basic_'+key,
            'evidence_ids':[f'demo:v4:desktop-demo:{key}:{index}' for index in indices], 'context':{}})
    return result
