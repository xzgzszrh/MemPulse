"""Topic-first evidence retrieval. Identity vectors never stand in for facts.

Structured person/resource/time constraints are exact filters. TIDE ranks task
prototypes; FTS and event evidence select the details inside candidate topics.
Ambiguous identities remain separate groups and never change write bindings.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import re

from .sqlite_store import fts_tokens


def plan_query(service, query, context=None):
    context = dict(context or {})
    topics = [topic for topic in service.store.list_topics(service.user_id) if topic.state != 'archived']
    named_projects = {topic.metadata.get('project_ref') for topic in topics
                      if any(len(str(name)) >= 2 and str(name) in query for name in
                             [topic.metadata.get('project_name', ''), *topic.metadata.get('project_aliases', [])])}
    named_projects.discard(None)
    if len(named_projects) == 1:
        context['project_ref'] = next(iter(named_projects))
    people = set(context.get('person_ids') or [])
    resources = set(context.get('resource_ids') or [])
    ambiguities = []
    unresolved = []
    aliases = service.store.conn.execute('SELECT entity_kind,alias,canonical,source_event_id FROM aliases WHERE user_id=?', (service.user_id,)).fetchall()
    matches = {}
    for row in aliases:
        requested = context.get('person_names' if row['entity_kind'] == 'person' else 'resource_names', [])
        if len(row['alias']) < 2 or (row['alias'] not in query and row['alias'] not in requested):
            continue
        if row['source_event_id'] and service._hidden_event(row['source_event_id']):
            continue
        source_topic_id=service.store.event_topic(row['source_event_id']) if row['source_event_id'] else None
        source_topic=service.store.get_topic(source_topic_id) if source_topic_id else None
        if source_topic and source_topic.state=='archived':
            continue
        if context.get('project_ref') and row['source_event_id']:
            topic_id = service.store.event_topic(row['source_event_id'])
            topic = service.store.get_topic(topic_id) if topic_id else None
            if not topic or topic.metadata.get('project_ref') != context['project_ref']:
                continue
        matches.setdefault((row['entity_kind'], row['alias']), set()).add(row['canonical'])
    for (kind, alias), identities in matches.items():
        if any(other_kind == kind and len(other) > len(alias) and alias in other for other_kind, other in matches):
            continue
        if len(identities) > 1:
            ambiguities.append({'kind': kind, 'alias': alias, 'candidates': sorted(identities),
                'options':[{'id':identity,'aliases':sorted({row['alias'] for row in aliases if row['entity_kind']==kind and row['canonical']==identity and row['alias']!=alias})[:4]}
                           for identity in sorted(identities)]})
            continue
        (people if kind == 'person' else resources).update(identities)
    for kind, names in [('person', context.get('person_names', [])), ('resource', context.get('resource_names', []))]:
        for name in names:
            if (kind, name) not in matches:
                unresolved.append({'kind': kind, 'name': name})
    name = re.match(r'^([\u4e00-\u9fff]{2,4})(?:上次|之前|最近|签过|参与过|负责过|审核过)', query)
    if name and name[1] not in ('我们', '你们', '他们', '用户') and not any(kind == 'person' and alias == name[1] for kind, alias in matches):
        unresolved.append({'kind': 'person', 'name': name[1]})
    organisation = re.match(r'^([\u4e00-\u9fff]{2,10}(?:医院|大学|公司|工厂|实验室|图书馆|展馆|档案馆|教学楼))', query)
    if organisation and not re.search(r'这个|那个|哪些|所有|某个', organisation[1]):
        known_names = [str(value) for topic in topics for value in [topic.metadata.get('project_name', ''), *topic.metadata.get('project_aliases', [])] if value]
        if not any(organisation[1] in value or value in organisation[1] for value in known_names):
            unresolved.append({'kind': 'project', 'name': organisation[1]})
    zone = ZoneInfo(context.get('timezone', 'Asia/Shanghai'))
    now = datetime.fromisoformat(str(context.get('reference_time') or datetime.now(zone).isoformat()).replace('Z', '+00:00'))
    if now.tzinfo is None:
        now = now.replace(tzinfo=zone)
    now = now.astimezone(zone)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end = None
    explicit = re.findall(r'(?:(\d{4})[-年])?(\d{1,2})[-月](\d{1,2})(?:日|号)?', re.sub(r'\s+', '', query))
    if explicit:
        dates = [day.replace(year=int(year or now.year), month=int(month), day=int(date)) for year, month, date in explicit[:2]]
        start, end = dates[0], dates[-1] + timedelta(days=1)
    elif '前天' in query:
        start, end = day - timedelta(days=2), day - timedelta(days=1)
    elif '昨天' in query:
        start, end = day - timedelta(days=1), day
    elif '上周' in query:
        end = day - timedelta(days=day.weekday())
        start = end - timedelta(days=7)
    elif '本周' in query or '这周' in query:
        start, end = day - timedelta(days=day.weekday()), day + timedelta(days=1)
    comparison = bool(re.search(r'旧稿|旧邮件|旧版本|覆盖|改回', query))
    axis = context.get('time_axis') or ('observed_at' if re.search(r'导入|归档|收到', query) else 'occurred_at')
    if axis not in ('observed_at', 'occurred_at'):
        raise ValueError('unsupported time axis')
    return {'person_ids': sorted(people), 'resource_ids': sorted(resources), 'ambiguous_entities': ambiguities,
            'unresolved_entities': unresolved, 'time_axis': axis, 'version_comparison': comparison,
            'from_time': context.get('from_time') or (start.isoformat() if start and not comparison else None),
            'to_time': context.get('to_time') or (end.isoformat() if end and not comparison else None),
            'topic_id': context.get('topic_id'), 'project_ref': context.get('project_ref'),
            'enumeration': bool(context.get('enumeration') or re.search(r'全部|所有|哪些|列出|多少|几次', query)),
            'reference_time': now.isoformat()}


def search_evidence(service, query, limit=20, context=None):
    plan = plan_query(service, query, context)
    route = service.resolve(query, context={
        **({'topic_id': plan['topic_id']} if plan['topic_id'] else {}),
        'person_refs': plan['person_ids'], 'resource_ids': plan['resource_ids'],
        'metadata': {'project_ref': plan['project_ref'], 'query': True},
    })
    using_model = bool(service.core.embed and not route.get('embedding_fallback'))
    if plan['ambiguous_entities'] or plan['unresolved_entities']:
        return {'query': query, 'results': [], 'groups': [], 'truncated': False, 'complete': False,
                'backend': 'topic_first_tide' if using_model else 'topic_first_fts',
                'route': {**route, 'route': 'AMBIGUOUS', 'topic_id': None}, 'plan': plan,
                'needs_clarification': True}
    # Structural enumeration is not constrained by the vector candidate Top-K.
    structural = bool(plan['person_ids'] or plan['resource_ids'] or plan['from_time'] or plan['to_time'])
    candidates = [row['topic_id'] for row in route.get('ranked_candidates', [])[:5]]
    if plan['topic_id']:
        service._topic(plan['topic_id'])
        candidates = [plan['topic_id']]
    if structural and plan['enumeration'] and not plan['topic_id']:
        candidates = [topic['topic_id'] for topic in service.list_topics()['topics']]
    selected = []
    for topic_id in candidates:
        try:
            topic = service._topic(topic_id)
        except KeyError:
            continue
        if plan['project_ref'] and topic.metadata.get('project_ref') != plan['project_ref']:
            continue
        selected.append(topic_id)
    if not selected:
        return {'query': query, 'results': [], 'groups': [], 'route': route, 'plan': plan,
                'complete': True, 'truncated': False, 'backend': 'topic_first_tide' if using_model else 'topic_first_fts'}
    clauses = ['e.user_id=?', 'x.topic_id IN (' + ','.join('?' for _ in selected) + ')']
    parameters = [service.user_id, *selected]
    for person in plan['person_ids']:
        clauses.append("EXISTS(SELECT 1 FROM mp_participation p WHERE p.event_id=e.id AND p.user_scope=e.user_id AND p.person_id=? AND p.status='confirmed')")
        parameters.append(person.removeprefix('person:').split('@')[0])
    for resource in plan['resource_ids']:
        clauses.append("EXISTS(SELECT 1 FROM json_each(e.payload,'$.resource_ids') r WHERE r.value=?)")
        parameters.append(resource)
    time_field = "json_extract(e.payload,'$.observed_at')" if plan['time_axis'] == 'observed_at' else 'e.occurred_at'
    if plan['from_time']:
        clauses.append('julianday(' + time_field + ')>=julianday(?)')
        parameters.append(plan['from_time'])
    if plan['to_time']:
        clauses.append('julianday(' + time_field + ')<julianday(?)')
        parameters.append(plan['to_time'])
    rows = service.store.conn.execute('SELECT e.payload,x.topic_id FROM events e JOIN event_topics x ON x.event_id=e.id WHERE '
        + ' AND '.join(clauses) + ' ORDER BY e.occurred_at DESC,e.id LIMIT 1001', parameters).fetchall()
    events = [{**json.loads(row['payload']), 'topic_id': row['topic_id']} for row in rows]
    events = [event for event in events if not service._hidden_event(event['event_id'])]
    terms = set(fts_tokens(query))
    scores = {row['topic_id']: row['score'] for row in route.get('ranked_candidates', [])}
    for event in events:
        overlap = terms & set(fts_tokens(event['content']))
        event['evidence_score'] = len(overlap) / max(1, len(terms))
        event['topic_score'] = scores.get(event['topic_id'], 0)
        event['score'] = event['evidence_score'] + 0.15 * event['topic_score']
        event['retrieval_policy'] = 'topic_first_evidence'
    # With exact structural filters, zero lexical overlap is still real evidence.
    relevant = events if structural or plan['topic_id'] else [event for event in events if event['evidence_score'] > 0]
    if not relevant and using_model and events:
        # Cross-language requests can have zero FTS overlap. Return bounded raw
        # evidence from the first semantic task candidate, explicitly labelled;
        # this still does not establish an identity or mutate its binding.
        semantic = next((candidate['topic_id'] for candidate in route.get('ranked_candidates', [])
                         if candidate['features']['D'] > 0 and candidate['topic_id'] in selected), None)
        relevant = [event for event in events if event['topic_id'] == semantic][:limit]
        for event in relevant:
            event['retrieval_policy'] = 'semantic_topic_candidate_evidence'
    relevant.sort(key=lambda event: (-event['score'], event['event_id']))
    titles = {topic['topic_id']: topic['title'] for topic in service.list_topics()['topics']}
    groups = []
    for topic_id in selected:
        own = [event for event in relevant if event['topic_id'] == topic_id]
        if own:
            groups.append({'topic_id': topic_id, 'title': titles.get(topic_id), 'score': scores.get(topic_id, 0), 'events': own[:limit]})
    # Keep identities explicit in the response. A candidate group is not a binding.
    return {'query': query, 'results': relevant[:limit], 'groups': groups, 'route': route, 'plan': plan,
            'complete': len(rows) <= 1000 and len(relevant) <= limit, 'total_matches': len(relevant),
            'truncated': len(relevant) > limit or len(rows) > 1000,
            'backend': 'topic_first_tide' if using_model else 'topic_first_fts',
            'embedding_role': 'task_identity_candidates_only', 'needs_clarification': not plan['topic_id'] and len(groups) > 1}
