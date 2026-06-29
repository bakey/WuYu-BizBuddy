#!/usr/bin/env python3
"""离线召回质检脚本（在 Linux 部署机上独立运行，不需要启动后端服务）。

目的：在投入调参/重排之前，先验证 gufei_vec 的某个 subdir 里到底有没有你要答的内容。
对一批问题做 bge-m3 向量检索，打印每题 top-k 的 cosine 相似度和正文预览，
并汇总相似度分布，用来判断：
  - 相似度普遍很低 / 正文明显跑题  -> 语料覆盖问题，调 probes 也没用，要换或补数据；
  - 相似度高且正文相关             -> 语料 OK，可以继续做 over-fetch + rerank 等优化。

用法示例：
  source /root/miniconda3/etc/profile.d/conda.sh && conda activate gufei_vec
  python scripts/retrieval_eval.py --subdir html_md --k 5 --probes 5 \
      --questions questions.txt
  # 不带 --questions 时使用脚本内置的几个示例问题。

依赖：psycopg2、sentence-transformers（与入库一致的 bge-m3 模型）。
连接串和模型路径默认从环境变量读取，也可用命令行覆盖：
  GUFEI_VEC_URL、BGE_M3_MODEL_PATH、BGE_M3_DEVICE
"""

import argparse
import os
import statistics
import sys

# 内置示例问题；建议用 --questions 传入你 V1 用过的真实问题集。
DEFAULT_QUESTIONS = [
    "生活垃圾焚烧设施需要建立哪些台账？",
    "污水处理厂的污泥处置有哪些合规要求？",
    "危险废物的转移联单制度是怎样的？",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="gufei_vec 离线召回质检")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("GUFEI_VEC_URL", ""),
        help="gufei_vec 连接串，默认读环境变量 GUFEI_VEC_URL",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get(
            "BGE_M3_MODEL_PATH", "/data/models/bge-m3_20250912_235519m"
        ),
        help="bge-m3 模型路径，默认读环境变量 BGE_M3_MODEL_PATH",
    )
    parser.add_argument(
        "--device",
        default=os.environ.get("BGE_M3_DEVICE", "cpu"),
        help="运行设备 cpu / cuda",
    )
    parser.add_argument("--subdir", default="html_md", help="限定检索的 subdir")
    parser.add_argument("--k", type=int, default=5, help="每题最终返回条数")
    parser.add_argument("--probes", type=int, default=5, help="IVFFlat probes")
    parser.add_argument(
        "--fetch-k", type=int, default=30, help="去重前向量多召回的候选数量"
    )
    parser.add_argument(
        "--min-chars", type=int, default=50, help="最小正文字符数，过滤标题/碎片；0 不过滤"
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=3,
        help="同一来源最多保留条数；0 不去重",
    )
    parser.add_argument(
        "--dedupe-content-prefix",
        type=int,
        default=80,
        help="内容近重去重的正文前缀长度（消除同文异源重复）；0 不做",
    )
    parser.add_argument(
        "--questions",
        default=None,
        help="问题文件路径，每行一个问题；不传则用内置示例",
    )
    parser.add_argument(
        "--preview-chars", type=int, default=160, help="每条正文预览字符数"
    )
    return parser.parse_args()


def load_questions(path: str | None) -> list[str]:
    if not path:
        return DEFAULT_QUESTIONS
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def to_vector_literal(embedding) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in embedding) + "]"


def dedupe_rows(rows: list, max_per_source: int, content_prefix: int) -> list:
    """去重：① 内容近重(正文索引4前缀相同)；② 同一来源(索引2)最多 max_per_source 条。"""
    if max_per_source <= 0 and content_prefix <= 0:
        return rows
    seen_content: set = set()
    source_count: dict = {}
    result = []
    for row in rows:
        source = row[2]
        content_key = ""
        if content_prefix > 0:
            content_key = "".join((row[4] or "").split())[:content_prefix]
            if content_key and content_key in seen_content:
                continue
        if (
            max_per_source > 0
            and source is not None
            and source_count.get(source, 0) >= max_per_source
        ):
            continue
        if content_key:
            seen_content.add(content_key)
        if source is not None:
            source_count[source] = source_count.get(source, 0) + 1
        result.append(row)
    return result


def main() -> int:
    args = parse_args()
    if not args.dsn:
        print("错误：未提供 gufei_vec 连接串（--dsn 或环境变量 GUFEI_VEC_URL）", file=sys.stderr)
        return 2

    # 延迟导入，避免没装依赖时连帮助信息都看不到。
    import psycopg2
    from sentence_transformers import SentenceTransformer

    print(f"加载模型: {args.model} (device={args.device}) ...", file=sys.stderr)
    model = SentenceTransformer(args.model, device=args.device)
    conn = psycopg2.connect(args.dsn)
    questions = load_questions(args.questions)

    # 多召回 fetch_k 条候选 + 最小长度过滤；之后在 Python 里去重并截断到 k。
    sql = """
      SELECT id, subdir, source, chunk_idx, txt,
             1 - ((embedding::halfvec(1024)) <=> %(qvec)s::halfvec(1024)) AS sim
      FROM chunks
      WHERE subdir = %(subdir)s
        AND char_length(txt) >= %(min_chars)s
      ORDER BY (embedding::halfvec(1024)) <=> %(qvec)s::halfvec(1024)
      LIMIT %(fetch_k)s
    """

    all_top1: list[float] = []
    all_sims: list[float] = []
    fetch_k = max(args.k, args.fetch_k)

    for qi, question in enumerate(questions, start=1):
        emb = model.encode([question], normalize_embeddings=True)[0]
        qvec = to_vector_literal(emb)

        cur = conn.cursor()
        cur.execute(f"SET ivfflat.probes = {int(args.probes)}")
        cur.execute(
            sql,
            {
                "qvec": qvec,
                "subdir": args.subdir,
                "min_chars": args.min_chars,
                "fetch_k": fetch_k,
            },
        )
        candidates = cur.fetchall()
        cur.close()

        # 内容近重 + 来源去重，再截断到 k。
        rows = dedupe_rows(
            candidates, args.max_per_source, args.dedupe_content_prefix
        )[: args.k]

        print(f"\n{'=' * 80}")
        print(f"[Q{qi}] {question}")
        print(f"{'-' * 80}")
        if not rows:
            print("  (无召回)")
            continue
        all_top1.append(float(rows[0][5]))
        for rank, (cid, subdir, source, chunk_idx, txt, sim) in enumerate(rows, 1):
            sim = float(sim)
            all_sims.append(sim)
            preview = (txt or "").replace("\n", " ")[: args.preview_chars]
            print(f"  #{rank} sim={sim:.4f} [{subdir}] {source} (chunk {chunk_idx})")
            print(f"      {preview}")

    print(f"\n{'=' * 80}")
    print("汇总")
    print(f"{'-' * 80}")
    if all_sims:
        print(f"  问题数: {len(questions)}  命中片段数: {len(all_sims)}")
        print(
            "  全部命中 cosine: "
            f"min={min(all_sims):.4f} "
            f"median={statistics.median(all_sims):.4f} "
            f"max={max(all_sims):.4f}"
        )
        if all_top1:
            print(
                "  各题 top1 cosine: "
                f"min={min(all_top1):.4f} "
                f"median={statistics.median(all_top1):.4f} "
                f"max={max(all_top1):.4f}"
            )
        print(
            "  判读参考：top1 普遍 < 0.5 或正文跑题 -> 语料覆盖问题；"
            "top1 普遍 > 0.6 且相关 -> 语料 OK，可继续优化检索。"
        )
    else:
        print("  所有问题均无召回，请检查 subdir 是否正确、库是否有数据。")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
