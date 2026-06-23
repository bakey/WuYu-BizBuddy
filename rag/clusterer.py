from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

import numpy as np

from .config import RetrieverConfig


class SemanticClusterer:
    """语义聚类：对 chunk 向量做 MiniBatchKMeans，产出簇心用于查询路由。

    用途：
      1. 检索加速 —— query 先找最近的 top-N 簇心，再在对应簇内 ANN
      2. 数据治理 —— 簇心标签用于了解数据分布、异常检测、数据分级
    """

    def __init__(self, config: RetrieverConfig | None = None):
        self.cfg = config or RetrieverConfig()
        self.centroids: np.ndarray | None = None
        self.labels: dict[str, int] = {}

    def _fetch_sample(
        self,
        subdir: str | None,
        sample_size: int,
    ) -> tuple[np.ndarray, list[str]]:
        import psycopg2

        conn = psycopg2.connect(self.cfg.pg_dsn)
        cur = conn.cursor()

        if subdir:
            pct = max(0.01, min(100.0, sample_size / 11_000_000 * 100 * 3))
            sql = """
                SELECT id, substring(embedding::text, 2, length(embedding::text)-2)
                FROM chunks TABLESAMPLE SYSTEM(%s)
                WHERE subdir = %s
                LIMIT %s
            """
            cur.execute(sql, [pct, subdir, sample_size])
        else:
            pct = max(0.01, min(100.0, sample_size / 68_000_000 * 100 * 3))
            sql = """
                SELECT id, substring(embedding::text, 2, length(embedding::text)-2)
                FROM chunks TABLESAMPLE SYSTEM(%s)
                LIMIT %s
            """
            cur.execute(sql, [pct, sample_size])

        rows = cur.fetchall()
        cur.close()
        conn.close()

        ids = [r[0] for r in rows]
        embs = np.array(
            [np.fromstring(r[1], sep=",", dtype=np.float32) for r in rows]
        )
        return embs, ids

    def fit(
        self,
        n_clusters: int = 50,
        sample_size: int = 50000,
        subdir: str | None = None,
        save: bool = True,
    ) -> dict:
        from sklearn.cluster import MiniBatchKMeans

        t0 = time.time()
        embs, ids = self._fetch_sample(subdir, sample_size)
        t_fetch = time.time() - t0

        t1 = time.time()
        km = MiniBatchKMeans(
            n_clusters=n_clusters,
            batch_size=min(4096, sample_size),
            random_state=42,
            n_init=3,
        )
        cluster_labels = km.fit_predict(embs)
        t_fit = time.time() - t1

        self.centroids = km.cluster_centers_.astype(np.float32)
        self.labels = {cid: int(lbl) for cid, lbl in zip(ids, cluster_labels)}

        if save:
            self._save(subdir)

        from collections import Counter
        dist = Counter(cluster_labels.tolist())

        return {
            "n_clusters": n_clusters,
            "sample_size": len(ids),
            "subdir": subdir or "all",
            "fetch_time_s": round(t_fetch, 2),
            "fit_time_s": round(t_fit, 2),
            "cluster_distribution": {
                int(k): int(v) for k, v in sorted(dist.items())
            },
        }

    def _save(self, subdir: str | None) -> None:
        tag = subdir or "all"
        out_dir = Path(self.cfg.cluster_centroids_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        cpath = out_dir / f"centroids_{tag}.npy"
        np.save(cpath, self.centroids)
        print(f"[clusterer] centroids saved -> {cpath}  shape={self.centroids.shape}")

    def load(self, subdir: str | None = None) -> bool:
        tag = subdir or "all"
        cpath = Path(self.cfg.cluster_centroids_path).parent / f"centroids_{tag}.npy"
        if not cpath.exists():
            return False
        self.centroids = np.load(cpath)
        return True

    def route(
        self,
        query_embedding: np.ndarray,
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        """给定 query 向量，返回最近的 top_n 个簇 (cluster_id, similarity)。"""
        if self.centroids is None:
            raise RuntimeError("call fit() or load() first")
        top_n = top_n or self.cfg.cluster_route_top_n
        sims = self.centroids @ query_embedding
        idx = np.argsort(sims)[::-1][:top_n]
        return [(int(i), float(sims[i])) for i in idx]
