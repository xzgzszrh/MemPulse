"""Unix-socket daemon transport for the PDF's yishu-memd runtime shape."""
from __future__ import annotations
import json, os, socketserver, threading
from pathlib import Path
from .facade import get_facade

class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        service=self.server.service
        for raw in self.rfile:
            try:
                req=json.loads(raw);method=req.get('method');args=req.get('arguments',{})
                if method=='health':out=service.health()
                elif method=='topics':out=service.list_topics()
                elif method=='context':out=service.context(**args)
                elif method=='ingest':out=service.ingest(args)
                elif method=='run':out=service.run_tool(**args)
                elif method=='search':out=service.search(args.get('query',''),limit=args.get('limit',20))
                elif method=='restore':out=service.restore(args.get('topic_id'),args.get('query'))
                elif method=='relations':out=service.query_relations(**args)
                elif method=='preference':out=service.update_preference(args)
                elif method=='knowledge':out=service.knowledge(args)
                elif method=='forget':out=service.forget(args['target_type'],args['target_id'])
                elif method=='forget_field':out=service.forget_field(args['event_id'],args['field_path'])
                elif method=='checkpoint':out=service.checkpoint(args['topic_id'])
                elif method=='worker':
                    from .worker import OutboxWorker
                    out=OutboxWorker(service.store,service).drain()
                elif method=='reindex':out=service.reindex()
                else:raise ValueError('unknown daemon method: '+str(method))
                response={'ok':True,'data':out}
            except Exception as exc:response={'ok':False,'error':str(exc)}
            self.wfile.write((json.dumps(response,ensure_ascii=False)+'\n').encode());self.wfile.flush()

class MemPulseDaemon:
    def __init__(self,socket_path,db_path=None,user_id='default'):
        self.socket_path=Path(socket_path);self.db_path=db_path;self.user_id=user_id
        self.server=None
    def serve_forever(self):
        self.socket_path.parent.mkdir(parents=True,exist_ok=True)
        try:self.socket_path.unlink()
        except FileNotFoundError:pass
        self.server=socketserver.ThreadingUnixStreamServer(str(self.socket_path),_Handler)
        self.server.daemon_threads=True;self.server.service=get_facade(self.db_path,user_id=self.user_id)
        os.chmod(self.socket_path,0o600)
        try:self.server.serve_forever(poll_interval=.2)
        finally:self.server.service.store.close();self.server.server_close();self.socket_path.unlink(missing_ok=True)
