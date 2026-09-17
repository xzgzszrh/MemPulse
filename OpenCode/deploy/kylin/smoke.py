#!/usr/bin/env python3
"""Exercise real JSON-lines IPC in an isolated temporary memory directory."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--service', type=Path, help='Native packaged service; omit to exercise Python source')
parser.add_argument('--bundled-model', action='store_true', help='Require automatic bundled FP32 loading')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
if args.bundled_model and not args.service:
    parser.error('--bundled-model requires --service')
calls = [('health', {}), ('bootstrap', {})]
if not args.bundled_model:
    calls.append(('configure_model', {'model_dir': str(root / '微调模型/revision4-model-bundle'), 'precision': 'fp32'}))
calls.append(('reindex', {}))
queries = ['澄海园区的夜间清洁用水如何分时？', '北麓实验室的接口鉴权问题解决了吗？',
           '栖川工厂的中文打印驱动还有什么待测？', '澄海园区的第三版验收模板', '继续那个报告']
calls.extend(('search', {'query': query, 'limit': 6}) for _ in range(3) for query in queries)
calls.extend([
    ('switch_workspace', {'workspace': 'personal'}),
    ('ingest', {'event_id': 'packaged-mode-probe', 'content': '安装包隔离测试：个人工作记录保留。',
                'metadata': {'force_new': True}}),
    ('switch_workspace', {'workspace': 'demo'}),
    ('switch_workspace', {'workspace': 'personal'}),
    ('switch_workspace', {'workspace': 'demo'}),
    ('bootstrap', {}), ('health', {}),
])
messages = '\n'.join(json.dumps({'id': i, 'method': method, 'params': params}, ensure_ascii=False)
                     for i, (method, params) in enumerate(calls)) + '\n'
with tempfile.TemporaryDirectory(prefix='mempulse-kylin-smoke-') as temporary:
    command = [str(args.service.resolve())] if args.service else [sys.executable, str(root / 'MemPulse/scripts/desktop_entry.py')]
    started = time.perf_counter()
    process = subprocess.run([*command, '--data-dir', temporary], input=messages, capture_output=True, text=True, timeout=180)
    if process.returncode:
        raise SystemExit(f'Sidecar exited {process.returncode}:\n{process.stderr[-6000:]}')
    rows = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    assert len(rows) == len(calls), f'Expected {len(calls)} responses, got {len(rows)}'
    for i, row in enumerate(rows):
        assert row['id'] == i and row['ok'], row
    assert rows[1]['data']['stats']['topics'] == 53 and rows[1]['data']['stats']['events'] == 284, 'Bundled demo must exist before enrichment'
    personal = [row['data'] for (method, params), row in zip(calls, rows) if method == 'switch_workspace' and params['workspace'] == 'personal']
    assert personal[0]['stats']['topics'] == 0 and personal[0]['stats']['events'] == 0
    assert personal[1]['stats']['topics'] == 1 and personal[1]['stats']['events'] == 1, 'Personal memory did not survive workspace switch'
    assert personal[1]['events'][0]['event_id'] == 'packaged-mode-probe'
    for (method, params), row in zip(calls, rows):
        if method != 'switch_workspace' or params['workspace'] != 'demo': continue
        assert row['data']['stats']['topics'] == 53 and row['data']['stats']['events'] == 284, 'Demo duplicated or replaced on switch'
    health = rows[-1]['data']
    assert health['embedding']['precision'] == 'fp32', health
    assert health['embedding']['manifest_verified'], health
    assert health['embedding']['automatic_binding_allowed'] is False, health
    if args.bundled_model:
        assert rows[0]['data']['embedding']['precision'] == 'fp32', rows[0]
    for (method, _), row in zip(calls, rows):
        if method != 'search':
            continue
        assert row['data']['backend'] == 'topic_first_tide', row
        assert row['data']['route']['routing_policy'] == 'retrieval_only', row
        assert row['data']['route']['topic_id'] is None, row
    report = {'ok': True, 'isolated_temporary_database': True, 'service': command,
              'bundled_model': args.bundled_model, 'checks': len(rows), 'search_requests': 15,
              'demo_available_before_enrichment': True, 'workspace_roundtrip_preserves_data': True,
              'wall_seconds': round(time.perf_counter() - started, 3),
              'stats': rows[-2]['data']['stats'], 'health': health,
              'search_ms': [row['data']['elapsed_ms'] for (method, _), row in zip(calls, rows) if method == 'search']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({key: report[key] for key in ['ok', 'checks', 'search_requests', 'stats']}, ensure_ascii=False))
