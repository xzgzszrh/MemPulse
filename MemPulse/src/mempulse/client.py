"""Thin clients for a resident local daemon."""
import json,socket
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError
class HTTPFacade:
    def __init__(self,url):
        if not url.startswith(('http://127.0.0.1:','http://localhost:')):raise ValueError('CLI server must be a loopback URL')
        self.url=url.rstrip('/')
    def request(self,path,body=None):
        req=Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=30) as r:return json.load(r)
        except HTTPError as e:raise ValueError(e.read().decode()) from e
    def health(self):return self.request('/api/health')
    def list_topics(self):return self.request('/api/topics')
    def ingest(self,event):return self.request('/api/ingest',event)
    def context(self,query,**kwargs):return self.request('/api/context?'+urlencode({'q':query}))
    def run_tool(self,**kwargs):return self.request('/api/run',kwargs)
    def search(self,query,**kwargs):return self.request('/api/search?'+urlencode({'q':query,'limit':kwargs.get('limit',20)}))
    def resolve(self,query):return self.request('/api/resolve?'+urlencode({'q':query}))
    def restore(self,topic_id=None,query=None):return self.request('/api/restore?'+urlencode({k:v for k,v in {'topic_id':topic_id,'q':query}.items() if v is not None}))
    def checkpoint(self,topic_id):return self.request('/api/checkpoint',{'topic_id':topic_id})
    def update_preference(self,event):return self.request('/api/preference',event)
    def knowledge(self,event):return self.request('/api/knowledge',event)
    def forget(self,target_type,target_id):return self.request('/api/forget',{'target_type':target_type,'target_id':target_id})
    def forget_field(self,event_id,field_path):return self.request('/api/forget-field',{'event_id':event_id,'field_path':field_path})
    def query_relations(self,person_a,person_b,**kwargs):return self.request('/api/relations?'+urlencode({k:v for k,v in {'person_a':person_a,'person_b':person_b,**kwargs}.items() if v is not None}))
    def reindex(self):return self.request('/api/reindex',{})
    def worker(self):return self.request('/api/worker',{})
class UnixFacade:
    def __init__(self,path):self.path=path
    def request(self,method,args=None):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.settimeout(30);s.connect(self.path);s.sendall((json.dumps({'method':method,'arguments':args or {}},ensure_ascii=False)+'\n').encode());data=b''
            while not data.endswith(b'\n'):data+=s.recv(65536)
        result=json.loads(data)
        if not result.get('ok'):raise ValueError(result.get('error','daemon error'))
        return result['data']
    def health(self):return self.request('health')
    def list_topics(self):return self.request('topics')
    def ingest(self,event):return self.request('ingest',event)
    def context(self,query,**kwargs):return self.request('context',{'query':query,**kwargs})
    def run_tool(self,**kwargs):return self.request('run',kwargs)
    def search(self,query,**kwargs):return self.request('search',{'query':query,**kwargs})
    def resolve(self,query):return self.request('context',{'query':query})
    def restore(self,topic_id=None,query=None):return self.request('restore',{'topic_id':topic_id,'query':query})
    def checkpoint(self,topic_id):return self.request('checkpoint',{'topic_id':topic_id})
    def update_preference(self,event):return self.request('preference',event)
    def knowledge(self,event):return self.request('knowledge',event)
    def forget(self,target_type,target_id):return self.request('forget',{'target_type':target_type,'target_id':target_id})
    def forget_field(self,event_id,field_path):return self.request('forget_field',{'event_id':event_id,'field_path':field_path})
    def query_relations(self,person_a,person_b,**kwargs):return self.request('relations',{'person_a':person_a,'person_b':person_b,**kwargs})
    def reindex(self):return self.request('reindex')
    def worker(self):return self.request('worker')
