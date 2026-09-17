"""Reproducible local integration benchmark. Synthetic engineering data, not formal acceptance."""
from __future__ import annotations
import argparse
import json
import math
import platform
import random
import statistics
import time
from pathlib import Path
from datetime import datetime, timezone
from mempulse.desktop import DesktopService
from mempulse.demo_scenarios import scenarios, seed_rich_demo, TASKS
from mempulse.embeddings import file_sha256
from mempulse.embeddings import OnnxEncoder
from mempulse.core import TopicCore


def percentile(values, q):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position-lower)


def queries():
    cases = []
    for row in scenarios():
        for i, text in enumerate(row['queries']):
            cases.append({'id': f'{row["id"]}:q{i}', 'query': text, 'gold': row['id'], 'kind': ['direct', 'paraphrase', 'continuation'][i]})
    for i, task in enumerate(TASKS):
        cases.append({'id': f'absent:{i}', 'query': f'岚江物流，{task[5][0]}', 'gold': None, 'kind': 'absent_customer'})
        cases.append({'id': f'ambiguous:{i}', 'query': task[5][i % 3], 'gold': None, 'kind': 'ambiguous_customer'})
    return cases


def summarize(rows):
    positives = [row for row in rows if row['gold'] is not None]
    accepted = [row for row in rows if row['route'] in ('RESUME', 'ATTACH')]
    reference = [row for row in rows if row['reference_route'] == 'RESUME']
    latency = [row['elapsed_ms'] for row in rows]
    return {
        'requests': len(rows), 'positive_requests': len(positives),
        'top1': sum(row['rank'] == 1 for row in positives) / len(positives),
        'recall_at_3': sum(row['rank'] is not None and row['rank'] <= 3 for row in positives) / len(positives),
        'recall_at_5': sum(row['rank'] is not None and row['rank'] <= 5 for row in positives) / len(positives),
        'mrr': statistics.mean(1/row['rank'] if row['rank'] else 0 for row in positives),
        'evidence_hit_at_6': statistics.mean(row['gold'] in row['hit_topics'] for row in positives),
        'accepted': len(accepted), 'accepted_error': sum(row['selected'] != row['gold'] or row['gold'] is None for row in accepted) / len(accepted) if accepted else None,
        'reference_accepted': len(reference),
        'reference_coverage': sum(row['reference_route'] == 'RESUME' for row in positives) / len(positives),
        'reference_accepted_error': sum(row['top1_id'] != row['gold'] or row['gold'] is None for row in reference) / len(reference) if reference else None,
        'latency_ms': {'p50': percentile(latency,.5), 'p95': percentile(latency,.95), 'max': max(latency)},
        'by_category': {kind: {'n': len(group), 'top1': sum(row['rank'] == 1 for row in group)/len(group)}
                        for kind in ('direct','paraphrase','continuation')
                        if (group := [row for row in positives if row['kind'] == kind])},
    }


def run_mode(mode, root, output, rounds):
    data = output / mode
    data.mkdir()
    # This historical benchmark deliberately keeps its original v1/v2 corpus,
    # independently of the product's newer default demonstration dataset.
    from mempulse.service import TopicFacade
    from mempulse.desktop_seed import seed_desktop
    initial=TopicFacade(data/'desktop-demo.sqlite3')
    seed_desktop(initial)
    initial.store.close()
    desktop = DesktopService(data)
    seeded = seed_rich_demo(desktop.service, prefix='benchmark-v2')
    ids = seeded['topic_ids']
    inverse = {value:key for key,value in ids.items()}
    load_ms = None
    index = None
    if mode != 'lexical':
        began = time.perf_counter()
        if mode == 'mixed-int8':
            # Evaluate the delivered candidate even when it fails the live activation gate.
            candidate = OnnxEncoder(root, precision=mode)
            desktop.service.core = TopicCore(desktop.service.store, embed=candidate, model_rev=candidate.revision)
            index = {**desktop.service.reindex(), 'evaluation_only': True}
        else:
            index = desktop.dispatch('configure_model', {'model_dir': str(root), 'precision': mode})
        load_ms = (time.perf_counter()-began)*1000
    encoder = desktop.service.core.embed
    rows = []
    trajectories = []
    query_vectors = []
    for round_index in range(rounds):
        # Each round really continues existing topics and refreshes their contracts.
        for scenario in scenarios():
            tid = ids[scenario['id']]
            content = f'{scenario["customer"]}的{scenario["title"].split(" · ")[1]}第{round_index+1}轮复核：{scenario["contents"][-1]}'
            event = desktop.dispatch('ingest', {'event_id': f'benchmark-turn:{scenario["id"]}:{round_index}', 'content': content, 'topic_id': tid,
                'metadata': {'synthetic': True, 'completed_steps': scenario['contents'][:3], 'pending_steps': [scenario['contents'][-1]]}})
            desktop.dispatch('checkpoint', {'topic_id': tid})
            context = desktop.dispatch('agent_context', {'query': '', 'topic_id': tid})
            trajectories.append({'round': round_index+1, 'scenario': scenario['id'], 'route': event['route'],
                'correct_binding': event['topic_id'] == tid and context['contract']['topic_id'] == tid,
                'has_evidence': bool(context['contract']['events']), 'checkpoint_present': bool(context['contract']['checkpoint'])})
        ordered = queries()
        random.Random(710 + round_index).shuffle(ordered)
        for case in ordered:
            if encoder:
                encoder.clear_cache()  # Uncached request; repeated internal encoding may reuse within this request.
            before_calls = encoder.inference_calls if encoder else 0
            began = time.perf_counter()
            result = desktop.dispatch('search', {'query': case['query'], 'limit': 6})
            elapsed = (time.perf_counter()-began)*1000
            route = result['route']
            candidates = route['ranked_candidates']
            ranked = [inverse.get(row['topic_id'], row['topic_id']) for row in candidates]
            first = candidates[0]['score'] if candidates else 0
            second = candidates[1]['score'] if len(candidates)>1 else 0
            proposed = 'NEW' if first < .22 else 'AMBIGUOUS' if first-second < .08 else 'RESUME'
            row = {**case, 'round': round_index+1, 'elapsed_ms': elapsed, 'rank': ranked.index(case['gold'])+1 if case['gold'] in ranked else None,
                'top1_id': ranked[0] if ranked else None, 'route': route['route'], 'selected': inverse.get(route['topic_id'], route['topic_id']),
                'reference_route': proposed, 'scores': candidates[:5], 'ranked': ranked,
                'hit_topics': [inverse.get(hit['topic_id'], hit['topic_id']) for hit in result['results']],
                'inference_calls': (encoder.inference_calls-before_calls) if encoder else 0, 'fallback': route.get('embedding_fallback')}
            rows.append(row)
            if encoder and round_index == 0 and case['gold']:
                query_vectors.append({'id': case['id'], 'vector': encoder.encode_query(case['query'])})
        print(json.dumps({'mode': mode, 'round': round_index+1, 'metrics': summarize(rows[-len(ordered):])}, ensure_ascii=False), flush=True)
    info = desktop.service.health()
    with (output / f'{mode}-requests.jsonl').open('w') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False)+'\n')
    (output / f'{mode}-trajectories.json').write_text(json.dumps(trajectories, ensure_ascii=False, indent=2))
    (output / f'{mode}-vectors.json').write_text(json.dumps(query_vectors))
    summary = {'mode': mode, 'topics': len(desktop.service.list_topics()['topics']), 'load_and_index_ms': load_ms, 'index': index,
        'health': info, 'metrics': summarize(rows), 'rounds': [summarize([row for row in rows if row['round']==i+1]) for i in range(rounds)],
        'trajectory_steps': len(trajectories), 'correct_binding_steps': sum(row['correct_binding'] for row in trajectories),
        'checkpoint_steps': sum(row['checkpoint_present'] for row in trajectories)}
    desktop.close()
    (output / f'{mode}-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--modes', nargs='+', default=['lexical','fp32','mixed-int8'])
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = queries()
    (output/'queries.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2))
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(), 'python': platform.python_version(),
        'dataset': 'office-memory-v2', 'synthetic': True, 'formal_acceptance': False, 'independent_human_review': False,
        'training_overlap_verified': False, 'unique_queries': len(cases), 'rounds': args.rounds,
        'timing_scope': 'DesktopService.dispatch search including FTS, query encoding, candidates, fusion, event evidence; excludes Electron IPC and answer generation',
        'cache_policy': 'query cache cleared before each request; reused only inside a request', 'modes': []}
    import importlib.metadata
    report['dependencies'] = {name: importlib.metadata.version(name) for name in ['numpy','onnxruntime','tokenizers']}
    project = Path(__file__).resolve().parents[1]
    report['source_sha256'] = {str(path.relative_to(project)): file_sha256(path) for path in [Path(__file__).resolve(), *sorted((project/'src/mempulse').glob('*.py'))]}
    for mode in args.modes:
        report['modes'].append(run_mode(mode, Path(args.model).resolve(), output, args.rounds))
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if {'fp32','mixed-int8'}.issubset(args.modes):
        left = {row['id']: row['vector'] for row in json.loads((output/'fp32-vectors.json').read_text())}
        right = {row['id']: row['vector'] for row in json.loads((output/'mixed-int8-vectors.json').read_text())}
        cosines = [sum(a*b for a,b in zip(left[key],right[key])) for key in left]
        report['precision_alignment'] = {'queries': len(cosines), 'minimum_cosine': min(cosines), 'mean_cosine': statistics.mean(cosines), 'all_above_0_99': min(cosines)>=.99}
    report['query_sha256'] = file_sha256(output/'queries.json')
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(str(output/'summary.json'), flush=True)

if __name__ == '__main__':
    main()
