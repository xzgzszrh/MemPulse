"""Local TIDE/BGE ONNX inference with explicit precision and input contracts."""
from __future__ import annotations
import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from threading import RLock


class EmbeddingInputError(ValueError):
    """Input needs lexical/graph fallback; identity evidence must not be truncated."""


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def model_assets(root, precision='fp32'):
    if precision not in ('fp32', 'mixed-int8'):
        raise ValueError('precision must be fp32 or mixed-int8')
    root = Path(root).expanduser().resolve()
    encoder = root / 'encoder' if (root / 'encoder').is_dir() else root
    bundle = root if encoder != root else root.parent
    manifest_path = bundle / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    name = 'model-fp32.onnx' if precision == 'fp32' else 'model-int8-mixed.onnx'
    model = encoder / name
    if not model.exists() and precision == 'fp32' and not manifest:
        model = encoder / 'model.onnx'
    required = [model, encoder / 'tokenizer.json']
    config_path = encoder / 'tide_config.json'
    if config_path.exists():
        required.append(config_path)
    if manifest and not config_path.exists():
        raise FileNotFoundError(f'missing TIDE input configuration: {config_path}')
    hashes = {}
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f'missing local model asset: {path}')
        actual = file_sha256(path)
        hashes[path.name] = actual
        if manifest:
            declared = manifest.get('files', {}).get(path.relative_to(bundle).as_posix())
            if not declared or declared.get('sha256') != actual or declared.get('bytes') != path.stat().st_size:
                raise ValueError(f'model manifest mismatch: {path.name}')
    config = json.loads(config_path.read_text()) if config_path.exists() else {
        'query_max_length': 128, 'topic_max_length': 384, 'pooling': 'cls', 'normalize': True,
        'query_instruction': '为这个句子生成表示以用于检索相关文章：',
    }
    fingerprint = hashlib.sha256(json.dumps({'hashes': hashes, 'config': config}, sort_keys=True).encode()).hexdigest()
    return {
        'root': encoder, 'model': model, 'config': config, 'precision': precision,
        'revision': f'tide:{precision}:{fingerprint[:20]}', 'hashes': hashes,
        'manifest_verified': bool(manifest),
        'automatic_binding_allowed': manifest.get('automatic_binding_allowed', False),
    }


class OnnxEncoder:
    dimension = 768

    def __init__(self, root, precision='fp32', threads=4, cache_size=128):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.assets = model_assets(root, precision)
        self.revision = self.assets['revision']
        self.config = self.assets['config']
        self.automatic_binding_allowed = self.assets['automatic_binding_allowed']
        if self.config.get('pooling') != 'cls' or not self.config.get('normalize'):
            raise ValueError('only CLS pooling with L2 normalization is supported')
        self.tokenizer = Tokenizer.from_file(str(self.assets['root'] / 'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.lock = RLock()
        self.cache = OrderedDict()
        self.cache_size = max(0, int(cache_size))
        self.inference_calls = 0
        self.cache_hits = 0
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, int(threads))
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(self.assets['model']), sess_options=options, providers=['CPUExecutionProvider'])
        self.input_names = {item.name for item in self.session.get_inputs()}
        output_names = {item.name for item in self.session.get_outputs()}
        self.output_name = 'sentence_embedding' if 'sentence_embedding' in output_names else self.session.get_outputs()[0].name

    def encode_batch(self, texts, *, query=False):
        import numpy as np
        texts = list(texts)
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingInputError('empty input; use lexical/graph fallback')
        prefix = self.config['query_instruction'] if query else ''
        limit = self.config['query_max_length' if query else 'topic_max_length']
        with self.lock:
            sequences = self.tokenizer.encode_batch([prefix + text for text in texts])
            if any(len(sequence.ids) > limit for sequence in sequences):
                raise EmbeddingInputError(f'complete input exceeds {limit} tokens; no truncation performed')
            shape = (len(sequences), max(len(sequence.ids) for sequence in sequences))
            ids = np.zeros(shape, dtype=np.int64)
            mask = np.zeros(shape, dtype=np.int64)
            types = np.zeros(shape, dtype=np.int64)
            for i, sequence in enumerate(sequences):
                size = len(sequence.ids)
                ids[i, :size] = sequence.ids
                mask[i, :size] = 1
                types[i, :size] = sequence.type_ids
            available = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': types}
            vectors = self.session.run([self.output_name], {key: available[key] for key in self.input_names})[0]
            self.inference_calls += 1
            if vectors.ndim == 3:
                vectors = vectors[:, 0, :]
            if vectors.shape != (len(texts), self.dimension) or not np.isfinite(vectors).all():
                raise RuntimeError('invalid embedding shape or non-finite output')
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if np.any(norms < 1e-12):
                raise RuntimeError('zero-length embedding')
            return [tuple(float(value) for value in row) for row in vectors / norms]

    def _encode(self, text, query):
        with self.lock:
            key = (query, text)
            if key in self.cache:
                self.cache_hits += 1
                self.cache.move_to_end(key)
                return self.cache[key]
            vector = self.encode_batch([text], query=query)[0]
            if self.cache_size:
                self.cache[key] = vector
                while len(self.cache) > self.cache_size:
                    self.cache.popitem(last=False)
            return vector

    def clear_cache(self):
        with self.lock:
            self.cache.clear()

    def encode_query(self, text):
        return self._encode(text, True)

    def __call__(self, text):
        return self._encode(text, False)

    def info(self):
        return {
            'revision': self.revision, 'precision': self.assets['precision'], 'dimension': self.dimension,
            'provider': 'CPUExecutionProvider', 'manifest_verified': self.assets['manifest_verified'],
            'model_sha256': self.assets['hashes'][self.assets['model'].name],
            'query_max_length': self.config['query_max_length'], 'topic_max_length': self.config['topic_max_length'],
            'automatic_binding_allowed': self.automatic_binding_allowed,
            'inference_calls': self.inference_calls, 'cache_hits': self.cache_hits,
        }
