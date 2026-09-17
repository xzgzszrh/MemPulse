"""Standalone FP32 topic-vector retrieval; never auto-assigns a topic."""
import argparse,json
from pathlib import Path
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

def main():
 p=argparse.ArgumentParser();p.add_argument('--query',required=True);p.add_argument('--topics',default='topics.json');p.add_argument('--model',default='encoder');p.add_argument('--precision',choices=['fp32','mixed-int8'],default='fp32');args=p.parse_args()
 root=Path(args.model);cfg=json.loads((root/'tide_config.json').read_text());tok=Tokenizer.from_file(str(root/'tokenizer.json'));tok.no_truncation();tok.no_padding()
 opt=ort.SessionOptions();opt.intra_op_num_threads=4;session=ort.InferenceSession(str(root/('model-fp32.onnx' if args.precision=='fp32' else 'model-int8-mixed.onnx')),sess_options=opt,providers=['CPUExecutionProvider'])
 def encode(texts,query=False):
  if any(not x.strip() for x in texts):raise ValueError('empty input: use fallback')
  seqs=tok.encode_batch([cfg['query_instruction']+t if query else t for t in texts]);limit=cfg['query_max_length' if query else 'topic_max_length']
  if any(len(s.ids)>limit for s in seqs):raise ValueError('input exceeds complete-text token budget: use fallback, do not truncate identity evidence')
  width=max(len(s.ids) for s in seqs);shape=(len(seqs),width);ids=np.zeros(shape,dtype=np.int64);mask=np.zeros(shape,dtype=np.int64);types=np.zeros(shape,dtype=np.int64)
  for i,s in enumerate(seqs):ids[i,:len(s.ids)]=s.ids;mask[i,:len(s.ids)]=1;types[i,:len(s.ids)]=s.type_ids
  v=session.run(['sentence_embedding'],{'input_ids':ids,'attention_mask':mask,'token_type_ids':types})[0]
  assert v.shape==(len(texts),768) and np.isfinite(v).all()
  return v/np.linalg.norm(v,axis=1,keepdims=True)
 topics=json.loads(Path(args.topics).read_text());assert len({t['topic_id'] for t in topics})==len(topics)
 q=encode([args.query],True)[0];vectors=encode([t['text'] for t in topics]) if topics else np.zeros((0,768));scores=vectors@q
 candidates=sorted([{'topic_id':t['topic_id'],'cosine_similarity':float(s)} for t,s in zip(topics,scores)],key=lambda x:-x['cosine_similarity'])
 print(json.dumps({'dimension':768,'candidates':candidates,'assignment':None,'attribution_probability':None,'status':'retrieval_only','automatic_binding_allowed':False},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
