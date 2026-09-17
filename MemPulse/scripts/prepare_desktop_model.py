"""Prepare a new desktop data directory from an API snapshot, without overwriting live files."""
import argparse
import json
from pathlib import Path
from mempulse.service import TopicFacade
from mempulse.desktop import DesktopService
from mempulse.models import Event
from mempulse.tags import normalize_person
from mempulse.embeddings import file_sha256

p=argparse.ArgumentParser()
p.add_argument('--snapshot',required=True);p.add_argument('--data-dir',required=True);p.add_argument('--model',required=True)
args=p.parse_args()
snapshot_path=Path(args.snapshot).resolve();target=Path(args.data_dir).resolve()
if target.exists(): raise SystemExit('Destination already exists; choose a new directory')
payload=json.loads(snapshot_path.read_text());data=payload['data'] if 'data' in payload else payload
if data['workspace'] != 'demo': raise SystemExit('This preparation only handles the demo workspace')
expected={eid for topic in data['topics'] for eid in topic['event_ids']}
received={event['event_id'] for event in data['events']}
if not expected.issubset(received): raise SystemExit('Snapshot is incomplete: some topic events are missing')
target.mkdir(parents=True)
service=TopicFacade(target/'desktop-demo.sqlite3')
with service.store.transaction():
    service.store.conn.execute('PRAGMA defer_foreign_keys=ON')
    for topic in data['topics']:
        service.store.save_topic(service.store._topic({'payload':json.dumps(topic)}))
    for row in data['events']:
        event=Event.from_mapping(row)
        service.store.save_event(event,row['topic_id'])
        for person in event.person_refs:
            tag=normalize_person(person.get('id',''),event.event_id,person.get('role')) if isinstance(person,dict) else normalize_person(person,event.event_id)
            service.store.conn.execute('INSERT OR IGNORE INTO mp_participation(event_id,topic_id,person_id,role,status,occurred_at,user_scope,evidence_event_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                (event.event_id,row['topic_id'],tag.value,tag.role,'confirmed',event.occurred_at,event.user_id,event.event_id,event.observed_at))
    for key,table in [('preferences','mp_preferences'),('knowledge','mp_knowledge'),('checkpoints','mp_checkpoints'),('receipts','mp_tombstones')]:
        columns={row[1] for row in service.store.conn.execute(f'PRAGMA table_info({table})')}
        for row in data['governance'].get(key,[]):
            restored={}
            for column in columns:
                if column in row: restored[column]=row[column]
                elif column.endswith('_json') and column[:-5] in row: restored[column]=json.dumps(row[column[:-5]],ensure_ascii=False)
            names=list(restored)
            service.store.conn.execute(f'INSERT INTO {table} ({",".join(names)}) VALUES ({",".join("?" for _ in names)})',[restored[name] for name in names])
    service.store.conn.execute('CREATE TABLE IF NOT EXISTS desktop_seed (version INTEGER PRIMARY KEY)')
    service.store.conn.execute('INSERT OR IGNORE INTO desktop_seed VALUES(1)')
service.store.close()
(target/'desktop-settings.json').write_text(json.dumps({'workspace':'demo'}))
desktop=DesktopService(target)
loaded=desktop.dispatch('configure_model',{'model_dir':str(Path(args.model).resolve()),'precision':'fp32'})
enriched=desktop.dispatch('enrich_demo')
index=desktop.dispatch('reindex')
result=desktop.dispatch('bootstrap')
actual={row[0] for row in desktop.service.store.conn.execute('SELECT id FROM events')}
assert expected.issubset(actual)
report={'source':'API snapshot recovery, not a full SQLite forensic backup','source_sha256':file_sha256(snapshot_path),
    'preserved_topics':len(data['topics']),'preserved_events':len(expected),'all_source_event_ids_preserved':expected.issubset(actual),
    'data_dir':str(target),'enrichment':enriched,'index':index,'stats':result['stats'],'health':result['health'],
    'limitations':['Snapshot preserves exposed topics, events and governance records; deleted-file private tables not exposed by the API cannot be verified.']}
(target/'preparation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
desktop.close()
print(json.dumps({key:report[key] for key in ['preserved_topics','preserved_events','all_source_event_ids_preserved','stats','index']},ensure_ascii=False),flush=True)
