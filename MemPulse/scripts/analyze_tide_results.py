"""Analyze a frozen evaluation run; threshold exploration never changes runtime policy."""
import argparse
import json
from collections import Counter
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('output');args=p.parse_args();root=Path(args.output)
rows=[json.loads(line) for line in (root/'fp32-requests.jsonl').read_text().splitlines()]
rows=[row for row in rows if row['round']==1]
validation=[row for row in rows if (row['gold'] and row['gold'].startswith('chenghai:')) or (row['gold'] is None and int(row['id'].split(':')[1])<6)]
validation_ids={row['id'] for row in validation}
test=[row for row in rows if row['id'] not in validation_ids]

def measure(items,theta,delta):
    accepted=[];positive=0;covered=0;correct=0
    for row in items:
        scores=row['scores'];first=scores[0]['score'] if scores else 0;second=scores[1]['score'] if len(scores)>1 else 0
        route='NEW' if first<theta else 'AMBIGUOUS' if first-second<delta else 'RESUME'
        if row['gold'] is not None:
            positive+=1;covered+=int(route=='RESUME')
        gold_route='RESUME' if row['gold'] else 'NEW' if row['kind']=='absent_customer' else 'AMBIGUOUS'
        correct+=int(route==gold_route and (route!='RESUME' or row['gold']==row['top1_id']))
        if route=='RESUME': accepted.append(row)
    return {'theta':theta,'delta':delta,'coverage':covered/positive,'accepted':len(accepted),
        'accepted_error':sum(row['gold'] is None or row['gold']!=row['top1_id'] for row in accepted)/len(accepted) if accepted else None,
        'route_and_identity_accuracy':correct/len(items)}

candidates=[measure(validation,theta/100,delta/100) for theta in range(10,91) for delta in range(31)]
valid=[item for item in candidates if item['coverage']>=.9 and item['accepted_error'] is not None and item['accepted_error']<=.03]
high_coverage=[item for item in candidates if item['coverage']>=.9 and item['accepted_error'] is not None]
low_error=[item for item in candidates if item['accepted_error'] is not None and item['accepted_error']<=.03]
selected=max(valid,key=lambda row:row['route_and_identity_accuracy']) if valid else None
best=min(high_coverage,key=lambda row:row['accepted_error']) if high_coverage else None
report={'method':'reference fusion scores; grid selected only on first-customer validation plus half of negative cases',
    'validation_queries':len(validation),'test_queries':len(test),'validation_ids':sorted(validation_ids),
    'constraints':{'coverage_min':.9,'accepted_error_max':.03},'passed_validation_gate':bool(valid),'selected':selected,
    'test_at_selected':measure(test,selected['theta'],selected['delta']) if selected else None,
    'best_error_at_90_coverage':best,'test_at_best_90_coverage':measure(test,best['theta'],best['delta']) if best else None,
    'max_coverage_at_3_error':max(low_error,key=lambda row:row['coverage']) if low_error else None,
    'applied_to_runtime':False,'synthetic':True,'formal_acceptance':False}
(root/'routing-calibration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
errors=[row for row in rows if row['gold'] is not None and row['rank']!=1]
counts=Counter()
for row in errors:
    gold=row['gold'].split(':');pred=(row['top1_id'] or '').split(':')
    kind='cross_customer_same_task' if len(pred)==2 and pred[1]==gold[1] else 'wrong_task_same_customer' if len(pred)==2 and pred[0]==gold[0] else 'other'
    counts[kind]+=1
(root/'error-analysis.json').write_text(json.dumps({'unique_positive_queries':108,'top1_errors':len(errors),'categories':dict(counts),
    'examples':[{key:row[key] for key in ['id','query','gold','top1_id','rank']} for row in errors]},ensure_ascii=False,indent=2))
print(json.dumps({'validation_gate':report['passed_validation_gate'],'best_error_at_90_coverage':best,'top1_error_categories':dict(counts)},ensure_ascii=False))
