"""Preview/apply the user-authorised demo migration while the desktop is stopped.

This is a maintenance entry point, not a model tool. Normal in-app changes use
the same operation preview and the renderer confirmation UI.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from mempulse.desktop import DesktopService
from mempulse.merged_demo import merge_preview

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir',type=Path,required=True)
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--apply',action='store_true')
args=parser.parse_args()
if not (args.data_dir/'desktop-demo.sqlite3').is_file():
    raise SystemExit('Existing demo database required; use prepare_realistic_desktop.py for a new directory')
if not args.apply:
    with tempfile.TemporaryDirectory(prefix='mempulse-demo-preview-') as temporary:
        source=sqlite3.connect((args.data_dir/'desktop-demo.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
        destination=sqlite3.connect(Path(temporary)/'desktop-demo.sqlite3')
        try: source.backup(destination)
        finally: source.close(); destination.close()
        preview_service=DesktopService(temporary)
        preview=merge_preview(preview_service.service)
        preview_service.close()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(preview,ensure_ascii=False,indent=2))
    print(json.dumps({key:preview[key] for key in ['dataset','topics','events','new_topics','source_events']},ensure_ascii=False))
    raise SystemExit(0)
desktop=DesktopService(args.data_dir)
if desktop.workspace!='demo':
    desktop.service.store.close()
    desktop.workspace='demo'
    desktop._open()  # The user's persisted active-workspace setting is unchanged.
preview=merge_preview(desktop.service)
archived={topic['topic_id'] for topic in preview['archive_topics']}


def protected_hashes():
    result={}
    for topic in desktop.service.store.list_topics(desktop.service.user_id):
        if topic.topic_id in archived or topic.metadata.get('curated_dataset')=='persistent-demo-v4': continue
        result['topic:'+topic.topic_id]=hashlib.sha256(json.dumps(topic.to_dict(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        for event in desktop.service.store.list_events(topic.topic_id):
            result['event:'+event.event_id]=hashlib.sha256(json.dumps(event.to_dict(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return result


before=protected_hashes()
operation=desktop.dispatch('propose_operation',{'kind':'import_demo','payload':{},'origin':'authorised-maintenance'})
applied=desktop.dispatch('confirm_operation',{'operation_id':operation['id'],'fingerprint':operation['fingerprint']})
after=protected_hashes()
assert before==after, 'Protected personal/mixed source records changed; inspect the retained backup before continuing'
report={'operation_id':operation['id'],'status':applied['status'],'result':applied['result'],
        'protected_records_verified':len(before),'protected_hashes':before,
        'all_protected_records_unchanged':True,'bootstrap_stats':desktop.dispatch('bootstrap')['stats'],
        'model':desktop.dispatch('health').get('embedding')}
args.report.parent.mkdir(parents=True,exist_ok=True)
args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({key:report[key] for key in ['status','protected_records_verified','all_protected_records_unchanged','bootstrap_stats']},ensure_ascii=False))
desktop.close()
