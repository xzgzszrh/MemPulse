"""Local numerical diagnostics with fixed text; never alters the delivered weights."""
import argparse
import json
import platform
import time
from pathlib import Path
import onnxruntime as ort
from mempulse.embeddings import OnnxEncoder

PROBES = ['夜班清洁那部分水量该放在哪个时段？','继续昨天的交付验收材料','澄海园区的库存接口签名仍然失败','北麓实验室需要恢复之前的离线备份','打印驱动升级后中文字体是否正常','英文摘要的产品型号保持原样']

p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--output',required=True);args=p.parse_args()
reference=OnnxEncoder(args.model)
expected=reference.encode_batch(PROBES,query=True)
rows=[]
for name,level in [('disabled',ort.GraphOptimizationLevel.ORT_DISABLE_ALL),('basic',ort.GraphOptimizationLevel.ORT_ENABLE_BASIC),('extended',ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED),('all',ort.GraphOptimizationLevel.ORT_ENABLE_ALL)]:
    candidate=OnnxEncoder(args.model,precision='mixed-int8')
    options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1;options.graph_optimization_level=level
    candidate.session=ort.InferenceSession(str(candidate.assets['model']),sess_options=options,providers=['CPUExecutionProvider'])
    for batch in (1,6):
        started=time.perf_counter()
        actual=[candidate.encode_batch([text],query=True)[0] for text in PROBES] if batch==1 else candidate.encode_batch(PROBES,query=True)
        cosines=[sum(a*b for a,b in zip(left,right)) for left,right in zip(expected,actual)]
        row={'optimization':name,'batch':batch,'cosines':cosines,'minimum_cosine':min(cosines),'elapsed_ms':(time.perf_counter()-started)*1000}
        rows.append(row);print(json.dumps(row),flush=True)
    del candidate
report={'onnxruntime':ort.__version__,'platform':platform.platform(),'queries':PROBES,'results':rows,'reference':reference.info()}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2))
