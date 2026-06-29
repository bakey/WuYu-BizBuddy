"""
模块作用：封装行业知识库问答相关的数据库读写操作。

    industry_knowledge_skills
    -> 查 skill 配置

    datasets_segments
    -> 查知识 chunks

    industry_knowledge_query_logs
    -> 写一次问答发生了什么
    写入的表是：INSERT INTO wuyu_industry.industry_knowledge_query_logs

    industry_knowledge_query_references
    -> 写这次问答引用了哪些 chunks
    写入的表是：INSERT INTO wuyu_industry.industry_knowledge_query_references

    industry_knowledge_feedback
    -> 写用户对这次问答的反馈
    写入的表是：INSERT INTO wuyu_industry.industry_knowledge_feedback
"""


"""Database access for industry knowledge skill query."""

# 导入 json，用来把 Python 字典转换成数据库 jsonb 字符串。
import json
# 导入 dataclass，用来定义轻量的数据结构。
from dataclasses import dataclass
# 导入 Any，用来标注 metadata、debug、tags 这类灵活字典。
from typing import Any
# 导入 UUID 类型，用来标注数据库中的 UUID 主键。
from uuid import UUID

# 导入 text，用来执行原生 SQL。
from sqlalchemy import text
# 导入 SQLAlchemy Session，用来执行数据库查询和提交事务。
from sqlalchemy.orm import Session

# 导入项目配置，例如 PostgreSQL 全文检索配置。
from bizbuddy_rag.config import settings


# 数据结构作用：表示一条已启用的行业知识技能配置，来源于 industry_knowledge_skills 表。
@dataclass(frozen=True)
class IndustryKnowledgeSkill:
    """Skill configuration loaded from industry_knowledge_skills."""

    # 技能 ID。
    id: UUID
    # 检索模式，例如 fulltext、vector。
    retrieval_mode: str
    # 默认返回的知识片段数量。
    top_k: int
    # 拼接给大模型的最大上下文字符数。
    max_context_chars: int
    # 该技能使用的大模型系统提示词。
    system_prompt: str | None
    # 全文检索绑定的数据集 ID；向量检索模式下可为空。
    dataset_id: UUID | None = None
    # 向量检索绑定的 gufei_vec subdir，例如 html_md；用于限定范围并大幅加速。
    vector_subdir: str | None = None
    # 召回分数阈值；向量模式下为 cosine 相似度阈值。
    score_threshold: float | None = None
    # 向量检索的 IVFFlat probes；为空时使用系统默认值。
    ivfflat_probes: int | None = None
    # 是否启用重排；为空时使用系统默认值。
    rerank_enabled: bool | None = None
    # 重排前向量多召回的候选数量；为空时使用系统默认值。
    rerank_over_fetch_k: int | None = None


# 数据结构作用：表示一条检索出来的知识片段。
# 全文模式来源于 public.datasets_segments；向量模式来源于 gufei_vec.chunks。
@dataclass(frozen=True)
class IndustryKnowledgeSegment:
    """Retrieved chunk from datasets_segments (fulltext) or gufei_vec (vector)."""

    # 片段 ID；全文模式是 uuid 字符串，向量模式是 gufei_vec 的 md5 text id。
    segment_id: str
    # 片段正文内容。
    content: str
    # 相关性分数；全文模式是 ts_rank，向量模式是 cosine 相似度（0~1）。
    score: float
    # 片段在文档中的分块序号。
    chunk_index: int
    # 片段所属文档 ID；向量库无此概念，可为空。
    document_id: UUID | None = None
    # 片段所属数据集 ID；向量库无此概念，可为空。
    dataset_id: UUID | None = None
    # 片段来源（向量库的原始文件路径 source）；全文模式可为空。
    source: str | None = None
    # 片段所属 subdir（向量库分区）；全文模式可为空。
    subdir: str | None = None
    # 片段元数据。
    metadata: dict[str, Any] | None = None


class IndustryKnowledgeRepository:
    # 类作用：集中处理行业知识技能配置、知识检索、问答日志、引用记录和用户反馈的数据库访问。
    """Repository for skill query configuration, retrieval, logs, and feedback."""

    # 函数作用：初始化 repository，保存业务库 Session，并可选保存向量库 Session。
    def __init__(self, db: Session, vector_db: Session | None = None) -> None:
        # 业务库会话：skill 配置、日志、引用、反馈都通过它读写。
        self.db = db
        # 向量库（gufei_vec）会话：仅向量检索使用；未配置时为 None。
        self.vector_db = vector_db

    # 函数作用：根据 skill_id 查询已启用的行业知识技能配置；如果不存在或未启用，返回 None。
    def get_enabled_skill(self, skill_id: UUID) -> IndustryKnowledgeSkill | None:
        """Return enabled skill config by ID."""
        # 执行 SQL 查询，读取指定 ID 且 enabled=true 的技能配置。
        row = self.db.execute(
            # 使用 text 编写原生 SQL，方便指定 schema 和字段。
            text(
                """
                SELECT
                  id,
                  dataset_id,
                  retrieval_mode,
                  top_k,
                  max_context_chars,
                  system_prompt,
                  score_threshold,
                  vector_subdir,
                  ivfflat_probes,
                  rerank_enabled,
                  rerank_over_fetch_k
                FROM wuyu_industry.industry_knowledge_skills
                WHERE id = :skill_id
                  AND enabled = true
                """
            ),
            # 绑定 SQL 参数，避免把 skill_id 直接拼进 SQL 字符串。
            {"skill_id": skill_id},
        # mappings() 让结果可以用字段名访问；first() 只取第一行。
        ).mappings().first()
        # 如果没有查到启用的技能，返回 None，由 service 层决定是否抛异常。
        if row is None:
            return None
        # 把数据库行转换成 service 层更好使用的 IndustryKnowledgeSkill 对象。
        return IndustryKnowledgeSkill(
            # 技能 ID。
            id=row["id"],
            # 技能关联的数据集 ID（向量模式可能为空）。
            dataset_id=row["dataset_id"],
            # 技能配置的检索模式。
            retrieval_mode=row["retrieval_mode"],
            # 技能配置的默认 top_k。
            top_k=row["top_k"],
            # 技能配置的最大上下文长度。
            max_context_chars=row["max_context_chars"],
            # 技能配置的系统提示词。
            system_prompt=row["system_prompt"],
            # 向量检索绑定的 subdir。
            vector_subdir=row["vector_subdir"],
            # 召回分数阈值。
            score_threshold=row["score_threshold"],
            # 向量检索 probes。
            ivfflat_probes=row["ivfflat_probes"],
            # 是否启用重排。
            rerank_enabled=row["rerank_enabled"],
            # 重排前多召回数量。
            rerank_over_fetch_k=row["rerank_over_fetch_k"],
        )

    # 函数作用：在指定数据集中用 PostgreSQL 全文检索查找相关 chunks，并按相关性返回前 top_k 条。
    def retrieve_fulltext(
        self,
        # 要检索的数据集 ID。
        dataset_id: UUID,
        # 用户查询文本。
        query: str,
        # 最多返回的片段数量。
        top_k: int,
    ) -> list[IndustryKnowledgeSegment]:
        """Retrieve chunks with PostgreSQL full-text search."""
        # 执行全文检索 SQL，从 public.datasets_segments 表中查匹配的知识片段。
        rows = self.db.execute(
            # SQL 中使用 to_tsvector + plainto_tsquery 做 PostgreSQL 全文检索。
            text(
                """
                SELECT
                  id AS segment_id,
                  document_id,
                  dataset_id,
                  chunk_index,
                  content,
                  metadata,
                  ts_rank(
                    to_tsvector(CAST(:fulltext_config AS regconfig), content),
                    plainto_tsquery(CAST(:fulltext_config AS regconfig), :query)
                  ) AS score
                FROM public.datasets_segments
                WHERE dataset_id = :dataset_id
                  AND enabled = 1
                  AND status = 'completed'
                  AND to_tsvector(CAST(:fulltext_config AS regconfig), content)
                    @@ plainto_tsquery(CAST(:fulltext_config AS regconfig), :query)
                ORDER BY score DESC, chunk_index ASC
                LIMIT :top_k
                """
            ),
            # 绑定检索参数，包括数据集、查询词、返回数量和全文检索语言配置。
            {
                "dataset_id": dataset_id,
                "query": query,
                "top_k": top_k,
                "fulltext_config": settings.industry_fulltext_config,
            },
        # mappings().all() 返回可按字段名访问的所有结果行。
        ).mappings().all()
        # 把数据库查询结果转换成 IndustryKnowledgeSegment 列表。
        return [
            IndustryKnowledgeSegment(
                # 片段 ID，统一转成字符串。
                segment_id=str(row["segment_id"]),
                # 片段正文。
                content=row["content"],
                # 相关性分数转成 float，方便后续响应序列化。
                score=float(row["score"]),
                # 分块序号。
                chunk_index=row["chunk_index"],
                # 文档 ID。
                document_id=row["document_id"],
                # 数据集 ID。
                dataset_id=row["dataset_id"],
                # metadata 如果已经是 dict 就保留，否则置为空。
                metadata=row["metadata"] if isinstance(row["metadata"], dict) else None,
            )
            # 遍历每一行全文检索结果。
            for row in rows
        ]

    # 函数作用：在 gufei_vec.chunks 上用 bge-m3 query 向量做 IVFFlat 余弦相似度检索。
    def retrieve_vector(
        self,
        *,
        # 已编码并格式化好的 query 向量字面量，例如 "[0.1,0.2,...]"。
        query_vector_literal: str,
        # 最多返回的片段数量。
        top_k: int,
        # 限定检索的 subdir（如 html_md）；为 None 时全表扫描（很慢，不推荐）。
        subdir: str | None,
        # IVFFlat probes，越大召回越高但越慢。
        probes: int,
        # cosine 相似度阈值，低于该值的片段会被过滤；0 表示不过滤。
        score_threshold: float,
        # 最小正文字符数，过滤标题/极短碎片；0 表示不过滤。
        min_chars: int = 0,
    ) -> list[IndustryKnowledgeSegment]:
        """Retrieve chunks from gufei_vec via bge-m3 vector similarity."""
        # 向量库未配置时直接报错，避免静默走空结果。
        if self.vector_db is None:
            raise RuntimeError("向量库 gufei_vec 未配置，无法执行向量检索")
        # probes 不能用绑定参数（SET 不支持占位符），强制转 int 后内联，杜绝注入。
        self.vector_db.execute(text(f"SET ivfflat.probes = {int(probes)}"))
        # 执行向量检索 SQL。
        # 关键：embedding 和 query 向量左右都 cast 成 halfvec(1024) 才能命中 IVFFlat 索引。
        rows = self.vector_db.execute(
            text(
                """
                SELECT
                  id,
                  subdir,
                  source,
                  chunk_idx,
                  n_chunks,
                  txt,
                  1 - ((embedding::halfvec(1024)) <=> CAST(:qvec AS halfvec(1024)))
                    AS score
                FROM chunks
                WHERE (:subdir IS NULL OR subdir = :subdir)
                  AND char_length(txt) >= :min_chars
                ORDER BY (embedding::halfvec(1024)) <=> CAST(:qvec AS halfvec(1024))
                LIMIT :top_k
                """
            ),
            # 绑定向量、subdir 过滤、最小长度和返回数量。
            {
                "qvec": query_vector_literal,
                "subdir": subdir,
                "top_k": top_k,
                "min_chars": min_chars,
            },
        ).mappings().all()
        # 把检索结果转换成 IndustryKnowledgeSegment，并按阈值过滤。
        segments: list[IndustryKnowledgeSegment] = []
        for row in rows:
            # cosine 相似度。
            score = float(row["score"])
            # 低于阈值的片段直接跳过。
            if score_threshold and score < score_threshold:
                continue
            segments.append(
                IndustryKnowledgeSegment(
                    # gufei_vec 的 md5 文本主键。
                    segment_id=str(row["id"]),
                    # chunk 正文。
                    content=row["txt"],
                    # cosine 相似度分数。
                    score=score,
                    # 文件内 chunk 序号。
                    chunk_index=row["chunk_idx"],
                    # 原始文件路径。
                    source=row["source"],
                    # 所属分区。
                    subdir=row["subdir"],
                    # 把向量库特有信息放进 metadata，便于前端展示和复盘。
                    metadata={
                        "source": row["source"],
                        "subdir": row["subdir"],
                        "chunk_idx": row["chunk_idx"],
                        "n_chunks": row["n_chunks"],
                    },
                )
            )
        return segments

    # 函数作用：写入一次问答执行日志，并返回新创建的 query_log_id。
    def create_query_log(
        self,
        *,
        # 本次问答使用的技能 ID。
        skill_id: UUID,
        # 本次问答使用的数据集 ID；向量模式可能为空。
        dataset_id: UUID | None,
        # 用户原始问题。
        query_text: str,
        # 最终回答文本。
        answer_text: str,
        # 本次使用的检索模式。
        retrieval_mode: str,
        # 本次实际使用的 top_k。
        top_k: int,
        # 实际检索到的片段数量。
        retrieved_count: int,
        # 本次问答耗时，单位毫秒。
        latency_ms: int | None,
        # 使用的大模型 ID。
        model_id: str | None,
        # 执行状态，例如 success 或 no_context。
        status: str,
        # 错误信息；正常流程通常为 None。
        error: str | None,
        # 调试信息字典。
        debug: dict[str, Any],
    ) -> UUID:
        """Persist one query execution log and return its ID."""
        # 执行 INSERT SQL 写入问答日志，并通过 RETURNING id 拿到新日志 ID。
        row = self.db.execute(
            # 插入行业知识问答日志表。
            text(
                """
                INSERT INTO wuyu_industry.industry_knowledge_query_logs (
                  skill_id,
                  dataset_id,
                  query_text,
                  answer_text,
                  retrieval_mode,
                  top_k,
                  retrieved_count,
                  latency_ms,
                  model_id,
                  status,
                  error,
                  debug
                )
                VALUES (
                  :skill_id,
                  :dataset_id,
                  :query_text,
                  :answer_text,
                  :retrieval_mode,
                  :top_k,
                  :retrieved_count,
                  :latency_ms,
                  :model_id,
                  :status,
                  :error,
                  CAST(:debug AS jsonb)
                )
                RETURNING id
                """
            ),
            # 绑定日志字段；debug 需要序列化成 JSON 字符串后写入 jsonb。
            {
                "skill_id": skill_id,
                "dataset_id": dataset_id,
                "query_text": query_text,
                "answer_text": answer_text,
                "retrieval_mode": retrieval_mode,
                "top_k": top_k,
                "retrieved_count": retrieved_count,
                "latency_ms": latency_ms,
                "model_id": model_id,
                "status": status,
                "error": error,
                "debug": json.dumps(debug, ensure_ascii=False),
            },
        # first() 读取 RETURNING id 返回的第一行。
        ).first()
        # 提交事务，让日志真正写入数据库。
        self.db.commit()
        # 返回新创建的日志 ID。
        return row[0]

    # 函数作用：把一次问答引用到的知识片段批量写入引用表，用于后续追踪回答依据。
    def create_query_references(
        self,
        # 问答日志 ID，用来关联本次引用属于哪次问答。
        query_log_id: UUID,
        # 本次回答引用的知识片段列表。
        references: list[IndustryKnowledgeSegment],
    ) -> None:
        """Persist retrieved evidence chunks for one query log."""
        # 没有引用片段时直接返回，不写数据库。
        if not references:
            return
        # 执行批量 INSERT，把每个引用片段写入 query_references 表。
        self.db.execute(
            # 插入引用表，保存片段 ID、排序、分数和内容快照。
            text(
                """
                INSERT INTO wuyu_industry.industry_knowledge_query_references (
                  query_log_id,
                  segment_id,
                  document_id,
                  dataset_id,
                  reference_rank,
                  score,
                  content_snapshot,
                  metadata_snapshot
                )
                VALUES (
                  :query_log_id,
                  :segment_id,
                  :document_id,
                  :dataset_id,
                  :reference_rank,
                  :score,
                  :content_snapshot,
                  CAST(:metadata_snapshot AS jsonb)
                )
                """
            ),
            # 构造批量参数列表；SQLAlchemy 会按列表批量执行。
            [
                {
                    # 关联的问答日志 ID。
                    "query_log_id": query_log_id,
                    # 引用片段 ID；向量模式是 gufei_vec 的 text md5。
                    "segment_id": segment.segment_id,
                    # 引用片段所属文档 ID；向量模式为空。
                    "document_id": segment.document_id,
                    # 引用片段所属数据集 ID；向量模式为空。
                    "dataset_id": segment.dataset_id,
                    # 引用排序，从 1 开始。
                    "reference_rank": rank,
                    # 检索相关性分数。
                    "score": segment.score,
                    # 内容快照，避免原始片段后续变更导致历史回答依据不可追溯。
                    "content_snapshot": segment.content,
                    # 元数据快照，写入 jsonb；合并 source/subdir/chunk 信息便于复盘。
                    "metadata_snapshot": json.dumps(
                        {
                            **(segment.metadata or {}),
                            "source": segment.source,
                            "subdir": segment.subdir,
                            "chunk_index": segment.chunk_index,
                        },
                        ensure_ascii=False,
                    ),
                }
                # 给每个引用片段生成 rank，并逐条转换成插入参数。
                for rank, segment in enumerate(references, start=1)
            ],
        )
        # 提交事务，让引用记录真正写入数据库。
        self.db.commit()

    # 函数作用：写入用户对某次问答的反馈，并返回新创建的 feedback_id。
    def create_feedback(
        self,
        *,
        # 被反馈的问答日志 ID。
        query_log_id: UUID,
        # 用户评分，可为空。
        rating: int | None,
        # 用户是否认为回答有帮助，可为空。
        is_helpful: bool | None,
        # 用户文字评论，可为空。
        comment: str | None,
        # 用户反馈标签，可为空。
        tags: dict[str, Any] | None,
    ) -> UUID:
        """Persist user feedback for one query log."""
        # 执行 INSERT SQL 写入用户反馈，并通过 RETURNING id 拿到反馈 ID。
        row = self.db.execute(
            # 插入行业知识反馈表。
            text(
                """
                INSERT INTO wuyu_industry.industry_knowledge_feedback (
                  query_log_id,
                  rating,
                  is_helpful,
                  comment,
                  tags
                )
                VALUES (
                  :query_log_id,
                  :rating,
                  :is_helpful,
                  :comment,
                  CAST(:tags AS jsonb)
                )
                RETURNING id
                """
            ),
            # 绑定反馈字段；tags 需要序列化成 JSON 字符串后写入 jsonb。
            {
                "query_log_id": query_log_id,
                "rating": rating,
                "is_helpful": is_helpful,
                "comment": comment,
                "tags": json.dumps(tags or {}, ensure_ascii=False),
            },
        # first() 读取 RETURNING id 返回的第一行。
        ).first()
        # 提交事务，让反馈记录真正写入数据库。
        self.db.commit()
        # 返回新创建的反馈 ID。
        return row[0]
