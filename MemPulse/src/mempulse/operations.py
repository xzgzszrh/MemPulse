"""Durable, reviewable desktop operations. Capture never creates a task topic.

The Electron gateway only exposes propose/read. Confirmation is a separate
renderer IPC action; model-supplied `confirmed` flags have no meaning here.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from .models import utc_now

KINDS = {'create_topic', 'bind_topic', 'remember', 'rename_topic', 'checkpoint',
         'forget', 'forget_field', 'move', 'merge', 'split', 'update_tags', 'import_demo'}


class MemoryOperations:
    def __init__(self, desktop):
        self.desktop = desktop
        self.service = desktop.service
        self.store = self.service.store
        self.store.conn.executescript('''
        CREATE TABLE IF NOT EXISTS mp_memory_operations (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL,
          payload TEXT NOT NULL, preview TEXT NOT NULL, fingerprint TEXT NOT NULL,
          status TEXT NOT NULL, result TEXT, error TEXT, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, origin TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS mp_session_bindings (
          user_id TEXT NOT NULL, session_id TEXT NOT NULL, project_ref TEXT NOT NULL,
          topic_id TEXT NOT NULL REFERENCES topics(id), operation_id TEXT NOT NULL,
          confirmed_at TEXT NOT NULL, PRIMARY KEY(user_id,session_id));
        CREATE TABLE IF NOT EXISTS mp_capture_inbox (
          event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, session_id TEXT NOT NULL,
          project_ref TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS mp_operations_pending ON mp_memory_operations(user_id,status,created_at);
        CREATE INDEX IF NOT EXISTS mp_inbox_session ON mp_capture_inbox(user_id,session_id,status);
        ''')

    def get(self, operation_id):
        row = self.store.conn.execute('SELECT * FROM mp_memory_operations WHERE id=? AND user_id=?',
                                      (operation_id, self.service.user_id)).fetchone()
        if row is None:
            raise KeyError('operation not found')
        return {**dict(row), 'payload': json.loads(row['payload']), 'preview': json.loads(row['preview']),
                'result': json.loads(row['result']) if row['result'] else None}

    def pending(self):
        rows = self.store.conn.execute("SELECT id FROM mp_memory_operations WHERE user_id=? AND status='pending' ORDER BY created_at LIMIT 50",
                                      (self.service.user_id,)).fetchall()
        return [self.get(row['id']) for row in rows]

    def bindings(self):
        return [dict(row) for row in self.store.conn.execute('SELECT * FROM mp_session_bindings WHERE user_id=?', (self.service.user_id,))
                if not self.service.governance.is_tombstoned(target_type='topic', target_id=row['topic_id'])
                and self.store.get_topic(row['topic_id']).state != 'archived']

    def bound(self, session_id, project_ref=None):
        row = self.store.conn.execute('SELECT * FROM mp_session_bindings WHERE user_id=? AND session_id=?',
                                      (self.service.user_id, session_id)).fetchone()
        if not row or (project_ref is not None and row['project_ref'] != project_ref):
            return None
        try:
            topic=self.service._topic(row['topic_id'])
            return topic if topic.state != 'archived' else None
        except KeyError:
            return None

    def capture(self, params):
        event = self.service.normalize_event(params)
        session = event.session_id or str(event.metadata.get('opencode_session_id') or '')
        project = str(event.metadata.get('opencode_directory') or '')
        if not session:
            raise ValueError('captured events require a source session')
        # A session is transport provenance, never authority to invent an identity.
        event.topic_hint = None
        event.metadata['keywords'] = []
        event.metadata.pop('keyword_candidates', None)
        event.metadata['tag_generation'] = 'capture_only'
        for key in ('force_new', 'title', 'creation_authority'):
            event.metadata.pop(key, None)
        if self.store.get_event(event.event_id):
            return {'event_id': event.event_id, 'status': 'already_recorded', 'duplicate': True}
        previous = self.store.conn.execute('SELECT status FROM mp_capture_inbox WHERE event_id=?', (event.event_id,)).fetchone()
        if previous:
            return {'event_id': event.event_id, 'status': previous['status'], 'duplicate': True}
        topic = self.bound(session, project)
        with self.store.transaction():
            if topic:
                result = self.service.ingest({**event.to_dict(), 'topic_id': topic.topic_id})
                return {**result, 'status': 'attached', 'binding': 'user_confirmed'}
            self.store.conn.execute('INSERT INTO mp_capture_inbox VALUES(?,?,?,?,?,?,?)',
                                   (event.event_id, self.service.user_id, session, project,
                                    json.dumps(event.to_dict(), ensure_ascii=False), 'pending', utc_now()))
        return {'event_id': event.event_id, 'topic_id': None, 'status': 'unassigned', 'requires_confirmation': True}

    def _prepare(self, kind, payload):
        if kind not in KINDS:
            raise ValueError('unsupported memory operation')
        data = dict(payload)
        fields = []
        revisions = {}
        affected = 0
        if kind == 'import_demo':
            if self.desktop.workspace != 'demo':
                raise ValueError('synthetic data can only be imported into the demo workspace')
            from .merged_demo import merge_preview
            preview=merge_preview(self.service)
            fields.extend([{'key': 'topics_count', 'value': str(preview['topics'])},
                           {'key': 'events_count', 'value': str(preview['events'])},
                           {'key': 'archive_count', 'value': str(len(preview['archive_topics']))}])
            revisions.update({topic['topic_id']:topic['revision'] for topic in preview['archive_topics']})
            affected=sum(topic['events'] for topic in preview['archive_topics'])
        for key in ('topic_id', 'source_id', 'target_id'):
            if not data.get(key) or (key == 'target_id' and kind == 'forget' and data.get('target_type') == 'event'):
                continue
            topic = self.service._topic(data[key])
            if topic.state == 'archived' and kind != 'forget':
                raise ValueError('this topic is archived; choose an active task topic')
            fields.append({'key': key, 'value': topic.title})
            revisions[topic.topic_id] = topic.revision
            affected += len(topic.event_ids)
        if kind in ('forget_field', 'move') or (kind == 'forget' and data.get('target_type') == 'event'):
            event_id = data.get('event_id') or data.get('target_id')
            event = self.store.get_event(event_id)
            if not event or event.user_id != self.service.user_id or self.service._hidden_event(event_id):
                raise KeyError('event not found')
            fields.append({'key': 'event', 'value': event.content[:600]})
            affected = 1
        if kind == 'create_topic':
            data['title'] = str(data.get('title') or '').strip()
            data['goal'] = str(data.get('goal') or '').strip()
            if not 2 <= len(data['title']) <= 120 or not 8 <= len(data['goal']) <= 800:
                raise ValueError('provide a task title (2–120 characters) and a persistent goal (8–800 characters)')
            if data.get('session_id') and not data.get('project_ref'):
                raise ValueError('binding a session requires its project directory')
            for key,limit in [('keywords',8),('person_refs',12),('resource_ids',12)]:
                values=data.get(key) or []
                if not isinstance(values,list) or len(values)>limit:
                    raise ValueError(f'{key} must be a list with at most {limit} entries')
                data[key]=values
            # Only explicitly selected inbox events can be imported on creation.
            data['event_ids'] = list(dict.fromkeys(data.get('event_ids') or []))
            for event_id in data['event_ids']:
                row = self.store.conn.execute("SELECT session_id,project_ref FROM mp_capture_inbox WHERE event_id=? AND user_id=? AND status='pending'",
                                              (event_id, self.service.user_id)).fetchone()
                if not row or row['session_id'] != data.get('session_id') or row['project_ref'] != data.get('project_ref'):
                    raise ValueError('selected inbox event does not belong to the reviewed source')
            affected = len(data['event_ids'])
        if kind == 'bind_topic' and (not data.get('topic_id') or not data.get('session_id') or not data.get('project_ref')):
            raise ValueError('topic, session and project are required for binding')
        if kind in ('create_topic', 'bind_topic'):
            data['event_ids'] = list(dict.fromkeys(data.get('event_ids') or []))
            for event_id in data['event_ids']:
                row=self.store.conn.execute("SELECT session_id,project_ref,payload FROM mp_capture_inbox WHERE event_id=? AND user_id=? AND status='pending'",(event_id,self.service.user_id)).fetchone()
                if not row or row['session_id']!=data.get('session_id') or row['project_ref']!=data.get('project_ref'):
                    raise ValueError('selected source does not belong to the reviewed session and project')
                fields.append({'key':'event','value':json.loads(row['payload'])['content'][:600]})
            affected=len(data['event_ids'])
        if kind == 'remember':
            if not data.get('topic_id'):
                raise ValueError('confirm a task topic before recording memory')
            if data.get('kind', 'note') not in ('note', 'preference', 'knowledge') or not isinstance(data.get('content'),str) or not data['content'].strip():
                raise ValueError('choose a memory kind and provide content')
            if data.get('kind') in ('preference', 'knowledge') and not data.get('key'):
                raise ValueError('preference/knowledge requires a key')
            if data.get('key') is not None and not isinstance(data['key'],str):
                raise ValueError('memory key must be text')
            if data.get('scope_type','topic') not in ('topic','global'):
                raise ValueError('choose topic or global scope')
            if data.get('temporary') and data.get('scope_type')=='global':
                raise ValueError('temporary preferences cannot have global scope')
        required = {'rename_topic': ('topic_id', 'title'), 'checkpoint': ('topic_id',),
                    'forget': ('target_type', 'target_id'), 'forget_field': ('event_id', 'field_path'),
                    'move': ('event_id', 'topic_id'), 'merge': ('source_id', 'target_id'),
                    'split': ('topic_id', 'event_ids', 'title'), 'update_tags': ('topic_id',)}
        if any(not data.get(key) for key in required.get(kind, ())):
            raise ValueError('the operation is missing its target or required fields')
        if kind == 'forget' and data['target_type'] not in ('topic', 'event'):
            raise ValueError('forget requires a topic or event target')
        if kind == 'split':
            topic = self.service._topic(data['topic_id'])
            if not set(data['event_ids']).issubset(topic.event_ids):
                raise ValueError('selected events do not belong to the source topic')
            affected = len(set(data['event_ids']))
        for key in ('title', 'goal', 'project_ref', 'content', 'key', 'scope_type', 'scope_id', 'reason', 'field_path'):
            if data.get(key):
                fields.append({'key': key, 'value': str(data[key])})
        if data.get('session_id'):
            fields.append({'key': 'session', 'value': data['session_id']})
        tags = []
        if kind in ('create_topic', 'update_tags'):
            from .tags import event_tags, validate_topic_tags
            from .models import Topic
            sample = self.service.normalize_event({'event_id': 'review', 'content': data.get('goal') or '标签修订',
                'person_refs': data.get('person_refs', []), 'resource_ids': data.get('resource_ids', []),
                'metadata': {'keywords': data.get('keywords', []), 'keywords_confirmed': True}})
            accepted, pending, missing = validate_topic_tags(Topic('review', self.service.user_id, 'review'), event_tags(sample))
            if kind == 'update_tags':
                topic=self.service._topic(data['topic_id'])
                accepted,pending,missing=self._derive_tags(topic,sample)
                kept={tag.canonical for tag in accepted}
                removed=[tag.label or tag.value for tag in topic.tags if tag.canonical not in kept]
                if removed: fields.append({'key':'removed_tags','value':', '.join(removed)})
            tags = [tag.to_dict() for tag in accepted + pending]
            fields.append({'key': 'missing_tags', 'value': ', '.join(missing)})
        return data, {'kind': kind, 'fields': fields, 'tags': tags, 'affected_events': affected, 'revisions': revisions}

    def propose(self, kind, payload, origin='agent'):
        data, preview = self._prepare(kind, payload)
        fingerprint = hashlib.sha256(json.dumps([kind, data, preview], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        existing = self.store.conn.execute("SELECT id FROM mp_memory_operations WHERE user_id=? AND fingerprint=? AND status='pending'",
                                           (self.service.user_id, fingerprint)).fetchone()
        if existing:
            return self.get(existing['id'])
        identifier = 'memory_op_' + uuid.uuid4().hex
        with self.store.transaction():
            self.store.conn.execute('INSERT INTO mp_memory_operations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (identifier, self.service.user_id, kind, json.dumps(data, ensure_ascii=False),
                 json.dumps(preview, ensure_ascii=False), fingerprint, 'pending', None, None, utc_now(), utc_now(), origin))
        return self.get(identifier)

    def reject(self, operation_id):
        operation = self.get(operation_id)
        if operation['status'] == 'pending':
            with self.store.transaction():
                self.store.conn.execute("UPDATE mp_memory_operations SET status='rejected',payload='{}',preview=?,updated_at=? WHERE id=?",
                    (json.dumps({'fields':[],'tags':[],'affected_events':0}),utc_now(),operation_id))
        return self.get(operation_id)

    def confirm(self, operation_id, fingerprint):
        operation = self.get(operation_id)
        if operation['fingerprint'] != fingerprint:
            raise ValueError('operation changed; review it again')
        if operation['status'] == 'applied':
            return operation
        if operation['status'] != 'pending':
            raise ValueError('this operation is no longer pending')
        kind, data = operation['kind'], operation['payload']
        if kind in {'forget', 'forget_field', 'move', 'merge', 'split', 'rename_topic', 'update_tags', 'import_demo'}:
            for topic_id, revision in operation['preview']['revisions'].items():
                if self.service._topic(topic_id).revision != revision:
                    raise ValueError('topic changed since the preview; cancel and request a fresh review')
        # A durable executing state prevents duplicate mutation after crashes.
        # Failed/interrupted operations require a fresh review, never blind replay.
        with self.store.transaction():
            self.store.conn.execute("UPDATE mp_memory_operations SET status='executing',updated_at=? WHERE id=?", (utc_now(), operation_id))
        try:
            if kind in ('remember','update_tags'):
                with self.store.transaction():
                    result = self._apply(kind, data, operation_id)
            else:
                result = self._apply(kind, data, operation_id)
        except Exception as error:
            with self.store.transaction():
                self.store.conn.execute("UPDATE mp_memory_operations SET status='failed',payload='{}',preview=?,error=?,updated_at=? WHERE id=?",
                    (json.dumps({'fields':[],'tags':[],'affected_events':0}),str(error),utc_now(),operation_id))
            raise
        with self.store.transaction():
            # A receipt is not a second plaintext memory store. Read the actual
            # event/knowledge through its governed API, never through old prompts.
            receipt=result if kind=='import_demo' else {key:value for key,value in result.items() if key in {
                'id','topic_id','event_id','source_id','target_id','target_type','previous_topic','checkpoint_id',
                'revision','status','tombstone_id','binding','session_id','parent_id'}}
            self.store.conn.execute("UPDATE mp_memory_operations SET status='applied',payload='{}',preview=?,result=?,updated_at=? WHERE id=?",
                (json.dumps({'fields':[],'tags':[],'affected_events':operation['preview']['affected_events']}),
                 json.dumps(receipt,ensure_ascii=False),utc_now(),operation_id))
        return self.get(operation_id)

    def _bind(self, topic_id, data, operation_id):
        if not data.get('session_id'):
            return
        self.store.conn.execute('INSERT INTO mp_session_bindings VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,session_id) DO UPDATE SET project_ref=excluded.project_ref,topic_id=excluded.topic_id,operation_id=excluded.operation_id,confirmed_at=excluded.confirmed_at',
            (self.service.user_id, data['session_id'], data.get('project_ref', ''), topic_id, operation_id, utc_now()))

    def _attach_inbox(self, topic_id, data):
        for event_id in data.get('event_ids', []):
            row=self.store.conn.execute('SELECT payload FROM mp_capture_inbox WHERE event_id=?',(event_id,)).fetchone()
            result=self.service.ingest({**json.loads(row['payload']),'topic_id':topic_id})
            if result.get('topic_id')!=topic_id:
                raise ValueError('source event was assigned elsewhere; review again')
            self.store.conn.execute("UPDATE mp_capture_inbox SET status='attached' WHERE event_id=?",(event_id,))

    def _derive_tags(self, topic, extra=None):
        from copy import deepcopy
        from .tags import event_tags, extract_keywords, validate_topic_tags
        from .models import Event
        sources=self.store.list_events(topic.topic_id)
        if extra: sources.append(extra)
        tags=[]
        for source in sources:
            metadata=dict(source.metadata)
            if not metadata.get('keywords_confirmed') and not metadata.get('keyword_candidates'):
                metadata['keywords']=extract_keywords(source.content) if source.source_type=='configuration' else []
            clean=Event.from_mapping({**source.to_dict(),'metadata':metadata})
            tags.extend(event_tags(clean,topic_id=topic.topic_id,model_rev=self.service.core.model_rev if topic.vector is not None else None))
        return validate_topic_tags(deepcopy(topic),tags)

    def _apply(self, kind, data, operation_id):
        service = self.service
        if kind == 'import_demo':
            import sqlite3
            from .merged_demo import seed_merged_demo
            backup=self.desktop.data_dir/'demo-backups'/f'{operation_id}.sqlite3'
            backup.parent.mkdir(parents=True,exist_ok=True)
            destination=sqlite3.connect(backup)
            try: self.store.conn.backup(destination)
            finally: destination.close()
            return {**seed_merged_demo(service),'backup_path':str(backup)}
        if kind == 'create_topic':
            with self.store.transaction():
                topic = service.core.create_topic(user_id=service.user_id, title=data['title'], goal=data['goal'],
                    metadata={'identity_confirmed': True, 'confirmation_operation': operation_id,
                              'project_ref': data.get('project_ref', ''), 'identity_goal': data['goal']})
                service.ingest({'event_id': operation_id + ':identity', 'topic_id': topic.topic_id,
                    'content': data['goal'], 'source_type': 'configuration', 'person_refs': data.get('person_refs', []),
                    'resource_ids': data.get('resource_ids', []),
                    'metadata': {'keywords': data.get('keywords', []), 'keywords_confirmed': True,
                                 'topic_identity_confirmation': True, 'operation_id': operation_id}})
                self._bind(topic.topic_id, data, operation_id)
                self._attach_inbox(topic.topic_id,data)
            return {'topic_id': topic.topic_id, 'title': topic.title}
        if kind == 'bind_topic':
            with self.store.transaction():
                self._bind(data['topic_id'], data, operation_id)
                self._attach_inbox(data['topic_id'],data)
            return {'topic_id': data['topic_id'], 'session_id': data['session_id'], 'binding': 'user_confirmed'}
        if kind in ('remember', 'update_tags'):
            evidence = service.ingest({'event_id': operation_id + ':evidence', 'idempotency_key': operation_id,
                'topic_id': data['topic_id'], 'content': data.get('content') or '用户确认的话题标签修订',
                'source_type': 'configuration', 'person_refs': data.get('person_refs', []), 'resource_ids': data.get('resource_ids', []),
                'metadata': {'keywords': data.get('keywords', []), 'keywords_confirmed': True, 'operation_id': operation_id}})
            if data.get('kind') in ('preference', 'knowledge'):
                fields = {'key': data['key'], 'value': data['content'], 'scope_type': data.get('scope_type', 'topic'),
                          'scope_id': '' if data.get('scope_type')=='global' else data['topic_id'], 'evidence_event_id': evidence['event_id']}
                if data['kind'] == 'preference':
                    return service.update_preference({**fields, 'choice_type': 'temporary' if data.get('temporary') else 'explicit'})
                return service.knowledge(fields)
            if kind == 'update_tags':
                # Re-derive from source events using today's extraction policy;
                # legacy tokenisation fragments are not retained merely by union.
                topic = service._topic(data['topic_id'])
                accepted, pending, missing = self._derive_tags(topic)
                topic.tags = accepted
                topic.state='incomplete' if missing else 'active'
                topic.metadata.update({'pending_tags': [tag.to_dict() for tag in pending], 'missing_tag_kinds': missing, 'tag_policy': 2})
                topic.revision += 1
                service.core.embed_topic(topic)
                self.store.save_topic(topic)
                service.core.graph.upsert_topic(topic)
            return evidence
        if kind == 'rename_topic':
            return self.desktop.rename_topic(data['topic_id'], data['title'])
        if kind == 'checkpoint':
            return service.checkpoint(data['topic_id'])
        if kind == 'forget':
            return service.forget(data['target_type'], data['target_id'])
        if kind == 'forget_field':
            return service.forget_field(data['event_id'], data['field_path'])
        if kind == 'move':
            return service.move_event(data['event_id'], data['topic_id'])
        if kind == 'merge':
            return service.merge_topics(data['source_id'], data['target_id'])
        if kind == 'split':
            return service.split_topic(data['topic_id'], data['event_ids'], data['title'])
        raise ValueError('unsupported operation')
