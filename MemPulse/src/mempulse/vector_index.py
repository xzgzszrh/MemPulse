"""Version-scoped HNSW cache over SQLite's authoritative vectors."""

from .graph import cosine


class VectorIndex:
    def __init__(self, records):
        self.ids = [r[0] for r in records]
        self.vectors = [tuple(r[1]) for r in records]
        self.index = None
        self.backend = "exact"
        if not self.ids:
            return
        self.dimension = len(self.vectors[0])
        if any(len(v) != self.dimension for v in self.vectors):
            raise ValueError("mixed vector dimensions")
        try:
            import hnswlib
            import numpy as np
        except ImportError:
            return
        self.index = hnswlib.Index(space="cosine", dim=self.dimension)
        self.index.init_index(
            max_elements=max(1, len(self.ids)),
            ef_construction=100,
            M=16,
            random_seed=42,
        )
        self.index.add_items(
            np.asarray(self.vectors, dtype=np.float32),
            list(range(len(self.ids))),
            num_threads=1,
        )
        self.index.set_ef(100)
        self.index.set_num_threads(1)
        self.backend = "hnsw"

    def search(self, query, limit=30):
        if not self.ids:
            return []
        if len(query) != self.dimension:
            raise ValueError("query dimension differs from index")
        k = min(max(1, limit), len(self.ids))
        if self.index is None:
            scored = [(tid, cosine(query, v)) for tid, v in zip(self.ids, self.vectors)]
            return sorted(scored, key=lambda x: (-x[1], x[0]))[:k]
        import numpy as np

        labels, dist = self.index.knn_query(
            np.asarray([query], dtype=np.float32), k=k, num_threads=1
        )
        return [(self.ids[int(i)], float(1 - d)) for i, d in zip(labels[0], dist[0])]
