"""Check the same JSON-lines transport used by Electron, on a prepared data directory."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True);p.add_argument('--output',required=True)
p.add_argument('--expected-topics',type=int);p.add_argument('--expected-events',type=int);args=p.parse_args()
project=Path(__file__).resolve().parents[1]
started=time.perf_counter()
child=subprocess.Popen([sys.executable,str(project/'scripts/desktop_entry.py'),'--data-dir',str(Path(args.data_dir).resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
seq=0
rows=[]
def call(method,params=None):
    global seq
    seq+=1
    before=time.perf_counter()
    child.stdin.write(json.dumps({'id':seq,'method':method,'params':params or {}},ensure_ascii=False)+'\n');child.stdin.flush()
    result=json.loads(child.stdout.readline())
    assert result['id']==seq and result['ok'],result
    rows.append({'method':method,'elapsed_ms':(time.perf_counter()-before)*1000})
    return result['data']
try:
    health=call('health')
    startup_ms=(time.perf_counter()-started)*1000
    assert health['embedding']['precision']=='fp32' and health['embedding']['dimension']==768
    bootstrap=call('bootstrap')
    assert bootstrap['stats']['topics']==len(bootstrap['topics'])
    assert bootstrap['stats']['events']==sum(len(topic['event_ids']) for topic in bootstrap['topics'])
    if args.expected_topics is not None: assert bootstrap['stats']['topics']==args.expected_topics
    if args.expected_events is not None: assert bootstrap['stats']['events']==args.expected_events
    for round_index in range(3):
        for query in ['澄海园区的夜间清洁用水如何分时？','北麓实验室的接口鉴权问题解决了吗？','栖川工厂的中文打印驱动还有什么待测？','澄海园区的第三版验收模板','继续那个报告']:
            result=call('search',{'query':query,'limit':6})
            assert result['backend']=='topic_first_tide'
            assert result['route']['routing_policy']=='retrieval_only'
            assert result['route']['topic_id'] is None
    assert call('bootstrap')['stats']==bootstrap['stats'], 'read-only searches changed memory statistics'
    output={'transport':'JSON-lines subprocess, same desktop_entry.py used by Electron','startup_to_health_ms':startup_ms,
        'health':health,'stats':bootstrap['stats'],'requests':rows,'search_rounds':3,'search_requests':15,
        'cache_policy':'first round has new queries; later rounds use the normal bounded query cache'}
    Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print(json.dumps({'startup_ms':startup_ms,'stats':bootstrap['stats'],'checks':len(rows)},ensure_ascii=False))
finally:
    child.stdin.close()
    child.wait(timeout=15)
    error=child.stderr.read()
    if error: print(error,file=sys.stderr)
