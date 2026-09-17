"""Reproducible local evidence tests against XA-202612; not formal acceptance.

Run from MemPulse with PYTHONPATH=src. Requires the existing ONNX environment.
Only creates databases below a NEW --output directory. No live client writes,
network calls, answer-model calls, or algorithm changes are performed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import select
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time

from competition_cases import fresh_questions
from mempulse.governance import Governance
from mempulse.merged_demo import merged_cases, merged_questions, seed_merged_demo
from mempulse.service import TopicFacade

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = '2026-09-15T10:00:00+08:00'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def jsonl(path, rows):
    with path.open('w') as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + '\n')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def timing(values):
    values = sorted(values)
    if not values:
        return {}
    return {'n': len(values), 'mean_ms': statistics.mean(values),
            **{f'p{q}_ms': values[max(0, math.ceil(q / 100 * len(values)) - 1)] for q in (50, 95, 99)},
            'max_ms': max(values), 'over_500_ms': sum(value > 500 for value in values)}


def wilson(passed, total):
    if not total:
        return None
    z = 1.95996398454
    p = passed / total
    center = (p + z*z/(2*total))/(1+z*z/total)
    half = z * math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [center-half, center+half]


def scored(query, events, ranked, topic_ids):
    expected = set(query['evidence_ids'])
    returned = {event['event_id'] for event in events}
    text = '\n'.join((event.get('content') or '')[:200] for event in events)
    gold = topic_ids.get(query['gold_topic'])
    return {'id': query['id'], 'split': query['split'], 'kind': query['kind'], 'query': query['query'],
            'gold_topic': query['gold_topic'], 'expected_evidence': sorted(expected),
            'returned_events': [event['event_id'] for event in events],
            'returned_topics': [event.get('topic_id') for event in events],
            'rank': ranked.index(gold)+1 if gold in ranked else None,
            'evidence_recall': len(expected & returned)/len(expected) if expected else None,
            'evidence_complete': expected <= returned if expected else None,
            'evidence_any': bool(expected & returned) if expected else None,
            'missing_evidence': sorted(expected-returned),
            'missing_atoms': [atom for atom in query.get('answer_atoms', []) if atom not in text],
            'atoms_complete': all(atom in text for atom in query['answer_atoms']) if query.get('answer_atoms') else None,
            'abstained': not events}


def aggregate(rows):
    # Accuracy denominators are unique questions, not repeated timing requests.
    unique = {row['id']: row for row in rows if row.get('round', 1) == 1}
    positives = [row for row in unique.values() if row['gold_topic']]
    negatives = [row for row in unique.values() if not row['gold_topic']]
    atoms = [row for row in positives if row['atoms_complete'] is not None]
    n = len(positives)
    result = {'unique_queries': len(unique), 'positive_queries': n, 'timing': timing([r['elapsed_ms'] for r in rows])}
    if n:
        result.update({
            'topic_top1': sum(r['rank'] == 1 for r in positives)/n,
            'topic_recall_at_3': sum(r['rank'] is not None and r['rank'] <= 3 for r in positives)/n,
            'evidence_recall_macro': statistics.mean(r['evidence_recall'] for r in positives),
            'evidence_recall_micro': sum(len(r['expected_evidence'])-len(r['missing_evidence']) for r in positives)/sum(len(r['expected_evidence']) for r in positives),
            'evidence_hit': sum(r['evidence_any'] for r in positives)/n,
            'evidence_complete': sum(r['evidence_complete'] for r in positives)/n,
            'evidence_complete_count': sum(r['evidence_complete'] for r in positives),
            'complete_wilson_95_descriptive_only': wilson(sum(r['evidence_complete'] for r in positives), n),
            'answer_atoms_complete': sum(r['atoms_complete'] for r in atoms)/len(atoms) if atoms else None,
            'answer_atoms_denominator': len(atoms),
        })
    result['negative_cases'] = [{'id': r['id'], 'kind': r['kind'], 'abstained': r['abstained'],
                                 'needs_clarification': r.get('needs_clarification')} for r in negatives]
    result['rounds_consistent'] = all(
        (row['returned_events'], row['rank']) == (unique[row['id']]['returned_events'], unique[row['id']]['rank']) for row in rows)
    return result


def grouped(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return {key: aggregate(value) for key, value in groups.items()}


def evaluate_retrieval(args, queries):
    result = {}
    for mode in ('lexical', 'fp32'):
        service = TopicFacade(args.output/f'{mode}.sqlite3')
        seed = seed_merged_demo(service)
        if mode == 'fp32':
            service.configure_model(str(args.model.resolve()), precision='fp32')
            service.reindex()
        rows = []
        try:
            for round_no in range(1, args.rounds+1):
                ordered = list(queries)
                random.Random(9160+round_no).shuffle(ordered)
                for query in ordered:
                    if service.core.embed:
                        service.core.embed.cache.clear()
                    started = time.perf_counter()
                    found = service.search(query['query'], limit=10,
                                           context={'reference_time': REFERENCE, **query.get('context', {})})
                    elapsed = (time.perf_counter()-started)*1000
                    ranked = [c['topic_id'] for c in found['route'].get('ranked_candidates', [])]
                    row = scored(query, found['results'], ranked, seed['topic_ids'])
                    row.update(round=round_no, elapsed_ms=elapsed, needs_clarification=found.get('needs_clarification', False),
                               backend=found.get('backend'), plan=found.get('plan'))
                    rows.append(row)
                print(json.dumps({'phase': 'retrieval', 'mode': mode, 'round': round_no, 'requests': len(ordered)}), flush=True)
            jsonl(args.output/f'{mode}-retrieval.jsonl', rows)
            result[mode] = {'seed': seed, 'health': service.health(), 'overall': aggregate(rows),
                            'by_split': grouped(rows, 'split'), 'by_kind': grouped(rows, 'kind')}
        finally:
            service.store.close()
    return result


class DesktopIPC:
    """Real JSON-lines entrypoint, exactly one outstanding request, bounded wait."""
    def __init__(self, directory, log):
        self.stderr = log.open('w')
        self.child = subprocess.Popen([sys.executable, str(ROOT/'scripts/desktop_entry.py'), '--data-dir', str(directory)],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, text=True, bufsize=1)
        self.seq = 0

    def call(self, method, params=None):
        self.seq += 1
        started = time.perf_counter()
        self.child.stdin.write(json.dumps({'id': self.seq, 'method': method, 'params': params or {}}, ensure_ascii=False)+'\n')
        self.child.stdin.flush()
        if not select.select([self.child.stdout], [], [], 60)[0]:
            raise TimeoutError(f'{method} exceeded 60 seconds')
        line = self.child.stdout.readline()
        if not line:
            raise RuntimeError(f'worker exited: {self.child.poll()}')
        response = json.loads(line)
        elapsed = (time.perf_counter()-started)*1000
        if response.get('id') != self.seq or not response.get('ok'):
            raise RuntimeError(response)
        return response['data'], elapsed

    def close(self):
        self.child.stdin.close()
        try:
            self.child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.child.terminate()
            self.child.wait(timeout=10)
        self.stderr.close()


def evaluate_context(args, fresh, topic_ids):
    directory = args.output/'ipc-data'
    directory.mkdir()
    shutil.copy2(args.output/'fp32.sqlite3', directory/'desktop-demo.sqlite3')
    dump(directory/'model.json', {'model_dir': str(args.model.resolve()), 'precision': 'fp32'})
    started = time.perf_counter()
    ipc = DesktopIPC(directory, args.output/'ipc-stderr.log')
    rows = []
    try:
        health, _ = ipc.call('health')
        startup = (time.perf_counter()-started)*1000
        before, _ = ipc.call('bootstrap')
        for round_no in range(1, args.rounds+1):
            for binding in ('unbound', 'explicit_topic'):
                ordered = [q for q in fresh if q['gold_topic'] or binding == 'unbound']
                random.Random(7160+round_no).shuffle(ordered)
                for query in ordered:
                    params = {'query': query['query'], 'limit': 6}
                    if binding == 'explicit_topic':
                        params['topic_id'] = topic_ids[query['gold_topic']]
                    found, elapsed = ipc.call('agent_context', params)
                    contract = found.get('contract') or {}
                    events = [*found['hits'], *[{**e, 'topic_id': contract.get('topic_id')} for e in contract.get('events', [])]]
                    ranked = [c['topic_id'] for c in (found.get('route') or {}).get('ranked_candidates', [])]
                    row = scored(query, events, ranked, topic_ids)
                    row.update(round=round_no, binding=binding, elapsed_ms=elapsed,
                               needs_clarification=bool(found.get('clarification')),
                               contract_topic=contract.get('topic_id'), contract_fields=contract.get('fields'),
                               hits=found['hits'], contract_events=contract.get('events'),
                               response_bytes=len(json.dumps(found, ensure_ascii=False).encode()))
                    rows.append(row)
                print(json.dumps({'phase': 'desktop_context', 'binding': binding, 'round': round_no}), flush=True)
        after, _ = ipc.call('bootstrap')
        assert before['stats'] == after['stats'], 'read queries changed corpus counts'
        assert before['topics'] == after['topics'], 'read queries changed topic content'
        jsonl(args.output/'context-requests.jsonl', rows)
        return {'startup_to_health_ms': startup, 'health': health, 'stats': after['stats'],
                'read_only_corpus_unchanged': True, 'by_binding': grouped(rows, 'binding'),
                'unbound_by_kind': grouped([r for r in rows if r['binding'] == 'unbound'], 'kind'),
                'first_unbound_round': timing([r['elapsed_ms'] for r in rows if r['round'] == 1 and r['binding'] == 'unbound']),
                'warm_later_rounds': timing([r['elapsed_ms'] for r in rows if r['round'] > 1])}
    finally:
        ipc.close()


def rule_suites(output):
    """Structured inputs test resolution, NOT natural-language extraction.

    Four domains exercise each scenario; correlated template variants are
    disclosed. Gold outcomes are explicit, never copied from service output.
    """
    conn = sqlite3.connect(output/'governance.sqlite3')
    gov = Governance(conn)
    rows = []
    def stamp(day):
        return f'2026-09-{day:02d}T00:00:00+00:00'
    def score(suite, case, domain, expected, actual, inputs):
        passed = all(actual.get(key) == value for key, value in expected.items())
        rows.append({'suite': suite, 'case': case, 'domain': domain, 'expected': expected,
                     'actual': actual, 'inputs': inputs, 'passed': passed})
    domains = [('output_language', '中文', '英文'), ('report_format', 'DOCX', 'PDF'),
               ('tool_choice', '本地编辑器', '在线编辑器'), ('review_style', '逐项说明', '简短结论')]
    for domain, old, new in domains:
        for case in ('global', 'scope', 'temporary', 'expired_temporary', 'fallback', 'new_explicit', 'late_old', 'cross_user'):
            user = f'{domain}:{case}'
            inputs = []
            def pref(value, **kwargs):
                payload = {'user_id': user, 'key': domain, 'value': value,
                           'valid_from': stamp(1), 'observed_at': stamp(1), **kwargs}
                inputs.append(payload)
                return gov.record_preference(**payload)
            pref(old)
            query = {'user_id': user, 'key': domain, 'at': stamp(15)}
            expected = {'found': True, 'value': old}
            if case == 'scope':
                pref(new, scope_type='task', scope_id='other_task', observed_at=stamp(3))
                query['task_id'] = 'this_task'
            elif case in ('temporary', 'expired_temporary'):
                pref(new, scope_type='topic', scope_id='topic', choice_type='temporary',
                     observed_at=stamp(3), valid_to=stamp(10) if case == 'expired_temporary' else stamp(20))
                query['topic_id'] = 'topic'
                if case == 'temporary':
                    expected['value'] = new
            elif case == 'fallback':
                pref(new, choice_type='fallback', observed_at=stamp(3))
            elif case == 'new_explicit':
                pref(new, observed_at=stamp(5), valid_from=stamp(5))
                expected['value'] = new
            elif case == 'late_old':
                pref(new, observed_at=stamp(5), valid_from=stamp(5))
                pref(old, observed_at=stamp(10), valid_from=stamp(1))
                expected['value'] = new  # late import must not revert effective preference
            elif case == 'cross_user':
                query['user_id'] = user+':other'
                expected = {'found': False, 'value': None}
            actual = gov.resolve_preference(**query)
            score('preference_resolution', case, domain, expected, actual, {'records': inputs, 'query': query})

        for case in ('current', 'historical', 'known_before_update', 'late_old_bounded', 'future', 'expired',
                     'collision', 'explicit_dispute', 'scope', 'cross_user', 'unknown_at', 'same_fact'):
            user = f'knowledge:{domain}:{case}'
            inputs = []
            def fact(value, **kwargs):
                payload = {'user_id': user, 'key': domain, 'value': value, 'scope_id': 'topic',
                           'valid_from': stamp(1), 'observed_at': stamp(1), **kwargs}
                inputs.append(payload)
                return gov.record_knowledge(**payload)
            first = fact(old, **({'valid_to': stamp(10)} if case == 'expired' else {}))
            query = {'user_id': user, 'key': domain, 'scope_id': 'topic', 'valid_at': stamp(15),
                     'known_at': stamp(15), 'include_disputed': True}
            expected = {'found': True, 'status': 'active', 'value': old}
            if case in ('current', 'historical', 'known_before_update'):
                fact(new, valid_from=stamp(5), observed_at=stamp(10), supersedes=first['id'])
                if case == 'current':
                    expected['value'] = new
                elif case == 'historical':
                    query['valid_at'] = stamp(3)
                else:
                    query['known_at'] = stamp(7)  # new version not observed yet
                    query['valid_at'] = stamp(7)
            elif case == 'late_old_bounded':
                second = fact(new, valid_from=stamp(5), observed_at=stamp(5), supersedes=first['id'])
                fact(old, valid_from=stamp(1), valid_to=stamp(5), observed_at=stamp(12))
                expected['value'] = new
            elif case == 'future':
                fact(new, valid_from=stamp(20), observed_at=stamp(10), supersedes=first['id'])
            elif case == 'expired':
                expected = {'found': False, 'status': 'missing', 'value': None}
            elif case in ('collision', 'explicit_dispute'):
                fact(new, observed_at=stamp(10), disputed=case == 'explicit_dispute', dispute_reason='两份签批互相矛盾')
                expected = {'found': True, 'status': 'disputed'}
            elif case == 'scope':
                fact(new, scope_id='other_topic', observed_at=stamp(10))
            elif case == 'cross_user':
                query['user_id'] = user+':other'
                expected = {'found': False, 'status': 'missing', 'value': None}
            elif case == 'unknown_at':
                query['known_at'] = '2026-08-31T00:00:00+00:00'
                expected = {'found': False, 'status': 'missing', 'value': None}
            elif case == 'same_fact':
                fact(old, observed_at=stamp(10))
            actual = gov.resolve_knowledge(**query)
            score('knowledge_conflict_resolution', case, domain, expected, actual, {'records': inputs, 'query': query})
    conn.close()
    jsonl(output/'rules.jsonl', rows)
    summaries = {}
    for suite in {row['suite'] for row in rows}:
        subset = [row for row in rows if row['suite'] == suite]
        summaries[suite] = {'passed': sum(row['passed'] for row in subset), 'total': len(subset),
                            'accuracy': sum(row['passed'] for row in subset)/len(subset),
                            'scenario_families': len({row['case'] for row in subset}), 'variants_per_family': 4,
                            'failures': [{'case': row['case'], 'domain': row['domain'],
                                          'expected': row['expected'], 'actual': row['actual']} for row in subset if not row['passed']]}
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=3)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error('--rounds must be positive')
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error('Use a NEW output directory; old results are immutable')
    if os.environ.get('MEMPULSE_MODEL_DIR'):
        parser.error('Unset MEMPULSE_MODEL_DIR so lexical baseline cannot load a model')
    args.output.mkdir(parents=True)
    sources = [*sorted((ROOT/'src/mempulse').rglob('*.py')), Path(__file__).resolve(), ROOT/'scripts/competition_cases.py', ROOT/'scripts/desktop_entry.py']
    source_hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    cases = merged_cases()
    fresh = fresh_questions(cases)
    queries = [{**q, 'split': 'existing_development'} for q in merged_questions()] + fresh
    assert len({q['id'] for q in queries}) == len(queries)
    assert len({q['query'] for q in queries}) == len(queries)
    dump(args.output/'questions.json', queries)
    dump(args.output/'corpus.json', cases)
    dump(args.output/'source-sha256.json', source_hashes)
    summary = {'created_at': datetime.now(timezone.utc).isoformat(), 'competition': 'XA-202612',
               'formal_acceptance': False, 'synthetic': True, 'human_reviewed': False,
               'training_overlap_verified': False, 'answer_model_tested': False,
               'preference_extraction_tested': False, 'kylin_sdk_tested': False,
               'environment': {'platform': platform.platform(), 'machine': platform.machine(),
                               'python': platform.python_version(), 'cpu_count': os.cpu_count()},
               'source_sha256': source_hashes, 'rounds': args.rounds, 'unique_questions': len(queries),
               'split_counts': dict(Counter(q['split'] for q in queries)),
               'metric_contract': {'retrieval': 'Macro/micro relevant source-event Recall@10, with separately labelled full evidence coverage; official PDF does not specify K.',
                                   'latency': 'Facade: query cache cleared each call; IPC: actual desktop_entry JSON-lines agent_context, default cache, 6 hits and optionally 4 bound events. Process startup separate. No Electron IPC or LLM generation.',
                                   'rules': 'Structured input supplied; resolution correctness only, no NLP extraction or confirmation inference.',
                                   'fresh_split': 'Fresh questions on existing synthetic corpus; authored with code knowledge, no claim of blind holdout.',
                                   'atoms': 'All authored factual substrings present in returned evidence truncated to 200 chars, as host hit rendering does. Context sufficiency proxy, not generated-answer correctness.'},
               'model_files': {str(p.relative_to(args.model)): digest(p) for p in sorted(args.model.rglob('*')) if p.is_file() and p.name in ('model-fp32.onnx', 'tokenizer.json', 'config.json', 'runtime_config.json')}}
    summary['rules'] = rule_suites(args.output)
    dump(args.output/'summary-progress.json', summary)
    summary['retrieval'] = evaluate_retrieval(args, queries)
    dump(args.output/'summary-progress.json', summary)
    summary['desktop_context'] = evaluate_context(args, fresh, summary['retrieval']['fp32']['seed']['topic_ids'])
    assert source_hashes == {str(path.relative_to(ROOT)): digest(path) for path in sources}, 'Production source changed during evaluation'
    dump(args.output/'summary.json', summary)
    print(json.dumps({'completed': str(args.output), 'rules': {k: (v['passed'], v['total']) for k, v in summary['rules'].items()}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
