"""
skill_id 如何加载 skill:
    skill = self._get_skill(skill_id)

如何确定 top_k:
    优先级是：
        接口请求传入的 top_k
        -> skill 自己配置的 top_k
        -> 系统默认 settings.industry_default_top_k

如何检索 chunks：
    目前只支持 fulltext 模式，直接调用 repository.retrieve_fulltext(skill.dataset_id, query, top_k)

如何拼 context：
    把每个 chunk 内容拼成：
        [1] 第一段内容

        [2] 第二段内容

        [3] 第三段内容
        同时用 skill.max_context_chars 控制总长度，超出就停止追加

何时兜底，何时调用 LLM，如何写日志和引用:
    只要没有检索到任何 chunk，就不会调用 LLM，而是直接返回 NO_CONTEXT_ANSWER 这个固定文本，并在日志里标记 status 为 no_context。
    只有检索到至少一个 chunk 时才调用 LLM，生成回答后在日志里标记 status 为 success。


answer()整体链路是：
    skill_id
    -> _get_skill()
    -> _resolve_top_k()
    -> _retrieve_segments()
    -> _format_context()
    -> 判断是否有 chunks
    -> 没有 chunks：兜底回答
    -> 有 chunks：调用 LLM
    -> create_query_log()
    -> create_query_references()
    -> 返回 answer + references + debug
"""


# 模块说明：这里封装行业知识库的检索、问答和反馈业务逻辑。
"""Industry knowledge skill query service."""

# 导入 dataclasses.replace，用于在重排后生成更新了分数的不可变片段对象。
from dataclasses import replace
# 导入高精度计时器，用来统计问答耗时。
from time import perf_counter
# 导入 Any，用于标注 debug、tags 等灵活结构的数据。
from typing import Any
# 导入 UUID 类型，用于标注数据库主键 ID。
from uuid import UUID

# 导入项目配置，例如默认 top_k 和最大 top_k。
from bizbuddy_rag.config import settings
from bizbuddy_rag.db.industry_knowledge_repository import (
    # 数据访问层，负责读写行业知识相关数据库表。
    IndustryKnowledgeRepository,
    # 检索命中的知识片段数据结构。
    IndustryKnowledgeSegment,
    # 行业知识技能配置数据结构。
    IndustryKnowledgeSkill,
)
from bizbuddy_rag.industry_models import (
    # 返回给前端的引用片段模型。
    IndustryKnowledgeReference,
    # 检索接口响应模型。
    IndustryKnowledgeRetrieveResponse,
    # 问答接口响应模型。
    IndustryKnowledgeQueryResponse,
)
# 本地 bge-m3 向量服务，用于向量检索时生成 query 向量。
from bizbuddy_rag.services.bge_embedding import BgeM3EmbeddingService
# 本地 bge-reranker 重排服务，用于向量多召回后的精排。
from bizbuddy_rag.services.reranker import BgeRerankerService
# 大模型服务，用于生成最终回答。
from bizbuddy_rag.services.llm import LLMService
# 项目自定义异常，用于抛出业务错误。
from bizbuddy_rag.utils.exceptions import RAGException


# 没有检索到可用上下文时返回给用户的兜底回答。
NO_CONTEXT_ANSWER = "当前知识库中没有检索到足够相关的资料，无法基于已有资料回答。"


class IndustryKnowledgeQueryService:
    # 服务类说明：组织行业知识技能的在线检索和问答流程。
    """Online retrieval and QA flow for industry knowledge skills."""

    # 函数作用：初始化行业知识查询服务，保存数据库仓库对象，并按需保存大模型服务对象。
    def __init__(
        self,
        # 注入数据仓库，负责数据库查询和写入。
        repository: IndustryKnowledgeRepository,
        # 可选注入大模型服务；只检索时可以不传。
        llm_service: LLMService | None = None,
        # 可选注入 bge-m3 向量服务；向量检索模式必须提供。
        embedding_service: BgeM3EmbeddingService | None = None,
        # 可选注入 bge-reranker 重排服务；启用重排时必须提供。
        reranker_service: BgeRerankerService | None = None,
    ) -> None:
        # 保存仓库实例，后续方法通过它访问数据库。
        self.repository = repository
        # 保存 LLM 服务实例，answer 方法会用它生成回答。
        self.llm_service = llm_service
        # 保存向量服务实例，向量检索时用它把 query 编码成向量。
        self.embedding_service = embedding_service
        # 保存重排服务实例，启用重排时用它对候选片段精排。
        self.reranker_service = reranker_service

    """
    负责只检索知识片段:
        拿到 skill 配置
        -> 确定 top_k
        -> 检索知识片段
        -> 转成 references
        -> 返回 IndustryKnowledgeRetrieveResponse
    """
    def retrieve(
        self,
        *,
        # 要使用的行业知识技能 ID。
        skill_id: UUID,
        # 用户输入的检索问题或关键词。
        query: str,
        # 可选的返回片段数量；为空则使用技能或系统默认值。
        top_k: int | None = None,
    ) -> IndustryKnowledgeRetrieveResponse:
        # 方法说明：只检索证据片段，不调用大模型。
        """Retrieve evidence chunks for one enabled skill."""
        # 根据技能 ID 获取已启用的技能配置。
        skill = self._get_skill(skill_id)
        # 计算最终使用的 top_k，并限制在系统允许范围内。
        resolved_top_k = self._resolve_top_k(top_k, skill)
        # 从知识库中检索匹配片段。
        segments = self._retrieve_segments(skill, query, resolved_top_k)
        # 把内部片段结构转换成接口返回的引用模型。
        references = [self._to_reference(segment) for segment in segments]
        return IndustryKnowledgeRetrieveResponse(
            # 返回检索到的引用片段列表。
            items=references,
            debug=self._build_debug(
                # 当前使用的技能配置。
                skill=skill,
                # 本次检索的问题。
                query=query,
                # 本次实际使用的 top_k。
                top_k=resolved_top_k,
                # 实际返回的片段数量。
                retrieved_count=len(references),
                # 所有返回片段正文长度之和。
                context_length=sum(len(item.content) for item in references),
            # 构造调试信息，方便排查检索效果。
            ),
        # 返回检索响应对象。
        )

    """
    负责完整行业知识问答流程，是这个 service 里最重要的方法:
        检查 llm_service 是否存在
        -> 记录开始时间
        -> 获取 skill 配置
        -> 确定 top_k
        -> 检索知识片段
        -> 拼接上下文 context
        -> 构造 debug 信息
        -> 如果没检索到片段，返回兜底回答
        -> 如果检索到片段，调用 LLM 生成回答
        -> 计算耗时
        -> 保存 query_log
        -> 保存 query_references
        -> 返回 IndustryKnowledgeQueryResponse
    """
    async def answer(
        self,
        *,
        # 要使用的行业知识技能 ID。
        skill_id: UUID,
        # 用户输入的问题。
        query: str,
        # 可选的检索片段数量；为空则使用默认配置。
        top_k: int | None = None,
    ) -> IndustryKnowledgeQueryResponse:
        # 方法说明：检索证据、生成答案，并保存查询日志。
        """Retrieve evidence, generate an answer, and persist query logs."""
        if self.llm_service is None:
            # 没有 LLM 服务时无法执行问答流程。
            raise RAGException("LLM service is required for query answering")

        # 记录开始时间，用于计算本次问答耗时。
        started_at = perf_counter()
        # 获取已启用的技能配置。
        skill = self._get_skill(skill_id)
        # 计算最终使用的 top_k。
        resolved_top_k = self._resolve_top_k(top_k, skill)
        # 检索与问题相关的知识片段。
        segments = self._retrieve_segments(skill, query, resolved_top_k)
        # 把检索片段拼成给大模型使用的上下文。
        context = self._format_context(segments, skill.max_context_chars)
        debug = self._build_debug(
            # 当前使用的技能配置。
            skill=skill,
            # 用户问题。
            query=query,
            # 实际检索数量。
            top_k=resolved_top_k,
            # 实际检索命中的片段数。
            retrieved_count=len(segments),
            # 最终传给大模型的上下文长度。
            context_length=len(context),
        # 构造基础调试信息。
        )

        if not segments:
            # 没有检索结果时返回兜底回答。
            answer_text = NO_CONTEXT_ANSWER
            # 标记本次查询状态为无上下文。
            status = "no_context"
        else:
            answer_text = await self.llm_service.chat(
                # 用户问题。
                query,
                # 检索出来并拼接后的知识上下文。
                context,
                # 技能配置中的系统提示词。
                system_prompt=skill.system_prompt,
            # 调用大模型生成基于上下文的回答。
            )
            # 标记本次查询状态为成功。
            status = "success"

        # 计算从开始到生成回答完成的耗时，单位毫秒。
        latency_ms = int((perf_counter() - started_at) * 1000)
        query_log_id = self.repository.create_query_log(
            # 记录本次查询使用的技能 ID。
            skill_id=skill.id,
            # 记录本次查询关联的数据集 ID。
            dataset_id=skill.dataset_id,
            # 记录用户原始问题。
            query_text=query,
            # 记录最终返回的回答。
            answer_text=answer_text,
            # 记录使用的检索模式。
            retrieval_mode=skill.retrieval_mode,
            # 记录实际使用的 top_k。
            top_k=resolved_top_k,
            # 记录命中的片段数量。
            retrieved_count=len(segments),
            # 记录本次查询耗时。
            latency_ms=latency_ms,
            # 记录使用的大模型标识。
            model_id=self.llm_service.model,
            # 记录查询状态，例如 success 或 no_context。
            status=status,
            # 当前流程没有捕获错误，所以错误字段为空。
            error=None,
            # 把调试信息和耗时一起写入日志。
            debug={**debug, "latency_ms": latency_ms},
        # 创建查询日志，并返回日志 ID。
        )
        # 保存本次回答引用了哪些知识片段。
        self.repository.create_query_references(query_log_id, segments)

        return IndustryKnowledgeQueryResponse(
            # 返回查询日志 ID，供后续反馈接口关联。
            query_log_id=query_log_id,
            # 返回生成的回答文本。
            answer=answer_text,
            # 返回本次回答引用的知识片段。
            references=[self._to_reference(segment) for segment in segments],
            # 返回调试信息，便于前端或开发者排查。
            debug={**debug, "latency_ms": latency_ms},
        # 返回问答响应对象。
        )

    # 函数作用：保存用户对某次问答结果的反馈，并返回新创建的反馈记录 ID。
    def create_feedback(
        self,
        *,
        # 用户反馈关联的查询日志 ID。
        query_log_id: UUID,
        # 用户评分，可为空。
        rating: int | None,
        # 用户是否认为回答有帮助，可为空。
        is_helpful: bool | None,
        # 用户文字评论，可为空。
        comment: str | None,
        # 结构化反馈标签，可为空。
        tags: dict[str, Any] | None,
    ) -> UUID:
        # 方法说明：保存某次问答的用户反馈。
        """Persist feedback for one query answer."""
        return self.repository.create_feedback(
            # 写入反馈关联的查询日志 ID。
            query_log_id=query_log_id,
            # 写入评分。
            rating=rating,
            # 写入是否有帮助。
            is_helpful=is_helpful,
            # 写入文字评论。
            comment=comment,
            # 写入反馈标签。
            tags=tags,
        # 返回新创建的反馈记录 ID。
        )

    # 函数作用：根据 skill_id 查询已启用的行业知识技能；如果不存在或未启用，就抛出业务异常。
    def _get_skill(self, skill_id: UUID) -> IndustryKnowledgeSkill:
        # 查询指定 ID 且已启用的行业知识技能。
        skill = self.repository.get_enabled_skill(skill_id)
        if skill is None:
            # 技能不存在或未启用时抛出业务异常。
            raise RAGException("Industry knowledge skill does not exist or is disabled")
        # 返回可用的技能配置。
        return skill

    # 函数作用：确定本次检索实际使用的 top_k，优先使用请求值，其次技能配置，最后系统默认值，并限制最大值。
    def _resolve_top_k(
        self,
        # 请求中传入的 top_k。
        requested_top_k: int | None,
        # 当前技能配置，里面可能有默认 top_k。
        skill: IndustryKnowledgeSkill,
    ) -> int:
        # 按“请求值 > 技能配置 > 系统默认值”的优先级确定 top_k。
        top_k = requested_top_k or skill.top_k or settings.industry_default_top_k
        # 限制 top_k 不超过系统配置的最大值。
        return min(top_k, settings.industry_max_top_k)

    # 函数作用：根据技能配置执行知识片段检索；支持 fulltext 和 vector 两种模式。
    def _retrieve_segments(
        self,
        # 当前技能配置。
        skill: IndustryKnowledgeSkill,
        # 用户查询文本。
        query: str,
        # 要检索的片段数量。
        top_k: int,
    ) -> list[IndustryKnowledgeSegment]:
        # 全文检索：在业务库 public.datasets_segments 上做中文全文检索。
        if skill.retrieval_mode == "fulltext":
            if skill.dataset_id is None:
                # 全文模式必须绑定 dataset_id。
                raise RAGException("Fulltext skill must be bound to a dataset_id")
            return self.repository.retrieve_fulltext(skill.dataset_id, query, top_k)
        # 向量检索：在 gufei_vec.chunks 上做 bge-m3 + IVFFlat 相似度检索。
        if skill.retrieval_mode == "vector":
            if self.embedding_service is None:
                # 向量模式必须注入 embedding 服务。
                raise RAGException("Vector retrieval requires an embedding service")
            # 把用户问题编码成 query 向量，并格式化成 pgvector 字面量。
            vector = self.embedding_service.embed_query(query)
            query_vector_literal = self.embedding_service.to_pgvector_literal(vector)
            # probes 优先用 skill 配置，其次系统默认。
            probes = skill.ivfflat_probes or settings.industry_vector_probes
            # 阈值优先用 skill 配置，其次系统默认。
            score_threshold = (
                skill.score_threshold
                if skill.score_threshold is not None
                else settings.industry_vector_score_threshold
            )
            # 是否启用重排：优先 skill 配置，其次系统默认。
            rerank_enabled = self._resolve_rerank_enabled(skill)
            # 重排或去重都需要先多召回候选，再精排/去重后截断到 top_k。
            needs_over_fetch = (
                rerank_enabled or settings.industry_vector_max_per_source > 0
            )
            fetch_k = (
                max(top_k, self._resolve_over_fetch_k(skill))
                if needs_over_fetch
                else top_k
            )
            segments = self.repository.retrieve_vector(
                query_vector_literal=query_vector_literal,
                top_k=fetch_k,
                subdir=skill.vector_subdir,
                probes=probes,
                score_threshold=score_threshold,
                # 过滤标题/极短碎片，避免无实质内容的 chunk 污染上下文。
                min_chars=settings.industry_vector_min_chunk_chars,
            )
            # 去重：来源去重 + 内容近重去重，避免碎片/同文异源占满 top_k。
            segments = self._dedupe(
                segments,
                max_per_source=settings.industry_vector_max_per_source,
                content_prefix=settings.industry_vector_dedupe_content_prefix,
            )
            # 启用重排且有候选时，用 cross-encoder 精排并截断到 top_k。
            if rerank_enabled and segments and self.reranker_service is not None:
                return self._rerank(query, segments, top_k)
            # 未重排时直接截断到 top_k（向量召回已按 cosine 排序）。
            return segments[:top_k]
        # 其它模式（如 hybrid）暂未实现。
        raise RAGException(f"Unsupported industry retrieval mode: {skill.retrieval_mode}")

    # 函数作用：解析当前 skill 是否启用重排（skill 配置优先，回退系统默认）。
    def _resolve_rerank_enabled(self, skill: IndustryKnowledgeSkill) -> bool:
        if skill.rerank_enabled is not None:
            return skill.rerank_enabled
        return settings.industry_rerank_enabled

    # 函数作用：解析重排前的 over-fetch 候选数量（skill 配置优先，回退系统默认）。
    def _resolve_over_fetch_k(self, skill: IndustryKnowledgeSkill) -> int:
        return skill.rerank_over_fetch_k or settings.industry_rerank_over_fetch_k

    # 函数作用：对候选片段去重，保持原有相关性顺序。
    # 两层：① 内容近重（正文规范化前缀相同视为同一篇）；② 同一来源最多 max_per_source 条。
    def _dedupe(
        self,
        # 候选片段列表（已按相关性排序）。
        segments: list[IndustryKnowledgeSegment],
        # 同一来源最多保留的片段数；<=0 表示不做来源去重。
        max_per_source: int,
        # 内容近重去重的正文前缀长度；<=0 表示不做内容去重。
        content_prefix: int,
    ) -> list[IndustryKnowledgeSegment]:
        if max_per_source <= 0 and content_prefix <= 0:
            return segments
        # 已出现的内容前缀（用于跨来源近重去重）。
        seen_content: set[str] = set()
        # 每个 source 已保留的数量。
        source_count: dict[str, int] = {}
        result: list[IndustryKnowledgeSegment] = []
        for segment in segments:
            # ① 内容近重：规范化（去空白）后取前缀作为指纹。
            content_key = ""
            if content_prefix > 0:
                content_key = "".join((segment.content or "").split())[:content_prefix]
                if content_key and content_key in seen_content:
                    continue
            # ② 来源去重：同一 source 超过上限则跳过；source 为空不参与。
            if (
                max_per_source > 0
                and segment.source is not None
                and source_count.get(segment.source, 0) >= max_per_source
            ):
                continue
            # 通过两层检查，记录指纹与计数后保留。
            if content_key:
                seen_content.add(content_key)
            if segment.source is not None:
                source_count[segment.source] = (
                    source_count.get(segment.source, 0) + 1
                )
            result.append(segment)
        return result

    # 函数作用：用 cross-encoder 对候选片段重排，截断到 top_k，并把重排分写回 score。
    def _rerank(
        self,
        # 用户查询文本。
        query: str,
        # 向量多召回得到的候选片段。
        segments: list[IndustryKnowledgeSegment],
        # 重排后要保留的片段数量。
        top_k: int,
    ) -> list[IndustryKnowledgeSegment]:
        if self.reranker_service is None:
            # 没有重排服务时退化为按 cosine 截断。
            return segments[:top_k]
        # 对 (query, 正文) 成对打分。
        scores = self.reranker_service.rerank(query, [s.content for s in segments])
        # 按重排分数从高到低排序。
        ranked = sorted(zip(segments, scores), key=lambda pair: pair[1], reverse=True)
        result: list[IndustryKnowledgeSegment] = []
        for segment, rerank_score in ranked[:top_k]:
            # 保留原始 cosine 分数到 metadata，便于对比和复盘。
            metadata = dict(segment.metadata or {})
            metadata["vector_score"] = segment.score
            metadata["rerank_score"] = float(rerank_score)
            # score 改为重排分数（最终排序依据），其余字段不变。
            result.append(
                replace(segment, score=float(rerank_score), metadata=metadata)
            )
        return result

    # 函数作用：把检索到的多个知识片段拼成大模型输入上下文，并确保不超过技能配置的最大上下文长度。
    def _format_context(
        self,
        # 检索命中的知识片段列表。
        segments: list[IndustryKnowledgeSegment],
        # 允许拼接到上下文中的最大字符数。
        max_context_chars: int,
    ) -> str:
        # 存放最终要拼接的上下文片段。
        parts: list[str] = []
        # 记录已加入上下文的字符总数。
        total_chars = 0
        for idx, segment in enumerate(segments, start=1):
            # 给每个片段加编号，方便回答中引用。
            part = f"[{idx}] {segment.content}"
            if total_chars + len(part) > max_context_chars:
                # 如果加入该片段会超过最大上下文长度，就停止继续追加。
                break
            # 把当前片段加入上下文。
            parts.append(part)
            # 更新已使用的上下文长度。
            total_chars += len(part)
        # 用空行分隔多个片段，形成最终上下文字符串。
        return "\n\n".join(parts)

    # 函数作用：构造调试信息字典，记录技能、数据集、查询文本、检索数量和上下文长度等排查信息。
    def _build_debug(
        self,
        *,
        # 当前技能配置。
        skill: IndustryKnowledgeSkill,
        # 本次用户查询。
        query: str,
        # 本次实际使用的 top_k。
        top_k: int,
        # 本次检索命中的片段数量。
        retrieved_count: int,
        # 本次构造出的上下文长度。
        context_length: int,
    ) -> dict[str, Any]:
        return {
            # 技能 ID，转成字符串方便 JSON 序列化。
            "skill_id": str(skill.id),
            # 数据集 ID（向量模式可能为空）。
            "dataset_id": str(skill.dataset_id) if skill.dataset_id else None,
            # 向量检索绑定的 subdir。
            "vector_subdir": skill.vector_subdir,
            # 向量检索 probes（全文模式为 None）。
            "ivfflat_probes": (
                skill.ivfflat_probes or settings.industry_vector_probes
                if skill.retrieval_mode == "vector"
                else None
            ),
            # 是否启用重排（仅向量模式有意义）。
            "rerank_enabled": (
                self._resolve_rerank_enabled(skill)
                if skill.retrieval_mode == "vector"
                else None
            ),
            # 重排前 over-fetch 候选数量（仅向量模式且启用重排时有意义）。
            "rerank_over_fetch_k": (
                self._resolve_over_fetch_k(skill)
                if skill.retrieval_mode == "vector"
                and self._resolve_rerank_enabled(skill)
                else None
            ),
            # 用户查询文本。
            "query": query,
            # 使用的检索模式。
            "retrieval_mode": skill.retrieval_mode,
            # 最小正文字符数过滤（仅向量模式有意义）。
            "min_chunk_chars": (
                settings.industry_vector_min_chunk_chars
                if skill.retrieval_mode == "vector"
                else None
            ),
            # 同一来源最多保留数（仅向量模式有意义）。
            "max_per_source": (
                settings.industry_vector_max_per_source
                if skill.retrieval_mode == "vector"
                else None
            ),
            # 内容近重去重前缀长度（仅向量模式有意义）。
            "dedupe_content_prefix": (
                settings.industry_vector_dedupe_content_prefix
                if skill.retrieval_mode == "vector"
                else None
            ),
            # 实际检索数量。
            "top_k": top_k,
            # 实际命中数量。
            "retrieved_count": retrieved_count,
            # 上下文长度。
            "context_length": context_length,
            # 技能允许的最大上下文长度。
            "max_context_chars": skill.max_context_chars,
        # 返回调试信息字典。
        }

    # 函数作用：把数据库/仓库层返回的知识片段对象转换成接口响应里使用的引用模型。
    def _to_reference(
        self,
        # 内部检索片段对象。
        segment: IndustryKnowledgeSegment,
    ) -> IndustryKnowledgeReference:
        return IndustryKnowledgeReference(
            # 片段 ID。
            segment_id=segment.segment_id,
            # 检索相关性分数。
            score=segment.score,
            # 片段在文档/文件中的分块序号。
            chunk_index=segment.chunk_index,
            # 片段正文内容。
            content=segment.content,
            # 片段所属文档 ID（向量模式为空）。
            document_id=segment.document_id,
            # 片段所属数据集 ID（向量模式为空）。
            dataset_id=segment.dataset_id,
            # 片段来源文件路径（向量模式）。
            source=segment.source,
            # 片段所属 subdir（向量模式）。
            subdir=segment.subdir,
            # 片段元数据。
            metadata=segment.metadata,
        # 返回接口层使用的引用对象。
        )
