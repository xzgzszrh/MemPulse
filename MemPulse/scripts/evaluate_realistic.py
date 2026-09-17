"""Evaluate authored persistent-work scenarios in fresh, isolated databases."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

from mempulse.realistic_scenarios import CASES, PEOPLE, questions, seed_realistic
from mempulse.service import TopicFacade


def percentile(values, quantile):
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, int((len(ordered)-1)*quantile))] if ordered else None


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--rounds', type=int, default=3)
parser.add_argument('--dataset', choices=['v3','merged'], default='merged')
args = parser.parse_args()
if args.output.exists():
    raise SystemExit('Use a new output directory; previous evaluations are immutable')
args.output.mkdir(parents=True)
if args.dataset == 'merged':
    from mempulse.merged_demo import merged_cases, merged_questions, seed_merged_demo
    queries = merged_questions()
    cases = merged_cases()
    seed = seed_merged_demo
    dataset = 'persistent-demo-v4'
else:
    queries = questions()
    cases = CASES
    seed = seed_realistic
    dataset = 'persistent-work-v3' 
source_root=Path(__file__).resolve().parents[1]
source_files=[*sorted((source_root/'src/mempulse').glob('*.py')),Path(__file__).resolve()]
source_hashes={str(path.relative_to(source_root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}
(args.output/'queries.json').write_text(json.dumps(queries, ensure_ascii=False, indent=2))
(args.output/'scenarios.json').write_text(json.dumps({'cases': cases, 'people': {person['id']:person for case in cases for event in case['events'] for person in event['person_refs']} if args.dataset=='merged' else PEOPLE, 'synthetic': True}, ensure_ascii=False, indent=2))
summary = {'created_at': datetime.now(timezone.utc).isoformat(), 'dataset': dataset,
           'synthetic': True, 'human_reviewed': False, 'training_overlap_verified': False,
           'formal_acceptance': False, 'rounds': args.rounds, 'unique_queries': len(queries),
           'query_categories': dict(Counter(query['kind'] for query in queries)),
           'timing_scope': 'TopicFacade.search: intent constraints, topic candidates, SQL evidence; excludes Electron IPC and answer generation',
           'modes': []}
for mode in ('lexical', 'fp32'):
    service = TopicFacade(args.output/f'{mode}.sqlite3')
    seeded = seed(service)
    if mode == 'fp32':
        service.configure_model(str(args.model.resolve()), precision='fp32')
        service.reindex()
    ids = seeded['topic_ids']
    rows = []
    for round_index in range(args.rounds):
        ordered = list(queries)
        random.Random(710 + round_index).shuffle(ordered)
        for query in ordered:
            if service.core.embed and hasattr(service.core.embed, 'cache'):
                service.core.embed.cache.clear()
            started = time.perf_counter()
            result = service.search(query['query'], limit=8, context={'reference_time': '2026-09-15T10:00:00+08:00', **query.get('context', {})})
            elapsed = (time.perf_counter()-started)*1000
            ranked = [candidate['topic_id'] for candidate in result['route'].get('ranked_candidates', [])]
            gold = ids.get(query['gold_topic'])
            hit_ids = {event['event_id'] for event in result['results']}
            expected = set(query['evidence_ids'])
            rows.append({'id': query['id'], 'query': query['query'], 'kind': query['kind'], 'round': round_index+1,
                'gold_topic': query['gold_topic'], 'rank': ranked.index(gold)+1 if gold in ranked else None,
                'evidence_any': bool(expected & hit_ids) if expected else None,
                'evidence_recall': len(expected & hit_ids)/len(expected) if expected else None,
                'expected_evidence': sorted(expected), 'returned_events': sorted(hit_ids),
                'returned_topics': sorted({event['topic_id'] for event in result['results']}),
                'needs_clarification': result.get('needs_clarification', False),
                'abstained': not result['results'], 'elapsed_ms': elapsed,
                'plan': result.get('plan'), 'backend': result.get('backend')})
        print(json.dumps({'mode': mode, 'round': round_index+1, 'requests': len(ordered)}, ensure_ascii=False), flush=True)
    positives = [row for row in rows if row['gold_topic']]
    groups = defaultdict(list)
    for row in positives:
        groups[row['kind']].append(row)
    metrics = {'requests':len(rows),'top1':sum(row['rank']==1 for row in positives)/len(positives),
        'recall_at_3':sum(row['rank'] is not None and row['rank']<=3 for row in positives)/len(positives),
        'evidence_hit_at_8':statistics.mean(row['evidence_any'] for row in positives),
        'evidence_recall_at_8':statistics.mean(row['evidence_recall'] for row in positives),
        'p50_ms':statistics.median(row['elapsed_ms'] for row in rows),'p95_ms':percentile([row['elapsed_ms'] for row in rows],.95),
        'ambiguous_handled':sum(row['needs_clarification'] for row in rows if row['kind']=='ambiguous')/sum(row['kind']=='ambiguous' for row in rows),
        'absent_abstention':sum(row['abstained'] for row in rows if row['kind']=='absent')/sum(row['kind']=='absent' for row in rows),
        'by_category':{kind:{'n':len(items),'top1':statistics.mean(row['rank']==1 for row in items),
                           'evidence_recall_at_8':statistics.mean(row['evidence_recall'] for row in items)} for kind,items in groups.items()}}
    with (args.output/f'{mode}-requests.jsonl').open('w') as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False)+'\n')
    summary['modes'].append({'mode':mode,'seed':seeded,'metrics':metrics,'health':service.health()})
    service.store.close()
assert source_hashes=={str(path.relative_to(source_root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}, 'Source changed during evaluation; use a frozen source snapshot'
summary['source_sha256']=source_hashes
(args.output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps({item['mode']:item['metrics'] for item in summary['modes']}, ensure_ascii=False, indent=2))
