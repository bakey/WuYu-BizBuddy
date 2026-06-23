from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import psycopg2
import psycopg2.extras
from sentence_transformers import SentenceTransformer

from .config import RetrieverConfig


@dataclass
class RetrievalResult:
    chunk_id: str
    subdir: str
    source: str
    chunk_idx: int
    n_chunks: int
    cosine_sim: float
    text: str

    def preview(self, n: int = 200) -> str:
        t = self.text[:n]
        return t + ("..." if len(self.text) > n else "")


class GufeiVecRetriever:
    """向量检索器：query -> BGE-M3 embedding -> pgvector ANN -> top-K"""

    def __init__(self, config: RetrieverConfig | None = None, lazy_model: bool = False):
        self.cfg = config or RetrieverConfig()
        self._model: SentenceTransformer | None = None
        self._conn = None
        if not lazy_model:
            self._load_model()

    def _load_model(self) -> None:
        if self._model is not None:
            return
        self._model = SentenceTransformer(self.cfg.model_path, device=self.cfg.device)

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.cfg.pg_dsn)
        return self._conn

    def encode(self, query: str) -> np.ndarray:
        self._load_model()
        emb = self._model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return emb[0]

    def _vec_to_pg(self, vec: np.ndarray) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

    def _resolve_subdirs(self, scope: str | Sequence[str] | None) -> list[str] | None:
        if scope is None:
            return None
        if isinstance(scope, str):
            alias = self.cfg.subdir_aliases.get(scope)
            if alias:
                return list(alias)
            return [scope]
        return list(scope)

    def retrieve(
        self,
        query: str,
        k: int | None = None,
        scope: str | Sequence[str] | None = None,
        probes: int | None = None,
        return_full_text: bool = True,
        return_embeddings: bool = False,
    ) -> list[RetrievalResult]:
        k = k or self.cfg.default_k
        probes = probes or self.cfg.default_probes

        t0 = time.time()
        qvec = self.encode(query)
        t_enc = time.time() - t0

        pg_vec = self._vec_to_pg(qvec)
        subdirs = self._resolve_subdirs(scope)

        cur = self._get_conn().cursor()
        cur.execute(f"SET ivfflat.probes = {int(probes)}")

        txt_col = "txt" if return_full_text else f"substring(txt, 1, {self.cfg.preview_chars})"
        emb_col = ", substring(embedding::text, 2, length(embedding::text)-2)" if return_embeddings else ""

        if subdirs:
            sql = f"""
                SELECT id, subdir, source, chunk_idx, n_chunks,
                       1 - (embedding::halfvec(1024) <=> %s::halfvec(1024)) AS cosine_sim,
                       {txt_col} AS text{emb_col}
                FROM chunks
                WHERE subdir = ANY(%s)
                ORDER BY (embedding::halfvec(1024)) <=> %s::halfvec(1024)
                LIMIT %s
            """
            params = [pg_vec, subdirs, pg_vec, k]
        else:
            sql = f"""
                SELECT id, subdir, source, chunk_idx, n_chunks,
                       1 - (embedding::halfvec(1024) <=> %s::halfvec(1024)) AS cosine_sim,
                       {txt_col} AS text{emb_col}
                FROM chunks
                ORDER BY (embedding::halfvec(1024)) <=> %s::halfvec(1024)
                LIMIT %s
            """
            params = [pg_vec, pg_vec, k]

        t1 = time.time()
        cur.execute(sql, params)
        rows = cur.fetchall()
        t_search = time.time() - t1
        cur.close()

        results = []
        for r in rows:
            res = RetrievalResult(
                chunk_id=r[0],
                subdir=r[1],
                source=r[2],
                chunk_idx=r[3],
                n_chunks=r[4],
                cosine_sim=float(r[5]),
                text=r[6],
            )
            if return_embeddings and len(r) > 7:
                res._embedding = np.fromstring(r[7], sep=",", dtype=np.float32)
            results.append(res)

        self.last_encode_time = t_enc
        self.last_search_time = t_search
        self.last_total_time = t_enc + t_search
        return results

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()
