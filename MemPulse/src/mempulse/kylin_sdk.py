"""Safe openKylin embedding SDK adapter boundary.

SDK symbol names/signatures vary by installed release; this adapter refuses to
silently substitute ONNX and reports the missing capability until a target
machine's header and library have been verified.
"""
from __future__ import annotations
import ctypes
from dataclasses import dataclass

class SDKUnavailable(RuntimeError):pass
@dataclass(frozen=True)
class SDKStatus:
    backend:str; library:str|None; model:str|None; dimension:int|None; status:str; reason:str|None=None
    def to_dict(self):return self.__dict__.copy()
class KylinEmbeddingSDK:
    def __init__(self,library='libkysdk-coreai-embedding.so',model=None,dimension=None):
        self.library=library;self.model=model;self.dimension=dimension;self.lib=None
    def probe(self):
        try:self.lib=ctypes.CDLL(self.library)
        except OSError as exc:return SDKStatus('kylin-sdk',self.library,self.model,self.dimension,'unavailable',str(exc))
        required=('text_embedding_session_new','text_embedding_init_model','text_embedding')
        missing=[name for name in required if not hasattr(self.lib,name)]
        if missing:return SDKStatus('kylin-sdk',self.library,self.model,self.dimension,'unavailable','missing symbols: '+','.join(missing))
        if not self.model or not self.dimension:return SDKStatus('kylin-sdk',self.library,self.model,self.dimension,'needs_header_verification','model and dimension are required')
        return SDKStatus('kylin-sdk',self.library,self.model,self.dimension,'library_loaded')
    def encode(self,texts):
        status=self.probe()
        raise SDKUnavailable(status.reason or 'C ABI signatures are not verified for this target')
