#!/usr/bin/env python3
"""Export public benchmark metrics and minimal per-request evidence without local paths/databases."""
import argparse
from pathlib import Path
import hashlib
import json
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--run',type=Path,required=True)
p.add_argument('--boundaries',type=Path,required=True)
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--cpu',required=True)
p.add_argument('--memory-gib',type=float,required=True)
p.add_argument('--onnxruntime-version',required=True)
a=p.parse_args()
s=json.loads((a.run/'summary.json').read_text())
b=json.loads((a.boundaries/'boundaries.json').read_text())
for name,expected in s['source_sha256'].items():
    assert hashlib.sha256((a.source_root/name).read_bytes()).hexdigest()==expected, name
for name,expected in b['source_sha256'].items():
    assert hashlib.sha256((a.source_root/name).read_bytes()).hexdigest()==expected, name
commit=subprocess.check_output(['git','-C',str(a.source_root),'rev-parse','HEAD'],text=True).strip()
keys=['unique_queries','positive_queries','topic_top1','topic_recall_at_3','evidence_recall_macro','evidence_recall_micro','evidence_hit','evidence_complete','evidence_complete_count','answer_atoms_complete','answer_atoms_denominator','timing','rounds_consistent']
def metrics(x):return {k:x[k] for k in keys if k in x}
result={
    'schema_version':1,'created_at':s['created_at'],
    'source':{'repository':'https://github.com/xzgzszrh/MemPulse','commit':commit,'sha256':s['source_sha256'],'boundary_sha256':b['source_sha256']},
    'model_files':s['model_files'],
    'environment':{**s['environment'],'cpu':a.cpu,'memory_gib':a.memory_gib,'onnxruntime_version':a.onnxruntime_version,'execution_provider':s['retrieval']['fp32']['health']['embedding']['provider']},
    'dataset':{'topics':s['desktop_context']['stats']['topics'],'events':s['desktop_context']['stats']['events'],'unique_queries':s['unique_questions'],'positive_queries':s['retrieval']['fp32']['overall']['positive_queries'],'split_counts':s['split_counts'],'rounds':s['rounds'],'synthetic':True,'independently_reviewed':False,'training_overlap_verified':False},
    'retrieval':{mode:{'overall':metrics(v['overall']),'by_kind':{k:metrics(x) for k,x in v['by_kind'].items()},'by_split':{k:metrics(x) for k,x in v['by_split'].items()}} for mode,v in s['retrieval'].items()},
    'desktop_context':{'by_binding':{k:metrics(x) for k,x in s['desktop_context']['by_binding'].items()},'startup_to_health_ms':s['desktop_context']['startup_to_health_ms'],'read_only_corpus_unchanged':s['desktop_context']['read_only_corpus_unchanged']},
    'structured_rule_checks':{k:{'passed':v['passed'],'total':v['total'],'accuracy':v['accuracy']} for k,v in s['rules'].items()},
    'boundary_checks':[{'name':x['name'],'passed':x['passed']} for x in b['probes']],
    'scope':{'comparison':'Both configurations use the same topic-based organization; this is an encoder comparison, not a topic-vs-flat-memory ablation.','accuracy_denominator':'First-round unique positive queries; repeated rounds are not independent accuracy samples.','timing':'All three rounds; retrieval query embedding cache cleared before each request. Excludes startup, Electron UI/IPC and LLM generation.','context':'Correct topic ID is supplied to the explicit_topic condition; it is not automatic topic recognition. Bound requests run after unbound requests and benefit from cache.','not_measured':['topic-vs-flat-memory causal benefit','LLM final answer quality','independent real-user holdout','Kylin target hardware/SDK','natural-language preference extraction']}
}
a.output.mkdir(parents=True,exist_ok=True)
(a.output/'measurements.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
public=[]
for mode in ['lexical','fp32']:
    rows=[json.loads(line) for line in (a.run/f'{mode}-retrieval.jsonl').read_text().splitlines()]
    for row in rows:
        public.append({'mode':mode,'id':row['id'],'round':row['round'],'split':row['split'],'kind':row['kind'],'positive':bool(row['gold_topic']),'rank':row['rank'],'expected_evidence_count':len(row['expected_evidence']),'matched_evidence_count':len(row['expected_evidence'])-len(row['missing_evidence']),'evidence_recall':row['evidence_recall'],'evidence_complete':row['evidence_complete'],'elapsed_ms':row['elapsed_ms']})
(a.output/'retrieval-requests.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in public))
rows=[json.loads(line) for line in (a.run/'context-requests.jsonl').read_text().splitlines()]
fields=['id','query','round','binding','evidence_recall','evidence_complete','atoms_complete','elapsed_ms']
context=[{**{k:x[k] for k in fields},'positive':bool(x['gold_topic']),'expected_evidence_count':len(x['expected_evidence']),'matched_evidence_count':len(x['expected_evidence'])-len(x['missing_evidence'])} for x in rows]
(a.output/'context-requests.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in context))
print(json.dumps({'source_commit':commit,'retrieval_requests':len(public),'context_requests':len(context)}))
