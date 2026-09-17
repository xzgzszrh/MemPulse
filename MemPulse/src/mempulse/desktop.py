"""Desktop transport. One local facade, JSON-lines IPC, no network listener in packaged apps."""
from __future__ import annotations
import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from .facade import get_facade
from .merged_demo import ensure_desktop_demo


def load_model_config(data_dir, bundled_model=None):
    """An explicit user configuration always takes precedence over bundled FP32."""
    path = Path(data_dir) / 'model.json'
    if path.exists():
        return json.loads(path.read_text())
    if bundled_model is not None and (Path(bundled_model) / 'encoder/model-fp32.onnx').is_file():
        return {'model_dir': str(Path(bundled_model).resolve()), 'precision': 'fp32'}
    return None


class DesktopService:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.settings_path = self.data_dir / 'desktop-settings.json'
        settings = json.loads(self.settings_path.read_text()) if self.settings_path.exists() else {}
        self.workspace = settings.get('workspace', 'demo')
        if self.workspace not in ('demo', 'personal'):
            self.workspace = 'demo'
        self.service = None
        self._open()

    def _open(self):
        bundled = Path(sys.executable).parent / 'models/tide' if getattr(sys, 'frozen', False) else None
        model_config = load_model_config(self.data_dir, bundled)
        self.service = get_facade(self.data_dir / ('desktop-demo.sqlite3' if self.workspace == 'demo' else 'memory.sqlite3'), model_config=model_config)
        if self.workspace == 'demo':
            ensure_desktop_demo(self.service)
        from .operations import MemoryOperations
        self.operations = MemoryOperations(self)

    def governance(self):
        result = {}
        for key, table in [('preferences', 'mp_preferences'), ('knowledge', 'mp_knowledge'), ('checkpoints', 'mp_checkpoints'), ('receipts', 'mp_tombstones')]:
            scope = 'requested_by' if key == 'receipts' else 'user_id'
            rows = self.service.store.conn.execute(f'SELECT * FROM {table} WHERE {scope}=? ORDER BY created_at DESC LIMIT 200', (self.service.user_id,))
            result[key] = []
            for row in rows:
                item = dict(row)
                for field in list(item):
                    if field.endswith('_json'):
                        item[field[:-5]] = json.loads(item.pop(field))
                result[key].append(item)
        return result

    def events(self, limit=100):
        visible = {t['topic_id']: t for t in self.service.list_topics()['topics']}
        rows = self.service.store.conn.execute('SELECT e.payload, et.topic_id FROM events e JOIN event_topics et ON e.id=et.event_id WHERE e.user_id=? ORDER BY e.occurred_at DESC', (self.service.user_id,))
        events = []
        for row in rows:
            event = json.loads(row['payload'])
            if row['topic_id'] not in visible or self.service._hidden_event(event['event_id']):
                continue
            events.append({**event, 'topic_id': row['topic_id'], 'topic_title': visible[row['topic_id']]['title']})
            if len(events) >= limit:
                break
        return events

    def dispatch(self, method, params=None):
        with self.lock, self.service.store._lock:
            return self._dispatch(method, params or {})

    def _dispatch(self, method, params):
        service = self.service
        if method == 'propose_operation':
            return self.operations.propose(params['kind'], params.get('payload') or {}, params.get('origin', 'agent'))
        if method == 'pending_operations':
            return {'operations': self.operations.pending()}
        if method == 'operation':
            return self.operations.get(params['operation_id'])
        if method == 'confirm_operation':
            return self.operations.confirm(params['operation_id'], params['fingerprint'])
        if method == 'reject_operation':
            return self.operations.reject(params['operation_id'])
        if method == 'capture_event':
            return self.operations.capture(params)
        if method == 'capture_inbox':
            rows = self.service.store.conn.execute("SELECT event_id,payload,project_ref FROM mp_capture_inbox WHERE user_id=? AND session_id=? AND status='pending' ORDER BY created_at LIMIT 100",
                (service.user_id, params.get('session_id', ''))).fetchall()
            return {'events': [{'event_id': row['event_id'], 'project_ref': row['project_ref'],
                               **json.loads(row['payload'])} for row in rows]}
        if method == 'configure_model':
            config = {'model_dir': str(Path(params['model_dir']).expanduser().resolve()), 'precision': params.get('precision', 'fp32')}
            result = service.configure_model(**config)
            temporary = self.data_dir / 'model.json.tmp'
            temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2))
            temporary.replace(self.data_dir / 'model.json')
            return result
        if method == 'enrich_demo':
            if self.workspace != 'demo':
                raise ValueError('demo enrichment requires the demo workspace')
            from .merged_demo import seed_merged_demo
            return seed_merged_demo(service)
        if method == 'health':
            return service.health()
        if method == 'bootstrap':
            topics = service.list_topics()['topics']
            return {'topics': topics, 'events': self.events(), 'governance': self.governance(),
                    'bindings': self.operations.bindings(),
                    'health': service.health(), 'workspace': self.workspace,
                    'stats': {'topics': len(topics), 'events': sum(len(t['event_ids']) for t in topics), 'tags': len({tag['canonical'] for t in topics for tag in t['tags']})}}
        if method == 'switch_workspace':
            mode = params.get('workspace')
            if mode not in ('demo', 'personal'):
                raise ValueError('未知工作区')
            service.store.close()
            self.workspace = mode
            self._open()
            self.settings_path.write_text(json.dumps({'workspace': mode}))
            return self._dispatch('bootstrap', {})
        if method == 'search':
            started = time.perf_counter()
            result = service.search(params.get('query', ''), **{key: value for key, value in params.items() if key != 'query'})
            return {**result, 'elapsed_ms': round((time.perf_counter()-started)*1000, 2)}
        if method == 'list_topics':
            return service.list_topics()
        if method == 'restore':
            return service.restore(**params)
        if method == 'ingest':
            return service.ingest(params)
        if method == 'preference':
            return service.update_preference(params)
        if method == 'knowledge':
            return service.knowledge(params)
        if method == 'graph':
            return self.graph()
        if method == 'session_topic':
            return self.session_topic(params.get('session_id', ''), params.get('project_ref'))
        if method == 'rename_topic':
            return self.rename_topic(params.get('topic_id', ''), params.get('title', ''))
        if method == 'agent_context':
            return self.agent_context(params.get('query', ''), session_id=params.get('session_id'),
                                      topic_id=params.get('topic_id'), limit=params.get('limit', 6), project_ref=params.get('project_ref'))
        methods = {'checkpoint': service.checkpoint, 'forget': service.forget, 'forget_field': service.forget_field,
                   'merge': service.merge_topics, 'split': service.split_topic, 'move': service.move_event,
                   'relations': service.query_relations, 'query_relations': service.query_relations, 'resolve': service.resolve, 'reindex': service.reindex}
        if method in methods:
            return methods[method](**params)
        if method == 'worker':
            from .worker import OutboxWorker
            return OutboxWorker(service.store, service).drain()
        raise ValueError('不支持的桌面操作：'+str(method))

    def graph(self):
        return project_graph(self.service)

    def close(self):
        self.service.store.close()

    def session_topic(self, session_id, project_ref=None):
        """Only a user-confirmed binding can select a session's active task.

        Legacy event metadata is retained as provenance, never silently promoted
        to an identity decision. Several sessions may bind the same topic.
        """
        topic = self.operations.bound(session_id, project_ref) if session_id else None
        if topic:
            return {'topic_id': topic.topic_id, 'title': topic.title, 'state': topic.state,
                    'event_count': len(topic.event_ids), 'binding': 'user_confirmed',
                    'project_ref': topic.metadata.get('project_ref')}
        return {'topic_id': None, 'title': None, 'requires_confirmation': True}

    def rename_topic(self, topic_id, title):
        title = (title or '').strip()
        if not title:
            raise ValueError('话题标题不能为空')
        topic = self.service._topic(topic_id)
        if topic.title == title:
            return {'topic_id': topic.topic_id, 'title': topic.title, 'changed': False}
        if topic.summary == topic.title:
            topic.summary = title
        topic.title = title[:120]
        topic.revision += 1
        self.service.core.embed_topic(topic)
        self.service.store.save_topic(topic)
        self.service.core.graph.upsert_topic(topic)
        return {'topic_id': topic.topic_id, 'title': topic.title, 'changed': True}

    def active_preferences(self, topic_id=None, limit=12):
        """Durable CPR choices that should shape an answer right now: explicit
        promotions and safety constraints, newest per key/scope, still valid."""
        rows = self.service.store.conn.execute(
            "SELECT pref_key FROM mp_preferences WHERE user_id=? AND status IN ('active','constraint','transient') "
            "GROUP BY pref_key ORDER BY MAX(created_at) DESC",
            (self.service.user_id,),
        ).fetchall()
        result = []
        for row in rows:
            resolved = self.service.resolve_preference(key=row['pref_key'], topic_id=topic_id, app_id='OpenCode')
            if not resolved['found']:
                continue
            source = resolved['source']
            result.append({'key': row['pref_key'], 'value': resolved['value'],
                           'scope_type': source['scope']['type'], 'scope_id': source['scope']['id'],
                           'choice_type': source['choice_type']})
            if len(result) >= limit:
                break
        return result

    def agent_context(self, query, session_id=None, topic_id=None, limit=6, project_ref=None):
        """One round trip per turn for the host agent: topic routing for the request,
        the restore contract of the session's own topic, cross-topic evidence hits and
        the preferences in force. Everything returned is evidence, not instructions."""
        started = time.perf_counter()
        service = self.service
        query = (query or '').strip()
        limit = max(1, min(int(limit or 6), 20))
        bound = None
        if topic_id:
            try:
                topic = service._topic(topic_id)
                bound = {'topic_id': topic.topic_id, 'title': topic.title, 'state': topic.state,
                         'event_count': len(topic.event_ids)}
            except KeyError:
                bound = None
        if bound is None and session_id:
            found = self.session_topic(session_id, project_ref)
            bound = found if found.get('topic_id') else None

        contract = None
        if bound:
            pack = service.restore(topic_id=bound['topic_id'])
            checkpoint = (pack.get('checkpoint') or {}).get('checkpoint') or {}
            checkpoint_payload = checkpoint.get('payload') or {}
            contract = {
                'topic_id': pack.get('topic_id'),
                'title': pack.get('title'),
                'overview': pack.get('overview'),
                'fields': [f for f in pack.get('fields', []) if f.get('status') == 'present'],
                'missing': pack.get('missing', []),
                'checkpoint': checkpoint_payload.get('overview') or checkpoint_payload.get('summary') or checkpoint.get('id'),
                'events': [{'event_id': e.get('event_id'), 'occurred_at': e.get('occurred_at'),
                            'source_type': e.get('source_type'), 'status': e.get('status'),
                            'content': (e.get('content') or '')[:240]} for e in pack.get('events', [])[-4:]],
            }

        route = None
        clarification = None
        hits = []
        topics = service.list_topics()['topics']
        if query:
            visible = {t['topic_id']: t for t in topics}
            contract_events = {event['event_id'] for event in (contract or {}).get('events', [])}
            found = service.search(query, limit=limit * 4)
            route = found.get('route')
            if found.get('needs_clarification'):
                clarification = {key: found.get('plan', {}).get(key, []) for key in ('ambiguous_entities', 'unresolved_entities')}
            candidates = []
            for row in found['results']:
                if row.get('event_id') in contract_events or row.get('topic_id') not in visible:
                    continue
                metadata = row.get('metadata') or {}
                if metadata.get('synthetic') and self.workspace != 'demo':
                    continue
                candidates.append(row)
            # Conversation and configuration evidence is what a new turn needs first;
            # raw tool output is long and only wins when nothing else matched.
            ordered = [r for r in candidates if r.get('source_type') != 'tool'] + \
                      [r for r in candidates if r.get('source_type') == 'tool']
            for row in ordered[:limit]:
                hits.append({
                    'event_id': row.get('event_id'),
                    'topic_id': row.get('topic_id'),
                    'topic_title': visible[row['topic_id']]['title'],
                    'occurred_at': row.get('occurred_at'),
                    'source_type': row.get('source_type'),
                    'status': row.get('status'),
                    'score': row.get('score'),
                    'synthetic': bool((row.get('metadata') or {}).get('synthetic')),
                    'content': (row.get('content') or '')[:240],
                })
            if route:
                titles = {t['topic_id']: t['title'] for t in topics}
                for candidate in route.get('candidates', []):
                    candidate.setdefault('title', titles.get(candidate.get('topic_id')))

        return {
            'query': query,
            'route': route,
            'clarification': clarification,
            'session_topic': bound,
            'contract': contract,
            'hits': hits,
            'preferences': self.active_preferences(topic_id=bound['topic_id'] if bound else None),
            'stats': {'topics': len(topics), 'events': sum(len(t['event_ids']) for t in topics)},
            'workspace': self.workspace,
            'embedding_backend': 'unloaded' if not service.core.embed else service.core.model_rev,
            'elapsed_ms': round((time.perf_counter() - started) * 1000, 2),
        }


def project_graph(service):
    topics = service.list_topics()['topics']
    topics = [{**topic, 'tags': [tag for tag in topic.get('tags', [])
              if tag.get('status', 'accepted') == 'accepted' and tag['kind'] in ('person', 'resource', 'keyword')]}
              for topic in topics]
    nodes = []
    edges = []
    node_set = set()

    for t in topics:
        nodes.append({
            'id': t['topic_id'],
            'label': t['title'],
            'type': 'topic',
            'state': t.get('state', 'active'),
            'revision': t.get('revision', 1),
            'goal': t.get('goal', ''),
            'summary': t.get('summary', ''),
            'event_count': len(t.get('event_ids', [])),
            'tags': [tag.get('canonical') for tag in t.get('tags', [])],
            'size': max(22, min(42, 20 + len(t.get('event_ids', [])) * 2)),
        })
        node_set.add(t['topic_id'])

    tag_counts = {}
    tag_info = {}
    for t in topics:
        for tag in t.get('tags', []):
            can = tag['canonical']
            tag_counts[can] = tag_counts.get(can, 0) + 1
            tag_info[can] = tag

    for can, count in tag_counts.items():
        tag = tag_info[can]
        kind = tag.get('kind', 'kw')
        val = tag.get('label') or tag.get('value', can)
        nodes.append({
            'id': can,
            'label': val,
            'type': 'entity',
            'kind': kind,
            'canonical': can,
            'degree': count,
            'size': max(14, min(30, 12 + count * 4)),
        })
        node_set.add(can)

    edge_id = 0
    for t in topics:
        for tag in t.get('tags', []):
            can = tag['canonical']
            if can in node_set:
                edges.append({
                    'id': f'e_{edge_id}',
                    'source': t['topic_id'],
                    'target': can,
                    'type': 'topic_tag',
                    'kind': tag.get('kind', 'kw'),
                    'label': tag.get('kind', ''),
                })
                edge_id += 1

    topic_ids = [t['topic_id'] for t in topics]
    for i in range(len(topic_ids)):
        for j in range(i + 1, len(topic_ids)):
            t1, t2 = topic_ids[i], topic_ids[j]
            tags1 = set(tag['canonical'] for tag in topics[i].get('tags', []))
            tags2 = set(tag['canonical'] for tag in topics[j].get('tags', []))
            shared = tags1.intersection(tags2)
            if shared:
                edges.append({
                    'id': f'e_{edge_id}',
                    'source': t1,
                    'target': t2,
                    'type': 'topic_topic',
                    'weight': len(shared),
                    'shared': list(shared),
                    'label': f'{len(shared)} 个共同实体',
                })
                edge_id += 1

    try:
        rows = service.store.conn.execute(
            'SELECT p1.person_id AS a, p2.person_id AS b, count(*) AS cnt '
            'FROM participation p1 JOIN participation p2 ON p1.event_id=p2.event_id '
            'WHERE p1.person_id < p2.person_id GROUP BY p1.person_id, p2.person_id'
        ).fetchall()
        for r in rows:
            pa = f"person:{r['a']}"
            pb = f"person:{r['b']}"
            if pa in node_set and pb in node_set:
                edges.append({
                    'id': f'e_{edge_id}',
                    'source': pa,
                    'target': pb,
                    'type': 'co_occurrence',
                    'weight': r['cnt'],
                    'label': f"{r['cnt']} 次协同",
                })
                edge_id += 1
    except Exception:
        pass

    return {
        'nodes': nodes,
        'edges': edges,
        'stats': {
            'topics': len(topics),
            'entities': len(tag_counts),
            'relations': len(edges),
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', required=True)
    args = parser.parse_args()
    desktop = DesktopService(args.data_dir)
    try:
        for line in sys.stdin:
            request = None
            try:
                request = json.loads(line)
                result = desktop.dispatch(request['method'], request.get('params'))
                response = {'id': request.get('id'), 'ok': True, 'data': result}
            except Exception as exc:
                response = {'id': request.get('id') if isinstance(request, dict) else None, 'ok': False, 'error': str(exc)}
            print(json.dumps(response, ensure_ascii=False), flush=True)
    finally:
        desktop.close()


if __name__ == '__main__':
    main()
