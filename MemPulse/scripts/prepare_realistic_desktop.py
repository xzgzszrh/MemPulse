"""Prepare the authored demo in a NEW directory; never replace live memory."""
import argparse
import json
from pathlib import Path

from mempulse.service import TopicFacade
from mempulse.merged_demo import seed_merged_demo

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir', type=Path, required=True)
parser.add_argument('--model', type=Path, required=True)
args = parser.parse_args()
if args.data_dir.exists():
    raise SystemExit('Destination exists; choose a new directory')
args.data_dir.mkdir(parents=True)
service = TopicFacade(args.data_dir/'desktop-demo.sqlite3')
with service.store.transaction():
    service.store.conn.execute('CREATE TABLE IF NOT EXISTS desktop_seed(version INTEGER PRIMARY KEY)')
    service.store.conn.execute('INSERT INTO desktop_seed VALUES(1)')
result = seed_merged_demo(service)
service.configure_model(str(args.model.resolve()), precision='fp32')
result['index'] = service.reindex()
result['health'] = service.health()
(args.data_dir/'model.json').write_text(json.dumps({'model_dir':str(args.model.resolve()),'precision':'fp32'}))
(args.data_dir/'preparation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
service.store.close()
print(json.dumps({key:result[key] for key in ['dataset','topics','events','sessions','people']},ensure_ascii=False))
